import click

from boss_agent_cli.display import handle_output


@click.command("hello")
@click.argument("name")                                     # 必填位置参数
@click.option("--loud/--no-loud", default=False,
              help="是否大声喊（全大写 + 感叹号）")
@click.pass_context
def hello_cmd(ctx: click.Context, name: str, loud: bool) -> None:
    """向指定的人打招呼（本地示例命令）"""
    greeting = f"Hello, {name}"
    if loud:
        greeting = greeting.upper() + "!!!"

    handle_output(
        ctx,
        "hello",                                            # ← 命令名，必须和 @click.command 一致
        {
            "name": name,
            "greeting": greeting,
            "loud": loud,
        },
        render=lambda d: click.echo(d["greeting"]),         # 人类模式直接打字符串
        hints={
            "next_actions": [
                "boss hello <name> --loud — 大声打招呼",
            ],
        },
    )
