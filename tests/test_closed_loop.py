"""Tests for closed-loop: PhysicsEnvironment.step_with_reasoning()."""
from unittest.mock import MagicMock

import pytest

from app.sim.environment import PhysicsEnvironment

MOCK_ACTION = {
    "action": "NAVIGATE",
    "target_id": "target_box",
    "coordinates": [6.0, 0.0, 0.5],
    "reasoning": "Clear path to target.",
}


def _mock_services(context: str = "Nearby objects (radius 5.0m):\n- obs1"):
    graph = MagicMock()
    graph.get_spatial_context.return_value = context
    reasoning = MagicMock()
    reasoning.plan_action.return_value = dict(MOCK_ACTION)  # copy — step_with_reasoning mutates it
    return graph, reasoning


def test_step_with_reasoning_returns_action_with_latency():
    graph, reasoning = _mock_services()
    with PhysicsEnvironment(gui=False) as env:
        env.add_object("obs1", (2.0, 0.0, 0.5), (1.0, 1.0, 1.0), mass=0.0, label="obstacle")
        result = env.step_with_reasoning(graph, reasoning, [0.0, 0.0, 0.0], "go forward")

    assert result["action"] == "NAVIGATE"
    assert "latency_s" in result
    assert isinstance(result["latency_s"], float)
    assert result["latency_s"] >= 0.0


def test_step_with_reasoning_calls_sync_and_context():
    graph, reasoning = _mock_services()
    with PhysicsEnvironment(gui=False) as env:
        env.add_object("box1", (1.0, 0.0, 0.0), (0.5, 0.5, 0.5), mass=0.0, label="box")
        env.step_with_reasoning(graph, reasoning, [0.0, 0.0, 0.0], "navigate")

    graph.upsert_object.assert_called_once()  # sync_to_graph called for 1 object
    graph.get_spatial_context.assert_called_once_with([0.0, 0.0, 0.0])


def test_step_with_reasoning_passes_context_to_plan_action():
    context_str = "Nearby objects (radius 5.0m):\n- box1 (box) at (1.00,0.00,0.00)"
    graph, reasoning = _mock_services(context=context_str)
    with PhysicsEnvironment(gui=False) as env:
        env.add_object("box1", (1.0, 0.0, 0.0), (0.5, 0.5, 0.5), mass=0.0, label="box")
        env.step_with_reasoning(graph, reasoning, [0.0, 0.0, 0.0], "pick up box")

    call_args = reasoning.plan_action.call_args
    assert call_args.args[0] == "pick up box"
    assert call_args.args[1] == context_str


def test_step_with_reasoning_latency_measured_accurately():
    """latency_s must be >= 0 and < 5s (generous upper bound for CI)."""
    graph, reasoning = _mock_services()
    with PhysicsEnvironment(gui=False) as env:
        result = env.step_with_reasoning(graph, reasoning, [0.0, 0.0, 0.0], "query")

    assert 0.0 <= result["latency_s"] < 5.0


def test_step_with_reasoning_empty_scene():
    """No objects in sim — sync sends nothing, context is empty string from mock."""
    graph, reasoning = _mock_services(context="No objects detected within 5.0m radius.")
    with PhysicsEnvironment(gui=False) as env:
        result = env.step_with_reasoning(graph, reasoning, [0.0, 0.0, 0.0], "navigate")

    graph.upsert_object.assert_not_called()
    assert result["action"] == "NAVIGATE"

