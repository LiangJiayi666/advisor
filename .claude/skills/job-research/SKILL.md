---
name: job-research
description: Parse job descriptions, persist structured job cards, research company/position data with social media sentiment analysis, and optional prism fit analysis.
triggers: User pastes a JD, mentions job hunting, asks about specific companies or positions.
---

# Job Research

## Trigger
User pastes a job description, mentions they are job hunting, asks about a specific company, role, or position, or requests career opportunity analysis.

## Workflow

1. **Pre-filter batch input** — When processing a batch of jobs (JSON, list, file), apply these rules sequentially:

   **1a. Category exclusion** — Exclude jobs whose `jobFamily` matches:
   - 零售类 (Retail)
   - 职能类 (Corporate Functions: HR, Finance, Legal, Admin, etc.)
   - 市场营销类 (Marketing)

   **1b. City deduplication** — When the same job (same `name` + same `department`) appears in multiple cities, keep only ONE entry using this priority order:
   1. 广州 or 深圳 (广深)
   2. 杭州
   3. 北京
   4. 上海
   Match the first available city in this priority list and discard the rest.

   **1c. Competency filter** — Remove jobs the user fundamentally cannot compete for based on their profile. Two sub-rules:

   *1c-i. Topic exclude* — Exclude jobs matching these keywords in job name, department, or description:
   - 安全工程, 应急响应, 渗透测试, 攻击模拟, 紫队
   - 测试开发, 质量工程 (NOT 大模型评测, which is relevant)
   - 运维研发
   - 无人车, 无人机, 具身智能, 自动驾驶
   - 计算机视觉工程师, 场景重建, 感知算法
   - 广告算法, 广告反作弊, 广告大模型, 生成式广告
   - 后端JAVA, JAVA开发
   - 大数据开发, 大数据应用测试
   - 空天计算, 传感器标定, 高精地图
   - 移动端开发, 大前端
   - 多模态生成大模型算法, 视频算法工程师
   - 内容安全算法
   - Keeta (overseas business, dept filter)
   - 大模型Infra工程师, 机器学习引擎工程师, 强化学习系统 (ML infrastructure / systems engineering)
   - 预训练算法, 结构和预训练 (foundation model pre-training)

   *1c-ii. Qualification exclude* — After topic filtering, check the remaining jobs' requirements/descriptions. Exclude any job that explicitly requires:
   - 博士 (PhD) or 博士研究生 as a mandatory or preferred qualification
   - 顶级会议论文 (top-tier conference publications: ACL, EMNLP, NeurIPS, ICML, ICLR, CVPR, etc.) as a requirement
   - 竞赛金牌/一等奖 (algorithm competition medals: ACM-ICPC, NOI, etc.) as a requirement
   Do NOT exclude based on program name alone (e.g., 北斗 is NOT a filter keyword — a 北斗 role that accepts 硕士 should be kept).

   Report how many were filtered at each step and why in a brief note before proceeding.

2. **Parse JD or job input** — Extract from pasted text or natural language:
   - Role title
   - Company name (if provided)
   - Location
   - Required qualifications / skills
   - Preferred qualifications
   - Salary range (if stated)
   - Job type (full-time, contract, remote, etc.)
   If the input is ambiguous, ask targeted clarification questions (not a blanket "tell me more").

3. **Generate structured job card** — Produce a compact card with all extracted fields normalized. Prefer this core schema:
   - `title`, `company`, `city`, `job_family`, `source`, `source_url`
   - `responsibilities`, `requirements`, `keywords`, `seniority`, `compensation`, `work_mode`, `tags`
   - `evidence`: field-level quotes / source URLs / confidence values where available.

4. **Persist job business data** — Job facts are business-object data, not Advisor memory. Save them under `advisor_data/jobs/{owner}/` using the job store convention. Each person gets their own isolated directory tree:
   - `advisor_data/jobs/{owner}/jobs.jsonl`: normalized job cards, one JSON object per line.
   - `advisor_data/jobs/{owner}/raw/{job_id}.md`: original JD / pasted raw input / fetched page text.
   - `advisor_data/jobs/{owner}/evidence/{job_id}.json`: field-level evidence such as quote, source URL, and confidence.
   - `advisor_data/jobs/{owner}/comparisons/`: comparison reports.
   
   **Owner determination**: 
   - For the user themselves: `owner = "self"` (default).
   - For the user's partner: `owner = "partner"`.
   - When the user asks to store/search jobs for someone other than themselves, infer the owner from context.
   - When ambiguous, use `owner="self"`.
   
   Use `scripts.job_store.JobStore(advisor_data_dir, owner=owner)` when coding against this store. Do not duplicate full JD content into `advisor_data/memories/memory.jsonl`; memory may store only high-level user preferences or decisions derived from the job analysis.

5. **Web research** — Use web search to gather:
   - Company overview (size, industry, funding stage, recent news)
   - Position market data (typical salary range for this role + location)
   - Industry trends relevant to the role
   - Company culture signals (Glassdoor/reviews if accessible)
   Record all source URLs.

6. **Social media sentiment (MediaCrawler)** — Probe public opinion from major Chinese social platforms. This step runs ONLY after explicit user consent.

   > **配置要求**：本步骤中 `{MEDIACRAWLER_HOME}` 为 MediaCrawler 项目的本地路径（如 Linux 上 `/home/user/MediaCrawler`、Windows 上 `D:/Workspace/MediaCrawler`）。此变量不应硬编码在仓库中——请将实际路径写在 `.claude/settings.local.json` 的 `additionalDirectories` 字段或环境变量中。

   **5a. Consent check** — Ask the user:
   > 要不要查一下 {company} 在社交媒体上的风评？会用 MediaCrawler 爬取小红书、微博、知乎等平台的帖子，需要扫码登录。
   If declined, skip to step 6.

   **5b. Determine login state** — Check which platforms have cached login sessions:
   ```bash
   ls {MEDIACRAWLER_HOME}/browser_data/
   ```
   For platforms with `*_user_data_dir/` present, use `--lt cookie`. For others, use `--lt qrcode` (user must scan QR in the opened browser window).

   **5c. Construct keywords** — Build 1-3 search queries from the job card:
   - Primary: `"{company}"` (exact company name)
   - Secondary: `"{company} {role}"` or `"{company} 工作体验"` or `"{company} 撤职"` etc. — tailored to what would surface employee sentiment.
   Show the proposed keywords to the user and let them adjust before running.

   **5d. Run MediaCrawler** — For each platform, execute:
   ```bash
   cd {MEDIACRAWLER_HOME} && uv run main.py \
     --platform {platform} \
     --lt {login_type} \
     --type search \
     --keywords "{keywords}" \
     --save_data_option jsonl \
     --headless false \
     --get_comment true
   ```
   Default platforms: `xhs` (小红书), `wb` (微博), `zhihu` (知乎). Run platforms sequentially (not parallel) to avoid rate-limiting. Each run is blocking; wait for completion before proceeding.

   **5e. Parse results** — After all platforms finish, read the jsonl output files from `{MEDIACRAWLER_HOME}/data/`. Filenames follow the pattern `{platform}_search_contents.jsonl`.
   For each platform, extract:
   - Post title + content snippet
   - Like / comment / share counts (engagement signals)
   - Comment text (first-level only, for sentiment sampling)
   Discard promotional / low-signal posts (ads, SEO spam).

   **5f. Sentiment synthesis** — Summarize into the report section. Classify posts into:
   - Positive signals (good WLB, fair pay, growth opportunities)
   - Negative signals (toxic culture, layoffs, overtime, PIP)
   - Neutral / mixed signals
   Note the sample size and platform distribution so the user can gauge representativeness.

7. **Evidence summary** — Synthesize ALL research findings (web + social media). Explicitly separate:
   - Verified facts (sourced, with links)
   - Social media sentiment (with platform, sample size, and date range)
   - Model inferences (reasonable but unsourced extrapolations)

8. **Fit analysis and comparison** — When comparing stored jobs, use deterministic scoring first (see `scripts.job_compare.compare_jobs`) and let the model explain the score. Do not let the model invent an untraceable ranking.

9. **Prism fit analysis (optional)** — Check `advisor_data/profiles/prism/` for existing profile. If present:
   - Assess role alignment with prism-derived strengths and elemental profile.
   - Present as a separate, clearly labeled section.
   If no profile exists, skip this step. Do not prompt user to create one unless they ask.

## Output Format

**Job Card:**
```markdown
## 职位卡片
| 字段 | 内容 |
|------|------|
| Job ID | {job_id} |
| 职位 | {title} |
| 公司 | {company} |
| 地点 | {city} |
| 类型 | {type} |
| 薪资范围 | {range} |
| 核心要求 | {requirements} |
| 来源 | {source_url} |
```

**Research Report:**
```markdown
## 调研报告: {company} - {role}

### 公司概况
{verified facts with source links}

### 岗位市场数据
{salary benchmarks, demand trends with sources}

### 行业趋势
{relevant trends with sources}

### 社交媒体舆情
{sentiment summary from MediaCrawler with data source counts, positive signals, negative signals, and confidence notes}

### 来源
- [Source 1](url)
- [Source 2](url)

### 推断说明
{model inferences, clearly separated from facts}
```

**Prism Section (if applicable):**
```markdown
## Prism 适配参考
{prism-based role alignment analysis}

---
*注：Prism 适配分析仅供参考，不构成职业决策依据*
```

## Constraints
- Every factual claim in the research report must have a source link. No exceptions.
- Model inferences must be in a separate section, never mixed with verified facts.
- Prism section is optional and always labeled as cultural perspective.
- Do not fabricate salary data. If not found, state "未查到公开薪资数据".
- Save report output to `advisor_data/archives/{date}/job_{session_id}.md`.
- Save job facts to `advisor_data/jobs/{owner}/`; do not save full JD content into `advisor_data/memories/memory.jsonl`.
- MediaCrawler step is strictly opt-in. Never run it without user confirmation.
- If MediaCrawler fails on a platform (login expired, timeout, rate-limit), log the failure and continue with remaining platforms. Do not retry more than once.
- Clean up MediaCrawler output files after parsing (delete jsonl from `data/` directory) to avoid stale data in future runs.
- MediaCrawler is at `{MEDIACRAWLER_HOME}/`. All commands must `cd` to that directory first.
