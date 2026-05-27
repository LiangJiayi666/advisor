# /research-job — 岗位采集 + 特征提取入口

用途：接收岗位链接、JD 文本或岗位描述，解析为结构化岗位卡片，提取特征，持久化到 job store。

本 command 负责**采集和特征提取**，不触发打分排序。打分排序使用 `/compare-jobs`。

## 输入

`$ARGUMENTS` 可以是：
- 岗位 URL
- 粘贴的 JD 文本
- 公司名 + 岗位名
- 多岗位批量输入

## 编排流程

### 第一步：解析输入形态

判断输入类型：单个 JD / 链接 / 批量。批量则逐条处理。

### 第二步：抓取与结构化

- URL → 抓取页面提取 JD
- 文本 → 直接解析
- 提取：title / company / city / requirements / responsibilities / keywords / deadline

### 第三步：特征提取（关键步骤）

阅读 JD 内容，按照 `job-research` skill 中定义的 feature schema 填写所有字段。

这一步是**结构化事实提取**，不是判断——回答"JD 说了什么"，不是"用户应不应该投"。

唯一需要结合用户画像的字段是 `matched_experiences`：从用户背景中选出 1-3 段最相关的经历。

提取结果写入 job card 的 `"features"` 字段。

### 第四步：硬筛（入库前过滤）

提取完 features 后，检查 4 个硬筛门槛。命中任何一个就**不存入** jobs.jsonl，告知用户跳过原因：

1. **排除方向** — 公务员/考公/博士后/教师/纯生物/纯行政
2. **学历不达标** — education_floor 为"博士优先"
3. **经验不匹配** — work_experience_required 为"3年及以上"或"5年及以上"
4. **专业硬壁垒** — major_required 含医学/法学/建筑等且无"不限"

拿不准的不筛，放进去让 `/compare-jobs` 处理。

### 第五步：持久化

写入 `advisor_data/jobs/self/`：
- `raw/` 保存原始 JD（.md）
- `jobs.jsonl` 追加带 features 的 job card（去重）

### 第六步：汇报

至少汇报：
- 岗位核心信息
- 保存状态（新增/已存在/被硬筛跳过+原因）
- 特征提取摘要（daily_work / tech_depth / coding）
- 如果用户问了匹配度，引导到 `/compare-jobs`

## 硬约束

- 每个入库的 job card **必须**有 `features` 字段
- features 的枚举值必须用 schema 中列出的，不要自创
- 不要调用任何打分/排序函数
- 不要把岗位事实塞进长期 memory
- **features 必须由 CC 逐个读取 JD 后填写，禁止用 Python 脚本批量启发式提取**
- **单次入库不超过 30 个岗位。超过 30 个时处理前 30 个，告诉用户分批继续**
- **如果输入数据自带分类/分桶/评分（strong_match/review/edge/exclude 等），忽略它，所有岗位一视同仁**

## 参考

- 特征提取 schema 和方法：`job-research` skill
- 打分排序：`/compare-jobs`
- 全局规则：`CLAUDE.md`
