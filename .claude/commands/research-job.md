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

### 第四步：持久化

写入 `advisor_data/jobs/self/`：
- `raw/` 保存原始 JD（.md）
- `jobs.jsonl` 追加带 features 的 job card（去重）

### 第五步：汇报

至少汇报：
- 岗位核心信息
- 保存状态（新增/已存在）
- 特征提取摘要（daily_work / tech_depth / coding）
- 如果用户问了匹配度，引导到 `/compare-jobs`

## 硬约束

- 每个入库的 job card **必须**有 `features` 字段
- features 的枚举值必须用 schema 中列出的，不要自创
- 不要调用任何打分/排序函数
- 不要把岗位事实塞进长期 memory

## 参考

- 特征提取 schema 和方法：`job-research` skill
- 打分排序：`/compare-jobs`
- 全局规则：`CLAUDE.md`
