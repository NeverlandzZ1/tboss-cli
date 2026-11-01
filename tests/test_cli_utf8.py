import json
import os
import subprocess
import sys


def test_cli_owns_pipe_encoding_even_with_gbk_environment():
	code = '''
import click
from boss_agent_cli.main import BossCliGroup
from boss_agent_cli.output import emit_success
@click.group(cls=BossCliGroup)
def root(): pass
@root.command()
def probe(): emit_success("probe", {"text": "中文•😀"})
root(["probe"])
'''
	result = subprocess.run(
		[sys.executable, "-c", code], capture_output=True,
		env=dict(os.environ, PYTHONIOENCODING="gbk", PYTHONUTF8="0"),
	)
	assert result.returncode == 0, result.stderr
	assert json.loads(result.stdout.decode("utf-8"))["data"]["text"] == "中文•😀"
