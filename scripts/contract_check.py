#!/usr/bin/env python3
"""Contract checks beyond `claude plugin validate`. Exit 0 = ok."""
import glob, json, re, sys

errors = []

def frontmatter(path):
    text = open(path).read()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.S)
    if not m:
        return None
    return dict(re.findall(r'^([A-Za-z_-]+):\s*(.*)$', m.group(1), re.M))

for j in ('.claude-plugin/plugin.json', '.claude-plugin/marketplace.json',
          'schemas/config.schema.json', 'hooks/hooks.json'):
    try:
        json.load(open(j))
    except FileNotFoundError:
        errors.append(f'missing {j}')
    except json.JSONDecodeError as e:
        errors.append(f'invalid JSON {j}: {e}')

agents = sorted(glob.glob('agents/*.md'))
skills = sorted(glob.glob('skills/*/SKILL.md'))
if len(agents) != 9:
    errors.append(f'expected 9 agents, found {len(agents)}')
if len(skills) != 2:
    errors.append(f'expected 2 skills, found {len(skills)}')

REQUIRED_AGENT_PHRASES = ['fallback: true', 'STOP', 'skills_loaded']
for p in agents:
    fm = frontmatter(p)
    body = open(p).read()
    if not fm or not fm.get('name') or not fm.get('description') or not fm.get('tools'):
        errors.append(f'{p}: frontmatter must have name/description/tools')
        continue
    if 'model' in fm:
        errors.append(f'{p}: model is forbidden in frontmatter')
    if fm['name'] != p.split('/')[-1][:-3]:
        errors.append(f'{p}: frontmatter name must match filename')
    for phrase in REQUIRED_AGENT_PHRASES:
        if phrase not in body:
            errors.append(f'{p}: missing contract phrase {phrase!r}')

for p in skills:
    fm = frontmatter(p)
    if not fm or not fm.get('name') or not fm.get('description'):
        errors.append(f'{p}: frontmatter must have name/description')

for e in errors:
    print(f'FAIL: {e}')
sys.exit(1 if errors else 0)
