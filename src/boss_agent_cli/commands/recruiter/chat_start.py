"""招聘者 — 推荐池首招（建立聊天关系并触发职位默认招呼语）。"""
import click

from boss_agent_cli.auth.manager import AuthManager
from boss_agent_cli.compliance import require_compliance_allowed
from boss_agent_cli.commands._recruiter_platform import get_recruiter_platform_instance
from boss_agent_cli.display import handle_auth_errors, handle_output, handle_platform_error_output


@click.command("chat-start")
@click.argument("encrypt_geek_id")
@click.option("--job-id", required=True, help="职位 encryptJobId（=调 hr recommend 时的 --job-id）")
@click.option("--expect-id", required=True, help="recommend 响应里 geek.expectId")
@click.option("--lid", required=True, help="recommend 响应里 geek.lid（含 sessionId，尽快用）")
@click.option("--security-id", required=True, help="recommend 响应里 geek.securityId（一次性凭证）")
@click.pass_context
@handle_auth_errors("recruiter-chat-start")
def chat_start_cmd(
	ctx: click.Context,
	encrypt_geek_id: str,
	job_id: str,
	expect_id: str,
	lid: str,
	security_id: str,
) -> None:
	"""推荐池首招：给 hr recommend 拿到的候选人发默认招呼语，建立聊天关系。

	成功后返回数字 friendId（zpData.geekId），后续可直接 `hr reply <fid> <msg>` 追问。
	所有参数都能从同一次 hr recommend 响应里直接取。
	"""
	if not require_compliance_allowed(ctx, "recruiter-chat-start"):
		return

	data_dir = ctx.obj["data_dir"]
	logger = ctx.obj["logger"]

	auth = AuthManager(data_dir, logger=logger, platform=ctx.obj.get("platform", "zhipin"))
	with get_recruiter_platform_instance(ctx, auth) as platform:
		result = platform.chat_start(
			encrypt_geek_id,
			job_id=job_id,
			expect_id=expect_id,
			lid=lid,
			security_id=security_id,
		)
		if not platform.is_success(result):
			handle_platform_error_output(
				ctx, "recruiter-chat-start", platform, result,
				fallback_message="首招失败（lid/securityId 可能过期，重新 hr recommend 后再试）",
			)
			return
		zp_data = platform.unwrap_data(result) or {}
		friend_id = zp_data.get("geekId")
		data = {
			"friend_id": friend_id,
			"newfriend": zp_data.get("newfriend"),
			"status": zp_data.get("status"),
			"greeting": zp_data.get("greeting"),
		}
		handle_output(
			ctx, "recruiter-chat-start", data,
			hints={"next_actions": [
				f"boss hr reply {friend_id} <消息> — 追加自定义消息",
				"boss hr chat — 查看沟通列表",
			]},
		)
