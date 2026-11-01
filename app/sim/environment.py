import time
from typing import Any, Optional, Sequence
import pybullet as p
import pybullet_data

_LATENCY_WARN_S = 1.5  # log a warning if reasoning round-trip exceeds this


class PhysicsEnvironment:
    """Headless 3D physics simulation engine backed by PyBullet."""

    def __init__(self, gui: bool = False, gravity: float = -9.81) -> None:
        self.gui = gui
        connection_mode = p.GUI if gui else p.DIRECT
        self.physics_client: int = p.connect(connection_mode)
        if self.physics_client < 0:
            raise ConnectionError("Failed to connect to PyBullet physics server.")

        p.setAdditionalSearchPath(pybullet_data.getDataPath(), physicsClientId=self.physics_client)
        p.setGravity(0.0, 0.0, gravity, physicsClientId=self.physics_client)

        self._objects: dict[str, int] = {}
        self._dimensions: dict[str, tuple[float, float, float]] = {}
        self._labels: dict[str, str] = {}

    def __enter__(self) -> "PhysicsEnvironment":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def add_object(
        self,
        obj_id: str,
        position: Sequence[float],
        dimensions: Sequence[float],
        mass: float = 1.0,
        label: str = "box",
    ) -> int:
        """Spawn a 3D box collision/rigid body shape into the physics world."""
        dx, dy, dz = float(dimensions[0]), float(dimensions[1]), float(dimensions[2])
        half_extents = [dx / 2.0, dy / 2.0, dz / 2.0]

        col_id = p.createCollisionShape(
            p.GEOM_BOX,
            halfExtents=half_extents,
            physicsClientId=self.physics_client,
        )
        body_id = p.createMultiBody(
            baseMass=float(mass),
            baseCollisionShapeIndex=col_id,
            basePosition=[float(position[0]), float(position[1]), float(position[2])],
            physicsClientId=self.physics_client,
        )
        self._objects[obj_id] = body_id
        self._dimensions[obj_id] = (dx, dy, dz)
        self._labels[obj_id] = label
        return body_id

    def step_simulation(self, steps: int = 10) -> None:
        """Advance physics simulation by the given number of steps."""
        for _ in range(steps):
            p.stepSimulation(physicsClientId=self.physics_client)

    def get_object_transform(self, obj_id: str) -> dict[str, list[float]]:
        """Return position [x, y, z] and orientation [roll, pitch, yaw] of an object."""
        if obj_id not in self._objects:
            raise KeyError(f"Object '{obj_id}' not found in simulation.")

        body_id = self._objects[obj_id]
        pos, quat = p.getBasePositionAndOrientation(body_id, physicsClientId=self.physics_client)
        euler = p.getEulerFromQuaternion(quat, physicsClientId=self.physics_client)

        return {
            "position": [float(pos[0]), float(pos[1]), float(pos[2])],
            "orientation": [float(euler[0]), float(euler[1]), float(euler[2])],
        }

    def check_collision(self, obj_id_a: str, obj_id_b: str) -> bool:
        """Check for contact points between two simulation objects."""
        if obj_id_a not in self._objects:
            raise KeyError(f"Object '{obj_id_a}' not found in simulation.")
        if obj_id_b not in self._objects:
            raise KeyError(f"Object '{obj_id_b}' not found in simulation.")

        body_a = self._objects[obj_id_a]
        body_b = self._objects[obj_id_b]
        p.performCollisionDetection(physicsClientId=self.physics_client)
        contacts = p.getContactPoints(
            bodyA=body_a,
            bodyB=body_b,
            physicsClientId=self.physics_client,
        )
        return len(contacts) > 0

    def sync_to_graph(self, graph_service: Any) -> int:
        """Update Neo4j node positions in real-time based on PyBullet rigid body states."""
        synced_count = 0
        for obj_id in self._objects:
            transform = self.get_object_transform(obj_id)
            dims = self._dimensions.get(obj_id, (1.0, 1.0, 1.0))
            label = self._labels.get(obj_id, "object")
            graph_service.upsert_object(
                obj_id=obj_id,
                label=label,
                pos=transform["position"],
                dims=dims,
            )
            synced_count += 1
        return synced_count

    def step_with_reasoning(
        self,
        graph_service: Any,
        reasoning_service: Any,
        robot_pos: Sequence[float],
        query: str,
        sim_steps: int = 10,
    ) -> dict[str, Any]:
        """Step physics, sync to graph, retrieve spatial context, get LLM action.

        Returns the action dict with an added 'latency_s' field.
        Warns to stdout if reasoning round-trip exceeds _LATENCY_WARN_S.
        """
        self.step_simulation(sim_steps)
        self.sync_to_graph(graph_service)
        context = graph_service.get_spatial_context(robot_pos)

        t0 = time.perf_counter()
        action = reasoning_service.plan_action(query, context)
        latency = time.perf_counter() - t0

        if latency > _LATENCY_WARN_S:
            print(f"[SpatialSpark] WARNING: reasoning latency {latency:.3f}s > {_LATENCY_WARN_S}s target")

        action["latency_s"] = round(latency, 4)
        return action

    def close(self) -> None:
        """Tear down physics client session."""
        if self.physics_client >= 0:
            try:
                p.disconnect(physicsClientId=self.physics_client)
            except Exception:
                pass
            self.physics_client = -1

