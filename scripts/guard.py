#!/usr/bin/env python3
"""PreToolUse guard for sf-orchestrator. Exit 0 allows; exit 2 blocks (stderr shown to the model)."""
import datetime, json, os, re, sys

APPROVAL = os.path.join('.claude', 'sf-orchestrator-approval.json')
APPROVAL_TTL_MIN = 60
DESTRUCTIVE = re.compile(
    r'\bsf\s+project\s+deploy\b|\bsfdx\s+force:source:deploy\b|'
    r'\bsfdx\s+force:source:push\b|\bsf\s+project\s+delete\s+source\b|'
    r'\bsf\s+data\s+delete\b|\bsf\s+org\s+delete\b')

def block(msg):
    print(f'sf-orchestrator guard: {msg}', file=sys.stderr)
    sys.exit(2)

def main():
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)  # not our concern; never break unrelated tooling
    tool = event.get('tool_name', '')
    tin = event.get('tool_input', {}) or {}

    if tool == 'Agent':
        sub = str(tin.get('subagent_type', ''))
        # installed plugin agents are namespaced ("<plugin>:sf-apex-worker") — match the agent segment
        if sub.split(':')[-1].startswith('sf-') and not tin.get('model'):
            block(f'dispatch of {sub} without an explicit model parameter. '
                  'Set model from .claude/sf-orchestrator.json and retry.')

    if tool == 'Bash':
        cmd = str(tin.get('command', ''))
        if DESTRUCTIVE.search(cmd):
            if not os.path.exists(APPROVAL):
                block('deploy/destructive command without approval. Confirm org and '
                      'scope with the user, write .claude/sf-orchestrator-approval.json, retry.')
            try:
                approval = json.load(open(APPROVAL))
                ts = approval['grantedAt']
                # Python < 3.11 rejects a trailing Z; normalize before parsing
                if isinstance(ts, str) and ts.endswith('Z'):
                    ts = ts[:-1] + '+00:00'
                granted = datetime.datetime.fromisoformat(ts)
                if granted.tzinfo is None:
                    granted = granted.replace(tzinfo=datetime.timezone.utc)
                age_min = (datetime.datetime.now(datetime.timezone.utc) - granted).total_seconds() / 60
                org = approval.get('org', '')
            except (KeyError, ValueError, TypeError, json.JSONDecodeError):
                block('approval file malformed; re-confirm with the user and rewrite it.')
            if age_min > APPROVAL_TTL_MIN:
                block(f'approval expired ({int(age_min)} min old, TTL {APPROVAL_TTL_MIN}). Re-confirm with the user.')
            if not isinstance(org, str) or not org.strip():
                block('approval file does not name a target org; re-confirm with the user and rewrite it.')
            targets = re.findall(r'(?:--target-org|--targetusername|-o|-u)[=\s]+(\S+)', cmd)
            if org not in targets:
                block(f'command does not target the approved org "{org}" via --target-org/-o.')
    sys.exit(0)

main()
