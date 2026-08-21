# tboss-cli HR 端命令速查

只覆盖招聘者(HR)一侧。tboss-cli 是基于上游 `boss-agent-cli` 的 fork(https://github.com/NeverlandzZ1/tboss-cli.git),命令入口仍然是 `boss`,主要在 HR 侧新增/修复了 `hr accept-resume` / `hr chat-start` / `hr friend-detail` / `hr request-resume` 等命令,其余命令与上游保持一致。

三层结构:

- **第一层**:常用命令 + 已确定的入参形态,复制即用
- **第二层**:全部 HR 命令的完整参数 + 响应关键字段
- **第三层**:任何人第一次用都得走一遍的环境准备命令(含安装)

所有 HR 命令都必须加 `--role recruiter`(或在 config 里默认设招聘者)。

---

## 第一层 · 常用命令(参数形态已确定)

```bash
# 职位列表 → 拿 encryptJobId
boss --role recruiter hr jobs list

# 沟通中(拿 friendId)
boss --role recruiter hr chat --label-id 0 --limit <n> --job-id <encryptJobId>

# 推荐牛人(拿 encryptGeekId / securityId / lid / expectId;--limit 控制一次拉几个)
boss --role recruiter hr recommend --job-id <encryptJobId> --limit <n>

# 直接给推荐牛人打招呼(整套凭证从 recommend 结果里搬)
boss --role recruiter hr chat-start <encryptGeekId> \
    --job-id <encryptJobId> \
    --expect-id <expectId> \
    --lid <lid> \
    --security-id "<securityId>"

# 用 friendId 反查加密 id(encryptUid / encryptJobId / securityId)
boss --role recruiter hr friend-detail <friendId>

# 看在线简历
boss --role recruiter hr resume <encryptUid> \
    --job-id <encryptJobId> \
    --security-id <securityId>

# 单人聊天历史
boss --role recruiter hr chatmsg <friendId>

# 回复候选人
boss --role recruiter hr reply <friendId> <message>

# 主动向候选人求附件简历
boss --role recruiter hr request-resume <friendId>

# 同意候选人主动发来的简历分享
boss --role recruiter hr accept-resume <friendId>
```

### 典型串联

```bash
# 1) 推荐流打招呼
JOB=<encryptJobId>
boss --role recruiter hr recommend --job-id $JOB --limit 5
# → 从 data.geekList[i].geekCard 拿 encryptGeekId / securityId / lid / expectId
boss --role recruiter hr chat-start <encGeekId> --job-id $JOB \
    --expect-id <expectId> --lid <lid> --security-id "<securityId>"

# 2) 沟通中候选人 → 看简历
boss --role recruiter hr chat --label-id 0 --limit 20 --job-id $JOB
# → 拿 friendId
boss --role recruiter hr friend-detail <friendId>
# → 拿 encryptUid / encryptJobId / securityId
boss --role recruiter hr resume <encryptUid> --job-id <encryptJobId> --security-id <securityId>

# 3) 双向简历流转
boss --role recruiter hr request-resume <friendId>    # 我主动求
boss --role recruiter hr accept-resume  <friendId>    # 对方主动发, 我同意
```

---

## 第二层 · HR 命令完整参数与响应

### `hr jobs list` — 我的岗位列表

```
Usage: boss hr jobs list
```

- 端点:`GET /wapi/zpjob/job/chatted/jobList`
- 响应:`data.jobList[]`,每条含 `encryptId` (= 后续 `--job-id`) / `jobName` / `jobStatus` / `salaryDesc` / `cityName`
- 相关子命令:`hr jobs offline <jobId>` / `hr jobs online <jobId>` / `hr jobs detail <encJobId>`

### `hr chat` — 沟通列表(是拿姓名的唯一稳定入口)

```
Usage: boss hr chat [OPTIONS]
  --page INTEGER      页码(默认 1)
  --job-id TEXT       按职位过滤(encJobId)
  --label-id INTEGER  0=沟通中(默认) / 1=新招呼 / 2=沟通中(旧) / 3-5 见下
  --limit INTEGER     只显示前 N 条(数据量大时省 token)
```

- 端点:`POST /wapi/zprelation/friend/filterByLabel`
- **只有 `--label-id 0` 的响应含 `name`**,其他 label 只有骨架
- 关键字段:`friendId`(数字主键) / `encryptFriendId` / `name` / `encJobId` / `jobName` / `lastMsgContent` / `lastMsgTime` / `unread` / `friendSource`

### `hr chatmsg <friend_id>` — 单人聊天历史

```
Usage: boss hr chatmsg [OPTIONS] FRIEND_ID
  --count INTEGER       消息数量(默认 20)
  --max-msg-id INTEGER  向前翻页游标
```

- 端点:`GET /wapi/zpchat/boss/historyMsg`
- 响应只含消息,不含档案

### `hr reply <friend_id> <message>` — 回复消息

```
Usage: boss hr reply FRIEND_ID MESSAGE
```

- 走前端 Vue 组件代劳,自动侦测 chat WS 帧作为成功证据
- 失败时 `zpData.ws_evidence` 里能看到匹配情况

### `hr last-messages` — 批量最近消息摘要

```
Usage: boss hr last-messages [OPTIONS]
  --page INTEGER      沟通列表页码(不传 friend-id 时用来拉取候选)
  --job-id TEXT       按职位过滤
  --label-id INTEGER  按标签过滤
  --friend-id INT     指定 friend_id,可重复
```

- 端点:`POST /wapi/zpchat/boss/userLastMsg`
- 返回 `friendId / unread / msg_status / last_msg / last_time`,**无姓名**

### `hr friend-detail <friend_ids...>` — 反查加密 ID

```
Usage: boss hr friend-detail FRIEND_IDS...
```

- 端点:`POST /wapi/zprelation/friend/getBossFriendListV2.json`
- 支持批量:`hr friend-detail 750327884 750327885`
- 关键字段:`uid`(=friendId) / `encryptUid` / `encryptJobId` / `securityId` / `name` / `friendSource`
- **用途**:`hr chat` 只给数字 id,而 `hr resume` 要加密 id,这里就是桥

### `hr candidates [query]` — 搜索牛人

```
Usage: boss hr candidates [OPTIONS] [QUERY]
  --city TEXT          cityCode(-2=全国, 101020100=上海)
  --job-id TEXT        按职位筛选
  --experience TEXT    如 -3,-3(应届) / -1,-1(不限)
  --degree TEXT        如 201,201
  --age TEXT           如 25,35
  --school-level TEXT  如 1101
  --activeness TEXT    活跃度
  --source TEXT        默认 4
  --salary TEXT        如 -1,3
  --select             带 select=true
  --page INTEGER       页码,每页 15 条
```

- 端点:`GET /wapi/zpitem/web/boss/search/geeks.json`
- 响应:`data.geeks[].geekCard`(近 100 字段),`totalCount` 通常硬顶 400
- 关键字段:`encryptGeekId` / `securityId` / `encryptJobId` / `lid` / `name`(脱敏如 `李**`) / `city / ageDesc / workYear / highestDegreeName / eduSchool / salary / expect / geekDesc / contacting / viewed / favor`

### `hr recommend --job-id <id>` — 推荐牛人

```
Usage: boss hr recommend [OPTIONS]
  --job-id TEXT                          必填,encryptJobId
  --page INTEGER                         默认 1
  --limit INTEGER                        只保留前 N 个候选人(默认全部;仅截列表长度,每个人字段完整保留)
  --age / --activation / --school /
  --gender / --recent-not-view /
  --exchange-resume-with-colleague /
  --major / --keyword1 /
  --switch-job-frequency / --degree /
  --experience / --intention / --salary /
  --cover-screen-memory / --card-type    默认全 "0"(不限)
```

- 端点:`GET /wapi/zpjob/rec/geek/list`
- 响应:`data.geekList[].geekCard`,**姓名未脱敏**(`geekName` 是原文)
- 关键字段:`encryptGeekId` / `encGeekId` / `securityId` / `encryptJobId` / `lid` / `expectId`(chat-start 必带) / `geekName` / `ageDesc / geekGender / geekWorkYear / geekDegree / expectPositionName / salary / matches[] / recallStgTag`
- **合规**:默认 `assisted` 模式会拦,需 `boss config set operating_mode research`

### `hr chat-start <encryptGeekId>` — 直接向推荐牛人打招呼

```
Usage: boss hr chat-start ENCRYPT_GEEK_ID [OPTIONS]
  --job-id TEXT       必填,encryptJobId(同调 recommend 时用的)
  --expect-id TEXT    必填,recommend 结果里的 expectId
  --lid TEXT          必填,recommend 结果里的 lid(含 sessionId, 时效短)
  --security-id TEXT  必填,recommend 结果里的 securityId(一次性)
```

- 端点:`POST /wapi/zpjob/chat/start`
- 四个凭证都从同一次 `hr recommend` 响应里搬,别混搭不同批次
- 成功后候选人会进入 `hr chat` 列表
- **业务级失败判定**(BOSS 侧坑点):HTTP 200 + `code:0` 不代表招呼真的送出去了。
  - 真送出:`zpData.newfriend=1, status=1|0, greeting=<招呼语>`
  - 未真送出:`zpData.newfriend=0, status=3, greeting=null` — 命中就报 `GREET_LIMIT` 错误码
  - 常见原因:①今日打招呼额度用完 ②候选人已在沟通列表 ③职位受风控
  - `details` 里会透传 `friend_id / newfriend / status / greeting` 供上层判断

### `hr resume <encryptUid>` — 看候选人简历

```
Usage: boss hr resume [OPTIONS] [GEEK_ID]
  --job-id TEXT          encryptJobId
  --security-id TEXT     securityId
  --exchange             同步触发交换联系方式
  --type [phone|wechat]  交换类型(默认 phone)
  --uid INT              旧路径,用 friend-id 更稳
  --gid INT              旧路径
  --friend-id INT        新路径 (issue #217)
  --raw                  输出原始 API,不解析
```

- 端点:`GET /wapi/zpjob/view/geek/info`
- 三个凭证一起用:`encryptUid` (地址位参) / `--job-id` (encryptJobId) / `--security-id`
- **合规**:默认拦,要 `research` 模式

### `hr request-resume <friend_id>` — 主动求附件简历

```
Usage: boss hr request-resume FRIEND_ID
```

- 走前端 Vue 组件 `ExchangeResume.handleExChange()`
- **BOSS 改版后可能没有确认弹窗**,现在的实现:handleExChange 跑完就算成功;WS 匹配到 `方便发一份简历过来吗?` 会额外置 `verified=true`
- 响应 `zpData` 里看 `verified` 字段判断是否有 WS 强证据
- **合规**:默认拦

### `hr accept-resume <friend_id>` — 同意对方发的简历分享

```
Usage: boss hr accept-resume FRIEND_ID
```

- 场景:候选人主动点了"发送附件简历申请",聊天窗里出现附件简历卡片,HR 需点"同意"
- 走 DOM 查找 `.chat-message-list .message-item` 里最近一张 `附件简历` 卡片的"同意"按钮
- 已同意的按钮会被 disabled 状态屏蔽,不会重复点

### `hr applications` — 投递申请列表

```
Usage: boss hr applications [OPTIONS]
  --job-id TEXT       按职位筛选
  --label-id INTEGER  按标签筛选(默认 0)
  --page INTEGER      页码
```

### `hr jobs offline / online / detail`

```
Usage: boss hr jobs offline JOB_ID
Usage: boss hr jobs online  JOB_ID
Usage: boss hr jobs detail  ENC_JOB_ID
```

---

## 第三层 · 首次使用必走的环境命令

按顺序执行一次即可。

```bash
# 0) 安装 tboss-cli(命令入口仍是 boss)
#    推荐 uv
uv tool install git+https://github.com/NeverlandzZ1/tboss-cli.git
#    备选 pipx
pipx install git+https://github.com/NeverlandzZ1/tboss-cli.git

#    升级 / 卸载
uv tool upgrade tboss-cli
uv tool uninstall tboss-cli

# 1) 环境体检 — 检查依赖、Chrome/CDP、cookie 提取能力
boss doctor

# 2) 登录当前平台 — 二维码/Cookie 三种降级链路自动选
boss --role recruiter login

# 3) 查登录态与账号信息
boss --role recruiter status

# 4) 允许"看简历/求简历/推荐流"等敏感命令
#    默认 assisted 会拦,切成 research 才能跑
boss config set operating_mode research
boss config get operating_mode        # 确认切换

# (可选) 换掉默认数据目录
boss --data-dir /path/to/dir status

# (可选) 复用本地已开 Chrome(--remote-debugging-port=9222)
boss --cdp-url http://localhost:9222 --role recruiter status

# 退出账号
boss --role recruiter logout
```

### 输出协议(所有命令通用)

- **stdout**:`{ok, schema_version, command, data, pagination, error, hints}`
- **stderr**:日志,受 `--log-level {error|warning|info|debug}` 控制
- **管道自动 JSON**:`boss ... | jq ...` 直接可用
- **敏感字段自动脱敏**:含 `token / cookie / password / stoken / api_key / session` 的键值一律 `[REDACTED]`

### 错误码速查(响应 `data.code` / BOSS 侧)

| code | 含义 | 处理 |
|---|---|---|
| 0 | 成功 | — |
| 9 | 限流 | 停 30s 再试,别高频翻页 |
| 36 | 账号风控 | 停手 24h,别再自动化 |
| 37 | 登录过期 | 重跑 `boss login` |
