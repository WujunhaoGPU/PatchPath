# PatchPath

自动分析真实 GitHub 项目和 issue，并用教练式指导帮助程序员提升工程能力。

## Why This Exists

能自动开 PR，不等于能训练出可靠的工程判断力。

程序员想通过真实开源项目成长，主要卡在这些地方：

1. **陌生项目很难进入**

   真实项目有历史包袱、目录约定、隐含设计和测试习惯。用户常常还没开始改代码，就已经卡在“这个项目到底怎么运转”。

2. **issue 本身经常不清楚**

   很多 issue 不是“这里有 bug，改这一行”，而是复现不完整、环境不明、预期行为不清，甚至和已有设计冲突。贡献者需要先判断问题是否真实、是否值得修、该怎么和 maintainer 对齐。

3. **PR 的难点不是写 diff，而是写对 diff**

   自动 agent 可以生成代码，但它不一定理解项目边界、兼容性、性能影响和维护成本。开源项目真正怕的是“看起来能跑，但半年后变成负债”的 patch。

4. **maintainer 信任的是贡献者，不只是代码**

   一个好贡献者会解释思路、补测试、回应 review、根据反馈修改、后续维护。自动 PR 如果没人负责，维护者反而要花更多时间审。

5. **大量贡献不是“修 bug”**

   还有测试补齐、文档、示例、错误信息优化、issue triage、复现脚本、性能 benchmark、迁移指南。这些非常适合人成长，也很难完全自动化。

6. **自动工具会增加 PR 数量，但不一定提升能力**

   项目越火，低质量 PR 越多。用户真正需要的不是一段看似能跑的代码，而是理解上下文、拆清问题、做小而准改动的能力。

所以本项目不做“替人自动开 PR”的机器人，而做：

> 自动分析驱动的开源实战教练：帮助程序员通过真实 GitHub 项目和 issue，训练项目理解、问题定位、修改推理、测试验证和维护者沟通能力。

第一阶段目标是把新人最卡的前 70% 路径压缩掉：项目理解、issue 拆解、代码定位、修改规划、验证和沟通。

## Target Users

- 想通过真实开源项目提升工程能力的开发者。
- 已经会基础编程，但面对真实项目 issue 不知道从哪里开始的人。
- 想在自动分析结果上学习判断过程，而不是只拿最终答案的人。
- 想筛选适合自己能力范围的 issue，并在贡献过程中形成可迁移方法的人。

## MVP

输入：

- GitHub repo URL
- GitHub issue URL 或 issue number

输出一份开源贡献训练单，包含自动分析结果和教练式指导：

- 项目是什么，核心结构和入口在哪里
- issue 在解决什么，缺哪些信息
- 是否适合当前贡献者尝试，以及为什么
- 相关文件 Top-K、证据和 trace
- 推荐阅读顺序，以及为什么先读这些文件
- 问题可能出现的位置和修改方向
- 修改可能造成的影响和风险
- 验证命令、复现方式或缺失的验证信息
- 测试结果应该如何理解
- 可以发给 maintainer 的澄清问题或 comment 草稿
- 本次训练覆盖的工程能力点
- trace：工具查了什么、为什么选这些文件

## Non-Goals

- 第 1 个月不默认自动生成 patch。
- 第 1 个月不自动开 PR。
- 第 1 个月不做复杂 Web UI。
- 第 1 个月不追求替代 SWE-agent、OpenHands、AutoCodeRover。

## Production Direction

这个项目按生产目标推进，不按学习 demo 推进。

第一版的生产质量不来自功能数量，而来自：

- 输出有证据引用。
- 文件定位可评测。
- 自动分析结论能被人复核。
- 教练指导能解释为什么这么判断。
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
- 推荐阅读顺序、可能修改点和教练式说明由 LLM 基于 Top-K 文件与 evidence 改写。

下一步是增加跨仓库 eval，并检查自动分析结果是否能支撑教练式指导；不要先扩大到自动 patch 或 Web UI。

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

`.env` is git-ignored. The LLM writes concise Chinese explanations and coach
guidance for project summary, issue summary, clarity, suitability, reading
order, likely change points, and next-step reasoning. File recommendations still
come from traced `rg + CodeGraph + heuristics` evidence.

CodeGraph writes `.codegraph/` in the analyzed target repository; that directory
is git-ignored here and should not be committed.
