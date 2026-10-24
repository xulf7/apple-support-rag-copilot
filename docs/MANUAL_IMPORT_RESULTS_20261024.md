# 手动页面导入结果 — 2026-10-24（北京时间）

本文为公开结果摘要。下列 `evidence/` 和语料路径仅指本地记录，公开仓库不附带
原始执行日志、课程材料或 Apple 全文；公开复现步骤以 README 为准。
本文保留导入阶段历史；[最新检索结果](RETRIEVAL_20261024.md)已完成 T03/T04。
六篇 AI 审查及用户对 Change password 整页的检查已支持 T02 本阶段验收；
下文“尚未开始/待人工验收”等措辞描述的是当时状态。

六篇用户保存的真实 Apple Support HTML 已全部导入，原文件名和文件字节均保留。
通过 HTML 的 canonical URL 和 h1 与种子清单匹配，不依赖文件名中的数字。
本轮没有网络请求，没有新增依赖，也没有开始 embedding、检索或生成。

## 实施和实际验证

- 真实 HTML 没有 `main/article` 标签，正文位于 `#content > #sections`；已适配。
- 修复独立操作链接丢失目标 URL、步骤内多段文字粘连的问题；移除设备选择控件，
  保留所有设备操作分支、前提条件、地区限制和原文免责声明。
- 保存原始 HTML 字节快照、清洗 Markdown、正文/快照 SHA-256 和来源 JSONL。
  导入方式为 `manual`，实际获取说明明确没有 Apple 单独许可。
- `published_at` 来自页面实际显示文本；`fetched_at` 为实际导入 UTC 时间。
  最终 URL 来自保存 HTML 的 canonical，不声称本轮重新验证了在线重定向。

执行命令（项目根目录 PowerShell）：

```powershell
python -B -m src.import_saved --limit 3 --provenance "User confirmed manually saving these public Apple Support pages for local MIS2001 coursework; no individual Apple permission obtained" --report evidence/manual_pilot_final_20261024.json
python -B -m src.check_corpus --report evidence/pilot_quality_20261024.json
python -B -m src.import_saved --limit 6 --provenance "User confirmed manually saving these public Apple Support pages for local MIS2001 coursework; no individual Apple permission obtained" --report evidence/manual_six_20261024.json
python -B -m src.import_saved --limit 6 --provenance "User confirmed manually saving these public Apple Support pages for local MIS2001 coursework; no individual Apple permission obtained" --report evidence/manual_repeat_20261024.json
python -B -m src.check_corpus --report evidence/corpus_quality_20261024.json
python -B -m src.ingest validate
python -B -m unittest discover -s tests -v
```

| 检查 | 真实结果 | 证据 |
|---|---|---|
| 三篇试点 | 3 成功、0 失败；3/3 正文比对通过 | manual_pilot_final_20261024.json、pilot_quality_20261024.json |
| 扩至六篇 | 新增 3、缓存 3、失败 0 | manual_six_20261024.json |
| 六篇重复导入 | 缓存 6、新增 0、失败 0；当前仍为六条文档 | manual_repeat_20261024.json |
| 六篇真实结构比对 | 152 段正文顺序、52 个标题顺序、59 个编号步骤、33 个来源链接均通过；未检出已知导航/反馈/页脚残留 | corpus_quality_20261024.json |
| 元数据及文件完整性 | 6 篇通过，ID/正文哈希无重复，6 篇人工审核 pending | data/sources.jsonl；corpus_quality_20261024.json |
| 回归测试 | 20/20，通过 | manual_real_tests_20261024.txt |

表内 JSON/TXT 证据均位于 `evidence/`。最初三篇试导入后继续改进操作链接等
细节，因此保留了历史 Markdown 版本；正式下游应只读取 `data/sources.jsonl`
中的当前 text/text_path，不能遍历 clean 目录把旧版本重复入库。原始快照与
旧清洗版本按既有版本策略保留，重复文档检查针对当前 JSONL。

## 六篇清单

| ID | 标题 | 主题 | 正文字符数 | 页面显示日期 |
|---|---|---|---|---|
| 118428 | Cancel a subscription from Apple | subscriptions | 6615 | September 29, 2026 |
| 101567 | Change your Apple Account password | apple_account | 3304 | September 29, 2026 |
| 108366 | How to back up your iPhone or iPad with iCloud | icloud | 2013 | September 24, 2026 |
| 118223 | Request a refund for apps or content that you bought from Apple | subscriptions | 3416 | September 17, 2026 |
| 102656 | If you forgot your password and can’t sign in to your Apple Account | apple_account | 6365 | October 05, 2026 |
| 118574 | What to expect during account recovery | apple_account | 4262 | October 05, 2026 |

原文件名 → 文章 → snapshot/text 路径映射见 `evidence/manual_six_20261024.json`。
原文件 SHA-256 清单见 `evidence/manual_originals_20261024.json`。

## 剩余验收

自动化检查证明本地来源映射、正文信息保留和去重行为，不等于团队人工认可
操作/政策表述。六篇均保持 `human_review: pending`；T02 从阻塞改为待验收。
请按 `docs/ARTICLE_REVIEW.md` 的六篇逐项检查点，核对当前 raw/clean 中的
关键条件、适用版本和步骤，记录审核人、日期、内容哈希和通过/修正结果。

T00 的 API/模型可达性仍待验收；T03–T04 尚未开始。后续用当前 JSONL 构建
切块与索引，保留 doc_id 到标题、URL 的映射及语料版本。无需更改原文件名。
