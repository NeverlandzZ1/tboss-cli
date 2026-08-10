# tboss-cli

基于 [can4hou6joeng4/boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli) 的分支,聚焦 BOSS 直聘招聘者(HR)侧自动化,新增了 `hr accept-resume` / `hr chat-start` / `hr friend-detail` 等命令,并修复了 `hr request-resume` 在 BOSS UI 改版后无二次确认弹窗导致的失败。

## 使用方法

命令用法、参数、示例、Agent 集成等详细文档,请查看上游项目:

👉 [can4hou6joeng4/boss-agent-cli](https://github.com/can4hou6joeng4/boss-agent-cli)

## 安装

```bash
uv tool install git+https://github.com/NeverlandzZ1/tboss-cli.git
```

安装完成后:

```bash
boss --role recruiter login          # 首次登录
boss --role recruiter hr jobs list   # 验证可用
```

升级 / 卸载:

```bash
uv tool upgrade tboss-cli
uv tool uninstall tboss-cli
```

> 没装 uv 的话,`pipx install git+https://github.com/NeverlandzZ1/tboss-cli.git` 也行。

## 命令速查

HR 端常用命令、参数、返回字段速查见:

👉 [skill/boss-cli-commands.md](skill/boss-cli-commands.md)

## License

MIT — 见 [LICENSE](LICENSE)。原作者 can4hou6joeng4 版权保留。
