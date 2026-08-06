# boss-agent-cli 本地开发上手指南

> 面向从未开发过 Python CLI 的人。目标：**跑起来 → 改一行代码看到效果 → 加一个自己的命令 → 让 Claude/Cursor 通过 MCP 用到它**。

---

## 0. 先搞清楚这个 CLI 长啥样

一次 CLI 调用就是一次进程：

```
终端敲   boss cities
         │
         ▼
  Python 解释器
         │
         ▼
  src/boss_agent_cli/main.py 的 cli() 函数
         │
         ▼
  Click 匹配到 "cities" 子命令
         │
         ▼
  src/boss_agent_cli/commands/cities.py 的 cities_cmd() 执行
         │
         ▼
  stdout 打出一段 JSON（信封契约）
  stderr 打日志（受 --log-level 控制）
  exit code 0=成功 / 1=失败
```

**记住三件事**：
1. **入口**是 `pyproject.toml` 里的 `[project.scripts]`：`boss = "boss_agent_cli.main:cli"`。装完包，系统里就多了个 `boss` 命令，指向 `main.py:cli`。
2. **框架**是 [Click](https://click.palletsprojects.com/)——用装饰器 `@click.command`、`@click.option` 声明命令和参数。
3. **输出契约**：命令的 `stdout` **只能** 是一段 JSON（叫「信封」），别的日志走 `stderr`。这样 AI Agent 可以 100% 可靠地解析。

---

## 1. 环境准备

### 装 uv

`uv` 是 Python 版的 npm/cargo，比 pip 快、能管虚拟环境。

```bash
# Windows PowerShell
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

装完敲 `uv --version` 有输出就 OK。

### 装项目依赖（editable 模式）

```bash
cd d:/Users/jingboma/proj/boss-agent-cli

# 一条命令搞定：核心 + dev + bridge + mcp + crawl，全塞进本地 .venv
uv sync --all-extras

# 浏览器自动化二进制（登录、搜索兜底会用到 Chromium）
uv run patchright install chromium

# 可选：提交前自动跑 ruff/mypy 的 git hook
uv run pre-commit install
```

**editable 模式**意思是：`.venv` 里的 `boss` 命令**直接指向** `src/boss_agent_cli/` 里的源码。你改代码，下次 `uv run boss ...` 立刻生效，**不用重装**。

### 验证跑得起来

```bash
uv run boss --help              # 应该看到几十个子命令
uv run boss cities              # 输出一大段 JSON，列出所有城市
uv run boss schema | head -30   # 命令能力清单
uv run pytest tests/ -q         # 跑全套测试，几十秒
```

---

## 2. 项目结构速览（只讲你会用到的）

```
boss-agent-cli/
├── pyproject.toml          # 项目定义、依赖、入口脚本、ruff/mypy 配置
├── src/boss_agent_cli/
│   ├── main.py             # CLI 根：@click.group("boss") + 全局选项
│   ├── output.py           # emit_success / emit_error / redact_sensitive
│   ├── config.py           # 读 ~/.boss-agent/config.json
│   ├── hooks.py            # 事件总线（可选）
│   ├── platforms/          # 平台适配层（zhipin / zhilian / qiancheng）
│   ├── api/                # HTTP 客户端 + 端点定义
│   ├── auth/               # 登录态、cookie 提取、加密存储
│   ├── automation/         # 浏览器自动化 + 打招呼决策
│   ├── ai/                 # AI 分析（jd/fit/polish）+ 本地模型
│   ├── cache/              # SQLite 缓存
│   ├── crawler/            # Research 模式采集
│   ├── mcp_server.py       # MCP 服务器（暴露工具给 Agent）
│   ├── mcp_tools.py        # MCP 工具定义（TOOLS 列表）
│   └── commands/           # 👈 你 90% 时间在这里加东西
│       ├── register.py     # 把命令挂到 cli 上
│       ├── schema.py       # 命令能力清单（SCHEMA_DATA）
│       ├── cities.py       # 最简单的示例：无参、只读、本地数据
│       ├── search.py       # 复杂点：调 API + 缓存 + AI 提示
│       └── ...
├── tests/                  # pytest，1600+ 用例
├── docs/                   # 文档（中英双语 + ADR）
├── evals/                  # Agent 场景评测
└── ~/.boss-agent/          # 运行时数据：登录态、缓存、配置（不在仓库里）
```

**你要改的文件**通常就是 `src/boss_agent_cli/commands/` + `tests/` + `schema.py`。

---

## 3. 读一个最简单的命令：`cities`

先把最小的例子看透，剩下都是它的升级版。

### 代码本体：[src/boss_agent_cli/commands/cities.py](src/boss_agent_cli/commands/cities.py)

```python
import click

from boss_agent_cli.api.endpoints import CITY_CODES
from boss_agent_cli.display import handle_output, render_string_grid


@click.command("cities")                 # ← 声明这是一个 Click 命令，名字叫 "cities"
@click.pass_context                      # ← 把全局 ctx 传进来（含 data_dir、logger 等）
def cities_cmd(ctx: click.Context) -> None:
    """列出所有支持的城市"""              # ← 这行 docstring 会作为 --help 显示
    cities = sorted(CITY_CODES.keys())
    handle_output(
        ctx, "cities", {
            "count": len(cities),
            "cities": cities,
        },
        render=lambda d: render_string_grid(d["cities"], "cities"),  # 人类看的表格
        hints={                          # ← 给 Agent 的下一步建议
            "next_actions": [
                "boss search <query> --city <城市名> — 搜索指定城市的职位",
            ],
        },
    )
```

**看点**：
- `@click.command("cities")` — 声明命令。
- `ctx` — 全局上下文，`main.py` 里塞进去的 `data_dir`、`logger`、`platform`、`config` 都在里面。
- `handle_output` — 智能输出：`--json` 时打 JSON 信封，否则打人类友好的表格。**你不要自己 `print()`**，永远走 `handle_output` / `emit_success` / `emit_error`。
- `hints.next_actions` — Agent 拿到结果后知道"下一步能干嘛"。

### 注册：[src/boss_agent_cli/commands/register.py](src/boss_agent_cli/commands/register.py)

```python
from boss_agent_cli.commands import ..., cities, ...

def register_candidate_commands(cli: click.Group) -> None:
    ...
    cli.add_command(cities.cities_cmd, "cities")   # 👈 挂到根 group 上
    ...
```

### 能力清单：[src/boss_agent_cli/commands/schema.py](src/boss_agent_cli/commands/schema.py)

```python
"cities": {
    "description": "列出所有支持的城市",
    "args": [],
    "options": {},
},
```

`schema` 是"给 Agent 看的说明书"，`boss schema` 会把它导成 OpenAI Tools / Anthropic Tools 格式。

**三处联动**：命令代码 → register → schema，缺一个都不完整。

---

## 4. 从零加一个自己的命令：`hello`

目标：加一个 `boss hello <name> --loud` 命令，返回一句问候。**跟着敲一遍，10 分钟能跑通**。

### Step 1：写命令代码

新建 `src/boss_agent_cli/commands/hello.py`：

```python
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
        render=lambda d: click.echo(d["greeting"]),         # 人类模式打字符串到 stdout
        hints={
            "next_actions": [
                "boss hello <name> --loud — 大声打招呼",
            ],
        },
    )
```

**Click 常用装饰器**：
| 装饰器 | 作用 | 示例 |
|---|---|---|
| `@click.command("name")` | 声明命令 | `boss name` |
| `@click.group("g")` | 命令组（有子命令） | `boss g sub` |
| `@click.argument("x")` | 必填位置参数 | `boss cmd VALUE` |
| `@click.option("--x")` | 可选参数 | `boss cmd --x=1` |
| `@click.option("--x/--no-x")` | 布尔开关 | `--x` 或 `--no-x` |
| `@click.pass_context` | 拿到全局 ctx | 几乎每个命令都要 |

### Step 2：注册到 CLI

编辑 [src/boss_agent_cli/commands/register.py](src/boss_agent_cli/commands/register.py)：

```python
from boss_agent_cli.commands import (
    ...,
    hello,      # 👈 加这行（按字母序）
    ...,
)

def register_candidate_commands(cli: click.Group) -> None:
    ...
    cli.add_command(hello.hello_cmd, "hello")       # 👈 加这行
    ...
```

### Step 3：登记到 schema

编辑 [src/boss_agent_cli/commands/schema.py](src/boss_agent_cli/commands/schema.py)，在 `SCHEMA_DATA["commands"]` 里加一条（位置随意，找个相近的命令旁边即可）：

```python
"hello": {
    "description": "向指定的人打招呼（本地示例）",
    "args": [
        {"name": "name", "required": True, "description": "要打招呼的名字"},
    ],
    "options": {
        "--loud/--no-loud": {
            "type": "bool",
            "default": False,
            "description": "是否大声喊",
        },
    },
},
```

**同步顶层命令数**：`SCHEMA_DATA["description"]` 里那句「共 38 个顶层命令」要改成 39。测试硬断言了这个数字。

顺手把 [src/boss_agent_cli/commands/schema.py:64](src/boss_agent_cli/commands/schema.py#L64) 的 `_ROLE_BOTH_COMMANDS` 或 `_CANDIDATE_COMMANDS` 集合也加上 `"hello"`，否则可用性检查会漏。

### Step 4：立即验证

```bash
uv run boss hello world
# → Hello, world

uv run boss hello world --loud
# → HELLO, WORLD!!!

uv run boss --json hello world
# → {"ok":true,"schema_version":"1.0","command":"hello","data":{"name":"world","greeting":"Hello, world","loud":false},...}

uv run boss --help | grep hello
# → 应该能看到你的新命令

uv run boss schema --format openai-tools | grep -A5 hello
# → 应该能看到 hello 的 JSON Schema
```

### Step 5：写测试

新建 `tests/test_hello.py`：

```python
import json

from click.testing import CliRunner

from boss_agent_cli.main import cli


def test_hello_basic():
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "hello", "Alice"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["ok"] is True
    assert payload["data"]["greeting"] == "Hello, Alice"
    assert payload["data"]["loud"] is False


def test_hello_loud():
    runner = CliRunner()
    result = runner.invoke(cli, ["--json", "hello", "bob", "--loud"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["data"]["greeting"] == "HELLO, BOB!!!"
    assert payload["data"]["loud"] is True


def test_hello_missing_name_returns_error():
    runner = CliRunner()
    result = runner.invoke(cli, ["hello"])                  # 忘了给 name
    # Click 的 usage error 会走 BossCliGroup 的错误信封
    assert result.exit_code != 0
```

跑一下：

```bash
uv run pytest tests/test_hello.py -v
```

绿了就成了。

### Step 6：（可选）暴露给 MCP，让 Claude/Cursor 能调

如果这个命令对 AI Agent 有用，编辑 [src/boss_agent_cli/mcp_tools.py](src/boss_agent_cli/mcp_tools.py)，在 `TOOLS` 列表加一条工具定义，`_build_args` 加一个分支把 MCP 传来的 JSON 参数拼成 CLI argv。看 `boss_cities` 或 `boss_search` 是怎么写的，照抄。

---

## 5. 输出契约（**必须遵守**）

CLI 的所有 stdout 都要走**信封 JSON**，结构如下：

### 成功

```json
{
  "ok": true,
  "schema_version": "1.0",
  "command": "hello",
  "data": { "name": "world", "greeting": "Hello, world" },
  "pagination": null,
  "error": null,
  "hints": { "next_actions": ["..."] }
}
```

### 失败

```json
{
  "ok": false,
  "schema_version": "1.0",
  "command": "hello",
  "data": null,
  "pagination": null,
  "error": {
    "code": "INVALID_PARAM",
    "message": "name 不能为空",
    "recoverable": true,
    "recovery_action": "重新提供 name 参数"
  },
  "hints": null
}
```

### 三条铁律

1. **stdout 只放 JSON**——不要在命令里 `print("done")`，那会污染信封。日志走 `ctx.obj["logger"].info(...)`（打到 stderr）。
2. **exit code**：`ok=true` 时 exit 0；`ok=false` 时 exit 1（`emit_error` 会自动 exit 1）。
3. **别自己拼 JSON**——用 `boss_agent_cli.output` 里的 `emit_success` / `emit_error`，或封装好的 `handle_output`。它们会自动脱敏 token / cookie / password 等敏感字段。

### 错误码

用现有的错误码，看 [src/boss_agent_cli/commands/schema.py](src/boss_agent_cli/commands/schema.py) 里的 `SCHEMA_DATA["error_codes"]`。常见：

- `INVALID_PARAM` — 参数错
- `NOT_LOGGED_IN` — 未登录
- `AUTH_EXPIRED` — 登录态过期
- `RATE_LIMITED` — 被限流
- `PLATFORM_ERROR` — 上游 API 报错
- `COMPLIANCE_BLOCKED` — 合规拦截（打招呼等敏感动作）

---

## 6. 全局上下文 `ctx.obj` 里有啥

看 [src/boss_agent_cli/main.py](src/boss_agent_cli/main.py) 的 `cli()` 函数，全局选项都塞在 `ctx.obj` 里：

| Key | 类型 | 用途 |
|---|---|---|
| `data_dir` | `Path` | `~/.boss-agent`，所有本地数据都写这里 |
| `json_output` | `bool` | 是否强制 JSON 输出 |
| `delay` | `tuple[float, float]` | 请求间隔范围 |
| `log_level` | `str` | error / warning / info / debug |
| `logger` | `Logger` | 打日志到 stderr，用它别用 print |
| `cdp_url` | `str \| None` | Chrome CDP 地址 |
| `platform` | `str` | 当前平台（zhipin / zhilian / …） |
| `role` | `str` | candidate / recruiter |
| `config` | `dict` | 读进来的 config.json |
| `hooks` | `HookBus` | 事件总线 |

你的命令里几乎肯定要用 `ctx.obj["data_dir"]`（存东西）和 `ctx.obj["logger"]`（打日志）。

---

## 7. 常用工作流备忘

```bash
# 装依赖 / 更新依赖
uv sync --all-extras

# 跑命令（editable，改代码立刻生效）
uv run boss <cmd> [args]
uv run boss --json <cmd>        # 强制 JSON 输出
uv run boss --log-level debug <cmd>   # 看详细日志

# 测试
uv run pytest tests/ -q                       # 全跑
uv run pytest tests/test_hello.py -v          # 单文件
uv run pytest tests/test_hello.py::test_hello_basic -v   # 单用例
uv run pytest tests/ -k "hello"               # 按名字过滤

# 质量门禁（提交前必过）
uv run ruff check src/ tests/
uv run mypy src/boss_agent_cli
uv run pytest tests/ -q
uv run boss schema --format native > /dev/null   # 校验 schema 一致性

# 一键跑完
uv run ruff check src/ tests/ && uv run mypy src/boss_agent_cli && uv run pytest tests/ -q
```

---

## 8. 让「本机所有终端」用到你改的版本

前面 `uv run boss ...` 都是**在本仓库里**跑。如果你想在别的目录、别的项目里直接敲 `boss` 用到你改的代码：

```bash
# editable 全局安装
uv tool install --editable d:/Users/jingboma/proj/boss-agent-cli
```

装完，任何终端敲 `boss` 都走你的源码。改代码立刻生效。

要卸载：`uv tool uninstall boss-agent-cli`。

---

## 9. 让 Claude Desktop / Cursor 通过 MCP 用到你的新命令

前提：你的命令已经在 [src/boss_agent_cli/mcp_tools.py](src/boss_agent_cli/mcp_tools.py) 的 `TOOLS` 里注册好了（参考 Step 6）。

### Claude Desktop 配置

打开 Claude Desktop 的 `claude_desktop_config.json`（Windows 在 `%APPDATA%\Claude\`），加：

```json
{
  "mcpServers": {
    "boss-agent-cli-dev": {
      "command": "uv",
      "args": [
        "run",
        "--project", "d:/Users/jingboma/proj/boss-agent-cli",
        "boss-mcp"
      ]
    }
  }
}
```

重启 Claude Desktop，就能看到你的新工具。改代码 → 重启 Claude → 生效。

### Cursor 类似，参考

- [docs/integrations/claude-code.md](docs/integrations/claude-code.md)
- [docs/integrations/cursor.md](docs/integrations/cursor.md)
- [docs/integrations/windsurf.md](docs/integrations/windsurf.md)

---

## 10. 常见坑

| 现象 | 原因 | 修法 |
|---|---|---|
| `boss --help` 找不到你的命令 | 忘了 `register.py` 里挂 | 补 `cli.add_command(...)` |
| `boss schema` 里没你的命令 | 忘了 `schema.py` | 补 `SCHEMA_DATA["commands"]` |
| 测试 `test_agent_docs.py` 挂了 | 顶层命令数变了 | 改 `SCHEMA_DATA["description"]` 里的「共 N 个」 |
| stdout 里除了 JSON 还有别的 | 你在命令里 `print()` 了 | 改用 `ctx.obj["logger"].info(...)` |
| 输出 JSON 里 token/cookie 泄露 | 没走 `emit_success` | 别自己 `json.dumps`，用信封函数会自动脱敏 |
| `patchright` 报没浏览器 | 忘装 chromium | `uv run patchright install chromium` |
| `boss-mcp` 报 `ImportError: mcp` | 没装 mcp extra | `uv sync --all-extras` |
| pytest 提示找不到模块 | 没 editable install | `uv sync` 重装 |
| mypy 报一堆错 | 你新加的模块没纳入 strict 名单是正常的；已有模块必须零错误 | 只修你动过的文件 |

---

## 11. 学习路径推荐

1. **今天**：跟着 §4 加一个 `hello` 命令，跑通测试。
2. **明天**：读 [src/boss_agent_cli/commands/cities.py](src/boss_agent_cli/commands/cities.py)、[history.py](src/boss_agent_cli/commands/history.py)、[stats.py](src/boss_agent_cli/commands/stats.py)——这三个都是**纯本地、不调网络**的命令，最容易理解。
3. **本周**：读 [search.py](src/boss_agent_cli/commands/search.py) + [api/client.py](src/boss_agent_cli/api/client.py)，理解「命令 → API 客户端 → 缓存」链路。
4. **进阶**：读 [platforms/base.py](src/boss_agent_cli/platforms/base.py) 和 [zhipin.py](src/boss_agent_cli/platforms/zhipin.py)，理解多平台抽象；再读 [mcp_server.py](src/boss_agent_cli/mcp_server.py) 理解 MCP 怎么把 CLI 命令暴露给 Agent。
5. **提 PR**：读 [CONTRIBUTING.md](CONTRIBUTING.md) 的完整流程。

---

## 12. 一句话总结

**editable install + Click 命令 + JSON 信封 + 三处联动（代码 / register / schema） + pytest**——就是这个 CLI 的全部套路。看透 `cities.py` 就看透了 80%。剩下 20% 是网络 / 认证 / 缓存 / 合规 / MCP，需要就查对应模块的 `CLAUDE.md`。
