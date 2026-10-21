"""Stdlib HTTP smoke test for an already-running local or Compose demo deployment."""
import json
import os
import time
from urllib.error import URLError
from urllib.request import Request, urlopen

base = os.getenv('DEVPILOT_SMOKE_URL', 'http://127.0.0.1:8080')
token = os.getenv('DEVPILOT_API_TOKEN', '')


def request(path, body=None, binary=False):
    data = json.dumps(body).encode() if body is not None else None
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    with urlopen(Request(base + '/api/v1' + path, data=data, headers=headers), timeout=10) as response:
        content = response.read()
        return content if binary else json.loads(content)


for attempt in range(40):
    try:
        assert request('/health')['status'] == 'ok'
        break
    except (URLError, AssertionError):
        time.sleep(1)
else:
    raise SystemExit('Service did not become healthy')

repo = request('/repositories', {'url': 'demo://calculator'})
assert request(f'/repositories/{repo["id"]}/search?q=add&mode=hybrid')
task = request('/tasks', {'repository_id': repo['id'], 'prompt': 'Fix the add function', 'variant': 'D'})


def wait_for(status):
    for attempt in range(60):
        current = request('/tasks/' + task['id'])
        if current['status'] == status:
            return current
        if current['status'] == 'failed':
            raise AssertionError(current['result'])
        time.sleep(1)
    raise AssertionError(f'Task did not reach {status}')


waiting = wait_for('awaiting_approval')
request(f'/tasks/{task["id"]}/approval', {'approved': True,
                                       'patch_digest': waiting['result']['patch']['digest']})
wait_for('approved_unverified')
assert request(f'/tasks/{task["id"]}/export', binary=True).startswith(b'PK')
print('HTTP smoke passed: import, retrieval, background task, checkpoint, approval and ZIP export')
