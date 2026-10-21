"""Run with the project's Python after reviewing a dependency change."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = subprocess.check_output([sys.executable, '-m', 'pip', 'freeze', '--exclude-editable'], text=True)
lines = []
for line in output.splitlines():
    if line.lower().startswith('pywin32=='):
        line += '; sys_platform == "win32"'
    if line.strip():
        lines.append(line)
(root / 'backend/requirements.lock').write_text(
    '# Python 3.12 dependency snapshot; refresh with scripts/lock_dependencies.py\n'
    + '\n'.join(lines) + '\n', encoding='utf-8',
)
print('Updated backend/requirements.lock')
