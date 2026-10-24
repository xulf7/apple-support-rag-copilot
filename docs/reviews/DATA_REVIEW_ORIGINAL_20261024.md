# 六篇 Apple Support 资料内容审查记录（AI）

审查日期：2026-10-24（北京时间）  
审核者：ChatGPT；审核方式：AI 阅读核对 + 独立文本比较 + 原有结构检查复跑。

## 结论

六篇当前文档均未发现阻塞检索开发的内容保真问题：五篇通过，一篇通过但有一处轻微空格瑕疵。已打开六个对应 Apple 官方页面，核对文章身份、页面显示日期及关键条件；本地已保存 HTML 是逐项文件比较的固定版本基准，不将在线页面的解析结果视为新采集快照。

本记录完成用户委托的资料内容核对。无需再等待同学上线或要求用户逐篇重复同样核对，便可推进 T03（文档切块、embedding 与索引构建）与 T04（问题检索与证据展示）。团队可按需抽检。

审查不冒充人类签字：没有修改原数据，六条 human_review 仍为 pending。这表示暂无人类复核记录，不等于这六篇内容尚未被审查。让 Codex 将本记录作为 AI 内容审核证据，如实记录审核方式，不把它填成用户或同学亲自审核。

## 输入与完整性

- 输入：AppleSupportRAGCopilotinitial.zip。
- ZIP SHA-256：`47ee0f4828378c34d851f8c1b45792a85d0949468a42e8ae1547683eeceec2fa`。
- data/sources.jsonl SHA-256：`800b037effed710e4f66c222ef63a98bd9e58a4295af8a8b71e90c80f19073f7`。
- 仅审查 JSONL 指向的六篇当前版本，未将三个历史清洗版本重复计入。
- 六篇正文均与 JSONL 的 text 字段一致，正文及原始快照 SHA-256 均匹配。
- 六个保存原件与相应 raw 快照在此前独立检查中逐篇字节一致；本轮检查输入未被修改。

## 逐篇结果

| 文档 ID | 主题 | 结论 | 关键语义核对 |
|---|---|---|---|
| apple-en-us-101567 | 修改账户密码 | 通过 | 可信设备和双因素认证前提、设备/网页分支、安全延迟及儿童账户条件均保留，未改写为任意设备均可直接操作。 |
| apple-en-us-102656 | 忘记密码及无法登录 | 通过 | 可信设备、无可信设备、恢复因素、账户恢复等待、系统版本相关入口与设备使用/取消条件均保留，未将条件化流程变成即时恢复保证。 |
| apple-en-us-108366 | iCloud 备份 | 通过 | 手动与自动备份分开；自动备份下的电源、Wi-Fi 与锁屏条件保留；手动备份中的保持网络连接、存储不足和旧系统提示保留。 |
| apple-en-us-118223 | 申请退款 | 通过 | 资格是条件性表述；申请状态更新时间与资金返还时间分开；待处理扣款、未付款订单、账户和地区等条件保留。 |
| apple-en-us-118428 | 取消订阅 | 通过，有轻微瑕疵 | 设备分支、无取消按钮的判断、不同付款方、家庭成员账户、试用取消条件与地区差异均保留；仅发现链接前空格问题。 |
| apple-en-us-118574 | 账户恢复等待 | 通过 | 确认消息时限与恢复等待时间分开；设备使用条件、取消触发、重复申请和客服不能缩短等待等限制均保留。 |

## 独立比较与结构结果

独立比较直接读取保存 HTML 的信息正文，不调用生产渲染器生成对照文本。排除已约定不入库的导航/反馈/设备选择控件及通用求助 CTA；清洗文本对照时去除 Markdown 标记、编号和图像替代文本，仅作正文词序比较。该比较不能替代语义阅读，所以又按各篇关键条件阅读核对。

| 文档 ID | 标题数 | 段落数 | 编号步骤数 | 关键来源链接数 | 正文词序比较 |
|---|---|---|---|---|
| apple-en-us-101567 | 7 | 22 | 12 | 4 | 一致 |
| apple-en-us-102656 | 10 | 30 | 0 | 8 | 一致 |
| apple-en-us-108366 | 3 | 13 | 9 | 5 | 一致 |
| apple-en-us-118223 | 6 | 20 | 7 | 7 | 一致 |
| apple-en-us-118428 | 18 | 46 | 31 | 7 | 仅链接前词边界空格差异 |
| apple-en-us-118574 | 8 | 21 | 0 | 2 | 一致 |

合计 52 个标题、152 段正文、59 个编号步骤、33 个来源链接检查通过。链接核对指保留相同目标及文档来源映射；本次没有登录或逐个访问退款、账户管理等操作页面，也没有实际执行账户操作。

本轮复跑命令：`python -B -m src.check_corpus --report <本轮独立报告路径>`，退出 0，六篇 HTML 结构均通过。五篇独立正文词序完全相同；取消订阅一篇存在下述空格问题。未重复声称本轮新跑了整个单元测试套件。

## 轻微问题：取消订阅链接前空格

- 文档：apple-en-us-118428。
- 位置：More about canceling subscriptions 中的地区差异段落。
- 当前 Markdown 在 `There are` 与后续链接之间缺少空格，渲染后容易粘成一个词。
- 原始 HTML 的空格位于锚点文本开头；src/ingest.py 的 inline() 对链接文本调用 strip() 后没有把这段边界空白补回。这是可定位的提取瑕疵。
- 影响：阅读和分词略受影响，地区条件、列举内容和链接目标仍在；不阻塞切块和检索开发。
- 建议在 feature/retrieval-index 开始时最小修复锚点边界空白，增加一条相关回归检查，重新导入受影响文档并更新正文哈希。避免给所有内联标签盲目插入空格，以免破坏标点或单词内部格式。
- 不要仅手动改 Markdown 而保留 JSONL 正文和旧哈希；重建后对新版本复核这一差异。原 HTML 字节保留不改。

## 给 Codex 的衔接要求

1. 先核对本机六篇当前正文哈希是否与本记录一致；有变化仅针对变化版本重新核对。
2. 将本记录内容整理到 docs/ARTICLE_REVIEW.md 或单独的 AI 审查记录，并让任务清单区分“AI 内容核对通过”和“人类复核未进行”。无需把未完成的人类签字变成检索编码的前置阻塞。
3. T02（采集、清洗与本地导入）的软件和资料内容核对已有证据，记录为内容审核通过（AI）；是否另做人类抽检单列，保持事实一致。
4. 修复轻微空格问题并重导入后，绑定新正文哈希，再继续 T03（文档切块、embedding 与索引构建）和 T04（问题检索与证据展示）。
5. 本次记录只覆盖已核验的正文版本与清洗保真度，检索及生成质量仍需后续真实测试。

## 可追溯的版本记录

```json
[
  {
    "doc_id": "apple-en-us-101567",
    "source_url": "https://support.apple.com/en-us/101567",
    "published_at": "September 29, 2026",
    "snapshot_path": "raw/apple-en-us-101567-0ef8a11692cd4567.html",
    "snapshot_sha256": "0ef8a11692cd4567cdde65f942b75fc68d7ec68c4619e7467ca49ac93756e087",
    "text_path": "clean/apple-en-us-101567-f61b464d4ec68772.md",
    "content_sha256": "f61b464d4ec68772cb76f4c13161e489131ccc3b056042a670af34e941ea625c",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed",
    "human_review_at_review": "pending"
  },
  {
    "doc_id": "apple-en-us-102656",
    "source_url": "https://support.apple.com/en-us/102656",
    "published_at": "October 05, 2026",
    "snapshot_path": "raw/apple-en-us-102656-40db3a51424b3683.html",
    "snapshot_sha256": "40db3a51424b3683b7f6908f78b7fb33f356b9c3ae150091ca1e44342cb61f80",
    "text_path": "clean/apple-en-us-102656-c518269bf0dc65eb.md",
    "content_sha256": "c518269bf0dc65eb668ea4925728911ab8ed33ce074a01164066d6aca5509f69",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed",
    "human_review_at_review": "pending"
  },
  {
    "doc_id": "apple-en-us-108366",
    "source_url": "https://support.apple.com/en-us/108366",
    "published_at": "September 24, 2026",
    "snapshot_path": "raw/apple-en-us-108366-4d62a95127bce7e7.html",
    "snapshot_sha256": "4d62a95127bce7e76739cf7de2770147b2e9d7e8ce68627d83ac22eaa3b36987",
    "text_path": "clean/apple-en-us-108366-0746d5197cde5a01.md",
    "content_sha256": "0746d5197cde5a01645f2d4616479ae3662f3f08d18566b215e87f0e1bc31ccc",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed",
    "human_review_at_review": "pending"
  },
  {
    "doc_id": "apple-en-us-118223",
    "source_url": "https://support.apple.com/en-us/118223",
    "published_at": "September 17, 2026",
    "snapshot_path": "raw/apple-en-us-118223-36e12628352e6511.html",
    "snapshot_sha256": "36e12628352e65116826e2446c8c6889b39483934b256e89720e43980df7d47d",
    "text_path": "clean/apple-en-us-118223-fb1c9b872d1da51b.md",
    "content_sha256": "fb1c9b872d1da51b42c9feab8b0c035a859878b6db5b496e7c5dcb3a9e18e629",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed",
    "human_review_at_review": "pending"
  },
  {
    "doc_id": "apple-en-us-118428",
    "source_url": "https://support.apple.com/en-us/118428",
    "published_at": "September 29, 2026",
    "snapshot_path": "raw/apple-en-us-118428-5e91e9b76405a35a.html",
    "snapshot_sha256": "5e91e9b76405a35ab65b763e734db114ba9267dce516e6f6dd8ebfbf997e970c",
    "text_path": "clean/apple-en-us-118428-3007bd385d845927.md",
    "content_sha256": "3007bd385d845927d2b5cdc41ee3d70bff6b6c0ee67696e1d291a49cc3c92752",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed_with_minor_issue",
    "human_review_at_review": "pending"
  },
  {
    "doc_id": "apple-en-us-118574",
    "source_url": "https://support.apple.com/en-us/118574",
    "published_at": "October 05, 2026",
    "snapshot_path": "raw/apple-en-us-118574-eb58156122a583d3.html",
    "snapshot_sha256": "eb58156122a583d378a74694f4b0fdab1ae4748a3394a8253941e1d64902cb58",
    "text_path": "clean/apple-en-us-118574-6cb56ccd93729984.md",
    "content_sha256": "6cb56ccd93729984db034b9ffbf5e542b22f15562fdec757a0b08067a02cc308",
    "reviewer": "ChatGPT",
    "reviewer_type": "ai",
    "review_date": "2026-10-24",
    "ai_review_status": "passed",
    "human_review_at_review": "pending"
  }
]
```

## 官方页面核对来源

- [Change your Apple Account password](https://support.apple.com/en-us/101567)
- [If you forgot your password and can’t sign in to your Apple Account](https://support.apple.com/en-us/102656)
- [How to back up your iPhone or iPad with iCloud](https://support.apple.com/en-us/108366)
- [Request a refund for apps or content that you bought from Apple](https://support.apple.com/en-us/118223)
- [Cancel a subscription from Apple](https://support.apple.com/en-us/118428)
- [What to expect during account recovery](https://support.apple.com/en-us/118574)

六个页面均在本轮成功打开。本文只概述核对结论，不附完整 Apple 正文。
