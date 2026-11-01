import json
from unittest.mock import MagicMock, patch
import pytest
import requests

from app.config import Settings
from app.services.reasoning_service import SpatialReasoningService


def test_service_initialization():
    service = SpatialReasoningService()
    assert service.api_key == ""
    assert service.timeout == 10.0
    assert service.api_url == "https://bridge.baseten.co/v1/chat/completions"

    custom_cfg = Settings(BASETEN_API_KEY="test_key_123")
    service_custom = SpatialReasoningService(settings=custom_cfg, model_id="abc1234", timeout=5.0)
    assert service_custom.api_key == "test_key_123"
    assert service_custom.timeout == 5.0
    assert service_custom.api_url == "https://model-abc1234.api.baseten.co/production/predict"


def test_prompt_assembly_and_token_constraints():
    service = SpatialReasoningService()
    context = (
        "Nearby objects (radius 5.0m):\n"
        "- table_1 (table) at (1.00,2.00,0.00) size=[1.00,1.00,0.80] dist: 2.24m\n"
        "- cup_1 (cup) at (1.00,2.00,0.80) size=[0.10,0.10,0.15] dist: 2.37m, rels: RESTING_ON:table_1"
    )
    query = "Navigate to the cup on the table and avoid the edges."

    prompt = service.build_prompt(user_query=query, spatial_context=context)

    assert "Spatial Context:" in prompt
    assert "Nearby objects" in prompt
    assert "User Query:" in prompt
    assert query in prompt
    assert "3D spatial navigation engine" in prompt

    # Verify token footprint is well within LLM input constraints (< 250 tokens)
    estimated_tokens = int(len(prompt.split()) * 1.3)
    assert estimated_tokens < 250


@patch("requests.post")
def test_plan_action_openai_format_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "action": "NAVIGATE",
                            "target_id": "cup_1",
                            "coordinates": [1.0, 2.0, 0.8],
                            "reasoning": "Moving to approach cup_1.",
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Approach the cup", "Nearby objects: cup_1")

    assert result["action"] == "NAVIGATE"
    assert result["target_id"] == "cup_1"
    assert result["coordinates"] == [1.0, 2.0, 0.8]
    assert "cup_1" in result["reasoning"]


@patch("requests.post")
def test_plan_action_markdown_fenced_output_success(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "output": (
            "```json\n"
            '{\n  "action": "PICK",\n  "target_id": "apple_1",\n  '
            '"coordinates": [0.5, 1.2, 0.9],\n  "reasoning": "Grasping apple_1."\n}\n'
            "```"
        )
    }
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Pick the apple", "apple_1 at (0.5, 1.2, 0.9)")

    assert result["action"] == "PICK"
    assert result["target_id"] == "apple_1"
    assert result["coordinates"] == [0.5, 1.2, 0.9]


@patch("requests.post")
def test_plan_action_non_200_fallback(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 503
    mock_resp.text = "Service Unavailable"
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Move forward", "Context")

    assert result["action"] == "AVOID"
    assert result["target_id"] is None
    assert result["coordinates"] == [0.0, 0.0, 0.0]
    assert "503" in result["reasoning"]


@patch("requests.post")
def test_plan_action_timeout_fallback(mock_post):
    mock_post.side_effect = requests.exceptions.Timeout("Request timed out")

    service = SpatialReasoningService(api_key="mock_key", timeout=10.0)
    result = service.plan_action("Move forward", "Context")

    assert result["action"] == "AVOID"
    assert result["target_id"] is None
    assert result["coordinates"] == [0.0, 0.0, 0.0]
    assert "timed out" in result["reasoning"]


@patch("requests.post")
def test_plan_action_malformed_json_fallback(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"choices": [{"message": {"content": "I cannot perform this."}}]}
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Move forward", "Context")

    assert result["action"] == "AVOID"
    assert result["target_id"] is None
    assert result["coordinates"] == [0.0, 0.0, 0.0]
    assert "parsing error" in result["reasoning"]


@patch("requests.post")
def test_plan_action_invalid_action_field_fallback(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "action": "JUMP_FORWARD",
                            "target_id": "box_1",
                            "coordinates": [1.0, 0.0, 0.0],
                            "reasoning": "Jumping over box",
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Jump over box", "Context")

    assert result["action"] == "AVOID"
    assert "Invalid action" in result["reasoning"]


@patch("requests.post")
def test_plan_action_invalid_coordinates_length_fallback(mock_post):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "action": "NAVIGATE",
                            "target_id": "box_1",
                            "coordinates": [1.0, 2.0],  # only 2 elements
                            "reasoning": "Missing z coordinate",
                        }
                    )
                }
            }
        ]
    }
    mock_post.return_value = mock_resp

    service = SpatialReasoningService(api_key="mock_key")
    result = service.plan_action("Go to box", "Context")

    assert result["action"] == "AVOID"
    assert "Coordinates must be list of 3 numbers" in result["reasoning"]

