"""招聘者 — 每日推荐牛人。"""
import click

from boss_agent_cli.auth.manager import AuthManager
from boss_agent_cli.compliance import require_compliance_allowed
from boss_agent_cli.commands._recruiter_platform import get_recruiter_platform_instance
from boss_agent_cli.display import handle_auth_errors, handle_output, handle_platform_error_output


@click.command("recommend")
@click.option("--job-id", required=True, help="职位 encryptJobId（必填，先用 `hr jobs list` 拿）")
@click.option("--page", default=1, type=int, help="页码（默认 1）")
@click.option("--age", default="16,-1", help="年龄范围，默认 16,-1（不限）")
@click.option("--activation", default="0", help="活跃度筛选（默认 0=不限）")
@click.option("--school", default="0", help="学校层次（默认 0=不限）")
@click.option("--gender", default="0", help="性别（默认 0=不限）")
@click.option("--recent-not-view", default="0", help="仅未看过（默认 0=不限）")
@click.option("--exchange-resume-with-colleague", default="0", help="与同事换过简历（默认 0=不限）")
@click.option("--major", default="0", help="专业筛选（默认 0=不限）")
@click.option("--keyword1", default="-1", help="关键词筛选（默认 -1=不限）")
@click.option("--switch-job-frequency", default="0", help="跳槽频率（默认 0=不限）")
@click.option("--degree", default="0", help="学历（默认 0=不限）")
@click.option("--experience", default="0", help="经验（默认 0=不限）")
@click.option("--intention", default="0", help="求职意向（默认 0=不限）")
@click.option("--salary", default="0", help="薪资范围（默认 0=不限）")
@click.option("--cover-screen-memory", default="0", help="翻页记忆（默认 0）")
@click.option("--card-type", default="0", help="卡片类型（默认 0）")
@click.pass_context
@handle_auth_errors("recruiter-recommend")
def recommend_cmd(
	ctx: click.Context,
	job_id: str,
	page: int,
	age: str,
	activation: str,
	school: str,
	gender: str,
	recent_not_view: str,
	exchange_resume_with_colleague: str,
	major: str,
	keyword1: str,
	switch_job_frequency: str,
	degree: str,
	experience: str,
	intention: str,
	salary: str,
	cover_screen_memory: str,
	card_type: str,
) -> None:
	"""按职位获取平台推荐的牛人列表"""
	if not require_compliance_allowed(ctx, "recruiter-recommend"):
		return

	data_dir = ctx.obj["data_dir"]
	logger = ctx.obj["logger"]

	auth = AuthManager(data_dir, logger=logger, platform=ctx.obj.get("platform", "zhipin"))
	with get_recruiter_platform_instance(ctx, auth) as platform:
		result = platform.recommend_geeks(
			job_id,
			page=page,
			age=age,
			activation=activation,
			school=school,
			gender=gender,
			recent_not_view=recent_not_view,
			exchange_resume_with_colleague=exchange_resume_with_colleague,
			major=major,
			keyword1=keyword1,
			switch_job_frequency=switch_job_frequency,
			degree=degree,
			experience=experience,
			intention=intention,
			salary=salary,
			cover_screen_memory=cover_screen_memory,
			card_type=card_type,
		)
		if not platform.is_success(result):
			handle_platform_error_output(ctx, "recruiter-recommend", platform, result, fallback_message="推荐牛人获取失败")
			return
		data = platform.unwrap_data(result) or {}
		handle_output(
			ctx, "recruiter-recommend", data,
			hints={"next_actions": [
				"boss hr chat-start <encryptGeekId> --job-id <encryptJobId> --expect-id <expectId> --lid <lid> --security-id <securityId> — 首招（尽快调用，lid/securityId 有时效）",
				"boss hr resume <geek_id> --job-id <id> --security-id <id> — 查看简历",
				"boss hr chat — 打招呼后转入聊天",
			]},
		)
