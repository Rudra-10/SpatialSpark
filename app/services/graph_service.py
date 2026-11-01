import re
from typing import Any, Optional, Sequence
from neo4j import Driver, GraphDatabase
from neo4j.exceptions import DriverError, ServiceUnavailable

from app.config import Settings, settings as default_settings


class SpatialGraphService:
    """Spatial reasoning graph service backed by Neo4j 3D point indices."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        uri: Optional[str] = None,
        auth: Optional[tuple[str, str]] = None,
        connection_timeout: float = 5.0,
    ) -> None:
        cfg = settings or default_settings
        self.uri = uri or cfg.NEO4J_URI
        self.auth = auth or (cfg.NEO4J_USER, cfg.NEO4J_PASSWORD)
        self.connection_timeout = connection_timeout
        try:
            self._driver: Driver = GraphDatabase.driver(
                self.uri,
                auth=self.auth,
                connection_timeout=self.connection_timeout,
            )
        except Exception as exc:
            raise ConnectionError(f"Failed to initialize Neo4j driver: {exc}") from exc

    def __enter__(self) -> "SpatialGraphService":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def close(self) -> None:
        """Close driver connections."""
        if self._driver is not None:
            self._driver.close()

    def verify_connectivity(self) -> bool:
        """Verify Neo4j reachability."""
        try:
            self._driver.verify_connectivity()
            return True
        except (ServiceUnavailable, DriverError, Exception):
            return False

    def upsert_object(
        self,
        obj_id: str,
        label: str,
        pos: Sequence[float],
        dims: Sequence[float],
    ) -> dict[str, Any]:
        """Upsert a 3D spatial entity with coordinates and bounding box dimensions."""
        x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        dx, dy, dz = float(dims[0]), float(dims[1]), float(dims[2])
        query = (
            "MERGE (o:SpatialObject {id: $id}) "
            "SET o.label = $label, "
            "    o.x = $x, o.y = $y, o.z = $z, "
            "    o.dx = $dx, o.dy = $dy, o.dz = $dz, "
            "    o.pos = point({x: $x, y: $y, z: $z}) "
            "RETURN o.id AS id, o.label AS label, o.x AS x, o.y AS y, o.z AS z, "
            "       o.dx AS dx, o.dy AS dy, o.dz AS dz"
        )
        with self._driver.session() as session:
            result = session.run(
                query,
                id=obj_id,
                label=label,
                x=x,
                y=y,
                z=z,
                dx=dx,
                dy=dy,
                dz=dz,
            )
            record = result.single()
            return dict(record) if record else {}

    def create_relationship(self, from_id: str, to_id: str, rel_type: str) -> bool:
        """Create a directed spatial relationship edge between two SpatialObjects."""
        clean_rel = rel_type.strip().upper()
        if not re.match(r"^[A-Z0-9_]+$", clean_rel):
            raise ValueError(f"Invalid relationship type: {rel_type}")

        # shortcut: static Cypher interpolation of regex-validated identifier, upgrade to APOC if dynamic schema is needed
        query = (
            f"MATCH (a:SpatialObject {{id: $from_id}}), (b:SpatialObject {{id: $to_id}}) "
            f"MERGE (a)-[r:{clean_rel}]->(b) "
            "RETURN count(r) AS rel_count"
        )
        with self._driver.session() as session:
            result = session.run(query, from_id=from_id, to_id=to_id)
            record = result.single()
            return bool(record and record["rel_count"] > 0)

    def get_spatial_context(
        self,
        robot_pos: Sequence[float],
        radius: float = 5.0,
    ) -> str:
        """Extract nearby objects using point.distance() formatted under 200 tokens."""
        rx, ry, rz = float(robot_pos[0]), float(robot_pos[1]), float(robot_pos[2])
        query = (
            "MATCH (o:SpatialObject) "
            "WHERE o.pos IS NOT NULL "
            "WITH o, point.distance(o.pos, point({x: $rx, y: $ry, z: $rz})) AS dist "
            "WHERE dist <= $radius "
            "OPTIONAL MATCH (o)-[r]->(target:SpatialObject) "
            "WHERE target.pos IS NOT NULL AND point.distance(target.pos, point({x: $rx, y: $ry, z: $rz})) <= $radius "
            "WITH o, dist, "
            "     [rel IN collect(DISTINCT CASE WHEN r IS NOT NULL THEN type(r) + ':' + target.id END) WHERE rel IS NOT NULL] AS rels "
            "RETURN o.id AS id, o.label AS label, o.x AS x, o.y AS y, o.z AS z, "
            "       o.dx AS dx, o.dy AS dy, o.dz AS dz, dist, rels "
            "ORDER BY dist ASC "
            "LIMIT 15"
        )
        with self._driver.session() as session:
            result = session.run(query, rx=rx, ry=ry, rz=rz, radius=float(radius))
            records = list(result)

        if not records:
            return f"No objects detected within {radius:.1f}m radius."

        lines = [f"Nearby objects (radius {radius:.1f}m):"]
        for rec in records:
            pos_str = f"({rec['x']:.2f},{rec['y']:.2f},{rec['z']:.2f})"
            dims_str = f"[{rec['dx']:.2f},{rec['dy']:.2f},{rec['dz']:.2f}]"
            dist_str = f"{rec['dist']:.2f}m"
            line = f"- {rec['id']} ({rec['label']}) at {pos_str} size={dims_str} dist: {dist_str}"
            rels = rec.get("rels") or []
            if rels:
                line += f", rels: {', '.join(rels)}"
            lines.append(line)

        return "\n".join(lines)

    def clear_all(self) -> None:
        """Remove all SpatialObject nodes and edges."""
        with self._driver.session() as session:
            session.run("MATCH (n:SpatialObject) DETACH DELETE n")
