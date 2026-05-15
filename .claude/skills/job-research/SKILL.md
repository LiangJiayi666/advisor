     1|---
     2|name: job-research
     3|description: Parse job descriptions, generate structured job cards, research company/position data with social media sentiment analysis, and optional prism fit analysis.
     4|triggers: User pastes a JD, mentions job hunting, asks about specific companies or positions.
     5|---
     6|
     7|# Job Research
     8|
     9|## Trigger
    10|User pastes a job description, mentions they are job hunting, asks about a specific company, role, or position, or requests career opportunity analysis.
    11|
    12|## Workflow
    13|
    14|1. **Parse JD or job input** — Extract from pasted text or natural language:
    15|   - Role title
    16|   - Company name (if provided)
    17|   - Location
    18|   - Required qualifications / skills
    19|   - Preferred qualifications
    20|   - Salary range (if stated)
    21|   - Job type (full-time, contract, remote, etc.)
    22|   If the input is ambiguous, ask targeted clarification questions (not a blanket "tell me more").
    23|
    24|2. **Generate structured job card** — Produce a compact card with all extracted fields normalized.
    25|
    26|3. **Web research** — Use web search to gather:
    27|   - Company overview (size, industry, funding stage, recent news)
    28|   - Position market data (typical salary range for this role + location)
    29|   - Industry trends relevant to the role
    30|   - Company culture signals (Glassdoor/reviews if accessible)
    31|   Record all source URLs.
    32|
4. **Social media sentiment (MediaCrawler)** — Probe public opinion from major Chinese social platforms.
   This step runs ONLY after explicit user consent.

   > **配置要求**：本步骤中 `{MEDIACRAWLER_HOME}` 为 MediaCrawler 项目的本地路径（如 Linux 上 `/home/user/MediaCrawler`、Windows 上 `D:/Workspace/MediaCrawler`）。此变量不应硬编码在仓库中——请将实际路径写在 `.claude/settings.local.json` 的 `additionalDirectories` 字段或环境变量中。
    35|
    36|   **4a. Consent check** — Ask the user:
    37|   > 要不要查一下 {company} 在社交媒体上的风评？会用 MediaCrawler 爬取小红书、微博、知乎等平台的帖子，需要扫码登录。
    38|   If declined, skip to step 5.
    39|
    40|   **4b. Determine login state** — Check which platforms have cached login sessions:
    41|   ```
    42|   ls {MEDIACRAWLER_HOME}/browser_data/
    43|   ```
    44|   For platforms with `*_user_data_dir/` present, use `--lt cookie`. For others, use `--lt qrcode` (user must scan QR in the opened browser window).
    45|
    46|   **4c. Construct keywords** — Build 1-3 search queries from the job card:
    47|   - Primary: `"{company}"` (exact company name)
    48|   - Secondary: `"{company} {role}"` or `"{company} 工作体验"` or `"{company} 撤职"` etc. — tailored to what would surface employee sentiment.
    49|   Show the proposed keywords to the user and let them adjust before running.
    50|
    51|   **4d. Run MediaCrawler** — For each platform, execute:
    52|   ```bash
    53|   cd {MEDIACRAWLER_HOME} && uv run main.py \
    54|     --platform {platform} \
    55|     --lt {login_type} \
    56|     --type search \
    57|     --keywords "{keywords}" \
    58|     --save_data_option jsonl \
    59|     --headless false \
    60|     --get_comment true
    61|   ```
    62|   Default platforms: `xhs` (小红书), `wb` (微博), `zhihu` (知乎).
    63|   Run platforms sequentially (not parallel) to avoid rate-limiting.
    64|   Each run is blocking; wait for completion before proceeding.
    65|
    66|   **4e. Parse results** — After all platforms finish, read the jsonl output files from `{MEDIACRAWLER_HOME}/data/`. Filenames follow the pattern `{platform}_search_contents.jsonl`.
    67|   For each platform, extract:
    68|   - Post title + content snippet
    69|   - Like / comment / share counts (engagement signals)
    70|   - Comment text (first-level only, for sentiment sampling)
    71|   Discard promotional / low-signal posts (ads, SEO spam).
    72|
    73|   **4f. Sentiment synthesis** — Summarize into the report section (see Output Format below). Classify posts into:
    74|   - Positive signals (good WLB, fair pay, growth opportunities)
    75|   - Negative signals (toxic culture, layoffs, overtime, PIP)
    76|   - Neutral / mixed signals
    77|   Note the sample size and platform distribution so the user can gauge representativeness.
    78|
    79|5. **Evidence summary** — Synthesize ALL research findings (web + social media). Explicitly separate:
    80|   - Verified facts (sourced, with links)
    81|   - Social media sentiment (with platform, sample size, and date range)
    82|   - Model inferences (reasonable but unsourced extrapolations)
    83|
    84|6. **Prism fit analysis (optional)** — Check `advisor_data/profiles/prism/` for existing profile. If present:
    85|   - Assess role alignment with prism-derived strengths and elemental profile.
    86|   - Present as a separate, clearly labeled section.
    87|   If no profile exists, skip this step. Do not prompt user to create one unless they ask.
    88|
    89|## Output Format
    90|
    91|**Job Card:**
    92|```markdown
    93|## 职位卡片
    94|| 字段 | 内容 |
    95||------|------|
    96|| 职位 | {title} |
    97|| 公司 | {company} |
    98|| 地点 | {location} |
    99|| 类型 | {type} |
   100|| 薪资范围 | {range} |
   101|| 核心要求 | {requirements} |
   102|```
   103|
   104|**Research Report:**
   105|```markdown
   106|## 调研报告: {company} - {role}
   107|
   108|### 公司概况
   109|{verified facts with source links}
   110|
   111|### 岗位市场数据
   112|{salary benchmarks, demand trends with sources}
   113|
   114|### 行业趋势
   115|{relevant trends with sources}
   116|
   117|### 社交媒体舆情
   118|{sentiment summary from MediaCrawler, structured as:
   119|
   120|**数据来源**：小红书 N 条 / 微博 N 条 / 知乎 N 条（采样日期 {date}）
   121|
   122|**正面信号**
   123|- {representative positive post excerpts with engagement metrics}
   124|
   125|**负面信号**
   126|- {representative negative post excerpts with engagement metrics}
   127|
   128|**综合判断**
   129|{1-2 sentence overall sentiment assessment with confidence level}
   130|
   131|**注意事项**
   132|- 社交媒体内容存在幸存者偏差，负面声量通常高于实际比例。
   133|- 样本量较小（<30条）时结论仅供参考。
   134|}
   135|
   136|### 来源
   137|- [Source 1](url)
   138|- [Source 2](url)
   139|
   140|### 推断说明
   141|{model inferences, clearly separated from facts}
   142|```
   143|
   144|**Prism Section (if applicable):**
   145|```markdown
   146|## Prism 适配参考
   147|{prism-based role alignment analysis}
   148|
   149|---
   150|*注：Prism 适配分析仅供参考，不构成职业决策依据*
   151|```
   152|
   153|## Constraints
   154|- Every factual claim in the research report must have a source link. No exceptions.
   155|- Model inferences must be in a separate section, never mixed with verified facts.
   156|- Prism section is optional and always labeled as cultural perspective.
   157|- Do not fabricate salary data. If not found, state "未查到公开薪资数据".
   158|- Save output to `advisor_data/archives/{date}/job_{session_id}.md`.
   159|- MediaCrawler step is strictly opt-in. Never run it without user confirmation.
   160|- If MediaCrawler fails on a platform (login expired, timeout, rate-limit), log the failure and continue with remaining platforms. Do not retry more than once.
   161|- Clean up MediaCrawler output files after parsing (delete jsonl from `data/` directory) to avoid stale data in future runs.
   162|- MediaCrawler is at `{MEDIACRAWLER_HOME}/`. All commands must `cd` to that directory first.
   163|