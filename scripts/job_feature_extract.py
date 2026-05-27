"""Job feature extraction schema and deterministic scoring from features.

This module defines:
1. The FEATURE_SCHEMA that CC fills when ingesting a JD
2. Feature-based scoring logic that replaces keyword matching in _score_job

CC does the LLM extraction (reading JD + user profile), writes the result
into the job card's "features" field.  This module consumes that field.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ── Schema definition ────────────────────────────────────────────────
# CC fills these fields when ingesting a job posting.
# Values are constrained enums unless noted.

FEATURE_SCHEMA = {
    "daily_work": {
        "type": "enum",
        "options": ["构建", "调优", "分析", "设计", "协调", "运营", "混合"],
        "description": "岗位日常主要做什么（单选）",
    },
    "tech_depth": {
        "type": "enum",
        "options": ["无技术要求", "能用工具就行", "要能调参和评估", "要能从零搭建"],
        "description": "技术要求的深度（单选）",
    },
    "tech_stack": {
        "type": "list",
        "description": "JD 中提到的具体技术工具/语言",
    },
    "quant_depth": {
        "type": "enum",
        "options": ["无量化要求", "基础统计", "建模推断", "原创研究"],
        "description": "量化/建模深度（单选）",
    },
    "team_role": {
        "type": "enum",
        "options": ["独立贡献者", "小项目负责人", "大项目协调者", "支撑辅助角色"],
        "description": "在团队里的位置（单选）",
    },
    "decision_scope": {
        "type": "enum",
        "options": ["自己能决定方案", "需要推动共识", "执行别人定的"],
        "description": "决策权限（单选）",
    },
    "work_intensity": {
        "type": "enum",
        "options": ["正常", "偏忙", "高强度"],
        "description": "JD 暗示的工作节奏/压力",
    },
    "education_floor": {
        "type": "enum",
        "options": ["本科可", "硕士优先", "硕士必须", "博士优先"],
        "description": "学历硬门槛",
    },
    "major_required": {
        "type": "list",
        "description": "专业背景要求（如：不限、计算机、经济/金融、数学/统计）",
    },
    "salary_range": {
        "type": "string",
        "description": "JD 提到的薪资区间，没有则留空",
    },
    "coding": {
        "type": "enum",
        "options": ["不需要", "加分项", "必须且日常写"],
        "description": "对'会写代码'的要求",
    },
    "work_experience_required": {
        "type": "enum",
        "options": ["不限/应届可", "1-2年", "3年及以上", "5年及以上"],
        "description": "全职工作经验要求（实习经历不算）",
    },
    "matched_experiences": {
        "type": "list",
        "description": "用户最匹配该岗位的 1-3 段经历（标题即可，从用户画像中选取）",
    },
}


# ── User profile compact summary ─────────────────────────────────────
# This is the reference CC uses when filling matched_experiences.
# Kept here as a constant; CC reads it from advisor_data if available.

USER_PROFILE_SUMMARY = """
梁佳仪 / 中大岭院经济学硕士 (2027届)
求职方向：AI/金融科技
核心技能：Python, R, SQL, 统计建模
毕设：Network Foundation of Power Law (一作, 势博弈+幂律分布)
实习：招行投行部
英语：CET-6 590
兴趣：数学形式化, 算法, Agent/多智能体系统, 大模型应用
偏好独立贡献者角色，喜欢从零构建胜过协调推动
"""


# ── Feature-based scoring ────────────────────────────────────────────

def score_from_features(features: Dict[str, Any]) -> Dict[str, Any]:
    """Deterministic scoring based on extracted features.

    Returns dimension scores (0-1) that _score_job can use.
    """
    if not features:
        return _empty_scores()

    skill_score = _score_skill_fit(features)
    experience_score = _score_experience_fit(features)
    industry_score = _score_industry_fit(features)
    growth_score = _score_growth_fit(features)
    cost_score = _score_cost_risk(features)
    hard_penalty = _score_hard_constraints(features)

    return {
        "feature_skill_fit": round(skill_score, 4),
        "feature_experience_fit": round(experience_score, 4),
        "feature_industry_fit": round(industry_score, 4),
        "feature_growth_fit": round(growth_score, 4),
        "feature_cost_risk": round(cost_score, 4),
        "feature_hard_constraints": round(hard_penalty, 4),
    }


def _empty_scores() -> Dict[str, float]:
    return {
        "feature_skill_fit": 0.0,
        "feature_experience_fit": 0.0,
        "feature_industry_fit": 0.0,
        "feature_growth_fit": 0.0,
        "feature_cost_risk": 0.0,
        "feature_hard_constraints": 0.0,
    }


# ── Individual dimension scorers ─────────────────────────────────────

def _score_skill_fit(f: Dict[str, Any]) -> float:
    """How well does the user's skill set match this role's requirements?

    Based on:
    - tech_depth vs user's actual capability
    - coding requirement alignment
    - tech_stack overlap
    """
    score = 0.0

    # tech_depth alignment
    # User can do: 要能调参和评估 level (stats/ML), not 从零搭建 level for heavy eng
    tech_depth = f.get("tech_depth", "")
    depth_map = {
        "无技术要求": 0.3,   # user is overqualified but not necessarily a fit
        "能用工具就行": 0.6,  # user can definitely do this
        "要能调参和评估": 0.85,  # sweet spot for user
        "要能从零搭建": 0.5,   # stretch but possible for ML/NLP tasks
    }
    score += depth_map.get(tech_depth, 0.3)

    # coding alignment
    coding = f.get("coding", "")
    coding_map = {
        "不需要": 0.2,
        "加分项": 0.8,  # user's coding is a competitive advantage
        "必须且日常写": 0.6,  # user can code but isn't CS major
    }
    score += coding_map.get(coding, 0.3)

    # tech_stack overlap
    user_stack = {"python", "r", "sql", "pytorch", "tensorflow", "pandas", "numpy",
                  "scipy", "sklearn", "scikit-learn", "jupyter", "git", "linux"}
    job_stack_raw = f.get("tech_stack", [])
    job_stack = {t.lower().strip() for t in job_stack_raw if t}
    if job_stack:
        overlap = len(user_stack & job_stack) / max(len(job_stack), 1)
        score += overlap
    else:
        score += 0.2  # no tech stack mentioned = neutral

    return min(1.0, score / 3.0)


def _score_experience_fit(f: Dict[str, Any]) -> float:
    """How many matching experiences does the user have?

    Based on matched_experiences count and quality indicators.
    """
    matched = f.get("matched_experiences", [])
    if not matched:
        return 0.15  # no match found, but not zero — could be incomplete extraction

    # 1 match = 0.4, 2 = 0.65, 3 = 0.85, more doesn't help
    count = len(matched)
    if count >= 3:
        return 0.85
    elif count == 2:
        return 0.65
    elif count == 1:
        return 0.4
    return 0.15


def _score_industry_fit(f: Dict[str, Any]) -> float:
    """Industry context alignment (fintech/quant/AI)."""
    major_raw = f.get("major_required", [])
    major_text = " ".join(major_raw).lower()

    score = 0.0
    # Economics background is a direct fit for finance/quant
    if any(kw in major_text for kw in ["经济", "金融", "统计", "不限"]):
        score += 0.4
    elif any(kw in major_text for kw in ["数学", "计算机"]):
        score += 0.3  # adjacent, user has overlap

    # quant_depth bonus
    quant = f.get("quant_depth", "")
    if quant == "原创研究":
        score += 0.3  # user's thesis is original research
    elif quant == "建模推断":
        score += 0.25
    elif quant == "基础统计":
        score += 0.15

    # daily_work that connects to user's analytical strengths
    daily = f.get("daily_work", "")
    if daily in ("分析", "构建"):
        score += 0.2
    elif daily == "调优":
        score += 0.15

    return min(1.0, score)


def _score_growth_fit(f: Dict[str, Any]) -> float:
    """Growth and role alignment."""
    score = 0.0

    # team_role: user prefers independent contributor or small project lead
    role = f.get("team_role", "")
    role_map = {
        "独立贡献者": 0.7,
        "小项目负责人": 0.6,
        "大项目协调者": 0.25,
        "支撑辅助角色": 0.15,
    }
    score += role_map.get(role, 0.3)

    # decision_scope: user prefers having autonomy
    decision = f.get("decision_scope", "")
    decision_map = {
        "自己能决定方案": 0.6,
        "需要推动共识": 0.35,
        "执行别人定的": 0.15,
    }
    score += decision_map.get(decision, 0.3)

    return min(1.0, score / 2.0)


def _score_cost_risk(f: Dict[str, Any]) -> float:
    """Work intensity penalty (higher = better for user)."""
    intensity = f.get("work_intensity", "")
    intensity_map = {
        "正常": 0.8,
        "偏忙": 0.5,
        "高强度": 0.25,
    }
    return intensity_map.get(intensity, 0.65)


def _score_hard_constraints(f: Dict[str, Any]) -> float:
    """Education floor check and other hard gates."""
    edu = f.get("education_floor", "")
    # User is Master's student
    edu_map = {
        "本科可": 1.0,
        "硕士优先": 1.0,
        "硕士必须": 1.0,
        "博士优先": 0.4,  # user doesn't have PhD
    }
    return edu_map.get(edu, 0.8)


# ── Ingest hard gate ────────────────────────────────────────────────

# Directions that are flat-out irrelevant to the user.
EXCLUDED_DIRECTION_HINTS = [
    "公务员", "考公", "博士后", "教师", "讲师", "副研究员", "科研助理",
    "生物实验", "湿实验", "细胞", "分子", "蛋白", "病理",
    "行政", "前台", "文员", "档案", "综合支持",
]

# Majors where the user has zero background and that are hard walls.
HARD_MAJOR_WALLS = ["医学", "药学", "法学", "建筑", "土木", "护理", "临床", "口腔", "中医"]


def should_reject_at_ingest(
    job: Dict[str, Any],
    features: Dict[str, Any],
) -> tuple[bool, str]:
    """Decide whether a job should be rejected before entering the store.

    Returns (rejected: bool, reason: str).
    """
    # --- Gate 1: excluded directions (keyword scan on JD text) ---
    text = " ".join([
        str(job.get("title", "")),
        str(job.get("job_family", "")),
        " ".join(job.get("keywords", []) or []),
        " ".join(job.get("requirements", []) or []),
        " ".join(job.get("responsibilities", []) or []),
    ])
    for hint in EXCLUDED_DIRECTION_HINTS:
        if hint in text:
            return True, f"命中排除方向: {hint}"

    # --- Gate 2: education floor (from features) ---
    if features:
        edu = features.get("education_floor", "")
        if edu in ("博士优先",):
            return True, f"学历门槛不达标: {edu}（用户为硕士）"

    # --- Gate 3: work experience (from features) ---
    if features:
        # Detect social-hire-only roles requiring 3+ years of full-time experience
        # The CC fills this during feature extraction by reading the JD
        work_exp = features.get("work_experience_required", "")
        if work_exp == "3年及以上":
            return True, f"工作经验不匹配: 要求{work_exp}全职经验（用户为应届生）"

    # --- Gate 4: hard major wall (from features) ---
    if features:
        majors = features.get("major_required", [])
        # Only reject if majors are specified AND none overlap with user's background
        if majors and majors != ["不限"]:
            user_majors = {"经济", "金融", "统计", "数学", "数量经济"}
            job_majors = set("".join(majors))
            has_overlap = any(
                any(um in mj for um in user_majors) or mj in ("不限", "理工科", "相关")
                for mj in majors
            )
            has_wall = any(
                any(wall in mj for wall in HARD_MAJOR_WALLS)
                for mj in majors
            )
            if has_wall and not has_overlap:
                return True, f"专业硬性壁垒: {majors}"

    return False, ""
