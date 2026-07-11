import psycopg2, json
conn = psycopg2.connect('postgresql://markly:markly@localhost:5432/markly_dev')
cur = conn.cursor()
cur.execute('SELECT run_id, goal, state_json FROM runs ORDER BY created_at DESC LIMIT 5;')
runs = cur.fetchall()
for run in runs:
    run_id = run[0]
    goal = run[1]
    cost = run[2].get('cost_total', 0)
    tokens = run[2].get('tokens_used', 0)
    status = run[2].get('status', 'unknown')
    print(f'\n==== RUN: {run_id} ====')
    print(f'Goal: {goal}')
    print(f'Cost: ${cost}')
    print(f'Tokens: {tokens}')
    print(f'Status: {status}')
    cur.execute('SELECT turn_number, subgoal, tool_name, tool_args, observation, verify_score FROM turns WHERE run_id = %s ORDER BY turn_number;', (run_id,))
    turns = cur.fetchall()
    for t in turns:
        print(f'  Turn {t[0]} [{t[1]}] | Tool: {t[2]} {json.dumps(t[3])} | Verify: {t[5]} | Obs: {repr(t[4][:200] if t[4] else None)}')
