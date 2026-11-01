from unittest.mock import MagicMock
import pytest
from app.services.graph_service import SpatialGraphService
from app.sim.environment import PhysicsEnvironment


def test_physics_env_initialization_and_close():
    env = PhysicsEnvironment(gui=False)
    assert env.physics_client >= 0
    assert env.gui is False
    env.close()
    assert env.physics_client == -1


def test_physics_env_context_manager():
    with PhysicsEnvironment(gui=False) as env:
        assert env.physics_client >= 0
    assert env.physics_client == -1


def test_add_object_and_gravity_step():
    with PhysicsEnvironment(gui=False) as env:
        body_id = env.add_object(
            obj_id="box_drop",
            position=(0.0, 0.0, 5.0),
            dimensions=(0.5, 0.5, 0.5),
            mass=1.0,
        )
        assert body_id >= 0

        init_transform = env.get_object_transform("box_drop")
        assert pytest.approx(init_transform["position"][2], abs=0.01) == 5.0

        # Step simulation to let gravity take effect
        env.step_simulation(steps=50)
        after_transform = env.get_object_transform("box_drop")
        assert after_transform["position"][2] < 5.0
        assert len(after_transform["orientation"]) == 3


def test_collision_detection_overlapping_vs_separated():
    with PhysicsEnvironment(gui=False) as env:
        # Overlapping objects (one static base, one dynamic object)
        env.add_object("box_a", position=(0.0, 0.0, 0.0), dimensions=(1.0, 1.0, 1.0), mass=0.0)
        env.add_object("box_b", position=(0.2, 0.2, 0.2), dimensions=(1.0, 1.0, 1.0), mass=1.0)
        env.step_simulation(steps=1)
        assert env.check_collision("box_a", "box_b") is True

        # Separated object
        env.add_object("box_c", position=(20.0, 20.0, 0.0), dimensions=(1.0, 1.0, 1.0), mass=1.0)
        env.step_simulation(steps=1)
        assert env.check_collision("box_a", "box_c") is False


def test_sync_to_graph_mocked():
    mock_graph = MagicMock()
    with PhysicsEnvironment(gui=False) as env:
        env.add_object(
            obj_id="cube_1",
            position=(1.0, 2.0, 0.5),
            dimensions=(0.4, 0.4, 0.6),
            mass=0.0,
            label="obstacle",
        )
        count = env.sync_to_graph(mock_graph)
        assert count == 1
        mock_graph.upsert_object.assert_called_once()
        kwargs = mock_graph.upsert_object.call_args.kwargs
        assert kwargs["obj_id"] == "cube_1"
        assert kwargs["label"] == "obstacle"
        assert kwargs["pos"] == [1.0, 2.0, 0.5]
        assert kwargs["dims"] == (0.4, 0.4, 0.6)


def test_sync_to_graph_live_neo4j():
    graph = SpatialGraphService()
    if not graph.verify_connectivity():
        pytest.skip("Neo4j database is not reachable at bolt://localhost:7687")

    graph.clear_all()
    try:
        with PhysicsEnvironment(gui=False) as env:
            env.add_object(
                obj_id="sim_box_live",
                position=(0.5, 1.5, 0.25),
                dimensions=(0.5, 0.5, 0.5),
                mass=0.0,
                label="sim_box",
            )
            synced = env.sync_to_graph(graph)
            assert synced == 1

            context = graph.get_spatial_context(robot_pos=(0.0, 0.0, 0.0), radius=5.0)
            assert "sim_box_live" in context
            assert "(sim_box)" in context
    finally:
        graph.clear_all()
        graph.close()


def test_object_not_found_errors():
    with PhysicsEnvironment(gui=False) as env:
        with pytest.raises(KeyError):
            env.get_object_transform("missing_obj")
        with pytest.raises(KeyError):
            env.check_collision("missing_a", "missing_b")

