import pytest
from app.config import Settings
from app.services.graph_service import SpatialGraphService


@pytest.fixture
def graph_service():
    service = SpatialGraphService()
    if not service.verify_connectivity():
        pytest.skip("Neo4j database is not reachable at bolt://localhost:7687")
    service.clear_all()
    try:
        yield service
    finally:
        service.clear_all()
        service.close()


def test_service_initialization_and_context_manager():
    custom_settings = Settings(NEO4J_URI="bolt://localhost:7687")
    with SpatialGraphService(settings=custom_settings) as service:
        assert service.uri == "bolt://localhost:7687"
        assert service.verify_connectivity() is True


def test_upsert_object_stores_node_and_point(graph_service):
    res = graph_service.upsert_object(
        obj_id="box_1",
        label="obstacle_box",
        pos=(1.0, 2.0, 0.5),
        dims=(0.4, 0.4, 0.6),
    )
    assert res["id"] == "box_1"
    assert res["label"] == "obstacle_box"
    assert res["x"] == 1.0
    assert res["y"] == 2.0
    assert res["z"] == 0.5
    assert res["dx"] == 0.4
    assert res["dy"] == 0.4
    assert res["dz"] == 0.6

    # Verify directly via session and check native point property
    with graph_service._driver.session() as session:
        record = session.run(
            "MATCH (o:SpatialObject {id: $id}) RETURN o.pos.x AS px, o.pos.y AS py, o.pos.z AS pz",
            id="box_1",
        ).single()
        assert record is not None
        assert record["px"] == 1.0
        assert record["py"] == 2.0
        assert record["pz"] == 0.5


def test_upsert_object_is_idempotent(graph_service):
    graph_service.upsert_object("table_1", "table", (0.0, 0.0, 0.0), (1.0, 1.0, 0.8))
    graph_service.upsert_object("table_1", "table", (0.5, 0.5, 0.0), (1.2, 1.2, 0.8))

    with graph_service._driver.session() as session:
        records = list(session.run("MATCH (o:SpatialObject {id: $id}) RETURN o", id="table_1"))
        assert len(records) == 1
        assert records[0]["o"]["x"] == 0.5
        assert records[0]["o"]["dx"] == 1.2


def test_create_relationship_success_and_invalid(graph_service):
    graph_service.upsert_object("cup_1", "mug", (0.0, 0.0, 0.8), (0.1, 0.1, 0.15))
    graph_service.upsert_object("table_1", "table", (0.0, 0.0, 0.0), (1.0, 1.0, 0.8))

    success = graph_service.create_relationship("cup_1", "table_1", "RESTING_ON")
    assert success is True

    # Test non-existent target returns False
    missing = graph_service.create_relationship("cup_1", "non_existent_id", "NEAR")
    assert missing is False

    # Test invalid relationship name rejects Cypher injection characters
    with pytest.raises(ValueError):
        graph_service.create_relationship("cup_1", "table_1", "INVALID REL; DROP TABLE;")


def test_get_spatial_context_distance_filtering_and_token_budget(graph_service):
    # Near object: dist ~1.41m (<= 5.0m)
    graph_service.upsert_object("obs_near", "chair", (1.0, 1.0, 0.0), (0.5, 0.5, 0.8))
    # Another near object: dist ~2.0m (<= 5.0m)
    graph_service.upsert_object("obs_table", "table", (2.0, 0.0, 0.0), (1.0, 1.0, 0.7))
    # Far object: dist 10.0m (> 5.0m)
    graph_service.upsert_object("obs_far", "pillar", (10.0, 0.0, 0.0), (1.0, 1.0, 3.0))

    graph_service.create_relationship("obs_near", "obs_table", "NEAR")
    graph_service.create_relationship("obs_near", "obs_far", "NEAR")

    context = graph_service.get_spatial_context(robot_pos=(0.0, 0.0, 0.0), radius=5.0)

    assert "obs_near" in context
    assert "obs_table" in context
    assert "NEAR:obs_table" in context
    assert "obs_far" not in context
    assert "Nearby objects (radius 5.0m):" in context
    assert "dist:" in context

    # Verify token footprint is well under 200 tokens
    estimated_tokens = int(len(context.split()) * 1.3)
    assert estimated_tokens < 200


def test_get_spatial_context_empty(graph_service):
    context = graph_service.get_spatial_context(robot_pos=(50.0, 50.0, 0.0), radius=2.0)
    assert "No objects detected within 2.0m radius." in context


def test_get_spatial_context_dense_cluster_limit_15(graph_service):
    # Insert 20 proximate objects within 5m
    for i in range(20):
        graph_service.upsert_object(
            obj_id=f"cluster_obj_{i:02d}",
            label="box",
            pos=(0.1 * (i + 1), 0.1 * (i + 1), 0.0),
            dims=(0.1, 0.1, 0.1),
        )

    context = graph_service.get_spatial_context(robot_pos=(0.0, 0.0, 0.0), radius=5.0)
    lines = [line for line in context.strip().split("\n") if line.startswith("- ")]
    assert len(lines) == 15
    # Token count safeguard check
    estimated_tokens = int(len(context.split()) * 1.3)
    assert estimated_tokens < 200
