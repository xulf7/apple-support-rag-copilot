# 资料与运行指南

本文供需要运行或维护程序的组员使用。只做报告写作时，先读[架构说明](ARCHITECTURE.md)。

## 1. 首批资料来自哪里

目前使用六篇 Apple 官方英文支持文章，语言地区为 `en-us`。下表使用中文简称，
原始英文标题和网址可在[种子清单](../data/seeds.json)核对。它们是首批资料范围，
不构成程序中的固定主题白名单。

| 主题 | 官方来源（中文简称） | 核对重点 |
|---|---|---|
| Apple 账户 | [修改账户密码](https://support.apple.com/en-us/101567) | 可信设备前提、设备分支、安全延迟 |
| Apple 账户 | [忘记密码及无法登录](https://support.apple.com/en-us/102656) | 不同恢复方式及其条件 |
| Apple 账户 | [账户恢复期间的预期情况](https://support.apple.com/en-us/118574) | 等待、使用设备的限制及取消恢复的条件 |
| 订阅 | [取消订阅](https://support.apple.com/en-us/118428) | 设备步骤、试用期限和收费方 |
| 订阅 | [申请购买内容退款](https://support.apple.com/en-us/118223) | 资格、待处理付款、地区及到账限制 |
| iCloud | [备份 iPhone 或 iPad](https://support.apple.com/en-us/108366) | 手动/自动备份、网络、电源、锁屏和空间条件 |

六篇已通过软件及 AI 内容审查，并已人工核对修改密码整页。
原始审查文件由维护者本地归档；写作所需的来源、方法、结果和剩余事项已列在公开文档中。

## 2. 先检查环境

使用 Python 3.11，在项目根目录运行。维护者的环境名是 `rag`，组员可以用自己的名称。
已有环境先核对依赖，不必批量升级。

```powershell
python -B -m src.check_environment
# 自己的环境缺少项目依赖时安装：
python -m pip install -r requirements.txt
# 要使用真实本地模型与向量检索时再安装：
python -m pip install -r requirements-retrieval.txt
```

没有资料、模型或 API key，也可以运行合成测试：

```powershell
python -B -m unittest discover -s tests -v
# 已安装 Node 时可运行前端逻辑测试，无需 npm 安装：
node --test tests/test_frontend.cjs
```

## 3. 在自己的电脑准备资料

GitHub 不附 Apple 全文。通过正常浏览器访问允许阅读的官方页面，保存 HTML 到
`data/manual/`，原文件名不用改成文章编号。导入器按 canonical URL（页面声明的规范网址）
和文章标题识别文件。不要保存登录页或错误页，也不要绕过访问限制。

先保存“取消订阅、修改账户密码、iCloud 备份”三篇（种子清单的前三条），
导入并抽查，再保存其余三篇：

```powershell
python -B -m src.import_saved --limit 3 --provenance "按实际情况填写获取方式和用途"
python -B -m src.ingest validate
python -B -m src.check_corpus
# 检查前三篇后，保存其余页面再运行：
python -B -m src.import_saved --limit 6 --provenance "按实际情况填写获取方式和用途"
python -B -m src.ingest validate
python -B -m src.check_corpus
```

抽查标题、步骤顺序、设备分支、前提条件、注意事项和链接是否保留，是否混入导航或反馈。
`validate` 检查身份、文件和哈希；`check_corpus` 还比较 HTML 正文结构。
纯文本导入只做适用检查，不会冒称通过 HTML 比对。空语料或检查失败会返回非零退出码。

如果只有允许使用的 UTF-8 纯文本，可保留标题、小标题、步骤和条件后手动导入，
不使用模型摘要代替官方正文。参数见 `python -B -m src.ingest import --help`。

## 4. 导入后文件放在哪里

| 本机路径 | 保存什么 |
|---|---|
| `data/manual/` | 自己保存的原始页面，导入时不改名 |
| `data/raw/` | 导入器保留的原始快照 |
| `data/clean/` | 清洗后的正文，历史版本也会保留 |
| `data/sources.jsonl` | 每篇当前有效资料的记录：标题、网址、正文、版本哈希、原文与清洗文件路径 |
| `evidence/` | 检查命令自动生成的本次报告和日志，不参与客服检索 |

下游只读取 `data/sources.jsonl` 中的当前记录，不遍历 clean 目录，以免重复使用历史版本。
同一资料重复导入不会追加重复记录；正文变化会更新活动版本并保留旧文件。

这些路径在公开仓库中被忽略。新电脑导入自己的资料后会生成对应文件，
不需要取得维护者过去某次导入的 JSON 报告。手动保存也不代表取得全文再发布许可。

## 5. 建立索引并启动

首次准备本地模型需要下载；其余命令使用本地资源。当前资料和提问均以英语为主，
因此下面的示例问题保留英语。

```powershell
python -B -m src.embedding download
python -B -m src.embedding check
python -B -m src.retrieval build
python -B -m src.retrieval query --question "How do I cancel an Apple subscription on my iPhone?"
python -B -m src.web --port 5000
```

打开 `http://127.0.0.1:5000`。模型和索引会在应用启动时加载，后续请求复用。
真实生成服务还未接入，当前页面展示真实检索证据及生成未配置状态。

资料、模型或切块配置变化后，先停止服务，检查资料，显式重建后重启：

```powershell
python -B -m src.ingest validate
python -B -m src.retrieval build --rebuild
python -B -m src.web --port 5000
```

## 6. 检查检索结果和管理留档

准备好本地资料、模型和索引后，可以运行开发问题集：

```powershell
python -B -m src.evaluate_copilot --extra-cases evaluation/review_cases.json
```

问题集保留题目和适用的预期文档标签。评测分别报告检索排名、生成未配置时的行为、
资源复用，并把真实 LLM 语义质量列为待验证。返回成功不等于回答正确率通过。

`evidence/` 是程序输出的本机运行记录；`dev_records/` 是维护者的工程调试和历史归档。
两者均不上传 GitHub。组员写作直接使用[架构说明](ARCHITECTURE.md)中的结果摘要；
需要某次原始运行材料时再由维护者提供。新的每轮调试总结放入 dev_records，不向 docs 累加报告。

未来真实 LLM 的供应商和协议确认后再接适配器。当前填入 key 也不会启用真实生成；
不要把 key 写进聊天或 Git。服务读取进程环境变量，不自动加载 `.env`。
