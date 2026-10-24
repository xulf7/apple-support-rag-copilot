# MIS2001 Apple Support RAG Copilot：MVP 实施计划与进度清单

更新日期：2026-10-24（北京时间）  
小组：RAG Support Team；两位成员分别负责后端整合与数据/UI/测试  
用途：交给 Codex 分轮实现，并作为持续更新的任务记录。建议放入项目仓库 `docs/MVP_PLAN_AND_TASKS.md`。

## 1. 当前事实、目标与时间边界

- 已读：正式 Project Plan PDF、2026-10-23 交接说明与 `MIS2001 Term project requirements 20260907.pdf`；项目定位、核心流程与两人初步分工已明确。后补的正式课程要求优先于交接摘要与本计划中的开发建议；最新教师/Blackboard 通知如有提供则优先。
- 2026-10-24 当前已在 feature/retrieval-index 分支完成本地检索：六篇冻结资料、56 个 chunk、384 维 FAISS 索引。统一使用现有 conda rag 环境，无包安装升级；40 项离线测试通过，12 个开发问题实测均在第 1 名命中预期文档。仅检索证据，尚无生成或网页闭环。详见 docs/RETRIEVAL_20261024.md。
- MVP 目标：staff 粘贴客户问题 → 检索 Apple 官方支持片段 → 通过 LLM API 生成 suggested response → 显示真实出处和证据片段 → staff 人工审核。证据不足时提示核实或澄清。
- 正式课程要求已核对：Week 7 中期展示；11/5 提交 PPT 与中期报告（至少 10 页，不含 appendix），中期报告占项目成绩 30%，展示本身不计分；中期 prototype demo 为可选。用户仍明确希望近期完成 MVP。正式文件只写 Week 7，具体 10/27 日期来自交接摘要，本轮未核对最新课程公告，作为保守准备节点使用。若有 10/29 的咨询或提交安排，不能仅凭当前文件推断其关系。
- 最终节点：12/15 提交最终 PPT、报告与相关 App；最终报告约 25 页，不含 appendix，需要 team contribution statement；最终报告与项目成果占项目成绩 70%。
- 以下文档数量、题数和验收门槛均为团队开发建议，不是课程硬性指标；如开始执行时已有代码，先复用并核验，不重建已完成模块。

## 2. 锁定本轮范围

### 必须完成

1. 真实官方文档、可重复的数据清洗和索引构建。
2. 真正的 embedding 与向量检索，保留 top-k 片段及来源映射。
3. 至少一次真实 LLM API 的端到端调用，并保存可核验结果。
4. staff 网页：输入问题、建议回复、引用链接、证据展开、清晰失败提示。
5. 证据不足、含混问题、范围外问题、API 异常的回退。
6. 小规模人工核验的评估集、测试结果、启动说明和演示脚本。

### 展示前不加入

多轮记忆、Agent、多角色系统、微调、大规模爬虫、登录权限、工单集成、自动发送客户回复、复杂管理后台、云部署。Mac / AirPods 等原计划主题可以后续扩展；此次缩小的是首批覆盖范围，不改变项目定位。

### 建议首批覆盖

- Apple Account：密码重置、找回登录标识、账户恢复等公开帮助流程。
- Subscriptions：取消、修改订阅、退款申请的条件与入口。
- iCloud：备份、存储空间和常见备份问题。
- 第一轮仅用 6 篇真实文章验证；闭环打通后扩至约 20–30 篇有用文章。数量服从内容质量，不凑数。
- 先统一英文文档和英文演示问题，降低地区与语言混杂。若需要中文提问，选择多语 embedding 并另外测试，不能默认支持跨语言检索。
- 初始统一 `en-us`。界面注明资料适用范围；遇到其他地区政策问题，须核对相应来源后回答。

## 3. 建议技术路线

| 模块 | 本轮默认 | 原因及边界 |
|---|---|---|
| 运行环境 | 复用现有 conda rag（Python 3.11.5） | 用户本轮指定整个项目统一使用 rag；必要库实际加载与编码已验证，未安装/升级包，不新建环境 |
| staff 界面 | Streamlit | 尽快实现输入、回答、来源和证据展示；已有 Flask 可运行项目则优先复用 |
| 采集 | requests + BeautifulSoup，指定 URL 清单 | 抓取允许访问的官方文章；保留手工文本导入路径 |
| 原文及元数据 | 本地 HTML 快照 + JSONL | 易检查、可追溯、可重复处理 |
| embedding | all-MiniLM-L6-v2，固定 revision，CPU | 已真实编码；384 维，实际输入上限 256，切块上限 240；未验证跨语言检索 |
| 向量检索 | FAISS CPU 精确索引 + JSONL metadata | 该规模优先简单可复现；记录索引、模型和语料版本 |
| 生成 | 一个可配置的 LLM API 适配器 | 模型与供应商依据用户已有可用 API 确定；不先实现多个供应商 |
| 配置 | 环境变量 + `.env.example` | 真实 key 由用户在本机配置；日志与提交不得包含 key |
| 测试记录 | JSONL/CSV + 人工审核表 | 自动检查引用映射等结构事实，人工判断回答是否真正有据 |

不要求独立 REST 服务、LangChain 或数据库服务。模块应可独立调用，方便后期拆分。若 FAISS 安装受阻，可先用持久化的向量矩阵完成精确检索并记录取舍，不能以关键词匹配冒充 embedding 检索。

## 4. 持续跟进清单

状态约定：`待核验` → `待做` → `进行中` → `待验收` → `完成`；遇外部依赖记 `阻塞`。初始均为待核验，因为未读取实际工程。

**当前：4/13 项阶段任务完成（T01–T04）；T00 的 embedding 部分通过，LLM API 部分仍待确认。** T02 依据软件检查、六篇 AI 审查及用户对 Change password 整页的人工检查完成本阶段验收；不宣称六篇均人工全文审核。任务数量不代表按工作量加权的完成率。

| ID | 任务 | 建议完成日 | 依赖 | 状态 | 验收条件 | 结果证据 / 阻塞 |
|---|---|---|---|---|---|---|
| T00 | 工程盘点、依赖与配置 | 10/23 | 无 | 待验收 | 说明已有内容；环境可启动；配置示例完整；确认 API/模型下载可达性 | rag 现有库加载、MiniLM 下载与 CPU 真实编码通过；evidence/retrieval_20261024/environment.txt、model_check.txt；LLM API 等用户咨询老师后确认，不阻塞检索 |
| T01 | 官方种子 URL 与主题范围 | 10/23 | T00 | 完成 | 先选 6 篇文章；官方域名、语言、主题、最终 URL 可追溯；不将导航页当正文 | data/seeds.json；evidence/web_metadata_checks.json；web 工具核对六篇标题/最终 URL，en-us，覆盖三个主题；仅元数据，非正文入库。依赖 T00 的本地环境部分已通过 |
| T02 | 采集、清洗与本地导入 | 10/23 | T01 | 完成 | 本阶段软件校验、六篇 AI 内容审查、用户确认 Change password 整页人工检查；版本绑定正确 | [最终审查报告](reviews/DATA_REVIEW_FINAL_20261024.md)；六篇正文/快照/URL 与报告一致；evidence/retrieval_20261024/review_binding.json；冻结资料及六条旧 pending 字段未改，人工范围不外推到其余五篇 |
| T03 | 切块、embedding 与索引 | 10/24 | T02 | 完成 | 可重建并重载索引；每个 chunk 对应原文；无旧索引混用或重复追加 | src/retrieval.py、src/embedding.py；6 篇/56 块/384 维；真实 tokenizer 最长 233≤240<256；模型与映射版本、artifact 哈希；实际重载一致/重复 cached，配置变化测试拒绝混用。证据 evidence/retrieval_20261024/ |
| T04 | 问题检索与证据查看 | 10/24 | T03 | 完成 | 英文自由问题默认 top-5，含分数、片段、章节、文档/块 ID、标题和真实 URL | 6 直接+6 同义问题，实际预期文档排名均为 1；evaluation/retrieval_cases.json；本地 evaluation.json、cli_query.txt。开发小样本非盲测；范围外仍返回片段，未实现 T06 回退 |
| T05 | LLM 建议回复与引用绑定 | 10/24 | T04 | 待核验 | 真实 API 调用成功；引用 ID 只从本次上下文选择；后端映射真实 URL；人工确认回答受支持 | 未提供 |
| T06 | 证据不足与异常回退 | 10/25 | T05 | 待核验 | 缺证据/含混/越界时核实或澄清；空索引、缺 key、超时、API 错误有清晰提示；不伪造回答 | 未提供 |
| T07 | staff 网页整合 | 10/25 | T05、T06 | 待核验 | 浏览器中完成问题→回复→查看出处；显示 suggested response 与人工审核提示；无自动发送功能 | 未提供 |
| T08 | 扩展并冻结首批知识库 | 10/25 | T04 | 待核验 | 约 20–30 篇有用文章或说明实际范围；新增内容抽查、重建索引、版本清单完整 | 未提供 |
| T09 | 人工核验问题集 | 10/25 | T08 | 待核验 | 30 题含题型、依据文档、关键答案点或回退预期；标准答案已逐题核对 | 未提供 |
| T10 | 实跑评测与缺陷修复 | 10/26 | T06、T07、T09 | 待核验 | 保存逐题输入输出、引用、人工评分、实际指标；复测修复问题；保留失败案例 | 未提供 |
| T11 | 重启复现与演示彩排 | 10/26 | T10 | 待核验 | 重启后可按 README 启动；演示 3 个有据问答、1 个澄清、1 个缺证据/越界、1 个 API 失败 | 未提供 |
| T12 | 演示与中期材料证据包 | 10/26 | T11 | 待核验 | 架构、真实界面、数据统计、结果、限制、分工记录齐全；备份录像/记录标明真实测试时间 | 未提供 |

T06、T07 可增量开发，T07 完成验收需要 T06 接入。T08 在基础闭环可用后进行，不为扩充数量延迟 T05。T09 可先起草，但需等语料冻结后核对。建议 10/26 完成核心验收；10/27 只做展示前启动检查。

### 每轮 Codex 的更新规范

1. 保留 T00–T12 固定编号；仅按真实情况改状态、证据和阻塞原因。
2. 证据写相对路径、执行命令、运行日期和关键结果；如果使用 git，可补充 commit ID。
3. `待验收` 表示代码已写但尚缺真实测试或人工核验；不得直接写完成。
4. `阻塞` 写清依赖，例如“用户尚未配置 LLM key”，并继续推进可独立进行的数据、检索、UI 和测试工作。
5. 每次输出已完成 ID、待验收 ID、阻塞项、下一轮任务和需要用户操作的最小步骤；不在消息中展示密钥。
6. 在下方记录历史，避免只保留最新口头汇总。用户新开 Codex 对话时让其先读本文件与实际仓库。

| 日期 | 任务 ID | 状态变化 | 验证命令 / 人工核验 | 证据路径 | 尚存问题 |
|---|---|---|---|---|---|
| 2026-10-23 | — | 建立计划；实现未核验（原始记录） | 原计划阶段审阅材料 | library/MVP_Plan_and_Tracker.md | 待盘点工程与环境 |
| 2026-10-23 | T00 | 待核验 → 待验收 | python -m src.check_environment；python -m src.ingest --help | evidence/environment.txt；evidence/cli-help.txt；.env.example；docs/ROUND_1_RESULTS.md | 本地启动已通过；未确认 API/embedding 模型可达性 |
| 2026-10-23 | T01 | 待核验 → 完成 | web 工具逐篇核对六篇官方 URL/标题/地区 | data/seeds.json；evidence/web_metadata_checks.json；docs/ARTICLE_REVIEW.md | 不等同于正文采集；六篇均待人工抽查 |
| 2026-10-23 | T02 | 待核验 → 阻塞 | python -B -m unittest discover -s tests -v（17/17）；python -m src.ingest collect --limit 3；python -m src.ingest collect --limit 6；python -m src.ingest validate | evidence/unittest.txt；evidence/pilot.txt；evidence/six.txt；evidence/validate.txt；data/logs/events.jsonl；evidence/network_checks.json | 真实正文 0；条款限制和网络失败；仅合成测试，真实 HTML 提取/官方手工导入尚未验证 |
| 2026-10-23 | T02 | 保持阻塞；改走手动文件路径 | 用户确认无单独许可；手动 CLI 改为 --provenance 记录实际获取方式，兼容旧参数；复测见后续证据 | docs/MANUAL_COLLECTION_ZH.md；evidence/manual_followup_tests.txt | 等待前三篇真实 HTML；不要求虚构许可，自动 HTTP 限制保留；测试源码保留，临时样本自动删除 |
| 2026-10-24 | T02 | 阻塞 → 待验收 | python -B -m src.import_saved --limit 3/6 --provenance 实际获取说明；python -B -m src.check_corpus；python -B -m src.ingest validate；python -B -m unittest discover -s tests -v | docs/MANUAL_IMPORT_RESULTS_20261024.md；data/sources.jsonl；evidence/corpus_quality_20261024.json；evidence/manual_real_tests_20261024.txt | 六篇真实正文已入库，canonical/标题匹配且保留原文件名；152 段、52 标题、59 编号步骤、33 链接检查通过；待团队人工核验关键条件。无网络请求、未启动 T03–T04 |

| 2026-10-24 | T00/T02 维护 | 公开前整理；验收状态不变 | 修复文本 HTML 不适用状态/单篇错误隔离、无关保存页隔离；29 项测试和无资料临时副本测试通过；六篇结构复查通过；忽略规则 50+13 项通过 | docs/PUBLIC_PREPARATION.md；本地 evidence/public_prep_20261024/ | 49 个受保护原文件哈希未变；T02 人工审核仍 pending；未开始 T03–T04；实际 Git 命令确认当前不是工作树，未暂存/提交/推送 |

## 5. 数据收集：Codex 可以做什么

2026-10-24 feature/retrieval-index：T02 按用户明确的本阶段验收口径收尾；
[最终 Review 归档](reviews/DATA_REVIEW_FINAL_20261024.md)保留原报告并修正人工
抽查范围，原样副本 SHA-256 一致。T03/T04 真实运行通过；40 项合成回归测试。
所有语料/历史证据保持不变，无解析器修改或重导入。实现与实测详见
`docs/RETRIEVAL_20261024.md`，本地证据 `evidence/retrieval_20261024/`。

可以让 Codex 执行从候选页面发现到正文清洗、去重、切块和建索引的完整工程流程，前提是它所在环境确实允许访问相关页面并能下载所选 embedding 模型。查到链接不等于抓到正文；HTTP 200 也不代表拿到了有效文章。

### 采集流程

1. 从下列官方种子页面开始，验证当前页面标题与正文，只扩展与选定主题有关的官方文章。
2. 首先小规模验证 2–3 页的正文提取，再处理 6 页；成功后才扩展。
3. 正文保留小标题、步骤顺序、适用设备、系统版本、条件限制和注意事项；清除导航、页脚、推荐营销与反馈表单。
4. 请求采用低并发、超时、有限重试与缓存；检查适用的访问规则，遇访问限制停止自动采集并记录。不要绕过验证码或登录。
5. 保存成功/失败清单；失败文档不得用模型补写内容。网络不可达时支持人工导入从官方页面合法取得的正文，保留原 URL 与导入方式。
6. 下载模型或调用 API 受网络限制时记录具体阻塞；不能把演示假数据、占位符回答写成实际抓取或推理成果。

### 已通过网页检索核对的官方种子链接（2026-10-23）

这些是候选入口，尚未在项目采集器中抓取或入库；Codex 应重新验证当前实际内容。

- Cancel a subscription from Apple — https://support.apple.com/en-us/118428
- Request a refund for apps or content that you bought from Apple — https://support.apple.com/en-us/118223
- Switch to a different subscription plan — https://support.apple.com/en-us/118448
- Change your Apple Account password — https://support.apple.com/en-us/101567
- If you forgot your password and can't sign in to your Apple Account — https://support.apple.com/en-us/102656
- If you forgot your Apple Account primary email address or phone number — https://support.apple.com/en-us/102627
- What to expect during account recovery — https://support.apple.com/en-us/118574
- How to back up your iPhone or iPad with iCloud — https://support.apple.com/en-us/108366

### 建议数据契约

`sources.jsonl` 每篇一条：

```json
{
  "doc_id": "stable_document_id",
  "title": "Title extracted from the actual page",
  "source_url": "https://support.apple.com/en-us/108366",
  "final_url": "https://support.apple.com/en-us/108366",
  "topic": "icloud",
  "locale": "en-us",
  "fetched_at": "actual ISO-8601 timestamp",
  "published_at": null,
  "ingestion_method": "http",
  "content_sha256": "actual hash",
  "snapshot_path": "raw/stable_document_id.html",
  "text": "actual cleaned official text"
}
```

此为字段示例，不是已采集数据。网页未显示发布日期时保持 null，不推测。手工导入写 `manual`，保留可用的原文快照，不能虚构 HTML 文件。`chunks.jsonl` 至少包含 `chunk_id, doc_id, heading, text`；标题/URL 通过 doc_id 查询。索引清单包含 embedding 模型、向量维度、距离定义、切块参数、语料哈希与生成时间。

人工工作量可控：6 篇首批文档逐篇核对；扩展时每类主题都抽查，且对异常短文、政策限制、关键操作步骤重点核对。两人最终逐题核验 30 个评估题的依据和关键答案点。无需先手工整理几十页全文再让 Codex 开始。

## 6. RAG 实现与验收细节

### 切块与检索

- 按小标题与段落切分，尽量保留完整操作步骤和前置条件；首轮可从约 300–500 tokens、约 50 tokens overlap 起步，需记录实际计数方法和参数。
- 若段落超过 embedding 模型输入上限，按上限进一步切分，不能静默截掉后半篇。
- 起步 top-k=5；召回后可合并重复文章展示，保留原始 chunk 记录供调试。
- 固定向量归一化和距离定义；相似度不是“答案正确率”，不能在界面标成置信概率。
- 改模型、维度、语料或切块设置后重建索引，使用版本清单检查不匹配。

### 生成与引用

- prompt 明确输入为参考资料而非指令，答案仅使用资料支持的信息；资料不足或条件不明时核实/澄清。
- API 返回至少包括 `status`（answered / insufficient_evidence / clarification_needed）、`suggested_response`、`citations`（上下文内 chunk ID）。
- 后端验证引用 ID 属于本次检索集合，再映射源标题与 URL。ID 越界、输出损坏或有据回答缺引用时，提示失败/核实，不默认当作成功。
- 引用真实不代表内容一定正确：除程序验证外，还需人工检查被引片段是否支持回复中的具体步骤与条件。
- 证据不足不能只靠一个拍脑袋的固定相似度阈值判断。结合覆盖范围、开发样例与模型的证据充分性判断；若设阈值，要记录定义与校准样例。
- 不向模型发送真实账户凭据、支付信息或设备序列号；演示用虚构客户问题。

### 展示界面

页面只需要：范围说明、问题输入、生成按钮、suggested response、来源标题与链接、可展开证据、加载状态与错误提示。注明 academic prototype / not affiliated with Apple / for staff review。不强制做登录、真实发送或“已审核”持久化工作流。

## 7. 最小评估与验收门槛

建议 30 题构成：18 题有据可答（含直接问法、同义改写、少量综合题），6 题涉及缺失条件或缺少资料，3 题含混需澄清，3 题超出覆盖范围。题型分组互斥，依据冻结后的语料标注；有些现实中可回答的问题仍可能超出本知识库。

每题记录：`case_id, category, question, expected_doc_ids, expected_key_points, expected_behavior`。缺证据/澄清题的预期应写清楚哪些部分能答、哪些必须保留或追问。

| 检查项 | 如何计算 / 判断 | 建议验收目标 |
|---|---|---|
| 文档命中 Hit@5 | 有据可答题中，top-5 chunk 所属文档与任一标注依据文档相交的题数 / 有据可答题数 | 首轮目标 ≥80%；18 题时至少 15 题命中 |
| 多文档覆盖 | 综合题是否召回所有必要依据；独立记录，不能被 Hit@5 掩盖 | 展示综合题如使用，必须召回必要依据 |
| 回答有据与正确性 | 逐题人工核对关键步骤、限制条件、无依据断言 | 记录实际通过数；演示用的可回答案例逐题通过 |
| 回退行为 | 缺证据/含混/范围外题是否按预期核实、保留或澄清 | 逐题审核；必须修复明确编造政策或保证结果的案例 |
| 引用有效性 | 结构上属于本次上下文且 URL 来自入库记录；语义上确实支持相关结论 | 所有用于演示的引用真实、可打开且支持回复 |
| API 异常与重启 | 模拟超时/缺 key 等故障，再重启按 README 实跑 | 不崩溃、不返回假成功；恢复配置后真实链路可用 |

不把不同题型混为“准确率”；命中部分依据也不等于回答正确。30 题属于开发验收集，不能宣称代表真实客户分布或模型普遍性能。若按其调整参数，在报告中披露，不称为独立盲测。

建议保存 `evaluation/cases.jsonl`、`evaluation/results.jsonl`、`evaluation/manual_review.csv`、`evaluation/summary.md`。记录检索、上下文、实际模型名、生成时间、耗时与错误；不要只保留聚合数字。另保留至少 2 个失败/改进案例，服务中期报告。

## 8. 两人分工与倒排

| 日期 | Codex 主要输出 | 后端与报告负责人 | 数据、界面与测试负责人 |
|---|---|---|---|
| 10/23 | T00–T02：环境、6 篇真实文档与采集流程 | 确认环境与 API，审核模块边界 | 审核文章主题、正文与来源 |
| 10/24 | T03–T05：索引、检索、真实 LLM 闭环 | 跑真实 API，检查证据与引用绑定 | 起草演示问题，核对检索结果 |
| 10/25 | T06–T09：网页、回退、扩库、问题集 | 审核集成与失败处理 | 抽查扩库，逐题核对标准答案，验收 UI |
| 10/26 | T10–T12：实测、修复、复现、展示素材 | 解释架构与指标，整合材料 | 组织彩排、截图/录像与测试审核 |
| 10/27 前 | 启动检查与课程安排确认 | 两人能解释完整流程 | 两人能操作并解释失败案例 |

Codex 是实现工具，报告的团队贡献应记录两位成员实际完成的设计、审核、测试和材料工作，不把生成代码自动归为未经参与的个人贡献。

时间不足的缩减顺序：停止扩充文章数量 → 延后多文档演示 → 延后 UI 美化。保留真实资料、向量检索、真实 API、引用、回退与基本测试。API 尚不可用时先交付检索闭环并明确标为部分完成，不能宣称完整 RAG MVP。

## 9. 分轮交给 Codex

共用提示：请同时提供正式 PDF、交接说明与本文件。每轮先盘点工程，执行本轮目标，运行与改动匹配的必要验证，更新清单与历史，再总结；保持小范围可审查提交。未经明确任务不加入高级功能。

### 第一轮：工程盘点与真实数据（T00–T02）

> 你正在实现 MIS2001 的 Apple Support RAG Copilot。请先读 library/ 中的正式课程要求、Project Plan、交接说明与本计划；正式课程要求优先于摘要与开发建议。保持内部 staff 辅助、官方来源、人工审核的定位。本轮只完成 T00–T02：盘点现有工程与环境；优先复用我电脑默认 Python 环境，检查必要依赖，缺什么再补什么，不默认新建环境或升级现有包；建立最简目录、配置示例和依赖；用指定官方 URL 收集并清洗首批 6 篇真实文章，保存快照、元数据、去重与失败日志，并支持手动导入。先用 2–3 页确认解析有效再扩展。不得用模型编写正文替代抓取。核对实际正文、小标题、步骤和关键条件，提交可复现命令与数据样例。网络或访问受限时记录阻塞，保留导入流程并推进其他可做事项。更新 docs/MVP_PLAN_AND_TASKS.md；没有真实证据的任务不得标完成。不要开始写复杂 UI 或高级 RAG 功能。真实 API key 由我在本机配置，你不要输出其值。

### 第二轮：检索（T03–T04）

> 在现有真实文档上完成标题/段落切块、真实 embedding、持久化向量索引和 top-5 检索；不要加入生成器。明确模型输入上限、查询/文档编码方式、归一化与分数定义，保存语料和索引版本清单。输出每个命中的片段、分数、标题与 URL；用普通表述与同义改写问题实测。验证索引重载结果一致、重复执行不重复追加、模型/语料变化不静默混用旧索引。更新 T03–T04 的状态与证据。

### 第三轮：生成与界面（T05–T07）

> 接入一个可配置的真实 LLM API，完成建议回复、上下文内引用 ID、后端源链接映射和证据不足/含混/范围外回退。构建最简 Streamlit staff 界面，显示 suggested response、来源、证据片段、审核提示和异常状态。未配置 key 时仍可调试检索，生成按钮提示配置要求。对 API 使用 mock 的测试必须单独标明，真实端到端成功后才能将 T05 标完成。测试未知引用 ID、空索引、缺 key、超时及 API 错误，保留结果并更新 T05–T07。不要实现自动发送、登录或多轮记忆。

### 第四轮：扩库、评测与演示（T08–T12）

> 闭环可运行后扩展有用官方文章并冻结语料；编写 30 题评估候选，列出依据和答案要点，交给团队人工核对后再计算指标。保存逐题检索、回答、引用及审核结果，分开报告 Hit@5、综合题依据覆盖、回答有据性和回退行为。修复影响当前演示的实际缺陷，按 README 重启复现并准备演示脚本、架构说明、真实统计与失败案例。建立备份录像/已记录结果；若 API 不通，界面不得把回放当作实时生成。更新任务状态、历史、剩余问题和中期材料证据索引。

## 10. 展示与中期报告衔接

展示叙事：客服查资料的困难 → 系统如何检索并给出有据建议 → 真实案例 → 证据不足与失败处理 → 当前覆盖和实测限制。用真实索引/语料统计与逐题结果，不承诺尚未实现的功能。

10/27 后至 11/5 的建议工作：整理已经实现的架构、数据处理、评测和局限；按实际错误改进检索/清洗，再扩展主题。正式文件明确 11/5 提交 PPT 与至少 10 页中期报告（不含 appendix）；prototype demo 是可选，完成 MVP 是用户本次自主目标。中期报告章节包括 title page（course id、group name、member names、sponsor name）、executive summary、TOC、introduction、project background、project description、important achievements、concluding remarks、references、appendix（含 project plan）。scope/schedule/deliverables 如有重大偏离，按正式要求解释并取得 instructor 批准，不将普通实现选择误判为重大变更。不要等报告截止前才补运行记录、截图与分工说明。

## 参考资料

- 用户提供：`MIS2001_Project_Plan_RAG Support Team.pdf`。
- 用户提供：`MIS2001_Apple_Support_RAG_Handoff_20261023(1).md`。其中课程节点为交接摘要；与后补正式文件冲突时以正式文件为准，最新公告仍需另行核对。
- 用户后补：`MIS2001 Term project requirements 20260907.pdf`，已于 2026-10-23 核对原文。
- Streamlit official tutorial: https://docs.streamlit.io/get-started/tutorials/create-an-app
- Sentence Transformers semantic search: https://www.sbert.net/examples/sentence_transformer/applications/semantic-search/README.html
- 第 5 节 Apple 官方文章链接：已通过检索核对候选入口，实际采集与清洗质量待 Codex 验证。

## 2026-10-23 本轮实施补充（T00–T02）

完整盘点、实际命令/退出码、数据统计、验证边界和下一轮衔接见 `docs/ROUND_1_RESULTS.md`。数据契约及导入操作见 `docs/DATA_PREPARATION.md`；六篇人工抽查点见 `docs/ARTICLE_REVIEW.md`。

- 自动采集默认阻止；未提供适用采集/复制/处理许可，不以 robots 允许或公开可见推定权限，也不用手工复制绕过限制。
- 最小外部步骤：提供可合法用于本项目的六篇官方本地正文及实际来源/许可依据，或解决适用自动采集许可；先三篇再六篇逐篇核验。无须提供聊天中的 API key。
- T00 中 API/模型可达性待下一轮选择端点后验证；本轮无 LLM key 不阻塞数据工具。T03–T04 尚未开始，应在真实语料验收后衔接，保留 doc_id/来源映射和语料版本。

### 2026-10-23 后续澄清：手动获取

用户确认没有 Apple 单独许可。前述“最小外部步骤”的手动路径不再以提供官方
许可为工程前提：应如实记录公开页面的手动获取方式、来源及本地课程用途，
不虚构许可；这也不代表所有复制、发布或 RAG 用途均已获准。自动 HTTP 入口
仍保留访问规则限制。具体三篇试点保存文件名、命令和检查顺序见
`docs/MANUAL_COLLECTION_ZH.md`；手动 CLI 新增 `--provenance`，兼容旧参数。

T02 保持阻塞：等待真实本地文件及正文验证，当前正文仍为 0 篇。保留一个长期
有用的回归测试文件；合成临时样本自动清理，编译缓存可清理。历史阻塞日志
和测试证据保留，不改写成成功采集记录。

### 2026-10-24 最新进展

上段为 10/23 历史记录。现已收到并导入六篇真实 HTML，无需改名；标题与
canonical URL 对应，结构与去重实测通过。T02 当前为待验收，剩余六篇团队
人工抽查，具体证据和命令见 `docs/MANUAL_IMPORT_RESULTS_20261024.md`。

### 公开版本与本地记录

本清单公开项目进度和实现说明，不包含学号或个人姓名。文中 `library/`、
`evidence/`、`data/sources.jsonl`、原始/清洗正文和 `docs/ROUND_1_RESULTS.md`
均为被忽略的本地记录路径，公开检出不附带这些文件。原始完整版本及本轮
文档备份保留在本地 `evidence/public_prep_20261024/originals/`。
公开复现步骤以 README 为准；不要将本地记录路径当成公开可下载附件。

### 最新结论覆盖旧等待事项

上文 10/23–10/24 的“等待六篇人工审核才能进入 T03”属于历史记录，现以用户
本轮说明和最终 Review 为准。六篇 AI 审查通过，用户检查了整个 Change password
网页并反馈无问题；其余五篇不冒称人工全文审核。链接前空格是非阻塞备注，
本轮未修改冻结正文。T03/T04 已完成，T05–T07 尚未开始；LLM 供应商仍待定。
