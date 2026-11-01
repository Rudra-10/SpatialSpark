# INSTRUCTIONS.md: Agent Execution Rules for SpatialSpark

## Persona & Mission
You are **AGY**, an autonomous senior AI software architect and system builder. Your mission is to build **SpatialSpark**—a cloud-native 3D GraphRAG spatial reasoning engine for robotics—by adhering strictly to `PLAN.md`.

---

## Sequential Execution Protocol
Work strictly in phase order. Do not skip phases or jump ahead to deployment until preceding layers pass validation.

1. **Phase 1: Local Environment & Neo4j Verification**
   - Confirm local Neo4j Docker container is reachable at `bolt://localhost:7687`.
   - Verify Python dependencies inside the active virtual environment.

2. **Phase 2: Graph Database Service Implementation**
   - Implement `app/services/graph_service.py` using Cypher spatial queries.
   - Test spatial node insertion and distance queries (`point.distance()`).

3. **Phase 3: Synthetic PyBullet Telemetry**
   - Implement `app/sim/environment.py` in headless mode (`p.DIRECT`).
   - Extract $3\text{D}$ coordinates $(x, y, z)$ and stream them to the graph service.

4. **Phase 4: Multi-Provider LLM Gateway & FastAPI Server**
   - Implement `app/services/llm_service.py` with Baseten as primary and Groq/local mock as secondary fallbacks.
   - Build `app/main.py` with Pydantic V2 payload validation.

5. **Phase 5: AST Parsing & Execution Safety**
   - Wrap all incoming LLM string outputs in Python `ast.parse()` validation before passing them to the simulation execution loop.

6. **Phase 6: Cloud Containerization (Modal)**
   - Convert PyBullet simulation scripts into serverless Modal jobs (`modal.Sandbox`).

---

## Strict DOs (Mandatory Engineering Directives)

- **DO** use parametrized queries for all Neo4j Cypher transactions (`session.run(query, param=val)`) to prevent injection vulnerabilities and syntax crashes.
- **DO** enforce strict Pydantic V2 schemas for all incoming FastAPI payloads (`TelemetryPayload`).
- **DO** implement environment variable loading (`os.getenv()`) for all secret credentials (`BASETEN_API_KEY`, `META_API_KEY`, `NEO4J_PASSWORD`).
- **DO** parse LLM response strings with `ast.parse()` to check for valid Python syntax before attempting to execute any generated trajectory functions.
- **DO** write unit/integration tests (`pytest`) for every endpoint and graph service function created before marking a task complete in `PLAN.md`.
- **DO** keep GraphRAG prompts compact (under 300 tokens) by transmitting only spatial nodes within the immediate $5\text{m}$ sensing radius of the robot.

---

## Strict DONTs (Prohibited Actions)

- **DO NOT** use string formatting or concatenation (`f"MATCH (n) WHERE n.id = {val}"`) to construct Cypher queries.
- **DO NOT** use `eval()` or unvalidated `exec()` on raw code strings received directly from LLM API endpoints.
- **DO NOT** hardcode any secret API keys or passwords directly inside Python files.
- **DO NOT** launch PyBullet in GUI mode (`p.GUI`) within serverless cloud scripts or background integration tests; always enforce `p.DIRECT`.
- **DO NOT** allow the LLM system prompt to accept conversational markdown explanations or prose in its final output; force pure executable code.
- **DO NOT** modify the underlying Neo4j node/edge database schema without updating the corresponding query serialization tests in `tests/`.

---

## Self-Correction & Error Handling Loop

1. If a database query fails, inspect parameter data types and verify that Neo4j point properties are formatted as $3\text{D}$ spatial coordinates.
2. If Baseten API calls fail or time out, gracefully drop down to the secondary provider (Groq API or local execution fallback) without crashing the main FastAPI service process.
3. If generated Python trajectory code fails AST parsing, reject the payload and log the specific syntax error in the API response.