# T03–T04：本地索引与证据检索 — 2026-10-24

本轮已在现有 `feature/retrieval-index` 分支实现并验证本地 embedding、持久化
FAISS 精确索引及 CLI 证据查询。没有生成式 LLM、网页界面、重排或记忆。

## 审查归档与冻结版本

- 实际收到的文件是 `MIS2001_Six_Articles_AI_Review_20261024.md`；
  [原样副本](reviews/DATA_REVIEW_ORIGINAL_20261024.md)逐字节复制前后 SHA-256
  均为 `7d2681c382beb23b502059340d753bc592174bf6a40bdceffb25f5bec34e5303`。
- [最终归档](reviews/DATA_REVIEW_FINAL_20261024.md)按用户明确要求修正人工
  抽查范围，所以其修订后哈希不同，不能冒称与原文件相同。
- 用户检查了 Change your Apple Account password 整个网页并反馈无问题，
  不是仅一个小节；其余五篇没有据此获得人工全文审核结论。
- 六篇当前正文、快照哈希及 URL 均与原报告记录一致；未重新抓取、修复空格或
  重导入。六条 `human_review: pending` 历史字段保持不变。
- T02 按软件校验、六篇 AI 内容核对、上述用户人工检查完成本阶段验收。

## 环境与实现

统一复用用户现有 conda **rag**（Python 3.11.5）。已有 NumPy 1.26.4、PyTorch
2.3.1+cu121、sentence-transformers 5.0.0、transformers 4.54.1、tokenizers
0.21.4、FAISS CPU 包 1.11.0.post1（模块版本 1.11.0）。全部实际加载通过，
本轮未安装或升级包。BeautifulSoup 4.8.2 通过原有测试，依赖声明兼容该版本。
编码固定 CPU、4 线程，batch size 16。首次沙箱模型下载因代理拒绝失败，经批准
在沙箱外成功下载；后续检查、构建和查询只读本地资源，无付费 API 或 key。

模型为 `sentence-transformers/all-MiniLM-L6-v2`，固定 revision
`c9745ed1d9f207416be6d2e6f8de32d1f16199bf`。只加载本地 safetensors，
禁用 remote code；资源文件逐个绑定 SHA-256。真实编码 smoke 为 2×384。
选择与编码方式参考[模型卡](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
和[官方语义相似度说明](https://sbert.net/docs/sentence_transformer/usage/semantic_textual_similarity.html)。

## 切块、索引与版本

- 仅从 `data/sources.jsonl` 的六条活动记录读语料，复用 `check_record`，不遍历
  clean 目录。三个历史清洗版本保留，不重复入库。
- 按 Markdown 标题层级形成章节，优先在段落/步骤边界截断；超长段落按真实
  tokenizer 字符 offsets 分割，记录 start/end 与正文哈希。短章节前提可在后续
  chunk 重复携带，context 上限 48 tokens；超长前提仍保留在正文块中。
- 每个模型输入包括文章标题、章节、可选前提与原文片段。实际 BertTokenizerFast
  含特殊 token 计数：模型上限 256，配置上限 240；overlap 最多 32 个正文
  wordpiece tokens，短段或需要保证前进时可减少。最终 56 块，最大 233 tokens。
  不静默截断，标题/前提使输入无法容纳下一 token 时明确报错。
- 稳定 chunk ID 绑定文档 ID、当前正文版本、章节/块序号及模型输入指纹；保存
  原文片段、章节、offset、标题与真实来源 URL。
- 文档和查询均用无额外 prompt 的 SentenceTransformer.encode，生成 L2
  归一化 float32 384 维向量。`FAISS IndexFlatIP` 是精确检索；归一化向量的
  内积等于余弦相似度，分数不是答案正确概率。
- 索引 manifest 保存模型/资源版本、维度、实际包版本、编码和切块配置、语料与
  来源映射哈希、文件哈希。查询前重验；语料/映射/模型/切块变化要求 `--rebuild`。
  不变的构建直接验证并复用现有索引；重建写新 generation，最后发布 manifest。
  老 generation 仍是本地历史，不会被追加进当前检索。

## 运行方法

项目根目录 PowerShell：

```powershell
conda activate rag
python -B -m src.check_environment
python -B -m src.embedding download
python -B -m src.embedding check
python -B -m src.retrieval build
python -B -m src.retrieval inspect
python -B -m src.retrieval query --question "How do I cancel an Apple subscription on my iPhone?"
python -B -m src.retrieval query --question "What connections are needed for automatic iCloud backups?" --json
python -B -m src.evaluate_retrieval
python -B -m unittest discover -s tests -v
```

下载只需执行一次。`inspect` 会从磁盘重载并校验索引；`query` 省略 question
时提示输入英文问题，默认 top-5。每项输出排名、分数、块/文档 ID、章节、
原文片段、文章标题和 URL；不生成客服答案。显式重建：
`python -B -m src.retrieval build --rebuild`。

## 实际测试结果

模型加载及 2 条真实编码约 30.75 秒；首次构建共约 14.43 秒（含该进程模型加载），
6 篇、56 块、384 维。重复构建为 cached，仍为 56 块，约 25.82 秒。
13 个问题的评测进程含模型加载约 23.28 秒；重载后同一查询结果完全一致。
冷启动/系统缓存影响这些耗时，不将其当作通用性能保证。

12 个有预期依据的开发问题（6 直接 + 6 同义改写），预期文档均排名第 1，
因此本集合文档 Hit@5 为 12/12。不是盲测，不是客服答案准确率或实际客户分布。

| 依据文档 | 直接问题首名分数 | 同义问题首名分数 | 两题预期文档排名 |
|---|---|---|---|
| 101567 修改密码 | 0.749453 | 0.589165 | 1 / 1 |
| 102656 忘记密码 | 0.774203 | 0.707739 | 1 / 1 |
| 108366 iCloud 备份 | 0.751574 | 0.545082 | 1 / 1 |
| 118223 退款 | 0.817899 | 0.732426 | 1 / 1 |
| 118428 取消订阅 | 0.886930 | 0.535817 | 1 / 1 |
| 118574 恢复等待 | 0.846194 | 0.570313 | 1 / 1 |

实际范围外例：问 MacBook 屏幕维修价格，首名却为退款文章，分数 0.250196。
六篇没有维修价格依据；当前纯检索仍返回近邻，不具备证据不足回退，不能拿这些
片段生成维修报价。此例单列，不计入 12 题命中率。后续 T06 需处理，不能用一个
未经校准的分数阈值冒充本轮已经解决。

40 项离线测试通过（原有 29 + 新增 11）。公开测试只用合成文本、固定测试向量
和测试索引替身，不下载模型，也不声称替身证明真实 embedding。真实模型与
FAISS 验证独立运行。覆盖长度与尾部保留、稳定 ID、来源、空语料/非法查询、
重复构建、重载、损坏文件、语料/映射/模型/切块版本不匹配。

## 文件与证据边界

源码：`src/embedding.py`、`src/retrieval.py`、`src/evaluate_retrieval.py`。
配置与无正文问题集：`config/retrieval.json`、`evaluation/retrieval_cases.json`。
本地资源 `models/`、索引和 chunk 正文 `data/index/`、原始运行记录
`evidence/retrieval_20261024/` 均被忽略；公开仓库不附带这些文件或 Apple 全文。
逐题完整 top-5、分数、片段与耗时在本地 `evaluation.json`；另有 model_check.txt、
build.txt、repeat_build.txt、cli_query.txt、tests.txt、review_binding.json。

原始 HTML、冻结语料、历史清洗版本及已有证据按本轮前的哈希清单复核。
Review 原样副本与用户修订件分别保存，不用实施结果覆盖审查报告。
最终核对：69 个受保护原文件均未变化，9 个清洗版本全部保留；40 项测试在
只含公开候选文件的临时副本中再次通过，未导入 torch、sentence-transformers
或 FAISS，也没有模型/真实语料/历史证据可用。28 个公开候选文件的定向扫描
未发现真实凭据、学号、本机绝对路径或断开的公开文档链接；模型、索引、chunk
正文和运行证据的 Git 忽略探针通过。
T03、T04 完成本轮验收；T00 embedding 可用性通过，LLM API 仍待用户咨询老师。
当前复用已有功能分支；不执行 add、commit 或 push。
