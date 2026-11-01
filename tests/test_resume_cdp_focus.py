import json
from unittest.mock import MagicMock, patch

import pytest

from boss_agent_cli.api.browser_client import _cdp_evaluate_in_chat_tab


@pytest.mark.parametrize("failure", [None, "js", "transport", "enable", "reset"])
def test_render_focus_is_scoped_and_cleaned_up(failure):
	ws = MagicMock()
	sent = []

	def send(payload):
		sent.append(json.loads(payload))

	def recv(**kwargs):
		message = sent[-1]
		mid = message["id"]
		if mid == 1:
			if failure == "transport":
				raise TimeoutError("transport")
			if failure == "js":
				return json.dumps({"id": mid, "result": {"result": {}, "exceptionDetails": {"text": "failed"}}})
			return json.dumps({"id": mid, "result": {"result": {"value": {"ok": True}}}})
		if (mid == 2 and failure == "enable") or (mid == 3 and failure == "reset"):
			return json.dumps({"id": mid, "error": {"message": "unsupported"}})
		return json.dumps({"id": mid, "result": {}})

	ws.send.side_effect = send
	ws.recv.side_effect = recv
	with (
		patch("boss_agent_cli.api.browser_client._pick_chat_target_ws", return_value="ws://test"),
		patch("websockets.sync.client.connect") as connect,
	):
		connect.return_value.__enter__.return_value = ws
		if failure:
			with pytest.raises((RuntimeError, TimeoutError)):
				_cdp_evaluate_in_chat_tab("http://test", "() => ({ok:true})", {}, maintain_rendering=True)
		else:
			assert _cdp_evaluate_in_chat_tab("http://test", "() => ({ok:true})", {}, maintain_rendering=True) == {
				"ok": True
			}
	assert sent[0]["method"] == "Emulation.setFocusEmulationEnabled"
	assert sent[0]["params"] == {"enabled": True}
	assert sent[-1]["method"] == "Emulation.setFocusEmulationEnabled"
	assert sent[-1]["params"] == {"enabled": False}
	ws.close.assert_called_once()


def test_ordinary_evaluation_does_not_emulate_focus():
	ws = MagicMock()
	ws.recv.return_value = json.dumps({"id": 1, "result": {"result": {"value": 42}}})
	with (
		patch("boss_agent_cli.api.browser_client._pick_chat_target_ws", return_value="ws://test"),
		patch("websockets.sync.client.connect") as connect,
	):
		connect.return_value.__enter__.return_value = ws
		assert _cdp_evaluate_in_chat_tab("http://test", "42", None) == 42
	assert [json.loads(c.args[0])["method"] for c in ws.send.call_args_list] == ["Runtime.evaluate"]
