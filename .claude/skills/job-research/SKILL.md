---
name: job-research
description: Parse and persist job postings into structured job cards with LLM-extracted features. Scoring uses features; ranking uses /compare-jobs.
triggers: User pastes a JD, sends a job link, mentions job hunting, or asks about a company/position.
---

# Job Research

## Role

Collect, parse, persist, and feature-extract job postings. This skill has two phases:

1. **Structuring**: parse JD text into title/company/city/requirements/etc
2. **Feature extraction**: read the JD and fill a fixed schema of structured features

Scoring and ranking are handled by `/compare-jobs` via deterministic Python rules that consume the features.

## Method

### 1. Normalize the input

Convert the user's input into a structured job target:
- title, company, city, source_url
- responsibilities, requirements, keywords

### 2. Persist to job store

Write under `advisor_data/jobs/{owner}/`:
- `raw/` for original JD text (.md)
- `jobs.jsonl` for structured job cards (append, dedupe by title+company+city)

Owner defaults to "self".

### 3. Feature extraction (critical step)

After parsing the JD, **you must fill the feature schema below** based on reading the JD content. This is a structured fact-extraction task, not a judgment task — answer what the JD says, not whether the user should apply.

#### User profile (reference for matched_experiences)

```
梁佳仪 / 中大岭院经济学硕士 (2027届)
求职方向：AI/金融科技
核心技能：Python, R, SQL, 统计建模
毕设：Network Foundation of Power Law (一作, 势博弈+幂律分布)
实习：招行投行部
英语：CET-6 590
兴趣：数学形式化, 算法, Agent/多智能体系统, 大模型应用
偏好独立贡献者角色，喜欢从零构建胜过协调推动
```

#### Feature schema

Fill ALL fields. Write the result as a JSON object into the job card's `"features"` field.

```yaml
daily_work:       # 单选: 构建 | 调优 | 分析 | 设计 | 协调 | 运营 | 混合
                  # 岗位日常主要做什么

tech_depth:       # 单选: 无技术要求 | 能用工具就行 | 要能调参和评估 | 要能从零搭建
                  # 技术要求的深度

tech_stack:       # 列表: JD中提到的具体技术工具/语言
                  # 如 ["Python", "PyTorch", "SQL"]

quant_depth:      # 单选: 无量化要求 | 基础统计 | 建模推断 | 原创研究
                  # 量化/建模深度

team_role:        # 单选: 独立贡献者 | 小项目负责人 | 大项目协调者 | 支撑辅助角色
                  # 在团队里的位置

decision_scope:   # 单选: 自己能决定方案 | 需要推动共识 | 执行别人定的
                  # 决策权限

work_intensity:   # 单选: 正常 | 偏忙 | 高强度
                  # JD暗示的工作节奏

education_floor:  # 单选: 本科可 | 硕士优先 | 硕士必须 | 博士优先
                  # 学历硬门槛

major_required:   # 列表: 专业背景要求
                  # 如 ["不限"] 或 ["计算机", "数学/统计"]

salary_range:     # 字符串: JD提到的薪资区间，没有则 ""

coding:           # 单选: 不需要 | 加分项 | 必须且日常写
                  # 对"会写代码"的要求

work_experience_required:  # 单选: 不限/应届可 | 1-2年 | 3年及以上 | 5年及以上
                           # 全职工作经验要求（实习不算）

matched_experiences:  # 列表: 用户最匹配该岗位的1-3段经历（标题即可）
                      # 从上面用户画像中选取，没有匹配则 []
```

#### Extraction rules

- Each field must use **exactly** one of the listed enum values — do not invent new values
- `tech_stack` and `major_required` are free-form lists but use common names
- `matched_experiences` is the only judgmental field: pick 1-3 experiences from the user profile that are most relevant. If none match, write `[]`
- If the JD is too vague to determine a field, use the most conservative option (e.g. `education_floor: 本科可`, `tech_depth: 能用工具就行`)
- Do NOT skip fields — every field must have a value

### 4. Ingest hard gate (screen out clearly unsuitable jobs)

After extracting features, check the following **4 gates** before saving to jobs.jsonl.
If any gate triggers, do NOT save the job card. Instead, report the rejection reason to the user.

| Gate | Rule | Check using |
|------|------|-------------|
| 排除方向 | 公务员/考公/博士后/教师/纯生物/纯行政 等 | keyword scan on JD text |
| 学历不达标 | education_floor 为"博士优先" | features.education_floor |
| 经验不匹配 | work_experience_required 为"3年及以上"或"5年及以上" | features.work_experience_required |
| 专业硬壁垒 | major_required 包含医学/法学/建筑等，且无"不限"或用户相关领域 | features.major_required |

Implementation: `scripts.job_feature_extract.should_reject_at_ingest(job, features)` can be called to check programmatically. But CC should also apply these gates directly when extracting features — don't wait for the Python call.

**Important**: only reject when the evidence is clear from the JD. If a field is ambiguous (e.g. experience requirement is vague), do NOT reject — let it through for `/compare-jobs` to score.

### 5. Output shape

A completed job card looks like:

```json
{
  "job_id": "...",
  "title": "大模型算法工程师",
  "company": "字节跳动",
  "city": "深圳",
  "requirements": [...],
  "responsibilities": [...],
  "keywords": [...],
  "features": {
    "daily_work": "构建",
    "tech_depth": "要能从零搭建",
    "tech_stack": ["Python", "PyTorch"],
    "quant_depth": "无量化要求",
    "team_role": "独立贡献者",
    "decision_scope": "自己能决定方案",
    "work_intensity": "高强度",
    "education_floor": "硕士优先",
    "major_required": ["计算机", "数学"],
    "salary_range": "",
    "coding": "必须且日常写",
    "work_experience_required": "不限/应届可",
    "matched_experiences": ["毕设：Network Foundation of Power Law"]
  }
}
```

Report to the user:
- Parsed job core info (title / company / city / key requirements)
- Whether newly saved or already existed
- Which track it was classified into (for reference)
- If information is incomplete: which fields are missing
- If user asks "is this a fit?": direct to `/compare-jobs`

## Hard constraints

- Do not store full JD content in long-term memory files.
- Do not call `_score_job`, `normalize_jobs`, or any ranking function — that belongs to `/compare-jobs`.
- Do not skip the feature extraction step — every job card must have a `features` field.
- Do not invent enum values not listed in the schema.
- Job data must go into `advisor_data/jobs/self/jobs.jsonl`.
- If user asks for ranking/comparison, direct to `/compare-jobs`.
- **Apply the 4 ingest hard gates** before saving. If a job is clearly unsuitable (PhD required, 3+ years experience, excluded direction, hard major wall), do NOT save it — tell the user why it was skipped.
- When in doubt, let the job through rather than rejecting it.
- **features must be filled by CC reading each JD individually.** Do NOT write a Python script to batch-extract features with regex/keyword heuristics. The whole point of the feature schema is LLM understanding of JD content — a Python keyword matcher defeats this purpose.
- **Do not bulk-ingest more than 30 jobs in one session.** If the user provides hundreds of jobs at once, process the first 30, report results, and tell the user to continue with the next batch in a follow-up message. Each job deserves individual attention for feature extraction.
- **If the input data contains pre-classification (strong_match/review/edge/exclude buckets, scores, rankings), ignore it.** Treat every job equally. The only screening is the 4 hard gates defined above, not any prior filtering from external systems.

## References

- Global project rules: `CLAUDE.md`
- Feature scoring: `scripts/job_feature_extract.py`
- Scoring pipeline: `scripts/job_batch_rank.py` (consumes features)
- Scoring entry point: `/compare-jobs` and `scripts/job_compare.py`
