#!/usr/bin/env python3
"""Read-only event and artifact analysis."""
import json, pathlib, sqlite3, sys
if len(sys.argv)!=2:raise SystemExit('Usage: python3 report.py runs/<run-directory>')
run=pathlib.Path(sys.argv[1]); db=sqlite3.connect(run/'events.sqlite3')
print('\n=== RESULTS ===')
for row in db.execute('SELECT agent,COUNT(*),SUM(correct) FROM scores GROUP BY agent ORDER BY agent'):
 print(f'{row[0]}: {row[2]}/{row[1]} correct')
print('\n=== SHARED ARTIFACTS ===')
shared=run/'shared'
for p in sorted(shared.glob('*')) if shared.exists() else []:
 if p.is_file():print(f'  {p.name} ({p.stat().st_size} bytes)')
print('\n=== OBSERVED ACTIONS ===')
for ts,agent,kind,detail in db.execute('SELECT ts,agent,kind,detail FROM events ORDER BY id'):
 d=json.loads(detail);print(ts,agent,kind,repr(d)[:180])
print('\nIMPORTANT: Shared writes alone do not establish social behavior. Look for cross-agent reads and subsequent reuse.')
