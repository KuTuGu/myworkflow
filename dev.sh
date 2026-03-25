#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

docker cp DeepAgent:/app/src/memories/. "$SCRIPT_DIR/src/memories/"

docker build -t myworkflow .

docker compose up -d
