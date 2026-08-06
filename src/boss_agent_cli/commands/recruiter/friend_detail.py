"""招聘者 — 批量拉候选人详情（反查 encryptUid/encryptJobId/securityId）。"""
import click

from boss_agent_cli.auth.manager import AuthManager
from boss_agent_cli.compliance import require_compliance_allowed
from boss_agent_cli.commands._recruiter_platform import get_recruiter_platform_instance
from boss_agent_cli.display import handle_auth_errors, handle_output, handle_platform_error_output


@click.command("friend-detail")
@click.argument("friend_ids", nargs=-1, type=int, required=True)
@click.pass_context
@handle_auth_errors("recruiter-friend-detail")
def friend_detail_cmd(ctx: click.Context, friend_ids: tuple[int, ...]) -> None:
    """批量拉沟通列表好友详情 —— 反查 encryptUid / encryptJobId / securityId。

    典型用法：`hr chatmsg` 只有 plain 数字 uid/jobId，通过本命令补齐
    加密 ID 后即可喂给 `hr resume`。
    """
    if not require_compliance_allowed(ctx, "recruiter-friend-detail"):
        return

    data_dir = ctx.obj["data_dir"]
    logger = ctx.obj["logger"]

    auth = AuthManager(data_dir, logger=logger, platform=ctx.obj.get("platform", "zhipin"))
    with get_recruiter_platform_instance(ctx, auth) as platform:
        result = platform.friend_detail(list(friend_ids))
        if not platform.is_success(result):
            handle_platform_error_output(
                ctx, "recruiter-friend-detail", platform, result,
                fallback_message="批量拉候选人详情失败",
            )
            return
        data = platform.unwrap_data(result) or {}
        handle_output(
            ctx, "recruiter-friend-detail", data,
            hints={"next_actions": [
                "boss hr resume <encryptUid> --job-id <encryptJobId> --security-id <securityId> — 查看在线简历",
                "boss hr request-resume <friend_id> — 请求附件简历",
            ]},
        )
