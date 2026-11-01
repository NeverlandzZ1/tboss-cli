# 在线简历 Canvas 采集

本地运行方式不变（浏览器需已登录招聘者聊天页）：

CDP 简历命令现在会在同一连接内临时启用焦点模拟，维持 Canvas 绘制，
无需把 Chrome 保持在前台；不激活标签、不恢复最小化窗口。采集成功或
失败都撤销模拟并断开该 CDP 会话，不关闭用户浏览器。其他命令默认不启用。
仍需浏览器运行、CDP 可连接、招聘者聊天页打开且登录有效；不支持电脑休眠。

```powershell
uv run boss --cdp-url http://localhost:9222 --role recruiter hr resume "<encryptUid>" --job-id "<encryptJobId>" --security-id "<securityId>"
```

## 推荐候选人（无需先打招呼）

从同一次 `hr recommend` 返回的 `data.geekList[].geekCard` 取
`encryptGeekId`、`encryptJobId`、`securityId`、`expectId`、`lid`：

```powershell
uv run boss --cdp-url http://localhost:9222 --role recruiter hr resume "<encryptGeekId>" --job-id "<encryptJobId>" --security-id "<securityId>" --source recommend --expect-id <expectId> --lid "<lid>" --raw
```

chat 来源默认不变，先调用 `/wapi/zpjob/chat/geek/info` 刷新凭证。
recommend 来源不调用该接口；官方 iframe 为 `c-resume/?source=recommend`，
请求参数为 `encryptJid / expectId / securityId / lid / entrance=0 / wayType=0 / sourceType=3`。
二者最终均使用 `/wapi/zpjob/view/geek/info/v2`，经 challenge 和官方渲染器处理；
推荐列表中的工作描述不代表完整在线简历。凭证过期应重新获取同一张卡片的整套参数，
不要混用不同候选人的字段。采集本身不发送首招。

`--raw` 的全文在 `data.zpData.geekDetailInfo.renderedText`，完整性在
`data.zpData.capture`；普通输出则是 `data.rendered_text` 和 `data.capture`。
简历采集可在已登录的沟通页或推荐页执行；聊天发送命令的页面要求不变。

## 采集机制

浏览器中的官方 iframe 负责新版接口、challenge 和 WASM。CLI 在发出
`SET_RESUME` 前监听该临时 iframe 的文字绘制，不点击聊天框、不发消息、
不请求附件。临时 iframe 使用独立滚动容器；采集器追踪离屏画布的
`drawImage` 合成与清屏，仅记录最终展示画布上的文字，并以重叠视口逐屏
滚到末尾。完成或达到 25 秒上限后清理容器、iframe、监听和计时器。
采集前直接测量官方 `#resume` 内容高度并同步 iframe，等待高度稳定，
不把初始化的 1200px 当作真实高度。每次滚动后必须观察到新的绘制；
未重绘则返回 `partial` / `render_stalled`，不会宣称已到底。

输出新增：

- `rendered_text`：按画布坐标还原的文字，保留未能结构化的内容。
- `rendered_sections`：基本信息、自述、工作、项目、教育、社团、荣誉、
  证书、技能等页面实际存在的章节，避免摘要模型没有字段导致遗漏。
- `project_experience[].description`：仅在项目标题能唯一匹配时填充绘制正文。
- `work_experience[].responsibility`：仅在公司标题能唯一匹配时填充工作正文。
- `capture.source`：`official_iframe_canvas`。
- `capture.completeness`：成功完成最终画布遍历及条目匹配时为
  `rendered_complete`；超时、未到底、绘制观察异常、匹配歧义或仍存在展开
  文案时为 `partial`，具体原因见 `capture.reasons`。
- `capture.reached_bottom` / `scroll_steps` / `snapshots` / `content_height`：
  遍历覆盖证据。`rendered_complete` 指页面已渲染内容，不是平台未公开或
  被遮蔽信息的完整性承诺。平台显示的星号会原样保留。

`--raw` 返回摘要与绘制文字合成的数据，不是原始 HTTP 响应。
招聘 Skill 使用 `data.zpData.geekDetailInfo` 下的 `geekEduExpList`、`renderedText`
与 `renderedSections` 提取筛选事实；不要把默认展示格式的空 `basic.degree`
当作无学历。采集与 `capture` 诊断由 CLI 负责，Skill 不重复实现采集完整性门禁。
CLI stdout/stderr 固定 UTF-8，Windows GBK 环境下的特殊字符不应变成网络错误。
没有绘制文字或候选人身份不匹配时返回错误，不将摘要当作全文成功。
不会将全文中的成果条目猜测拆成 `achievement`，也不会自动点击展开控件。

旧版只取首屏及文字最多的画布，长简历会漏采，且可能记录未合成到页面的
「查看全部」文案。本版不再把这些离屏中间绘制当作可见正文。
复杂分栏、非文字图片、自定义剪裁或页面改版仍可能影响提取；本方案不是
截图/OCR，不提取图片中的文字。重复标题不自动分配描述，仍保留原文供核查。
遇到安全验证应停止重试，在原浏览器手动完成验证后再执行。

## 验证记录

2026-11-01：通过 Ego 登录态运行正式 JS 与 Python 解析器，对一份 4510px
长简历完成 7 次滚动、9 次快照，得到 5967 字符；两段工作正文和三个项目
正文均非空，底部社团、荣誉、证书、技能及平台提示与可见页面核对。
临时 iframe 数量恢复到运行前。此验证不替代用户本地 CDP 端口的端到端验证。

后续用户反馈暴露了初始高度被误判为末尾的问题，已补充真实高度测量与
重绘进展检查，相关 72 项测试通过（含初始高度与实际高度不同、滚动不重绘
的模拟测试）。恢复 Ego 登录后，以反馈的同一份简历运行正式 JS 和 Python
解析器：805 字符提升到 2788 字符，测量高度 2768px，4 次滚动、6 次快照；
两个项目正文分别为 339 / 456 字符，工作正文 785 字符。教育、荣誉、证书、
技能及平台提示均已采到，底部页面截图核对通过，临时 iframe 已清理。
结果为 `rendered_complete`，无缺项原因；仍需用户本地 CDP CLI 复测。

后续正式命令验证：在用户 `localhost:9222` 上以当前任杰简历执行
`uv run boss --cdp-url http://localhost:9222 --role recruiter hr resume ...`。
改前后台状态为 828 字符、`render_stalled`；接入焦点保障后，最小化状态
得到 1708 字符、2 次滚动，两个项目正文 446 / 357 字符，结果为
`rendered_complete`。验证脚本只设置窗口状态并启动正式命令，没有外加焦点模拟；
命令结束时窗口仍为最小化。105 项相关测试及 Ruff 检查通过。
切换到其他标签页后，同一正式命令也得到相同的 1708 字符；结束后招聘者页
恢复 `hidden`，验证焦点模拟未残留。测试创建的空白标签已关闭。

2026-11-02 推荐来源正式命令验收：重新绑定已登录的 `localhost:9222` 会话后，
执行 `hr recommend`，选取 `isFriend=0`、`haveChatted=0` 的卡片，将同一卡片
参数传给 `hr resume --source recommend --expect-id ... --lid ... --raw`。
Chrome 最小化状态下获得 1613 字符、481 字符项目正文，2 次滚动、4 次快照，
结果为 `rendered_complete`，原因列表为空；命令结束时窗口仍为最小化，随后恢复
原窗口状态。没有调用打招呼或附件请求。110 项 CLI 相关测试与 6 项 Skill
契约测试通过。此结果验证该样本的已渲染正文采集，不代表所有候选人的信息均完整。
