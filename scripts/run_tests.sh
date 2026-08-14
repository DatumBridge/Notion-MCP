#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
python scripts/test_helpers.py -v
