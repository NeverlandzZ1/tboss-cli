from unittest.mock import Mock

from boss_agent_cli.api import recruiter_endpoints as ep
from boss_agent_cli.api.recruiter_client import BossRecruiterClient
from boss_agent_cli.commands.recruiter.resume_parser import parse_resume


class FakeAuthManager:
	def get_token(self):
		return {"cookies": {}, "user_agent": "test-agent"}


def test_recommend_resume_uses_card_credentials_without_chat_refresh():
	client = BossRecruiterClient(FakeAuthManager())
	client._request = Mock(side_effect=AssertionError("must not refresh chat context"))
	browser = Mock()
	browser.evaluate_js.return_value = {
		"ok": True,
		"data": {"abstractData": {"geekBaseInfo": {"name": "fixture"}}},
		"canvas": {"draws": [{"canvas": 0, "x": 0, "y": 20, "text": "fixture"}]},
	}
	client._get_browser = Mock(return_value=browser)
	result = client.view_geek("geek", "job", "card-security", source="recommend", expect_id=123, lid="card-lid")
	assert result["code"] == 0
	client._request.assert_not_called()
	args = browser.evaluate_js.call_args.args[1]
	assert args["securityId"] == "card-security"
	assert args["expectId"] == 123
	assert args["lid"] == "card-lid"
	assert args["resumeSource"] == "recommend"
	assert browser.evaluate_js.call_args.kwargs == {"maintain_rendering": True}


def test_recommend_resume_rejects_missing_context_before_browser():
	client = BossRecruiterClient(FakeAuthManager())
	client._request = Mock()
	client._get_browser = Mock()
	assert client.view_geek("geek", "job", "security", source="recommend")["code"] != 0
	client._request.assert_not_called()
	client._get_browser.assert_not_called()


def test_view_geek_refreshes_context_and_uses_wasm_iframe():
	client = BossRecruiterClient(FakeAuthManager())
	client._request = Mock(
		return_value={
			"code": 0,
			"zpData": {
				"data": {
					"uid": 573011855,
					"jobId": 563357698,
					"securityId": "fresh-security",
					"encryptExpectId": "encrypted-expect",
					"expectId": 1373024696,
				}
			},
		}
	)
	browser = Mock()
	browser.evaluate_js.return_value = {
		"ok": True,
		"data": {
			"abstractData": {
				"geekBaseInfo": {"name": "任杰", "gender": 1},
				"geekEduExpList": [],
			}
		},
		"canvas": {"draws": [{"canvas": 1, "x": 0, "y": 20, "text": "任杰"}]},
	}
	client._get_browser = Mock(return_value=browser)

	result = client.view_geek("encrypted-uid", "encrypted-job", security_id="stale-security")

	client._request.assert_called_once_with(
		"GET",
		ep.BOSS_CHAT_GEEK_INFO_URL,
		params={
			"encryptGeekId": "encrypted-uid",
			"securityId": "stale-security",
			"jobId": "encrypted-job",
		},
	)
	args = browser.evaluate_js.call_args.args[1]
	assert browser.evaluate_js.call_args.kwargs == {"maintain_rendering": True}
	assert args == {
		"encryptUid": "encrypted-uid",
		"encryptJobId": "encrypted-job",
		"securityId": "fresh-security",
		"encryptExpectId": "encrypted-expect",
		"expectId": 1373024696,
		"uid": 573011855,
		"jobId": 563357698,
		"timeoutMs": 25000,
	}
	assert result["code"] == 0
	assert result["zpData"]["geekDetailInfo"]["geekBaseInfo"]["name"] == "任杰"
	assert result["__cli_endpoint_hint__"] == ep.BOSS_VIEW_GEEK_URL
	assert result["zpData"]["capture"]["completeness"] == "partial"
	client.close()


def test_view_geek_returns_context_error_without_starting_wasm():
	client = BossRecruiterClient(FakeAuthManager())
	client._request = Mock(return_value={"code": 8, "message": "无效的签名", "zpData": {}})
	client._get_browser = Mock()

	result = client.view_geek("encrypted-uid", "encrypted-job", security_id="security")

	assert result["code"] == 8
	client._get_browser.assert_not_called()
	client.close()


def test_parse_resume_accepts_v2_wasm_education_fields():
	result = parse_resume(
		{
			"code": 0,
			"zpData": {
				"geekDetailInfo": {
					"geekBaseInfo": {"name": "任杰", "gender": 1},
					"geekEduExpList": [
						{
							"school": "华东理工大学",
							"major": "控制科学与工程",
							"degreeName": "硕士",
							"startDateDesc": "2023",
							"endDateDesc": "2026",
						}
					],
				}
			},
		}
	)

	assert result["education"] == [
		{
			"school": "华东理工大学",
			"major": "控制科学与工程",
			"degree": "硕士",
			"start": "2023",
			"end": "2026",
		}
	]


def test_canvas_reconstruction_deduplicates_positions_not_words():
	from boss_agent_cli.api.resume_canvas import reconstruct_text

	rows = [
		{"canvas": 1, "x": 0, "y": 0, "text": "Boss-TraceID test"},
		{"canvas": 2, "x": 20, "y": 10, "text": "Redux"},
		{"canvas": 2, "x": 0, "y": 10, "text": "React "},
		{"canvas": 2, "x": 0, "y": 10, "text": "React "},
		{"canvas": 2, "x": 0, "y": 30, "text": "React "},
		{"canvas": 2, "x": float("nan"), "y": 0, "text": "bad"},
	]
	assert reconstruct_text(rows) == "React Redux\nReact"


def test_canvas_project_mapping_and_partial_metadata():
	from boss_agent_cli.api.resume_canvas import enrich_canvas_resume

	summary = {"geekProjExpList": [{"name": "项目甲"}, {"name": "项目乙"}]}
	lines = [
		"项目经验项目甲负责人",
		"2024.10 - 2025.06",
		"React 技术栈",
		"材料库导出查看全部",
		"项目乙负责人",
		"2024.08 - 2024.10",
		"Axios 请求模块",
		"教育经历大学",
		"课程",
	]
	canvas = {"draws": [{"canvas": 1, "x": 0, "y": i * 20, "text": text} for i, text in enumerate(lines)]}
	info, capture = enrich_canvas_resume(summary, canvas)
	assert info["geekProjExpList"][0]["projectDescription"] == "React 技术栈\n材料库导出"
	assert info["geekProjExpList"][1]["projectDescription"] == "Axios 请求模块"
	assert "projectDescription" not in summary["geekProjExpList"][0]
	assert capture["completeness"] == "partial"
	assert "expand_controls_present" in capture["reasons"]
	parsed = parse_resume({"zpData": {"geekDetailInfo": info, "capture": capture}})
	assert parsed["project_experience"][1]["description"] == "Axios 请求模块"
	assert parsed["capture"]["raw_is_api_response"] is False
	assert "教育经历" in parsed["rendered_text"]


def test_canvas_duplicate_project_titles_do_not_guess():
	from boss_agent_cli.api.resume_canvas import enrich_canvas_resume

	info, capture = enrich_canvas_resume(
		{"geekProjExpList": [{"name": "项目甲"}]},
		{
			"draws": [{"text": "项目甲", "x": 0, "y": y} for y in (10, 30)],
			"capped": True,
			"timed_out": True,
		},
	)
	assert "projectDescription" not in info["geekProjExpList"][0]
	assert "project_anchor_ambiguous" in capture["reasons"]
	assert "capture_limit" in capture["reasons"]
	assert "capture_timeout" in capture["reasons"]


def test_summary_only_is_not_reported_as_canvas_success():
	client = BossRecruiterClient(FakeAuthManager())
	client._request = Mock(return_value={"code": 0, "zpData": {"data": {"securityId": "fresh"}}})
	browser = Mock()
	browser.evaluate_js.return_value = {"ok": True, "data": {"abstractData": {"geekBaseInfo": {"name": "任杰"}}}}
	client._get_browser = Mock(return_value=browser)
	result = client.view_geek("g", "j", security_id="s")
	assert result["code"] == -1
	assert "未采集到简历正文" in result["message"]
	client.close()


def test_full_traversal_maps_work_and_preserves_extra_sections():
	from boss_agent_cli.api.resume_canvas import enrich_canvas_resume

	summary = {
		"geekWorkExpList": [{"company": "公司甲"}, {"company": "公司乙"}],
		"geekEduExpList": [{"school": "大学"}],
	}
	lines = [
		"基本信息",
		"工作经历公司甲工程师",
		"2024.01 - 2025.01",
		"第一段职责",
		"公司乙工程师",
		"2023.01 - 2024.01",
		"第二段职责",
		"教育经历大学",
		"2020 - 2023",
		"主修课程：计算机",
		"所获荣誉",
		"奖学金",
		"专业技能",
		"Python",
	]
	canvas = {
		"draws": [{"canvas": 0, "x": 0, "y": i * 20, "text": t} for i, t in enumerate(lines)],
		"composited": True,
		"reached_bottom": True,
		"height_measured": True,
		"snapshots": 4,
		"scroll_steps": 2,
	}
	info, capture = enrich_canvas_resume(summary, canvas)
	assert info["geekWorkExpList"][0]["responsibility"] == "第一段职责"
	assert info["geekWorkExpList"][1]["responsibility"] == "第二段职责"
	assert "计算机" in info["geekEduExpList"][0]["description"]
	assert info["renderedSections"]["所获荣誉"] == "所获荣誉\n奖学金"
	assert capture["completeness"] == "rendered_complete"
	assert capture["reached_bottom"]
