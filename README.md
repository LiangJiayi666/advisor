# Life Advisor

基于 Claude Code 的长期个人顾问工作区。单用户、本地运行，把 LLM 的自由发挥空间压缩到最小，核心业务逻辑全部压回确定性 Python 脚本。

## 架构

三层结构，每层有明确职责：

```
Command（编排）  →  Skill（方法/约束）  →  Script（确定性逻辑）
```

- **Command**：用户入口，负责解析输入、编排流程、汇报结果
- **Skill**：可复用的方法定义和约束规则，不持有业务真相
- **Script**：确定性 Python 脚本，排序、校验、生成、计算全部在这里

## 功能模块

### 职业研究

`/research-job` — 接收岗位链接 / JD 文本 / 公司名，结构化为岗位卡片，持久化到本地存储，可选做背景调研和适配判断。

`/compare-jobs` — 对已存储的多个岗位做确定性比较评分，输出维度得分和排名。

### 简历生成

`/write-resume` — 为单个目标岗位生成定制简历，流程：

1. 解析目标岗位（job_id / URL / JD 文本）
2. 构造 shortlist
3. Pipeline 生成初稿 HTML（evidence 匹配 → 确定性 draft → harness 校验）
4. JD 分析报告（逐条分析 evidence 应如何回应 JD 期待）
5. 基于分析重写简历（用 JD 的语言体系组织 evidence，不新增事实）
6. 汇报结果

产物：初稿 HTML + JD 分析报告 + 最终简历 HTML。

简历生成严格遵循 evidence-constrained 原则：所有 bullet 内容必须能追溯到 `evidence.jsonl` 中的条目，不允许无中生有。

### 会话管理

`/intake` — 引导式情绪摄入，基于 CBT 方法框架。

`/recall-memory` — 回忆长期记忆，按类别和标签分组呈现。

`/close-session` — 会话归档 + 记忆提炼 + 状态更新。

## 技术栈

- **编排层**：Claude Code commands / skills / hooks
- **业务层**：Python 脚本（岗位排序、确定性比较、简历 pipeline、校验）
- **状态层**：本地 JSONL / JSON / Markdown 文件存储

## 简历 Pipeline

```
jobs.jsonl
  ↓ scripts.job_batch_rank
shortlist JSON
  ↓ scripts.generate_tailored_resumes
  ↓ scripts.resume_core (evidence matching + draft + harness)
draft HTML
  ↓ JD analysis + constrained rewrite
final HTML
```

关键设计：
- Evidence 匹配和 harness 校验是确定性的，不依赖 LLM 判断
- LLM 只参与最后一步的 bullet 重写，且必须在 evidence 约束内
- 写作风格要求：动作开头、一句一事、具体词、像亲历者写的

## 安全机制

每条用户消息自动做风险分层：

- **GREEN**：正常对话
- **YELLOW**：情绪升高，增加共情回应，避免放大焦虑
- **RED**：危机信号，立即停止所有咨询模块，输出危机热线，不做治疗

通过 constraints 文件 + hook 脚本双重保障，确保安全优先级永远高于其他模块。

## 目录结构

```
.claude/
  commands/        ← 用户入口
  constraints/     ← 全局约束（安全、记忆、输出格式）
  skills/          ← 可复用方法
  settings.json    ← hook 配置
scripts/
  resume_core.py              ← 简历核心库
  resume_generator.py         ← legacy CLI wrapper
  generate_tailored_resumes.py ← 用户级主编排器
  job_store.py                ← 岗位持久化
  job_compare.py              ← 确定性比较
  job_batch_rank.py           ← shortlist 生成
  hooks/                      ← 生命周期辅助
CLAUDE.md                     ← 项目总规则
```

## 设计原则

1. **确定性优先**：能写成 Python 的事情不靠 prompt 控制
2. **Evidence-first**：简历 bullet 必须有证据支撑，禁止生成式编造
3. **薄编排**：Claude 层只做入口和编排，不持有业务真相
4. **单用户长会话**：记忆、归档、状态更新保证跨会话连续性
