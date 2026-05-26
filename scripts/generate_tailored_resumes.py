from __future__ import annotations

import argparse
import json
import re
from datetime import date
from pathlib import Path
from typing import Any, Dict, List

from scripts.resume_core import prepare_resume_for_job_card, validate_resume_for_job_card


def default_shortlist_path() -> Path:
    jobs_dir = Path("outputs/jobs")
    dated = sorted(jobs_dir.glob("job_shortlist_*.json"))
    if dated:
        return dated[-1]
    return jobs_dir / "job_shortlist.json"

CURATED_BULLETS = {
    "project_lingnan_ai_database": "基于 FastAPI 搭建 AI 知识库，7 阶段 Pipeline 将交互日志蒸馏为可检索 Wiki（2400+篇），集成 RAG 问答与 SSE 流式输出。",
    "project_cal_cli_scheduler": "设计双池架构（任务池+日程池）的个人日程管理工具，采用 DDD 分层架构，支持 CLI 与 Web 前端，并开发 Claude Code Skill 支持自然语言操控。",
    "project_gongwen_lingnan": "使用 Claude Code Skill 从 Markdown 生成格式化 .docx 公文，支持岭南学院公文模板，含 Python 和 Node.js 双版本。",
    "intern_huamei_pe_data_analysis": "基于 Choice 与 Python 处理光伏行业数据，比较产业链投资前景并支持行业研究。",
    "intern_huamei_pe_due_diligence": "参与目标公司尽调与资料整理，协助准备路演材料并支持投资流程推进。",
    "intern_cmb_multi_agent_workflow": "使用 Claude Code 与 Python 搭建多 Agent 自动化流程，支持业务材料整理与数据处理。",
    "intern_cmb_reporting_automation": "汇总经营与绩效数据，自动化生成经营周报、支行画像与展示图，支撑经营分析。",
    "intern_cmb_business_tech_bridge": "对接业务与技术团队，撰写需求并校验数据平台结果，协助定位与修复缺陷。",
    "paper_overconfidence_first_author": "以第一作者完成过度自信与性别差异研究，围绕认知偏差与反馈机制开展行为经济学分析。",
    "paper_overconfidence_experiment_modeling": "使用 Python 与 R 完成行为实验数据清洗、可视化与贝叶斯更新建模。",
    "paper_network_foundation_power_law": "围绕势博弈与幂律分布进行数学建模，完成比较静态与网络经济学分析。",
    "paper_power_law_formal_analysis": "在 Power Law 研究中完成均衡分析、后向递归与理论证明。",
    "skill_python_r_data_stack": "熟练使用 Python 与 R 进行数据处理、统计建模与可视化，并在研究与实习场景中落地。",
    "skill_english_financial_reading": "具备英文研报与财报阅读能力，CET-6 590 分，可支持英文资料检索与写作。",
    "skill_sql_data_analysis": "具备 SQL 数据查询与分析能力，在实习与研究场景中使用 SQL 进行数据提取与处理。",
}

EVIDENCE_META = {
    "project_lingnan_ai_database": {"section": "项目经历", "heading": "Lingnan-AI-Database（AI 知识库平台）", "date": "2026年2月——2026年5月"},
    "project_cal_cli_scheduler": {"section": "项目经历", "heading": "cal（个人日程管理工具）", "date": "2025年11月——2026年3月"},
    "project_gongwen_lingnan": {"section": "项目经历", "heading": "gongwen_lingnan（公文生成工具）", "date": "2026年3月——2026年4月"},
    "intern_huamei_pe_data_analysis": {"section": "实习经历", "heading": "华美国际投资集团有限公司，股权投资事业部实习生", "date": "2022年7月——2022年8月"},
    "intern_huamei_pe_due_diligence": {"section": "实习经历", "heading": "华美国际投资集团有限公司，股权投资事业部实习生", "date": "2022年7月——2022年8月"},
    "intern_cmb_multi_agent_workflow": {"section": "实习经历", "heading": "招商银行广州分行，投行与金融市场部实习生", "date": "2025年12月——2026年2月"},
    "intern_cmb_reporting_automation": {"section": "实习经历", "heading": "招商银行广州分行，投行与金融市场部实习生", "date": "2025年12月——2026年2月"},
    "intern_cmb_business_tech_bridge": {"section": "实习经历", "heading": "招商银行广州分行，投行与金融市场部实习生", "date": "2025年12月——2026年2月"},
    "paper_overconfidence_first_author": {"section": "学术与研究经历", "heading": "过度自信的结构与性别差异研究（第一作者，SSRN: 5440815）", "date": "2023年——2025年"},
    "paper_overconfidence_experiment_modeling": {"section": "学术与研究经历", "heading": "过度自信的结构与性别差异研究（第一作者，SSRN: 5440815）", "date": "2023年——2025年"},
    "paper_network_foundation_power_law": {"section": "学术与研究经历", "heading": "Network Foundation of Power Law", "date": "2025年——2026年"},
    "paper_power_law_formal_analysis": {"section": "学术与研究经历", "heading": "Network Foundation of Power Law", "date": "2025年——2026年"},
    "skill_python_r_data_stack": {"section": "专业技能", "heading": "数据分析与建模", "date": ""},
    "skill_english_financial_reading": {"section": "专业技能", "heading": "英语与研究阅读", "date": ""},
    "skill_sql_data_analysis": {"section": "专业技能", "heading": "SQL 数据分析", "date": ""},
}

PROFILE_SUMMARIES = {
    "ai_pm": "应用经济学+统计/金融辅修背景，结合招行业务技术协同、AI项目与数据分析经历，适合 AI 产品、智能体产品与数据产品岗位。",
    "fintech_pm": "兼具金融场景理解、数据分析与 AI 工具落地经验，适合金融科技产品、数据平台与智能化工具方向岗位。",
    "research_data": "具备行为实验、Python/R 建模、金融与研究训练背景，适合量化研究、数据分析与研究工具相关岗位。",
}

SKILLS_BY_PROFILE = {
    "ai_pm": [
        "英语能力：具备英文研报与技术资料阅读能力，CET-6 590分。",
        "数据与研究：熟练使用 Python（Pandas、NumPy、Matplotlib、Scikit-learn）及 R 完成数据处理、建模与可视化。",
        "AI与产品：持续使用 Claude Code、LangGraph、FastAPI、Flask、SQLite 等工具搭建 AI 工作流、智能体与知识库原型。",
    ],
    "fintech_pm": [
        "英语能力：具备英文研报、财报与技术资料阅读能力，CET-6 590分。",
        "数据与金融：熟练使用 Python、R 完成经营分析、统计建模与研究支持，具备金融与投研基础。",
        "AI与协同：有多 Agent 自动化、需求分析、业务技术协同与数据平台校验实践。",
    ],
    "research_data": [
        "英语能力：具备英文论文、研报与财报阅读能力，CET-6 590分。",
        "研究与建模：熟练使用 Python、R 进行行为实验分析、贝叶斯建模、统计推断与可视化。",
        "技术工具：持续使用 Claude Code、Agent 工作流与数据分析工具提升研究与信息处理效率。",
    ],
}

FALLBACK_ORDER = {
    "ai_pm": [
        "project_lingnan_ai_database",
        "project_cal_cli_scheduler",
        "intern_cmb_multi_agent_workflow",
        "intern_cmb_business_tech_bridge",
        "paper_overconfidence_experiment_modeling",
    ],
    "fintech_pm": [
        "intern_cmb_multi_agent_workflow",
        "intern_cmb_reporting_automation",
        "intern_cmb_business_tech_bridge",
        "intern_huamei_pe_data_analysis",
        "project_lingnan_ai_database",
    ],
    "research_data": [
        "paper_overconfidence_experiment_modeling",
        "paper_network_foundation_power_law",
        "paper_power_law_formal_analysis",
        "intern_huamei_pe_data_analysis",
        "skill_python_r_data_stack",
    ],
}


def choose_profile(job: Dict[str, Any]) -> str:
    track = str(job.get("target_track") or "")
    text = " ".join([
        str(job.get("title") or ""),
        str(job.get("job_family") or ""),
        " ".join(job.get("keywords", [])),
    ])
    if track == "quant_research":
        return "research_data"
    if any(token in text for token in ["金融", "投研", "风控", "银行", "数据平台"]):
        return "fintech_pm"
    return "ai_pm"


def _supplement_bullets(profile: str, rewritten: List[Dict[str, Any]], prepared: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected_ids = [bullet["evidence_ids"][0] for bullet in rewritten if bullet.get("evidence_ids")]
    for evidence_id in FALLBACK_ORDER.get(profile, []):
        if evidence_id in selected_ids:
            continue
        for candidate in prepared["draft"]["bullets"]:
            if candidate.get("evidence_ids") == [evidence_id]:
                rewritten.append({**candidate, "text": CURATED_BULLETS.get(evidence_id, candidate["text"])})
                selected_ids.append(evidence_id)
                break
        if len(rewritten) >= 6:
            break
    return rewritten


def rewrite_bullets(profile: str, prepared: Dict[str, Any]) -> List[Dict[str, Any]]:
    rewritten = []
    for bullet in prepared["draft"]["bullets"]:
        evidence_ids = bullet.get("evidence_ids") or []
        evidence_id = evidence_ids[0] if evidence_ids else ""
        rewritten.append({**bullet, "text": CURATED_BULLETS.get(evidence_id, bullet["text"])})
    rewritten = _supplement_bullets(profile, rewritten, prepared)
    return rewritten


def group_sections(validated: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    sections: Dict[str, Dict[str, Dict[str, Any]]] = {}
    for bullet in validated["resume_draft"]["bullets"]:
        evidence_id = (bullet.get("evidence_ids") or [""])[0]
        meta = EVIDENCE_META.get(evidence_id, {"section": bullet.get("section", "相关经历"), "heading": evidence_id, "date": ""})
        section_name = meta["section"]
        section_group = sections.setdefault(section_name, {})
        block = section_group.setdefault(meta["heading"], {"heading": meta["heading"], "date": meta.get("date", ""), "bullets": []})
        if bullet["text"] not in block["bullets"]:
            block["bullets"].append(bullet["text"])
    return {key: list(value.values()) for key, value in sections.items()}


def _render_custom_sections_html(job: Dict[str, Any], validated: Dict[str, Any], profile: str) -> str:
    sections = group_sections(validated)
    skills = SKILLS_BY_PROFILE[profile]

    lines: list[str] = []

    section_order = ["项目经历", "实习经历", "学术与研究经历"]
    for section_name in section_order:
        blocks = sections.get(section_name, [])
        if not blocks:
            continue
        lines.append(f"<h2>{section_name}</h2>")
        for block in blocks:
            heading = block["heading"]
            date_text = block["date"]
            if date_text:
                lines.append(f'<div class="entry-header">')
                lines.append(f'<span class="heading">{heading}</span>')
                lines.append(f'<span class="date">{date_text}</span>')
                lines.append(f"</div>")
            else:
                lines.append(f'<div class="entry-header">')
                lines.append(f'<span class="heading">{heading}</span>')
                lines.append(f"</div>")
            lines.append("<ul>")
            for bullet in block["bullets"][:3]:
                lines.append(f"<li>{bullet}</li>")
            lines.append("</ul>")

    lines.append("<h2>专业技能</h2>")
    lines.append('<ul class="skills-list">')
    for skill in skills:
        lines.append(f"<li>{skill}</li>")
    lines.append("</ul>")
    return "\n".join(lines)


def build_html(job: Dict[str, Any], validated: Dict[str, Any], profile: str, base_html_path: Path) -> str:
    base_html = base_html_path.read_text(encoding="utf-8")
    marker = "<!-- RESUME_CONTENT -->"
    if marker not in base_html:
        raise ValueError(f"base HTML template missing {marker}: {base_html_path}")
    custom_sections = _render_custom_sections_html(job, validated, profile)
    return base_html.replace(marker, custom_sections)


def sanitize_filename(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", text)
    slug = re.sub(r"_+", "_", slug).strip("_")
    return slug or "resume"


def generate(
    shortlist_path: Path,
    evidence_path: Path,
    advisor_data_dir: Path,
    output_dir: Path,
    limit: int,
    base_html_path: Path,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    shortlist = json.loads(shortlist_path.read_text(encoding="utf-8"))
    selected = shortlist[:limit]
    generated = []
    index_lines = [
        "# 定制简历批次索引",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "| 序号 | 公司 | 岗位 | Profile | Harness | 文件 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for idx, job in enumerate(selected, start=1):
        profile = choose_profile(job)
        prepared = prepare_resume_for_job_card(job, evidence_path)
        rewritten = rewrite_bullets(profile, prepared)
        validated = validate_resume_for_job_card(
            job,
            rewritten,
            evidence_path=evidence_path,
            writer_name="curated_batch",
            advisor_data_dir=advisor_data_dir,
        )
        html = build_html(job, validated, profile, base_html_path)
        filename = f"resume_{idx:02d}_{job['normalized_job_id']}_{sanitize_filename(profile)}.html"
        output_path = output_dir / filename
        output_path.write_text(html, encoding="utf-8")
        generated.append({
            "company": job["company"],
            "title": job["title"],
            "profile": profile,
            "harness_passed": validated["harness_report"]["passed"],
            "html_path": str(output_path),
            "output_dir": validated.get("output_dir", ""),
        })
        index_lines.append(
            f"| {idx} | {job['company']} | {job['title']} | {profile} | {'PASS' if validated['harness_report']['passed'] else 'FAIL'} | {filename} |"
        )
    index_path = output_dir / f"resume_batch_index_{date.today().strftime('%Y%m%d')}.md"
    index_path.write_text("\n".join(index_lines) + "\n", encoding="utf-8")
    return {
        "generated": generated,
        "index_path": str(index_path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate tailored HTML resumes from the ranked shortlist.")
    parser.add_argument("--shortlist", default=str(default_shortlist_path()))
    parser.add_argument("--evidence-jsonl", default="advisor_data/resume/evidence.jsonl")
    parser.add_argument("--advisor-data-dir", default="advisor_data")
    parser.add_argument("--output-dir", default="outputs/resumes")
    parser.add_argument("--base-html", default="resume_master.html")
    parser.add_argument("--limit", type=int, default=6)
    args = parser.parse_args()
    result = generate(
        Path(args.shortlist),
        Path(args.evidence_jsonl),
        Path(args.advisor_data_dir),
        Path(args.output_dir),
        args.limit,
        Path(args.base_html),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
