# tboss-cli

基于 [can4hou6joeng4/boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli) 的分支,聚焦 BOSS 直聘招聘者(HR)侧自动化,新增了 `hr accept-resume` / `hr chat-start` / `hr friend-detail` 等命令,并修复了 `hr request-resume` 在 BOSS UI 改版后无二次确认弹窗导致的失败。

## 使用方法

本分支 HR 命令以 [本地命令契约](skill/boss-agent-cli-commands.md) 为准；通用背景可查看上游项目:

👉 [can4hou6joeng4/boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli)

## 安装

```bash
uv tool install --force --refresh git+https://github.com/NeverlandzZ1/tboss-cli.git
```

安装完成后:

```bash
boss --cdp-url http://localhost:9222 --role recruiter login --cdp  # 绑定已登录 Chrome
boss --cdp-url http://localhost:9222 --role recruiter hr jobs list # 验证可用
```

升级 / 卸载:

```bash
uv tool install --force --refresh git+https://github.com/NeverlandzZ1/tboss-cli.git
uv tool uninstall tboss-cli
```

配置 Skill 统一使用 `install_cli.py` 解析最新 Git HEAD 并验证安装提交、实际可执行路径
和新版简历参数，不以版本号相同跳过更新。开发中的本地改动需先发布到此 Git 源，
再更新全局安装；`uv run boss` 仅用于本地开发验证。

## 命令速查

HR 端常用命令、参数、返回字段速查见:

👉 [skill/boss-agent-cli-commands.md](skill/boss-agent-cli-commands.md)

新版在线简历支持 chat / recommend 来源，参数、Canvas 采集与后台窗口支持见
[在线简历文档](docs/online-resume-canvas.md)。推荐来源在筛选前即可查看，无需先首招。

## License

MIT — 见 [LICENSE](LICENSE)。原作者 can4hou6joeng4 版权保留。
