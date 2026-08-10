"""招聘者 — 同意候选人发送附件简历。"""
import click

from boss_agent_cli.auth.manager import AuthManager
from boss_agent_cli.compliance import require_compliance_allowed
from boss_agent_cli.commands._recruiter_platform import get_recruiter_platform_instance
from boss_agent_cli.display import handle_auth_errors, handle_output, handle_platform_error_output


@click.command("accept-resume")
@click.argument("friend_id", type=int)
@click.pass_context
@handle_auth_errors("recruiter-accept-resume")
def accept_resume_cmd(ctx: click.Context, friend_id: int) -> None:
	"""同意候选人发来的附件简历请求。"""
	if not require_compliance_allowed(ctx, "recruiter-accept-resume"):
		return

	data_dir = ctx.obj["data_dir"]
	logger = ctx.obj["logger"]

	auth = AuthManager(data_dir, logger=logger, platform=ctx.obj.get("platform", "zhipin"))
	with get_recruiter_platform_instance(ctx, auth) as platform:
		result = platform.accept_resume_by_friend(friend_id)
		if not platform.is_success(result):
			handle_platform_error_output(
				ctx,
				"recruiter-accept-resume",
				platform,
				result,
				fallback_message="同意附件简历失败",
			)
			return
		data = platform.unwrap_data(result) or {}
		handle_output(
			ctx,
			"recruiter-accept-resume",
			data,
			hints={"next_actions": [
				f"boss hr chatmsg {friend_id} — 查看候选人后续消息",
				"boss hr chat --label-id 4 — 查看已获取简历候选人",
			]},
		)
