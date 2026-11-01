"""Tests for POST /api/v1/reason — all services fully mocked."""
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ── Helpers ───────────────────────────────────────────────────────────────────

VALID_ACTION = {
    "action": "NAVIGATE",
    "target_id": "box_1",
    "coordinates": [1.0, 2.0, 3.0],
    "reasoning": "Clear path ahead.",
}

VALID_PAYLOAD = {
    "robot_id": "r1",
    "position": [0.0, 0.0, 0.0],
    "query": "Navigate to the box",
    "objects": [
        {
            "obj_id": "box_1",
            "label": "box",
            "position": [1.0, 2.0, 3.0],
            "dimensions": [0.5, 0.5, 0.5],
        }
    ],
}


def _make_client():
    """Return TestClient with both services mocked via module-level patch."""
    mock_graph = MagicMock()
    mock_graph.upsert_object.return_value = {}
    mock_graph.get_spatial_context.return_value = "Nearby objects (radius 5.0m):\n- box_1 (box) at (1.00,2.00,3.00)"

    mock_reasoning = MagicMock()
    mock_reasoning.plan_action.return_value = VALID_ACTION

    with (
        patch("app.main.SpatialGraphService", return_value=mock_graph),
        patch("app.main.SpatialReasoningService", return_value=mock_reasoning),
    ):
        # Import here so patches apply before the app module caches instances
        from app.main import app

        client = TestClient(app)
        return client, mock_graph, mock_reasoning


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health():
    from app.main import app
    client = TestClient(app)
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_reason_valid_payload():
    mock_graph = MagicMock()
    mock_graph.upsert_object.return_value = {}
    mock_graph.get_spatial_context.return_value = "context"
    mock_reasoning = MagicMock()
    mock_reasoning.plan_action.return_value = VALID_ACTION

    with (
        patch("app.main._graph", mock_graph),
        patch("app.main._reasoning", mock_reasoning),
    ):
        from app.main import app
        client = TestClient(app)
        resp = client.post("/api/v1/reason", json=VALID_PAYLOAD)

    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "NAVIGATE"
    assert body["coordinates"] == [1.0, 2.0, 3.0]


def test_reason_calls_upsert_for_each_object():
    mock_graph = MagicMock()
    mock_graph.upsert_object.return_value = {}
    mock_graph.get_spatial_context.return_value = "ctx"
    mock_reasoning = MagicMock()
    mock_reasoning.plan_action.return_value = VALID_ACTION

    payload = dict(VALID_PAYLOAD)
    payload["objects"] = [
        {"obj_id": "a", "label": "box", "position": [0.0, 0.0, 0.0], "dimensions": [1.0, 1.0, 1.0]},
        {"obj_id": "b", "label": "table", "position": [2.0, 0.0, 0.0], "dimensions": [2.0, 1.0, 0.5]},
    ]

    with (
        patch("app.main._graph", mock_graph),
        patch("app.main._reasoning", mock_reasoning),
    ):
        from app.main import app
        client = TestClient(app)
        client.post("/api/v1/reason", json=payload)

    assert mock_graph.upsert_object.call_count == 2


def test_reason_missing_required_fields_returns_422():
    from app.main import app
    client = TestClient(app)
    resp = client.post("/api/v1/reason", json={"robot_id": "r1"})
    assert resp.status_code == 422


def test_reason_invalid_robot_position_length_returns_422():
    from app.main import app
    client = TestClient(app)
    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["position"] = [0.0, 0.0]  # only 2 elements
    resp = client.post("/api/v1/reason", json=bad_payload)
    assert resp.status_code == 422


def test_reason_invalid_object_position_length_returns_422():
    from app.main import app
    client = TestClient(app)
    bad_payload = dict(VALID_PAYLOAD)
    bad_payload["objects"] = [
        {"obj_id": "x", "label": "box", "position": [0.0, 0.0], "dimensions": [1.0, 1.0, 1.0]}
    ]
    resp = client.post("/api/v1/reason", json=bad_payload)
    assert resp.status_code == 422


def test_reason_empty_objects_list():
    """No objects is valid — graph context query runs on existing nodes."""
    mock_graph = MagicMock()
    mock_graph.get_spatial_context.return_value = "No objects detected within 5.0m radius."
    mock_reasoning = MagicMock()
    mock_reasoning.plan_action.return_value = VALID_ACTION

    payload = dict(VALID_PAYLOAD)
    payload["objects"] = []

    with (
        patch("app.main._graph", mock_graph),
        patch("app.main._reasoning", mock_reasoning),
    ):
        from app.main import app
        client = TestClient(app)
        resp = client.post("/api/v1/reason", json=payload)

    assert resp.status_code == 200
    mock_graph.upsert_object.assert_not_called()

