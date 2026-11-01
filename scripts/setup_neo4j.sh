#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="spatialspark-neo4j"
IMAGE="neo4j:latest"
AUTH="neo4j/spatialpassword"
HTTP_PORT="7474"
BOLT_PORT="7687"

if ! command -v docker &> /dev/null; then
    echo "Error: docker is not installed or not in PATH."
    exit 1
fi

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Neo4j container '${CONTAINER_NAME}' is already running."
    exit 0
fi

if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo "Starting existing Neo4j container '${CONTAINER_NAME}'..."
    docker start "${CONTAINER_NAME}"
else
    echo "Creating and starting new Neo4j container '${CONTAINER_NAME}'..."
    docker run -d \
        --name "${CONTAINER_NAME}" \
        -p "${HTTP_PORT}:7474" \
        -p "${BOLT_PORT}:7687" \
        -e NEO4J_AUTH="${AUTH}" \
        "${IMAGE}"
fi

echo "Neo4j container '${CONTAINER_NAME}' is up on ports ${HTTP_PORT} (HTTP) and ${BOLT_PORT} (Bolt)."

