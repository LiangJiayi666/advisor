# /research-job — 岗位研究入口

用途：接收岗位链接、JD 文本或岗位描述，生成结构化岗位卡片，并在需要时给出研究与适配判断。

这个 command 负责入口编排，不负责重复定义 job research 的全部方法细节。方法、约束和证据边界由 `job-research` skill 承担。

## 输入

`$ARGUMENTS` 可以是：
- 岗位 URL
- 粘贴的 JD 文本
- 公司名 + 岗位名
- 一个待判断是否匹配的岗位描述

## 编排流程

### 第一步：解析输入形态

先判断当前输入属于哪一类：
- 单个明确 JD
- 单个岗位链接
- 一个模糊岗位描述
- 多岗位批量输入

如果是批量输入，先说明会做预筛选与结构化，不直接进入逐条长篇分析。

### 第二步：激活 job-research 方法

使用 `job-research` skill 的方法完成：
- JD 结构化
- job card 规范化
- owner 判定
- 持久化到 `advisor_data/jobs/{owner}/`
- 在需要时补公司 / 行业 / 岗位背景研究

### 第三步：确认是否已经形成结构化 job card

输出前必须确认结果不只是 archive note 或 raw text，而是真正写入了结构化岗位数据。

### 第四步：决定输出深度

根据用户问题决定回答深度：
- 如果用户只是说“先存一下这个岗位”，重点汇报岗位卡片和保存结果。
- 如果用户问“这个适合我吗”，增加 fit judgment。
- 如果用户问“帮我调研这个公司/岗位”，增加研究报告与来源。
- 如果用户给了很多岗位，先缩成 shortlist，再决定是否做深读。

### 第五步：汇报结果

至少汇报：
- 解析出的岗位核心信息
- 保存位置 / owner
- 是否已经形成结构化 job card
- 如果做了研究：哪些是 verified facts，哪些是 inference
- 如果做了 fit judgment：结论和主要依据

## 硬约束

- 不要把岗位事实直接塞进长期 memory 代替 job store。
- 不要只生成 raw markdown 却漏掉结构化岗位卡片。
- 不要把 public sentiment crawling 设成默认步骤。
- 不要让 command 重新写一整套方法学；方法归 skill，业务真相归 Python 层。

## 参考

- 方法与约束：`job-research` skill
- 全局规则：`CLAUDE.md`
- 架构说明：`AdvisorPrivate_ArchitectureRefactor_20260526.md`
