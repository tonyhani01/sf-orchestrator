#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
fail=0
expect() { # expect <exit-code> <fixture>
  python3 scripts/guard.py < "tests/fixtures/$2" >/dev/null 2>&1
  actual=$?
  [ "$actual" -eq "$1" ] || { echo "FAIL: $2 expected exit $1 got $actual"; fail=1; }
}
rm -f .claude/sf-orchestrator-approval.json
expect 2 agent_missing_model.json
expect 2 bash_deploy_unapproved.json
expect 0 bash_ok.json
mkdir -p .claude
python3 - <<'EOF'
import json, datetime
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"],
           "grantedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 0 bash_deploy_unapproved.json   # now approved: same org appears in command
rm -f .claude/sf-orchestrator-approval.json
[ "$fail" -eq 0 ] && echo GUARD-PASS || { echo GUARD-FAIL; exit 1; }
