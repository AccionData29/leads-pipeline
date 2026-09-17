#!/usr/bin/env bash
set -euo pipefail
python -m pipeline.main --source-dir "${SOURCE_DIR:-./data/raw}" ${INIT_DB:+--init-db} ${NO_DB:+--no-db}
