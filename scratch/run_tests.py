import subprocess
import os
import sys

env = os.environ.copy()
env['DATABASE_URL'] = 'postgresql://markly:markly@localhost:5432/markly_dev'
env['PYTHONIOENCODING'] = 'utf-8'

tests = [
    ('1.1', 'Use shell.execute to echo "Test 1.1 Passed"'),
    ('1.2', 'Use shell.execute to read a non-existent file missing_12.txt'),
    ('1.3', 'Use shell.execute to read missing_13.txt. The critic will retry twice. DO NOT create the file.'),
    ('1.4', 'Use shell.execute to echo "Test 1.4 Passed"'),
    ('1.5', 'Use shell.execute to echo "dedup_1" and then echo "dedup_2" in a separate subgoal'),
]

with open('scratch/outputs.txt', 'w', encoding='utf-8') as f:
    for name, prompt in tests:
        print(f'Running {name}...')
        f.write(f'\n--- TEST {name} ---\n')
        r = subprocess.run(f'uv run markly run "{prompt}"', input='y\ny\ny\ny\ny\ny\n', capture_output=True, text=True, shell=True, env=env, encoding='utf-8', errors='replace')
        if r.stdout: f.write(r.stdout)
        f.write('\nSTDERR:\n')
        if r.stderr: f.write(r.stderr)
        f.write('\n')
