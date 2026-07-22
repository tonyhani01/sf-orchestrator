#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
if command -v claude >/dev/null 2>&1; then
  claude plugin validate . --strict || fail=1
else
  echo "note: claude CLI not found, skipping plugin validate"
fi
python3 scripts/contract_check.py || fail=1
bash tests/test_guard.sh || fail=1
bash tests/test_config.sh || fail=1
[ "$fail" -eq 0 ] && echo PASS || { echo FAIL; exit 1; }
