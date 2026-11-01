"""Closed-loop demo: PyBullet sim → Neo4j graph sync → LLM spatial reasoning.

Run with:
    python scripts/run_loop.py

Requires Neo4j running at bolt://localhost:7687 and BASETEN_API_KEY in .env.
Without a real API key the reasoning service returns a fallback AVOID action.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.graph_service import SpatialGraphService
from app.services.reasoning_service import SpatialReasoningService
from app.sim.environment import PhysicsEnvironment

SCENE = [
    # (obj_id, label, position, dimensions, mass)
    ("obstacle_1", "obstacle", (2.0, 0.0, 0.5), (1.0, 1.0, 1.0), 0.0),
    ("obstacle_2", "obstacle", (4.0, 1.0, 0.5), (0.5, 0.5, 0.5), 0.0),
    ("target_box", "target",   (6.0, 0.0, 0.5), (0.5, 0.5, 0.5), 0.0),
]

ROBOT_POS  = [0.0, 0.0, 0.0]
QUERY      = "Navigate to the target box avoiding all obstacles."
LOOP_TICKS = 3


def main() -> None:
    graph = SpatialGraphService()
    if not graph.verify_connectivity():
        print("Neo4j unreachable — update .env and restart the Docker container.")
        return

    graph.clear_all()
    reasoning = SpatialReasoningService()

    with PhysicsEnvironment(gui=False) as env:
        for obj_id, label, pos, dims, mass in SCENE:
            env.add_object(obj_id, pos, dims, mass=mass, label=label)
        print(f"Scene loaded: {len(SCENE)} objects\n")

        for tick in range(1, LOOP_TICKS + 1):
            print(f"─── Tick {tick}/{LOOP_TICKS} ─────────────────────────")
            action = env.step_with_reasoning(graph, reasoning, ROBOT_POS, QUERY)
            print(f"  action   : {action['action']}")
            print(f"  target   : {action['target_id']}")
            print(f"  coords   : {action['coordinates']}")
            print(f"  reasoning: {action['reasoning']}")
            print(f"  latency  : {action['latency_s']}s\n")

    graph.clear_all()
    graph.close()
    print("Loop complete.")


if __name__ == "__main__":
    main()

