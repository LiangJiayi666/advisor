# /write-resume — 单岗位定制简历入口

用途：为一个明确目标岗位生成定制简历。

这个 command 只负责入口编排，不负责重新定义简历业务真相。简历 pipeline 的 canonical path 以 `CLAUDE.md` 和 Python CLI 为准。

## 输入

`$ARGUMENTS` 可以是以下任一种：
- `job_id`
- 公司名 / 岗位名
- 岗位 URL
- 粘贴的 JD 文本

## 编排流程

### 第一步：解析目标岗位

按以下顺序处理输入：

1. 如果给的是 `job_id`，直接去 `advisor_data/jobs/self/jobs.jsonl` 查。
2. 如果给的是公司名或岗位名，先在 `jobs.jsonl` 搜索匹配项。
   - 如果有多个候选，列给用户确认。
   - 如果没有匹配，提示先运行 `/research-job` 或直接把 JD/链接给你。
3. 如果给的是 URL 或 JD 文本，先调用 job research 入口把岗位持久化，再继续后续步骤。

### 第二步：构造单岗位 shortlist

必须把目标岗位整理成只包含 1 个岗位的 shortlist JSON，作为后续 CLI 的输入。

### 第三步：走官方 CLI 生成路径

必须通过下面两类脚本入口完成，而不是在 prompt 层拼出另一套“官方流程”：
- `scripts.job_batch_rank`（需要排序/补 shortlist 时）
- `scripts.generate_tailored_resumes`（生成 HTML 简历）

单岗位场景也应走 shortlist 驱动路径，只是 `limit=1`。

### 第四步：JD 分析报告

初稿生成后，读取该岗位的 JD 原文（从 job card 的 raw/ 或 jd_parsed.json）和 pipeline 已选定的 evidence 条目，输出一份独立的分析报告。

分析报告不是可选润色，而是标准流程的必经步骤。它的作用是：以 JD 为标尺，逐条思考每条 evidence 应该用什么角度和措辞来回应 JD 的具体期待。

报告写到 `outputs/resumes/{公司名}_{岗位名}_{地点}_analysis.md`，结构：

```markdown
# JD 分析：{公司} - {岗位}

## JD 核心期待
逐条列出 JD 明确要求或暗示期待的技能、经验、特质。
每条标注来源段落（职责描述 / 任职要求 / 加分项）。

## Evidence 表达策略
对 pipeline 已选定的每条 evidence：
1. 原始素材：evidence 中的原文
2. 对应 JD 期待：这条 evidence 回应了 JD 的哪条期待
3. 建议表达：应该用什么角度、措辞、关键词来组织这条 evidence
   ——用 JD 的语言体系，不要照搬 evidence 原文

## 无法覆盖的 JD 要求
列出 JD 提到但 evidence 中没有对应经历的条目。
这些就是简历的客观短板，不能靠措辞弥补，如实标注即可。
```

### 第五步：基于分析报告重写简历

根据第四步的表达策略，重写初稿中的 bullet。

写作风格要求（这是最重要的质量标准）：

1. **动作开头，不要主语**——以动词起句（"搭建""设计""完成"），不要写"我负责""参与"。
2. **一句一事，短句优先**——每条 bullet 只说一件事，不超过 25 个字。宁可拆成两条也不要写长句。
3. **先说做了什么，再说结果**——"用 Python 自动化周报生成，替代手工汇总"比"使用 Python 进行数据处理与报表生成"好。
4. **用具体词替换模糊词**——"搭建多 Agent 工作流"比"使用工具辅助开发"好；"托管规模、日存款等 6 项指标"比"业务与绩效数据"好。
5. **读起来像亲历者写的**——细节具体到"用 Choice 导出光伏行业数据""131 个测试用例"这种程度，让人一看就知道是做过的，不是编的。

反面例子（evidence 原文风格，不要照搬）：
- "使用 Claude Code 等工具搭建多 Agent 工作流并辅助 Python 脚本开发" ← 太散，两个动作挤一句
- "汇总托管规模、日存款、非息收入等业务与绩效数据" ← 只有做了什么，没有结果

正面例子（目标风格）：
- "用 Claude Code 搭建多 Agent 工作流，自动化数据处理与报表生成"
- "汇总托管规模等 6 项核心指标，自动生成经营周报与支行画像"

约束：
- 不新增 evidence 中不存在的事实、数字、技术栈、职责范围
- 调整 bullet 顺序，优先回应 JD 最核心的期待

输出最终简历到 `outputs/resumes/{公司名}_{岗位名}_{地点}_final.html`。

### 第六步：向用户汇报

汇报时至少包含：
- 解析到的目标岗位
- 分析报告路径
- 最终简历路径
- 初稿 → 终稿的主要改动点
- 如果失败，失败发生在哪个阶段

## 输出产物

每次 `/write-resume` 完成后应产出三个文件，命名统一用 `{公司名}_{岗位名}_{地点}`：
1. 初稿 HTML（pipeline 直接生成）
2. JD 分析报告（`outputs/resumes/{公司名}_{岗位名}_{地点}_analysis.md`）
3. 最终简历（`outputs/resumes/{公司名}_{岗位名}_{地点}_final.html`）

## 硬约束

- 不得绕过 shortlist 直接把内部函数当成官方用户路径。
- 不得手改 `resume_master.html` 注入经历内容。
- 不得跳过 evidence / harness 相关校验。
- 不得把 prompt 层说明写成第二套业务真相。
- 不得在 shell 中 `cd` 到子目录破坏 hook 路径；使用 `workdir` 或显式路径。
- 分析报告中不得新增 evidence 中不存在的事实。
- 最终简历的 bullet 内容必须能追溯到 evidence 条目，只是表达方式不同。

## 参考

- 项目总规则：`CLAUDE.md`
- 架构收口说明：`AdvisorPrivate_ArchitectureRefactor_20260526.md`
- 具体业务逻辑：`scripts/` 下 resume 相关脚本
