# 小组 GitHub 协作指南

适用于 `xulf7`、`JunjieLiuCUHKSZ` 和 `Lawrenceluo827`。
`xulf7` 负责仓库维护和合并协调；开始前先在群里确认各自负责的任务。

**日常修改在自己的分支上做，提交 PR 给协作者审查。不要直接改 main，
也不要自行点击 Merge 合并到 main；由 xulf7 确认后统一合并。**

## 1. 开始修改前

在 VS Code 打开项目，检查左下角的分支名称。没有未保存/未提交的修改时，
可在终端依次运行：

```powershell
git switch main
git pull --ff-only origin main
git switch -c docs/your-task
```

把 `docs/your-task` 换成自己的分支名：文档用 `docs/...`，功能用
`feature/...`，修复用 `fix/...`。一个分支尽量只做一件事。
如果已有未提交修改，或提示冲突/无法切换，先保留现场并找组员一起处理。

## 2. 在 VS Code 提交并上传

1. 修改并保存文件，打开左侧 **Source Control（源代码管理）**。
2. 点开 Changes 中的文件查看差异；确认后点击文件旁的 **+**，加入暂存区。
3. 输入简短的提交说明，例如 `docs: clarify setup instructions`，点击 **Commit**。
4. 点击 **Publish Branch**（首次发布分支）或 **Push**，上传到 GitHub。

Commit 保存到本机，Push 上传分支；它们都不等于合并到 main。
不要把无关文件一起提交，也不要上传 `.env`、密钥、课程资料、Apple 全文、
模型、索引或运行日志；提交前看一遍文件列表。

## 3. 在 GitHub 提交 PR

1. 打开仓库，点击 **Compare & pull request**；或进入 Pull requests → New pull request。
2. 确认 **base 是 main，compare 是自己的分支**。
3. 写明改了什么、对应任务、如何检查，以及还没完成的内容。
4. 创建 PR，在 Reviewers 中请另一位协作者审查，并在群里提醒。
5. 根据意见修改，在同一分支继续 Commit、Push；原 PR 会自动更新。
6. 等 `xulf7` 确认并合并。合并后，下次任务重新更新 main，再建新分支。

PR 示例：`T07: improve evidence display`；说明可写“调整证据卡片，已运行相关
测试；请检查链接和展开效果”。有冲突或审查意见时先处理，不急着合并。

## 4. 在自己电脑运行

`rag` 是 xulf7 本机已有的环境，**组员不需要使用相同的环境名称**。
使用自己的 Python 3.11 环境，在项目根目录按依赖文件安装：

```powershell
python -m pip install -r requirements.txt
# 需要运行本地 embedding / 检索时再安装：
python -m pip install -r requirements-retrieval.txt
python -B -m src.check_environment
python -B -m unittest discover -s tests -v
```

若已有环境，先检查依赖，避免随意升级。模型、语料、索引与启动步骤见
[README](README.md)；公开仓库不附带这些本地数据，按 README 自行准备并构建。
只改文档无需安装全部运行依赖；改代码后请运行相关测试，在 PR 里写明结果。

使用自己的 GitHub/Git 身份。不强推、不改写共享历史；不确定的 Git 操作先问
组员。使用编程智能体时先检查它的改动，提交、推送或合并须由成员明确决定。
