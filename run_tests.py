import subprocess
import sys

test_dir = 'C:/Users/Iran/Downloads/Telegram Desktop/autozcoder-@ArchiveTell/tests'
venv_python = 'C:/Users/Iran/Downloads/Telegram Desktop/autozcoder-@ArchiveTell/.venv/Scripts/python.exe'

result = subprocess.run([venv_python, '-m', 'pytest', test_dir, '-q', '--no-header'], capture_output=True, text=True)
print(result.stdout)
print(result.stderr)
print('Exit code:', result.returncode)

