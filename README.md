# PatchPath

帮助想参与开源项目的人更快理解 issue、定位代码、写出更容易被接受的 PR。

## Why This Exists

能自动开 PR，不等于能稳定贡献被合并的 PR。

快速成长的 GitHub 项目仍然需要人，主要卡在这些地方：

1. **issue 本身经常不清楚**

   很多 issue 不是“这里有 bug，改这一行”，而是复现不完整、环境不明、预期行为不清，甚至和已有设计冲突。贡献者需要先判断问题是否真实、是否值得修、该怎么和 maintainer 对齐。

2. **PR 的难点不是写 diff，而是写对 diff**

   自动 agent 可以生成代码，但它不一定理解项目边界、兼容性、性能影响和维护成本。开源项目真正怕的是“看起来能跑，但半年后变成负债”的 patch。

3. **maintainer 信任的是贡献者，不只是代码**

   一个好贡献者会解释思路、补测试、回应 review、根据反馈修改、后续维护。自动 PR 如果没人负责，维护者反而要花更多时间审。

4. **大量贡献不是“修 bug”**

   还有测试补齐、文档、示例、错误信息优化、issue triage、复现脚本、性能 benchmark、迁移指南。这些非常适合人成长，也很难完全自动化。

5. **自动工具会增加 PR 数量，但不一定减少维护压力**

   项目越火，低质量 PR 越多。维护者更需要的是能理解上下文的人，把问题拆清楚、做小而准的改动。

所以本项目不做“替人自动开 PR”的机器人，而做：

> 帮助人类贡献者更快理解 issue、定位代码、写出可被接受 PR 的开源贡献助手。

第一阶段目标是把新人最卡的前 70% 路径压缩掉：选题、理解、定位、验证、表达。

## Target Users

- 想通过开源贡献提升工程能力的开发者。
- 已经会基础编程，但面对真实项目 issue 不知道从哪里开始的人。
- 想筛选适合自己能力范围的 issue，而不是盲目接高风险任务的人。

## MVP

输入：

- GitHub repo URL
- GitHub issue URL 或 issue number

输出一份贡献作战单：

- 项目是什么
- issue 在解决什么
- issue 是否清楚，缺哪些信息
- 是否适合当前贡献者尝试
- 相关文件 Top-K
- 推荐阅读顺序
- 可能修改点
- 验证命令或复现方式
- 风险点
- 可以发给 maintainer 的澄清问题或 comment 草稿
- trace：工具查了什么、为什么选这些文件

## Non-Goals

- 第 1 个月不自动生成 patch。
- 第 1 个月不自动开 PR。
- 第 1 个月不做复杂 Web UI。
- 第 1 个月不追求替代 SWE-agent、OpenHands、AutoCodeRover。

## Production Direction

这个项目按生产目标推进，不按学习 demo 推进。

第一版的生产质量不来自功能数量，而来自：

- 输出有证据引用。
- 文件定位可评测。
- 建议能被人复核。
- 每次分析有 trace。
- 能用真实 issue 形成回归集。

## Current Status

Status: M1 CLI vertical slice verified

已完成：

- 接受 `Plan -> Retrieve -> Inspect -> Brief -> Guard` Agent runtime。
- 建立 `docs/eval-set-v0.md`，包含 5 个 `pallets/click` gold issues。
- 完成 Tool Execution retrieval 实验，并将 V1 默认检索更新为 `rg + CodeGraph + heuristics`。
- 实现最小 CLI：

```text
patchpath analyze --repo <repo-url-or-path> --issue <issue-url-or-number>
```

- 在本地 `pallets/click` checkout 上跑通 5 个真实 issue，5/5 gold source files 进入 Top-5。
- brief 的前四个说明字段必须由 DeepSeek 生成；没有 `DEEPSEEK_API_KEY` 时命令会失败。
- CodeGraph 现在是默认检索增强：CLI 会在目标仓库初始化/查询 CodeGraph，并把结构命中写入 trace。
- 推荐阅读顺序和可能修改点由 LLM 基于 Top-K 文件与 evidence 改写。

下一步是增加跨仓库 eval，不要先扩大到自动 patch 或 Web UI。

## Project Map

- [AGENTS.md](AGENTS.md): 仓库级工作规则。
- [ARCHITECTURE.md](ARCHITECTURE.md): 顶层架构地图。
- [docs/index.md](docs/index.md): 文档入口。
- [docs/project-map.md](docs/project-map.md): 代码和验证地图。
- [docs/product-specs/mvp.md](docs/product-specs/mvp.md): MVP 产品规格。
- [docs/eval-set-v0.md](docs/eval-set-v0.md): 第一组真实 issue 样本。
- [docs/design-docs/tool-execution-retrieval-experiment.md](docs/design-docs/tool-execution-retrieval-experiment.md): Tool Execution 检索实验。
- [docs/exec-plans/active/day-01-bootstrap.md](docs/exec-plans/active/day-01-bootstrap.md): 当前执行计划。
- [docs/reviews/m1-click-3502-brief.md](docs/reviews/m1-click-3502-brief.md): 第一份生成 brief 的轻量 review。

## Verification

Setup:

```bash
uv sync --extra dev
source .venv/bin/activate
cp .env.example .env
```

Edit `.env`:

```env
DEEPSEEK_API_KEY=<your-key>
PATCHPATH_LLM_MODEL=deepseek-v4-flash
```

Checks:

```bash
./scripts/check-docs.sh
pytest
patchpath analyze --repo ../click --issue pallets/click#3502
```

`.env` is git-ignored. The LLM only writes concise Chinese descriptions for
project summary, issue summary, clarity, suitability, reading order, and likely
change points. File recommendations still come from traced `rg + CodeGraph +
heuristics` evidence.

CodeGraph writes `.codegraph/` in the analyzed target repository; that directory
is git-ignored here and should not be committed.
