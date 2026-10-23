# 首批六篇文章：手动保存与本地导入

## 当前决定

2026-10-23：用户确认没有 Apple 单独许可。ChatGPT 的网页工具能够读取
Apple Support 页面，但其返回结果不等于本地原始 HTML 快照，也不等于全文
复制或重新发布的授权。低频访问能减少负载，不能单独解决网站条款和用途条件。

前一轮把所有手动导入也写成必须取得官方许可，措辞过于绝对。现在手动入口
只要求如实说明来源、获取方式和用途；不要求填写不存在的许可。自动 HTTP
采集仍保持原限制。手动保存不构成绕过验证码、登录或访问拒绝的理由，也不
自动解决全文再发布或后续 RAG 用途的适用条件。

## 先保存三篇

请在普通浏览器中打开以下三个公开页面。页面可正常阅读后，使用 Ctrl+S，
保存类型优先选择“网页，仅 HTML”，存入项目的 `data/manual/`：

| 保存文件名 | 官方页面 | 主题 |
|---|---|---|
| `118428.html` | https://support.apple.com/en-us/118428 | Subscriptions |
| `101567.html` | https://support.apple.com/en-us/101567 | Apple Account |
| `108366.html` | https://support.apple.com/en-us/108366 | iCloud |

保存前展开设备分支等相关内容，并保留原始文件及版权通知。不要把登录页面、
错误页面或浏览器“查看源代码”窗口当成正文。如果保存类型只有完整网页，也
可保留 HTML 与附属资源目录；解析器不执行其中脚本。若 HTML 没有文章内容，
再考虑手动文本导入，保留标题、小标题、步骤与注意事项，不能用模型摘要替代。

不要先保存成 PDF：当前导入器不支持 PDF。浏览器无法正常访问时，记录具体
错误，不绕过访问限制。不把完整正文上传到公开仓库或公开下载页。

## 保存后导入

在项目根目录 PowerShell 中运行以下命令。来源说明仅在确实这样获取文件时使用：

```powershell
python -B -m src.ingest import --file data/manual/118428.html --format html --url https://support.apple.com/en-us/118428 --topic subscriptions --provenance "Saved manually from the public official page for local non-commercial coursework; no individual Apple permission obtained"
python -B -m src.ingest import --file data/manual/101567.html --format html --url https://support.apple.com/en-us/101567 --topic apple_account --provenance "Saved manually from the public official page for local non-commercial coursework; no individual Apple permission obtained"
python -B -m src.ingest import --file data/manual/108366.html --format html --url https://support.apple.com/en-us/108366 --topic icloud --provenance "Saved manually from the public official page for local non-commercial coursework; no individual Apple permission obtained"
python -B -m src.ingest validate
```

也可以只保存文件后交回本任务，由开发协作者执行导入、检查并修正真实 HTML
的解析兼容性。当前真实页面提取尚未验证，不能保证浏览器保存后直接导入成功。

先对照来源页面、raw 快照和 clean 文本核对前三篇的小标题、步骤、条件、链接
与结尾，确认未混入导航/反馈内容，然后再保存：

| 保存文件名 | 官方页面 | 主题 |
|---|---|---|
| `118223.html` | https://support.apple.com/en-us/118223 | Subscriptions |
| `102656.html` | https://support.apple.com/en-us/102656 | Apple Account |
| `118574.html` | https://support.apple.com/en-us/118574 | Apple Account |

六篇逐项抽查点见 `docs/ARTICLE_REVIEW.md`。2026-10-24 已收到六篇用户保存的
HTML，按页面 canonical URL 和标题识别，原文件名无需更改。已完成三篇试点、
扩至六篇及重复导入验证；六篇结构检查通过，均待团队人工核验。

当前可直接运行 `python -B -m src.ingest validate` 和
`python -B -m src.check_corpus` 检查已入库数据。后续若继续使用浏览器默认
文件名，可用 `python -B -m src.import_saved --limit 6 --provenance "实际获取说明"`
导入，不必逐个填写文件名。原始样本与当前文本映射见
`evidence/manual_six_20261024.json`。

## 测试与清理

保留 `tests/test_ingest.py`：该单文件覆盖正文结构、去重、元数据、失败处理，
后续修改真实页面解析器时需要复测。合成样本在测试临时目录中自动删除，不会
混入正式语料。可删除 Python 的 `__pycache__` 编译缓存；保留实际测试结果和
失败日志作为课程证据，不能因失败而删除记录。
