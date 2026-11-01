import json
import re
from typing import Any, Optional
import requests

from app.config import Settings, settings as default_settings


class SpatialReasoningService:
    """Spatial reasoning engine that interfaces with Meta models on Baseten."""

    SYSTEM_PROMPT = (
        "You are a 3D spatial navigation engine for a mobile robot. "
        "Analyze the user command and 3D spatial context. "
        "Decide the next deterministic action. "
        "Output ONLY a valid JSON object matching this exact schema:\n"
        "{\n"
        '  "action": "NAVIGATE" | "PICK" | "PLACE" | "AVOID",\n'
        '  "target_id": "<object_id or null>",\n'
        '  "coordinates": [x, y, z],\n'
        '  "reasoning": "<short explanation>"\n'
        "}"
    )

    ALLOWED_ACTIONS = {"NAVIGATE", "PICK", "PLACE", "AVOID"}

    def __init__(
        self,
        settings: Optional[Settings] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        model_id: Optional[str] = None,
        timeout: float = 10.0,
    ) -> None:
        cfg = settings or default_settings
        self.api_key = api_key or cfg.BASETEN_API_KEY
        self.timeout = timeout
        if api_url:
            self.api_url = api_url
        elif model_id:
            self.api_url = f"https://model-{model_id}.api.baseten.co/production/predict"
        else:
            self.api_url = "https://bridge.baseten.co/v1/chat/completions"

    def build_prompt(self, user_query: str, spatial_context: str) -> str:
        """Construct deterministic prompt for token estimation and logging."""
        return (
            f"{self.SYSTEM_PROMPT}\n\n"
            f"Spatial Context:\n{spatial_context}\n\n"
            f"User Query:\n{user_query}"
        )

    def _build_payload(self, user_query: str, spatial_context: str) -> dict[str, Any]:
        """Build request payload conforming to chat completion standards."""
        return {
            "model": "meta-llama/Meta-Llama-3-8B-Instruct",
            "messages": [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Spatial Context:\n{spatial_context}\n\nUser Query:\n{user_query}",
                },
            ],
            "temperature": 0.0,
            "max_tokens": 150,
        }

    def _fallback_action(self, reason: str) -> dict[str, Any]:
        # shortcut: fallback action defaults to AVOID at origin, upgrade to multi-provider failover in Phase 4
        return {
            "action": "AVOID",
            "target_id": None,
            "coordinates": [0.0, 0.0, 0.0],
            "reasoning": f"Fallback: {reason}",
        }

    def _validate_action_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        action = str(data.get("action", "")).strip().upper()
        if action not in self.ALLOWED_ACTIONS:
            raise ValueError(f"Invalid action '{action}'. Must be one of {self.ALLOWED_ACTIONS}")

        target_id = data.get("target_id")
        if target_id is not None:
            target_id = str(target_id).strip()

        coords = data.get("coordinates")
        if not isinstance(coords, (list, tuple)) or len(coords) != 3:
            raise ValueError(f"Coordinates must be list of 3 numbers, got: {coords}")
        parsed_coords = [float(coords[0]), float(coords[1]), float(coords[2])]

        reasoning = str(data.get("reasoning", "")).strip()

        return {
            "action": action,
            "target_id": target_id,
            "coordinates": parsed_coords,
            "reasoning": reasoning,
        }

    def _parse_model_output(self, data: Any) -> dict[str, Any]:
        """Extract and validate action dict from various LLM gateway response formats."""
        if isinstance(data, dict):
            if "choices" in data and isinstance(data["choices"], list) and data["choices"]:
                msg = data["choices"][0].get("message", {})
                raw_text = msg.get("content", "")
            elif "output" in data:
                raw_text = data["output"]
            elif "action" in data and "coordinates" in data:
                return self._validate_action_dict(data)
            else:
                raw_text = json.dumps(data)
        elif isinstance(data, str):
            raw_text = data
        else:
            raise ValueError(f"Unexpected response data type: {type(data)}")

        if isinstance(raw_text, dict):
            return self._validate_action_dict(raw_text)

        clean_text = raw_text.strip()
        if clean_text.startswith("```"):
            clean_text = re.sub(r"^```(?:json)?\s*", "", clean_text)
            clean_text = re.sub(r"\s*```$", "", clean_text)
            clean_text = clean_text.strip()

        json_match = re.search(r"\{.*\}", clean_text, re.DOTALL)
        if json_match:
            clean_text = json_match.group(0)

        parsed = json.loads(clean_text)
        if not isinstance(parsed, dict):
            raise ValueError("Model output did not parse into a JSON object")

        return self._validate_action_dict(parsed)

    def plan_action(self, user_query: str, spatial_context: str) -> dict[str, Any]:
        """Issue HTTP POST to Baseten endpoint with strict timeout and structured fallback."""
        payload = self._build_payload(user_query, spatial_context)
        auth_header = (
            self.api_key
            if self.api_key.startswith(("Api-Key ", "Bearer "))
            else f"Api-Key {self.api_key}"
        )
        headers = {
            "Authorization": auth_header,
            "Content-Type": "application/json",
        }

        try:
            response = requests.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
            if response.status_code != 200:
                return self._fallback_action(
                    f"Baseten returned status {response.status_code}: {response.text[:100]}"
                )

            data = response.json()
            return self._parse_model_output(data)
        except requests.exceptions.Timeout:
            return self._fallback_action(f"Baseten request timed out after {self.timeout}s")
        except requests.exceptions.RequestException as exc:
            return self._fallback_action(f"Baseten request error: {exc}")
        except (json.JSONDecodeError, ValueError) as exc:
            return self._fallback_action(f"Model output parsing error: {exc}")

