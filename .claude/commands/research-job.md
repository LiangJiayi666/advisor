# /research-job — 岗位采集入口

用途：接收岗位链接、JD 文本或岗位描述，解析为结构化岗位卡片，持久化到 job store。

本 command 只管采集和存储，不触发打分排序。打分排序使用 `/compare-jobs`。

## 输入

`$ARGUMENTS` 可以是：
- 岗位 URL
- 粘贴的 JD 文本
- 公司名 + 岗位名
- 多岗位批量输入

## 编排流程

### 第一步：解析输入形态

先判断当前输入属于哪一类：
- 单个明确 JD
- 单个岗位链接
- 一个模糊岗位描述
- 多岗位批量输入

如果是批量输入，逐条处理，每条生成一个结构化 job card。

### 第二步：抓取与结构化

- 如果是 URL：抓取页面，提取 JD 内容
- 如果是文本：直接解析
- 提取结构化字段：title / company / city / requirements / responsibilities / keywords / deadline

### 第三步：持久化到 job store

写入 `advisor_data/jobs/self/`：
- `raw/` 保存原始 JD 文本（.md 格式）
- `jobs.jsonl` 追加结构化 job card（去重）

如果该岗位已存在（title + company + city 三元组重复），跳过并告知用户。

### 第四步：汇报结果

至少汇报：
- 解析出的岗位核心信息（title / company / city / 关键要求）
- 保存位置
- 是否为新岗位 / 已存在
- 如果信息不完整：哪些字段缺失

## 硬约束

- 本 command 不触发 `_score_job`、shortlist 生成、报告输出
- 不要把岗位事实塞进长期 memory 代替 job store
- 不要只生成 raw markdown 却漏掉结构化岗位卡片
- 岗位数据必须写入 `advisor_data/jobs/self/jobs.jsonl`，不是对话上下文
- 如果用户问了"这个适合我吗"或"帮我排序"，引导用户使用 `/compare-jobs`

## 参考

- 方法与约束：`job-research` skill
- 打分排序：`/compare-jobs`
- 简历生成：`/write-resume`
- 全局规则：`CLAUDE.md`
