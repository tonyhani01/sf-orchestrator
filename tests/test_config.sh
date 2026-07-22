#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0

expect() { # expect <exit-code> <fixture-or-path>
  out=$(python3 scripts/check_config.py "$1" 2>&1)
  actual=$?
  [ "$actual" -eq "$2" ] || { echo "FAIL: $1 expected exit $2 got $actual"; fail=1; }
  echo "$out"
}

out=$(expect tests/fixtures/config_malformed.json 1)
echo "$out" | grep -q . || { echo "FAIL: config_malformed.json produced no message"; fail=1; }

out=$(expect tests/fixtures/config_bad_model.json 1)
echo "$out" | grep -q "models.default" || { echo "FAIL: config_bad_model.json did not name models.default"; fail=1; }

expect tests/fixtures/config_valid.json 0 >/dev/null
expect tests/fixtures/does_not_exist.json 0 >/dev/null

[ "$fail" -eq 0 ] && echo CONFIG-PASS || { echo CONFIG-FAIL; exit 1; }
