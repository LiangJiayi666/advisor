# /close-session — 会话关闭入口

用途：在结束一个有实质内容的 advisor 会话前，完成归档、记忆提炼和状态更新。

这个 command 是会话关闭的 orchestration 入口。归档格式由 `archive-writer` skill 约束，记忆提炼规则由 `memory-policy` skill 约束。

## 编排流程

### 第一步：检查是否需要归档

先判断当前会话是否有实质内容：
- 有明确咨询、研究、判断、情绪支持、决策推进
- 或产生了应进入长期记录的结果

如果只是极短闲聊或没有形成有效内容，可以说明无需正式归档。

### 第二步：检查状态，避免重复归档

查看 `advisor_data/state/state.json` 中的相关状态。
如果已经归档，不要重复执行整套流程。

### 第三步：执行归档写作

调用 archive 方法，产出结构化会话归档文件到 `advisor_data/archives/`。

### 第四步：执行记忆提炼

调用 memory 方法，从本次会话提取 durable facts / preferences / patterns / decisions。
注意只提炼长期有效信息，不写入原始对话文本。

### 第五步：更新 session state

只有当归档和记忆提炼都成功后，才更新：
- `archive_state`
- `last_session_id`
- `last_session_date`
- `session_count`
- `recent_topics`
- `current_session_id`
- 其他轻量 session log 信息

### 第六步：向用户汇报

简要说明：
- 是否已归档
- 是否提炼了记忆
- 更新了哪些状态
- 如果有失败，失败在归档、记忆还是状态更新阶段

## 硬约束

- 不要在归档失败时继续假装完成会话关闭。
- 不要把原始敏感对话直接写入长期 memory。
- 不要让 command 自己重新定义记忆 schema 或 archive 格式。
- 不要跳过状态检查导致重复归档。

## 参考

- 归档格式：`archive-writer` skill
- 记忆策略：`memory-policy` skill
- 全局规则：`CLAUDE.md`
- 架构说明：`AdvisorPrivate_ArchitectureRefactor_20260526.md`
