# boss-agent-cli 命令速查

面向本地开发/日常使用的完整命令清单。以本项目源码 + 真机实测为准,不引用旧版文档。

## 全局约定

### 通用调用形态

- 开发模式(项目目录内):`uv run boss <cmd> [args...]`
- 已激活 venv 或全局安装:`boss <cmd> [args...]`
- MCP 入口:`boss-mcp`(供 Claude/Cursor 等外部 Agent 连接)

### 全局选项(位置:`boss` 和 `<cmd>` 之间)

| 选项 | 默认 | 说明 |
|---|---|---|
| `--data-dir PATH` | `~/.boss-agent` | 登录态、配置、缓存的存储目录 |
| `--delay LOW-HIGH` | 由 config 决定 | 请求间隔范围,如 `1.5-3.0` |
| `--cdp-url URL` | 无 | 复用本地 Chrome CDP(如 `http://localhost:9222`) |
| `--platform NAME` | `zhipin` | 平台适配器,可选值见 `boss platforms` |
| `--role {candidate,recruiter}` | `candidate` | 求职者 / 招聘者角色 |
| `--log-level {error,warning,info,debug}` | `error` | stderr 日志级别 |
| `--json / --no-json` | 自动 | 强制 JSON 输出;管道下自动开启 |

### 输出协议

- **stdout**:所有命令统一封套 `{ok, schema_version, command, data, pagination, error, hints}`
- **stderr**:Logger 打印,受 `--log-level` 控制
- **退出码**:成功 `0`,任何 error 均 `1`
- **敏感字段**自动脱敏:含 `token / cookie / password / stoken / api_key / session` 的字段直接替换为 `[REDACTED]`

### 合规模式(compliance)

`operating_mode` 有两档:

- `assisted`(默认):拦截"平台写入 / 候选人筛选 / 简历外呼"等敏感命令,报 `COMPLIANCE_BLOCKED`
- `research`:全部放行,需**显式**切换 `boss config set operating_mode research`

被默认拦截的命令(节选):`greet`、`batch-greet`、`apply`、`exchange`、`pipeline`、`hr candidates`、`hr resume`、`hr request-resume`、`chatmsg --raw` 等。

## 招聘者(HR)命令

### 🎯 拉人核心三条命令(状态管理 & 落库入口)

这三条是**候选人数据的唯一入口**——所有后续状态管理(已看/已招呼/已面试/淘汰)、本地落库、CRM 都从这里进。**先看完这节再看下面细节。**

#### 一、三个源的定位

| 源 | 命令 | BOSS 侧入口 | 语义 |
|---|---|---|---|
| **搜索牛人** | `boss hr candidates --job-id $JOB` | 左栏"搜索牛人" | HR 主动按岗位/关键词匹配的**全库候选人** |
| **推荐牛人** | `boss hr recommend --job-id $JOB` | 左栏"推荐牛人" | 平台按**该岗位**算法**主动推**的当日候选人 |
| **沟通中** | `boss hr chat --label-id 0` | 左栏"沟通中" | 我(HR)与候选人**已经产生会话**的关系流 |

⚠️ `hr chat` 不带 `--job-id`——加上会退化到骨架版丢 name;想按岗位过滤在响应里 `jq 'select(.encJobId == $JOB)'`。

⚠️ 三条都不加 `--page` = `--page 1` = **只拿首屏**。全量翻页脚本见文末补充章节。

#### 二、三份响应的顶层信封(统一,来自 BOSS wapi)

```jsonc
{
  "code": 0,                    // 0=成功;9=限流;36=风控;37=登录过期
  "message": "Success",
  "zpData": { ... }             // CLI 层 unwrap 后即 data 字段
}
```

CLI 输出:
```jsonc
{
  "ok": true,
  "command": "recruiter-<candidates|recommend|chat>",
  "data": { ... },              // 就是上面的 zpData
  "hints": { "next_actions": [...] }
}
```

#### 三、三份响应对照(落库关键字段)

##### 3.1 `hr candidates` — 搜索牛人

**顶层 `data` 结构**:

| 字段 | 类型 | 用途 |
|---|---|---|
| `geeks` | `[]` | **候选人数组(核心)** |
| `totalCount` | int | 匹配总数(硬顶 ~400) |
| `hasMore` | bool | 是否有下一页 |
| `page / startIndex` | int | 分页游标 |
| `filters / segs` | obj | BOSS 侧筛选下拉数据(可忽略) |

**`geeks[i]` 顶层** → 主结构在 `geekCard` 下,`geeks[i]` 本身只是壳。

**`geeks[i].geekCard` 核心字段**(近 100 项,只列**落库必留**的):

| 字段 | 类型 | 落库用途 |
|---|---|---|
| `encryptGeekId` ⭐ | str | **主键**(候选人唯一 id,后续 resume/greet/exchange 必带) |
| `securityId` ⭐ | str | **动态 token**,后续调用必带,一次一变(不落库,每次拉最新的) |
| `encryptJobId` ⭐ | str | 匹配到的岗位 id(可能 ≠ 你传入的 job-id,BOSS 会给你别的岗位) |
| `lid` | str | 搜索埋点 id(建议落库,做溯源) |
| `name` | str | 姓名(已脱敏,如 `李**`) |
| `city / cityName` | int/str | 所在城市 |
| `ageDesc` | str | 年龄描述,如 `28岁` |
| `workYear` | str | 工作年限,如 `5年` |
| `highestDegreeName` | str | 学历,如 `本科` |
| `eduSchool / eduMajor` | str | 学校 / 专业 |
| `salary / lowSalary / highSalary` | str/int | 期望薪资 |
| `expect / current` | obj | 结构化期望 & 当前工作 |
| `geekDesc / geekEdu / geekWork` | obj/[] | 自我介绍 / 教育 / 工作历史 |
| `contacting / viewed / contact / favor` | bool | **状态字段**(沟通中/已看/已联系/已收藏) |

##### 3.2 `hr recommend` — 推荐牛人

**顶层 `data` 结构**:

| 字段 | 类型 | 用途 |
|---|---|---|
| `geekList` | `[]` | **候选人数组(注意:是 `geekList` 不是 `geeks`)** |
| `hasMore` | bool | 是否有下一页(**无 `totalCount`**) |
| `cityCode / jobExperience` | int | 岗位所在地/年限要求 |
| `displayTraineeStyle / heightGray / advantageShow / displayAboard` | int/bool | UI 标记位(可忽略) |
| `recDividerInfo / emptyListText` | any | 空/分隔提示(可忽略) |

**`geekList[i]` 顶层**(比 candidates 多一层):

| 字段 | 类型 | 落库用途 |
|---|---|---|
| `encryptGeekId` | str | 候选人主键(**同 candidates**) |
| `isFriend` | int | 是否已建立会话关系(0=否,1=是) |
| `cooperate` | int | 合作状态 |
| `blur` | int | 是否被平台模糊处理(1=模糊,需付费/权限) |
| `geekCard` ⭐ | obj | **档案主体,字段结构同下** |
| `geekLastWork` | obj | 最近一份工作(便于列表快速展示) |
| `showEdus[] / showWorks[]` | [] | 精简版教育 / 工作历史 |

**`geekList[i].geekCard` 核心字段**(和 candidates 的 `geekCard` **不完全同名**,注意区分):

| 字段 | 类型 | 落库用途 |
|---|---|---|
| `encGeekId` / `encryptGeekId` ⭐ | str | 主键 |
| `securityId` ⭐ | str | 动态 token |
| `encryptJobId` ⭐ | str | 该次推荐关联的岗位 id |
| `lid` | str | 推荐链路埋点 |
| `geekName` ⭐ | str | **姓名(未脱敏!如 "何雨洁"——比 candidates 敏感度高)** |
| `geekAvatar` | str | 头像 URL |
| `geekGender` | int | 性别 0=保密 1=男 2=女 |
| `ageDesc / birthday` | str | 年龄 |
| `geekWorkYear` | str | 工龄描述,如 `27年应届生` |
| `geekDegree` | str | 学历 |
| `freshGraduate` | int | 应届标记 |
| `salary / lowSalary / highSalary` | str/int | 期望薪资 |
| `expectPositionName / expectLocationName` | str | 期望职位 / 地点 |
| `geekDesc.content` | str | 自我介绍 |
| `middleContent.content` | str | 一句话高亮(如 `xx公司·测试开发实习生`) |
| `geekEdu / geekEdus[] / geekWorks[]` | obj/[] | 结构化档案 |
| `matches[] / hlmatches[] / markWords[]` | [] | **匹配到的技能标签**(推荐算法核心信号) |
| `rcdBizType / recallStgTag` | str | 推荐算法链路 tag,如 `f1_brcd` / `2towers-s1f-13k`(**建议落库,做召回策略分析**) |
| `viewed` | bool | 是否已看 |
| `chatButtonFlag / recOnline` | any | 沟通按钮状态 / 在线状态 |

##### 3.3 `hr chat --label-id 0` — 沟通中

**顶层 `data` 结构**(⚠️ label-id 0 独占字段最多,换 label 结构会变):

| 字段 | 类型 | 用途 |
|---|---|---|
| `result` | `[]` | **会话数组(核心)** |
| `filterEncryptIdList / filterGeekIdList` | [] | **仅 label 0 下发**——BOSS 侧筛选辅助 id 列表 |
| `hasMore` | bool | 是否有下一页 |

**`result[i]` 字段**(11 项,含姓名):

| 字段 | 类型 | 落库用途 |
|---|---|---|
| `friendId` ⭐ | int | **会话主键**(数字 id,和 encryptGeekId 不同——`friend_id` 是关系 id,`geekId` 是候选人 id) |
| `encryptFriendId` | str | 加密版 friendId |
| `name` ⭐ | str | **候选人姓名**(此列表**唯一含 name 的入口**,珍惜) |
| `friendSource` | int | 关系来源,如 1=候选人打招呼来,2=HR 主动 |
| `encJobId` ⭐ | str | 关联岗位 id(**用于本地按岗位过滤**) |
| `jobName` | str | 岗位名 |
| `lastMsgContent / lastMsgTime` | str/int | 最后一条消息 / 时间戳 |
| `unread` | int | 未读数 |
| `msg_status` | int | 消息状态 |
| `avatar` | str | 头像 |
| `label` | int | 会话标签(0/1/2/3/4/5) |

#### 四、"同一个人在三个源"的 id 拼接关系

```
                        encryptGeekId(候选人主键,跨源统一)
                              ▲
              ┌───────────────┼───────────────┐
              │               │               │
     ┌────────┴──────┐ ┌──────┴─────┐ ┌───────┴────────┐
     │  candidates    │ │  recommend │ │  chat          │
     │                │ │            │ │                │
     │  geeks[].      │ │ geekList[].│ │ result[]:      │
     │   geekCard.    │ │  geekCard. │ │  friendId(数字)│
     │   encryptGeekId│ │  encGeekId │ │  encryptFriendId│
     │                │ │  =         │ │  ↓ 需二次查询   │
     │                │ │  encryptGeekId│ │ friend_detail  │
     │                │ │            │ │  才能对齐        │
     └────────────────┘ └────────────┘ └────────────────┘
```

**落库建议**:
- **候选人表主键**:`encryptGeekId`
- **岗位关联表**:`encryptGeekId × encryptJobId`(一人可能匹配多岗)
- **会话表**:`friendId`(数字) + `encryptFriendId` + `encryptGeekId`(通过 `friend_detail` 端点补全映射)
- **状态字段**:每次拉取后更新 `contacting / viewed / favor / isFriend`
- **`securityId` 不落库**——动态 token,每次调 resume/exchange 前重新拉一次 candidates/recommend 拿最新的

#### 五、三份响应各自缺什么(避坑)

| 缺失 | 补法 |
|---|---|
| `candidates` 有 `name`(脱敏) 但不含 `friendId` | 想发消息要么先 `hr chat` 拿 friendId 映射,要么用 `encryptGeekId + securityId` 走 greet 链路 |
| `recommend` 有 `geekName`(未脱敏) 但不含 `friendId` | 同上 |
| `chat --label-id 0` 有 `friendId + name` 但**无 `encryptGeekId`** | 打 `friend_detail`(`POST /wapi/zprelation/friend/getBossFriendListV2.json`)传 friendIds 批量补 |

#### 六、直接可跑的三条命令

前置:
```bash
boss --role recruiter login                           # 未登录先来一发
boss --role recruiter hr jobs list                    # 拿 encryptJobId
boss config set operating_mode research               # recommend 挂了合规拦截
JOB=<上面拿到的 encryptId>
```

拉:
```bash
boss --role recruiter hr candidates --job-id $JOB > candidates.json
boss --role recruiter hr recommend  --job-id $JOB > recommend.json
boss --role recruiter hr chat       --label-id 0  > chat.json
```

看关键字段:
```bash
jq '.data.geeks[] | {gid: .geekCard.encryptGeekId, name: .geekCard.name, job: .geekCard.encryptJobId, sid: .geekCard.securityId}' candidates.json
jq '.data.geekList[] | {gid: .encryptGeekId, name: .geekCard.geekName, job: .geekCard.encryptJobId, sid: .geekCard.securityId, tag: .geekCard.recallStgTag}' recommend.json
jq --arg j "$JOB" '.data.result[] | select(.encJobId == $j) | {fid: .friendId, name, job: .encJobId, unread}' chat.json
```

#### 七、补充:全量翻页(参考,不建议高频跑)

```bash
拉全部() {
  local cmd=$1 job=$2 out=$3 arr_key=$4 extra_filter=$5
  local page=1; > "$out"
  while :; do
    local args=("hr" "$cmd")
    [ -n "$job" ] && args+=("--job-id" "$job")
    [ "$cmd" = "chat" ] && args+=("--label-id" "0")
    args+=("--page" "$page")
    resp=$(boss --role recruiter "${args[@]}")
    echo "$resp" | jq -c ".data.$arr_key[]? $extra_filter" >> "$out"
    [ "$(echo "$resp" | jq -r '.data.hasMore // false')" = "true" ] || break
    ((page++)); sleep 2
  done
  echo "$cmd → $(wc -l < "$out") 条"
}

拉全部 candidates "$JOB" candidates.jsonl geeks ""
拉全部 recommend  "$JOB" recommend.jsonl  geekList ""
拉全部 chat       ""     chat.jsonl       result "| select(.encJobId == \"$JOB\")"
```

⚠️ 每页 sleep 2s,不然会触发 `code:9` (RATE_LIMITED) / `code:36` (ACCOUNT_RISK)。

---

### `boss hr chat` — 查看沟通列表【已完整实测】

拿"我(招聘者)与候选人"的沟通/招呼列表。**是拿候选人姓名的唯一可靠入口**。

```
Usage: boss hr chat [OPTIONS]

Options:
  --page INTEGER       页码(默认 1)
  --job-id TEXT        按职位筛选
  --label-id INTEGER   按标签筛选(默认 0)
```

CLI 端所有 `label-id` 都打同一个端点 `POST /wapi/zprelation/friend/filterByLabel`,只改 body 里的 `labelId`。**响应结构由 BOSS 服务端根据 label 值决定**——这是实测的差异表(同一账号、`page=1`):

| 命令 | 顶层键 | 记录字段 | 是否含 `name` |
|---|---|---|---|
| `hr chat`(等价 `--label-id 0`) | `filterEncryptIdList, filterGeekIdList, result` | 11 项,含 `name` | ✅ 是 |
| `hr chat --label-id 0` | 同上 | 同上 | ✅ 是 |
| `hr chat --label-id 1` | `lastWeekGreetingNum, result` | 10 项,**无 `name`** | ❌ 否 |
| `hr chat --label-id 2` | `result` | 10 项,无 `name` | ❌ 否 |
| `hr chat --label-id 3` | `result` | 空 | — |
| `hr chat --label-id 4` | `result` | 10 项,无 `name` | ❌ 否 |
| `hr chat --label-id 5` | `result` | 空 | — |

结论:

- **想拿到候选人姓名 → 只能用 `boss hr chat`(不加 `--label-id`)。**
- 其它 label 只有 id/时间/状态骨架;要补姓名必须再打一次 [`friend_detail`](../src/boss_agent_cli/api/recruiter_client.py#L332)。
- `label-id 0` 独占的附加字段 `filterEncryptIdList / filterGeekIdList` 是 BOSS 侧筛选辅助数据,只在"全部"视图下发。
- `--job-id` 会附加到 body(`encJobId`)——响应字段结构不受它影响,仍取决于 `label-id`。

### `boss hr chatmsg <friend_id>` — 单人聊天历史

```
Usage: boss hr chatmsg [OPTIONS] FRIEND_ID
Options:
  --count INTEGER        消息条数(默认 20)
  --max-msg-id INTEGER   向前翻页游标
```

打 `GET /wapi/zpchat/boss/historyMsg`,响应**只含消息数据,不含档案**。想要姓名先从 `hr chat` 拿到 `friendId` 与 `name` 的映射再交叉。

### `boss hr last-messages` — 批量最近消息摘要

```
Usage: boss hr last-messages [OPTIONS]
Options:
  --page INTEGER      沟通列表页码(用于自动拉取 friend_ids)
  --job-id TEXT       按职位筛选
  --label-id INTEGER  按标签筛选(默认 0)
  --friend-id INT     指定 friend_id,可重复传多次
```

若不传 `--friend-id`,内部先跑一次 `friend_list` 拉出 id 再打 `POST /wapi/zpchat/boss/userLastMsg`。返回的每条只有 `friendId / unread / msg_status / last_msg / last_time`——**没有姓名**。

### `boss hr candidates [query]` — 搜索候选人(BOSS 产品语境:**搜索牛人**)【已实测】

对应 BOSS 招聘者端左侧栏"**搜索牛人**"入口。别把它和"推荐牛人"混——推荐牛人走 `hr recommend`,端点不同。

```
Usage: boss hr candidates [OPTIONS] [QUERY]

Options:
  --city TEXT          cityCode(101020100=上海;-2=全国)
  --job-id TEXT        按职位筛选
  --experience TEXT    经验,如 -3,-3(应届)/ -1,-1(不限)
  --degree TEXT        学历,如 201,201 / -1,-1
  --age TEXT           年龄范围,如 25,35
  --school-level TEXT  学校层次,如 1101
  --activeness TEXT    活跃度
  --source TEXT        来源(默认 4)
  --salary TEXT        薪资,如 -1,3
  --select             带 select=true
  --page INTEGER       页码,每页 15 条
```

- 端点:`GET /wapi/zpitem/web/boss/search/geeks.json`
- `data` 顶层 29 项,核心:`geeks[] / totalCount / page / startIndex / hasMore / filters / segs`
- `geeks[i].geekCard` 才是候选人档案(近 100 字段)
- 单页固定 15 条;`totalCount` 通常上限 400(BOSS 侧硬顶)
- 空查询 `hr candidates` 也返回列表(BOSS 默认推荐);无效关键词返回 `totalCount:0, geeks:[]` 不报错

**`geekCard` 关键字段速查**:

| 字段 | 用途 |
|---|---|
| `name` | 姓名(BOSS 已脱敏,如 `李**`) |
| `encryptGeekId` | 后续 `resume/greet/exchange` 的目标 id |
| `securityId` | `resume/greet/exchange` 必带 |
| `encryptJobId` | 匹配的职位 id |
| `lid` | 搜索链路埋点 |
| `city / ageDesc / workYear / highestDegreeName / eduSchool / eduMajor / salary` | 基础档案 |
| `expect / current / geekDesc / geekEdu / geekWork` | 结构化历史 |
| `contacting / viewed / contact / favor` | 沟通/已看/联系/收藏状态 |

⚠️ **当前版本实测未被 assisted 拦截**——`ok:true` 直接返回真实数据。历史记忆里"hr candidates 属于合规敏感命令"的说法在当前代码上不成立,需要复核。

### `boss hr recommend --job-id <id>` — 每日推荐牛人【已抓包实证】

对应 BOSS 招聘者端"**推荐牛人**"(`/web/frame/recommend/`)入口。跟 `hr candidates` 区别是:这个是**平台按职位算法主动推**的,不是 HR 搜关键词得来的;拿不到就先切一个有推荐流量的活跃职位。

```
Usage: boss hr recommend [OPTIONS]

Options:
  --job-id TEXT                        职位 encryptJobId(必填,先用 `hr jobs list` 拿)
  --page INTEGER                       页码,默认 1
  --age TEXT                           年龄范围,默认 "16,-1"(不限)
  --activation TEXT                    活跃度,默认 "0"
  --school TEXT                        学校层次,默认 "0"
  --gender TEXT                        性别,默认 "0"
  --recent-not-view TEXT               仅未看过,默认 "0"
  --exchange-resume-with-colleague TEXT 与同事换过简历,默认 "0"
  --major TEXT                         专业,默认 "0"
  --keyword1 TEXT                      关键词,默认 "-1"
  --switch-job-frequency TEXT          跳槽频率,默认 "0"
  --degree TEXT                        学历,默认 "0"
  --experience TEXT                    经验,默认 "0"
  --intention TEXT                     求职意向,默认 "0"
  --salary TEXT                        薪资,默认 "0"
  --cover-screen-memory TEXT           翻页记忆,默认 "0"
  --card-type TEXT                     卡片类型,默认 "0"
```

- 端点:`GET /wapi/zpjob/rec/geek/list`(注意是 `zpjob`,不是 `zpitem`)
- Referer 必须带对应 jobid,客户端已自动拼
- `data` 顶层:`geekList[] / hasMore / cityCode / heightGray / advantageShow / displayAboard / displayTraineeStyle / jobExperience / recDividerInfo / emptyListText`(**无 `totalCount`**,靠 `hasMore` 翻页)
- 单条 `geekList[i]` 结构和 `hr candidates` **不完全同构**——真正档案在 `geekCard` 下面

**`geekList[i]` 顶层**:`encryptGeekId / isFriend / blur / cooperate / geekLastWork / showEdus / showWorks / geekCard`

**`geekCard` 核心字段**:

| 字段 | 用途 |
|---|---|
| `geekName` | 姓名(**未脱敏**,如 "何雨洁") |
| `encGeekId` / `encryptGeekId` | 后续 `resume/greet/exchange` 目标 id |
| `securityId` | 后续调用必带(动态,一次一变) |
| `encryptJobId` | 匹配职位 id |
| `lid` | 推荐链路埋点(必带) |
| `expectPositionName / expectLocationName / salary` | 求职意向 |
| `ageDesc / geekGender / geekWorkYear / geekDegree` | 基础档案 |
| `geekDesc.content / middleContent.content` | 一句话简介 / 显眼工作经历 |
| `geekEdu / geekEdus[] / geekWorks[]` | 教育与工作历史 |
| `matches[] / hlmatches[] / markWords[]` | 匹配的技能标签 |
| `rcdBizType / recallStgTag` | 推荐算法链路 tag(如 f1_brcd / 2towers-s1f-13k) |
| `viewed / cooperate` | 已看/合作状态 |

⚠️ **敏感度提醒**:`geekName`(全名)、`geekAvatar`、完整 `geekWorks[].responsibility` 都是**未脱敏原文**——比 `hr candidates` 的 `李**` 强得多。写入档案/导出前建议按 `redact_sensitive` 二次过滤。

⚠️ **合规**:命令挂了 `require_compliance_allowed("recruiter-recommend")`,默认 assisted 模式**会拦**。需要 `boss config set operating_mode research` 才能跑。

### HR 候选人来源速查(区分入口)

BOSS 招聘者端一共 4 种候选人来源,别混:

| BOSS 侧入口 | 语义 | CLI 命令 |
|---|---|---|
| **搜索牛人**(左栏顶部) | HR 主动按关键词/筛选查 | `hr candidates` |
| **推荐牛人** / 每日推荐 | 平台按职位智能推 | `hr recommend --job-id <id>` |
| **打招呼列表**(新招呼) | 候选人主动打招呼过来 | `hr chat --label-id 1` |
| **沟通中列表** | 双向发过消息的会话 | `hr chat`(默认 label=0) |

### 其它 HR 子命令

| 命令 | 说明 | 默认 `assisted` 模式 |
|---|---|---|
| `hr jobs` | 管理职位发布(列表/上线/下线) | ✅ 放行 |
| `hr applications` | 查看候选人投递申请列表 | ✅ 放行 |
| `hr reply <friend_id> <message>` | 回复候选人 | ⚠️ 部分子操作受限 |
| `hr resume <geek_id> --job-id <id> --security-id <id>` | 查看简历 | ❌ 拦截 |
| `hr request-resume <friend_id>` | 请求候选人分享附件简历(issue #217) | ❌ 拦截 |

跑被拦的命令时会返回 `COMPLIANCE_BLOCKED` + `required_mode: research`;要用需先 `boss config set operating_mode research`。

## 求职者(candidate)命令

按用途分组。以 `boss <cmd> --help` 为准,下面只标注**必填参数**和**核心用途**;可选参数请用 `--help` 查看。

### 会话 / 消息

| 命令 | 必填 | 用途 |
|---|---|---|
| `chat` | — | 查看我(候选人)的沟通列表,支持按发起方/时间筛选,支持导出 HTML/MD/CSV/JSON |
| `chatmsg <security_id>` | ✓ | 查看与某招聘者的聊天历史 |
| `chat-summary <security_id>` | ✓ | 生成会话摘要 |
| `mark <security_id>` | ✓ | 给联系人打/去标签 |

### 职位发现

| 命令 | 必填 | 用途 |
|---|---|---|
| `search [query]` | — | 关键词 + 筛选搜索职位 |
| `recommend` | — | 基于简历的个性化推荐 |
| `show <index>` | ✓ | 按上次搜索结果编号看详情(如 `boss show 3`) |
| `detail <security_id>` | ✓ | 直接按 `security_id` 看完整详情 |
| `history` | — | 最近浏览过的职位 |
| `favorites list / sync` | — | BOSS 收藏 → 本地 shortlist |
| `preset ...` | — | 管理可复用搜索预设 |
| `watch ...` | — | 保存搜索条件 + 增量监控 |
| `export [query]` | — | 搜索结果导出为 CSV / JSON |

### 主动操作(默认 `assisted` 拦截)

| 命令 | 必填 | 用途 |
|---|---|---|
| `greet <security_id> <job_id>` | ✓ | 向某招聘者打招呼 |
| `batch-greet <query>` | ✓ | 搜索后批量打招呼(硬上限 10) |
| `apply <security_id> <job_id>` | ✓ | 立即沟通/投递(当前复用立即沟通链路) |
| `exchange <security_id>` | ✓ | 请求交换联系方式(手机号/微信) |
| `pipeline` | — | 平台数据聚合流水线 |

### 简历 / 个人数据

| 命令 | 用途 |
|---|---|
| `me` | 当前登录用户的个人信息 / 简历 / 求职期望 / 投递记录 |
| `resume ...` | 本地简历管理(子命令用 `boss resume --help`) |
| `ai ...` | AI 简历优化(子命令用 `boss ai --help`) |
| `interviews` | 面试邀请列表 |
| `stats` | 投递转化漏斗统计(只读聚合) |
| `shortlist ...` | 本地候选池管理 |
| `follow-up` | 跟进提醒 |
| `digest` | 汇总摘要 |

### 环境 / 会话管理

| 命令 | 用途 |
|---|---|
| `login` | 登录当前平台(Cookie / CDP / 浏览器降级链路) |
| `logout` | 清除本地登录态 |
| `status` | 检查当前登录态 |
| `doctor` | 诊断环境 / 依赖 / 登录条件 |
| `platforms` | 列出已注册平台与能力状态 |
| `cities` | 支持的城市列表 |
| `config [get/set/list]` | 读写配置(`operating_mode` 也在这里改) |
| `clean` | 清理过期缓存 / 临时文件 |
| `schema` | 返回工具完整能力描述的 JSON(供外部 Agent 消费) |
| `hello <name>` | 本地示例命令,验证 CLI 通不通 |

### 高阶入口(自身是命令组)

以下都是 `group`,要跟子命令。用 `boss <group> --help` 展开。

- `agent` — 招聘自动化编排入口
- `crawl` — DrissionPage 可恢复批量采集
- `favorites` — 收藏同步
- `preset` — 搜索预设
- `resume` — 本地简历管理
- `shortlist` — 候选池
- `watch` — 增量监控
- `ai` — AI 简历优化
- `config` — 配置读写
- `hr` — 招聘者模式(见上一章)

## 补充计划

以下条目**未在本文中细化**,后续按需要补:

- `hr chat` 之外 HR 子命令的实测参数矩阵
- 各 candidate 命令的完整选项 + JSON 响应字段
- 合规拦截命令切到 `research` 后的实测输出结构
- MCP 工具透传后各 tool 的入参对照

有需要时告诉我要补哪个,我按小块加进来即可。
