# PLAN.md: SpatialSpark Development Roadmap

## Project Overview
**SpatialSpark** is a cloud-native spatial reasoning engine that converts simulated 3D sensor streams and SAM 3.1 segmentation into queryable Neo4j 3D scene graphs (GraphRAG) for zero-shot robotic navigation using Meta open-weights models.

---

## Phase 1: Environment & Infrastructure Setup
- [ ] Initialize Python 3.11 virtual environment and install primary dependencies (`fastapi`, `uvicorn`, `neo4j`, `pybullet`, `requests`, `pydantic`).
- [ ] Spin up local Neo4j Docker container with authentication (`bolt://localhost:7687`).
- [ ] Establish repository file structure:
  ```
  spatialspark/
  ├── app/
  │   ├── __init__.py
  │   ├── main.py
  │   ├── config.py
  │   ├── services/
  │   │   ├── graph_service.py
  │   │   └── llm_service.py
  │   └── sim/
  │       └── environment.py
  ├── tests/
  ├── Dockerfile
  └── README.md
  ```

---

## Phase 2: Spatial Graph Database & GraphRAG Pipeline
- [x] **Node & Edge Definition**: Define Cypher schema for `SpatialObject` nodes containing label, 3D bounds $(x, y, z, dx, dy, dz)$, and spatial relationship edges (`RESTING_ON`, `OBSTRUCTING`, `NEAR`).
- [x] **Graph Service Implementation (`graph_service.py`)**:
  - Implement `upsert_object()` to dynamically record segmented objects.
  - Implement `get_spatial_context()` using Neo4j point formulas (`point.distance()`) to extract objects within a target radius of the robot.
- [x] **Validation**: Run integration tests to ensure graph queries return lightweight, structured context payloads under 200 tokens.

---

## Phase 3: Synthetic Perception & PyBullet Simulation
- [x] **Headless Simulation Engine (`environment.py`)**:
  - Configure PyBullet in `DIRECT` mode to run headless.
  - Load ground plane, obstacles, and agent URDF chassis (`r2d2.urdf` / custom URDF).
- [ ] **Synthetic Telemetry Extraction**:
  - Extract synthetic camera depth buffers and perform virtual raycasting to mimic LiDAR point clouds.
  - Map synthetic 3D coordinates $(x, y, z)$ directly into the spatial graph pipeline.

---

## Phase 4: API Orchestration Gateway & LLM Inference
- [ ] **Multi-Provider Gateway (`llm_service.py`)**:
  - Implement Baseten endpoint integration for Meta open-weights models (`2M TPM` rate limit handling).
  - Add failover fallback support (Groq API / local Ollama endpoint) to ensure uninterrupted offline execution.
- [ ] **Prompt Engineering & Output Enforcement**:
  - Craft system prompts forcing Meta models to ingest 3D scene graph context and output raw, executable Python control scripts (`def get_next_action():`).
  - Implement Python `ast.parse()` validation to check generated code syntax prior to execution.
- [ ] **FastAPI Endpoint (`main.py`)**:
  - Build `POST /api/v1/reason` route accepting telemetry payloads, updating Neo4j, executing GraphRAG retrieval, querying the LLM, and returning trajectory code.

---

## Phase 5: Closed-Loop Execution & Validation
- [ ] Connect `environment.py` loop to poll `/api/v1/reason` when path blockage occurs.
- [ ] Execute generated trajectory scripts safely within a sandboxed `exec()` block or isolated local container.
- [ ] Measure end-to-end loop latency (Target: $< 1.5$s per spatial reasoning decision).

---

## Phase 6: Cloud Deployment & Submission Deliverables
- [ ] Deploy PyBullet simulation and execution sandboxes to Modal serverless containers using `modal.Sandbox`.
- [ ] Create system architecture diagrams highlighting the GraphRAG pipeline and 3D Scene Graph advantage.
- [ ] Record a 3-minute video demonstration showing PyBullet dynamic obstacle bypass driven by Meta open-weights models.
- [ ] Finalize README with installation instructions, API documentation, and architecture breakdown.