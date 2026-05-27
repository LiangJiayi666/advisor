# /compare-jobs — 岗位打分排序主入口

对已存入 `advisor_data/jobs/self/` 的岗位执行确定性打分排序。

## 输入

`$ARGUMENTS` 可以是：
- 空（不传参数）：对 jobs.jsonl 全量打分排序
- 一批岗位标识（job_id、公司名、岗位名）：只对匹配的岗位打分排序
- "全部" / "全量" 等同义词：等同于空参数

## 编排流程

### 第一步：确定模式

根据参数判断：
- 无参数或"全部"→ 全量模式
- 有具体岗位标识 → 过滤模式

### 第二步：调用打分引擎

```
python -m scripts.job_compare \
  --jobs-jsonl advisor_data/jobs/self/jobs.jsonl \
  --raw-dir advisor_data/jobs/self/raw \
  --evidence-jsonl advisor_data/resume/evidence.jsonl \
  [job_id1 job_id2 ...]
```

或直接调用 `scripts.job_compare.compare_jobs()`。

该函数内部：
1. 从 job_batch_rank 导入打分体系（轨道分类、8 维评分、偏好配置）
2. 加载 jobs.jsonl + raw/ + evidence.jsonl
3. 走完整 normalize → _derive_track → _score_job → 去重 → company soft cap 流程
4. 如果指定了 job_ids，只返回匹配的子集；否则返回全量

### 第三步：呈现结果

至少汇报：
- 模式（全量/过滤）和返回数量
- 轨道分布（ai_engineer / quant_research / ai_pm / adjacent / other 各几个）
- 排序列表，每条包含：排名、岗位名、公司、城市、轨道、fit_score、priority_score、优势、风险
- 如果用户问"选哪个"，基于分数给建议，但明确标注是分数推断而非事实

### 第四步：提示后续动作

- 高分岗位可以接着用 `/write-resume` 生成定制简历
- 分数高但证据不足的岗位，建议先补充经历再投
- 城市有 penalty 的岗位，提醒确认城市偏好

## 硬约束

- 打分逻辑 100% 来自 `scripts/job_batch_rank`，本 command 不定义任何评分维度或权重
- 岗位数据必须来自 `advisor_data/jobs/self/jobs.jsonl`，不从对话记忆里取
- 如果 jobs.jsonl 为空或不存在，直接告知用户先用 `/research-job` 采集岗位
- 不要把分数当作绝对真理——用分数辅助判断，但最终决定权在用户

## 参考

- 评分体系：`scripts/job_batch_rank.py`（唯一评分源）
- 对外 API：`scripts.job_compare.compare_jobs()`
- 岗位采集：`/research-job`
