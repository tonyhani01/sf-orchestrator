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
expect 2 agent_missing_model_namespaced.json
expect 2 bash_deploy_unapproved.json
expect 2 bash_delete_source.json
expect 0 bash_ok.json
mkdir -p .claude
python3 - <<'EOF'
import json, datetime
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"],
           "grantedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 0 bash_deploy_unapproved.json   # now approved: --target-org matches
expect 0 bash_delete_source.json       # delete source is gated, and approved here
expect 2 bash_deploy_wrong_org.json    # approved org only in a path, --target-org differs
expect 2 bash_deploy_no_org_flag.json  # no explicit --target-org flag: blocked
python3 - <<'EOF'
import json, datetime
ts = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"], "grantedAt": ts},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 0 bash_deploy_unapproved.json   # Z-suffixed timestamp parses on all Pythons
python3 - <<'EOF'
import json, datetime
json.dump({"org": "", "scope": ["classes/Foo.cls"],
           "grantedAt": datetime.datetime.now(datetime.timezone.utc).isoformat()},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 2 bash_deploy_unapproved.json   # empty org must not bypass the org check
python3 - <<'EOF'
import json
json.dump({"org": "my-sandbox", "scope": ["classes/Foo.cls"],
           "grantedAt": "2026-07-21T09:00:00"},
          open('.claude/sf-orchestrator-approval.json', 'w'))
EOF
expect 2 bash_deploy_unapproved.json   # naive+stale timestamp: clean block, not a crash
rm -f .claude/sf-orchestrator-approval.json
[ "$fail" -eq 0 ] && echo GUARD-PASS || { echo GUARD-FAIL; exit 1; }
