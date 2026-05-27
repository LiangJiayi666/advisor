from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

DATE_PATTERN = re.compile(r"(?P<year>20\d{2})[-/.年](?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})")
PARTIAL_DATE_PATTERN = re.compile(r"(?P<month>\d{1,2})[-/.月](?P<day>\d{1,2})(?:日)?")
CHINESE_DATE_PATTERN = re.compile(r"(?P<year>20\d{2})年(?P<month>\d{1,2})月(?P<day>\d{1,2})日")
LINE_ITEM_PATTERN = re.compile(r"^(?:[-*•]|\d+[.、）)])\s*")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9+.#_-]+|[一-鿿]{2,}")
DEADLINE_HINTS = ["截止", "网申截止", "招满即止", "尽快", "ASAP", "rolling", "近期到岗"]
INTENSE_HINTS = ["996", "高强度", "出差", "加班", "oncall", "值班"]
PRIMARY_KEYWORDS = [
    "大模型", "AIGC", "Agent", "多智能体", "工作流", "自动化", "RAG",
    "算法", "机器学习", "深度学习", "NLP", "LLM", "智能体",
    "金融科技", "AI应用",
]
BACKUP_KEYWORDS = ["量化", "因子", "策略", "中频", "投研", "研究员", "数据科学"]
ADJACENT_KEYWORDS = [
    "Python", "R", "SQL", "统计", "建模", "实验", "分析", "可视化", "平台",
    "产品经理", "AI产品经理", "数据产品", "需求分析", "产品设计", "用户研究",
]
AI_ENGINEER_HINTS = ["算法工程师", "AI工程师", "大模型", "NLP", "LLM", "AIGC", "Agent", "多智能体", "机器学习", "深度学习"]
AI_PRODUCT_HINTS = ["AI产品", "产品经理", "大模型产品", "AIGC产品", "AI应用产品", "Agent产品"]
QUANT_HINTS = ["量化", "因子", "策略研究", "中频", "投研", "研究员"]
ADJACENT_TRACK_HINTS = ["数据产品", "分析", "平台产品", "自动化", "风控", "推荐", "增长"]
EXPLICIT_EXCLUSION_HINTS = ["公务员", "考公", "博士后", "教师", "讲师", "副研究员", "科研助理"]
PURE_BIOLOGY_HINTS = ["生物实验", "湿实验", "细胞", "分子", "蛋白", "病理"]
ADMIN_SUPPORT_HINTS = ["行政", "前台", "文员", "档案", "综合支持"]
FINTECH_HINTS = ["金融", "银行", "证券", "基金", "投研", "风控", "量化", "广告投放", "营销科技"]


@dataclass
class UserPreferences:
    preferred_cities: List[str]
    primary_keywords: List[str]
    backup_keywords: List[str]
    adjacent_keywords: List[str]
    primary_families: List[str]
    backup_families: List[str]
    explicit_exclusions: List[str]
    inferred_exclusions: List[str]


def default_preferences() -> UserPreferences:
    return UserPreferences(
        preferred_cities=["广州", "深圳"],
        primary_keywords=PRIMARY_KEYWORDS,
        backup_keywords=BACKUP_KEYWORDS,
        adjacent_keywords=ADJACENT_KEYWORDS,
        primary_families=["AI/算法", "金融科技产品", "数据科学"],
        backup_families=["产品", "数据产品", "量化研究", "研究"],
        explicit_exclusions=["学术岗位", "科研教职路径", "考公", "公务员岗位"],
        inferred_exclusions=["纯生物实验岗位", "纯行政支持岗位", "长反馈周期且高不确定性的纯研究环境"],
    )


def _norm_text(value: Any) -> str:
    return str(value or "").strip()


def _norm_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [str(value).strip()] if str(value).strip() else []


def _normalize_company(value: str) -> str:
    text = _norm_text(value)
    if not text:
        return "unknown"
    replacements = {
        "字节AI": "字节跳动",
        "字节": "字节跳动",
        "抖音": "字节跳动",
        "TikTok": "字节跳动",
        "阿里": "阿里巴巴",
        "腾讯公司": "腾讯",
        "招商银行广州分行": "招商银行",
        "安克创新": "安克",
        "MINISO": "名创优品",
        "华夏基金股权子公司": "华夏基金",
    }
    return replacements.get(text, text)


def _normalize_city(value: str) -> str:
    text = _norm_text(value)
    if not text:
        return "unknown"
    text = text.replace("市", "")
    parts = [part.strip() for part in re.split(r"[,，/]", text) if part.strip()]
    return ", ".join(parts) if parts else "unknown"


def _normalize_title(value: str) -> str:
    text = _norm_text(value)
    text = re.sub(r"\s+", "", text)
    return text


def _flatten_recruit_type(value: Any) -> str:
    if isinstance(value, dict):
        return _norm_text(value.get("name") or value.get("i18n_name") or value.get("en_name"))
    return _norm_text(value)


def _tokenize(text: str) -> List[str]:
    return [token for token in TOKEN_PATTERN.findall(text.lower()) if token]


def _extract_terms_from_lines(lines: Iterable[str]) -> List[str]:
    seen: List[str] = []
    for line in lines:
        clean = LINE_ITEM_PATTERN.sub("", _norm_text(line)).strip("：:；;，, ")
        for token in _tokenize(clean):
            if len(token) <= 1:
                continue
            if token not in seen:
                seen.append(token)
    return seen


def _parse_date_from_text(text: str, today: date) -> tuple[str, str]:
    for pattern in [DATE_PATTERN, CHINESE_DATE_PATTERN]:
        match = pattern.search(text)
        if match:
            year = int(match.group("year"))
            month = int(match.group("month"))
            day = int(match.group("day"))
            try:
                parsed = date(year, month, day)
            except ValueError:
                continue
            return parsed.isoformat(), "explicit"
    match = PARTIAL_DATE_PATTERN.search(text)
    if match:
        month = int(match.group("month"))
        day = int(match.group("day"))
        year = today.year
        try:
            parsed = date(year, month, day)
        except ValueError:
            return "", "none"
        if parsed < today:
            try:
                parsed = date(year + 1, month, day)
            except ValueError:
                return "", "none"
        return parsed.isoformat(), "inferred"
    return "", "none"


def _split_section_lines(lines: List[str]) -> List[str]:
    items: List[str] = []
    for line in lines:
        clean = _norm_text(line)
        if not clean:
            continue
        clean = LINE_ITEM_PATTERN.sub("", clean).strip()
        if clean:
            items.append(clean)
    return items


def parse_raw_markdown(path: Path, today: date | None = None) -> Dict[str, Any]:
    today = today or date.today()
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    title = ""
    company = ""
    city = ""
    requirements: List[str] = []
    responsibilities: List[str] = []
    deadline_hits: List[str] = []
    current_section = ""
    section_lines: Dict[str, List[str]] = defaultdict(list)

    for raw_line in lines:
        line = raw_line.rstrip()
        if line.startswith("# ") and not title:
            title = line[2:].strip()
            continue
        if line.startswith("Company:"):
            company = line.split(":", 1)[1].strip()
            continue
        if line.startswith("City:"):
            city = line.split(":", 1)[1].strip()
            continue
        if line.startswith("城市:"):
            city = line.split(":", 1)[1].strip()
            continue
        if line.startswith("Requirements:"):
            current_section = "requirements"
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                section_lines[current_section].append(remainder)
            continue
        if line.startswith("Description:"):
            current_section = "description"
            remainder = line.split(":", 1)[1].strip()
            if remainder:
                section_lines[current_section].append(remainder)
            continue
        if line.startswith("## "):
            heading = line[3:].strip().lower()
            if "requirement" in heading or "岗位要求" in heading or heading == "requirements":
                current_section = "requirements"
            elif "description" in heading or "岗位职责" in heading:
                current_section = "description"
            else:
                current_section = ""
            continue
        if any(hint in line for hint in DEADLINE_HINTS):
            deadline_hits.append(line.strip())
        if current_section:
            section_lines[current_section].append(line)

    requirements = _split_section_lines(section_lines.get("requirements", []))
    responsibilities = _split_section_lines(section_lines.get("description", []))
    deadline_text = " | ".join(deadline_hits)
    deadline_date, deadline_confidence = _parse_date_from_text(deadline_text, today)
    keywords = _extract_terms_from_lines([title, company, city] + requirements[:8] + responsibilities[:8])
    return {
        "raw_path": str(path),
        "title": title,
        "company": company,
        "city": city,
        "requirements": requirements,
        "responsibilities": responsibilities,
        "keywords": keywords,
        "deadline_text": deadline_text,
        "deadline_date": deadline_date,
        "deadline_confidence": deadline_confidence,
        "text": text,
    }


def load_jobs(path: Path) -> List[Dict[str, Any]]:
    jobs: List[Dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                jobs.append(json.loads(line))
    return jobs


def load_evidence_terms(path: Path) -> List[str]:
    terms: List[str] = []
    if not path.exists():
        return terms
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            for value in _norm_list(row.get("skills")) + _norm_list(row.get("claims")) + [_norm_text(row.get("title"))]:
                for token in _tokenize(value):
                    if token not in terms:
                        terms.append(token)
    return terms


def load_raw_index(raw_dir: Path, today: date | None = None) -> Dict[str, Any]:
    today = today or date.today()
    direct: Dict[str, Dict[str, Any]] = {}
    by_title_company: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    by_title_only: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    parsed_items: List[Dict[str, Any]] = []
    for path in sorted(raw_dir.glob("*.md")):
        parsed = parse_raw_markdown(path, today=today)
        lines = _read_raw_lines(path)
        parsed["title"] = _clean_raw_title(parsed.get("title") or (lines[0] if lines else ""))
        parsed["company"] = _infer_company_from_raw(path, parsed, lines)
        parsed["city"] = _infer_city_from_lines(lines, parsed.get("city") or "")
        parsed_items.append(parsed)
        stem = path.stem
        direct[stem] = parsed
        title_key = _normalize_title(parsed.get("title"))
        company_key = _normalize_company(parsed.get("company"))
        by_title_only[title_key].append(parsed)
        by_title_company[(title_key, company_key)].append(parsed)
    return {
        "direct": direct,
        "by_title_company": by_title_company,
        "by_title_only": by_title_only,
        "items": parsed_items,
    }


def _source_to_prefix(source: str) -> str:
    source_l = source.lower()
    if "alibaba" in source_l or source_l.startswith("ali"):
        return "ali"
    if "anker" in source_l:
        return "anker"
    if "tencent" in source_l:
        return "tc"
    if "kuaishou" in source_l or source_l.startswith("ks"):
        return "ks"
    if "58tc" in source_l or "58tongcheng" in source_l:
        return "58tc"
    if "g-bits" in source_l or "gbits" in source_l or "jibite" in source_l:
        return "gb"
    return ""


def link_raw(job: Dict[str, Any], raw_index: Dict[str, Any]) -> Dict[str, Any] | None:
    source = _norm_text(job.get("source")).lower()
    job_id = _norm_text(job.get("job_id"))
    prefix = _source_to_prefix(source)
    if prefix and job_id:
        direct_key = f"{prefix}_{job_id}"
        if direct_key in raw_index["direct"]:
            return raw_index["direct"][direct_key]
    title_key = _normalize_title(job.get("title"))
    company_key = _normalize_company(job.get("company"))
    exact = raw_index["by_title_company"].get((title_key, company_key), [])
    if len(exact) == 1:
        return exact[0]
    if "bytedance" in source or "字节" in company_key:
        candidates = raw_index["by_title_only"].get(title_key, [])
        if len(candidates) == 1:
            return candidates[0]
    return None


def _read_raw_lines(path: Path) -> List[str]:
    return path.read_text(encoding="utf-8", errors="ignore").splitlines()


def _clean_raw_title(title: str) -> str:
    clean = _norm_text(title)
    return clean.removesuffix("- 原始JD").strip()


def _infer_city_from_lines(lines: List[str], parsed_city: str) -> str:
    city = _norm_text(parsed_city)
    if city and city != "unknown":
        return city
    if len(lines) >= 2:
        second = _norm_text(lines[1])
        if second and not any(second.startswith(prefix) for prefix in ["Company:", "City:", "城市:", "部门:", "##", "Requirements:", "Description:"]):
            return second
    for line in lines[:20]:
        if line.startswith("City:") or line.startswith("城市:"):
            return _norm_text(line.split(":", 1)[1])
    return city or "unknown"


def _infer_company_from_raw(path: Path, parsed: Dict[str, Any], lines: List[str]) -> str:
    company = _normalize_company(parsed.get("company"))
    if company != "unknown":
        return company
    title = _clean_raw_title(parsed.get("title") or (lines[0] if lines else ""))
    text = "\n".join(lines[:40])
    stem = path.stem.lower()

    bracket_match = re.match(r"^\[(?P<company>[^\]]+)\]", title)
    if bracket_match:
        return _normalize_company(bracket_match.group("company"))

    explicit_match = re.match(r"^(?:公司[:：])?(?P<company>[^（(\-｜|]+)", title)
    if title.startswith("公司：") and explicit_match:
        return _normalize_company(explicit_match.group("company"))

    for delimiter in [" - ", "｜", "|"]:
        if delimiter in title:
            prefix = _norm_text(title.split(delimiter, 1)[0])
            if prefix and len(prefix) <= 20:
                return _normalize_company(prefix)

    email_domain_map = {
        "bytedance.com": "字节跳动",
        "tiktok.com": "字节跳动",
        "lighthousecap.cn": "光源资本",
        "chinaamc.com": "华夏基金",
        "cibwm.com.cn": "兴银理财",
        "sinexcel.com": "盛弘电气",
    }
    for line in lines[:20]:
        if "@" not in line:
            continue
        lowered = line.lower()
        for domain, inferred_company in email_domain_map.items():
            if domain in lowered:
                return inferred_company

    guesses = [
        ("名创优品", ["MINISO", "名创优品", "job_miniso_"]),
        ("招银理财", ["招银理财", "cmbwm"]),
        ("广发基金", ["广发基金", "job_gf_"]),
        ("美团", ["美团", "核心本地商业", "北斗实习", "外卖业务"]),
        ("滴滴", ["滴滴", "didi", "IBG产品运营"]),
        ("CVTE", ["CVTE", "cvte_"]),
        ("快手", ["快手", "ks_"]),
        ("阿里巴巴", ["阿里巴巴", "ali_"]),
        ("安克", ["安克", "anker_", "安克创新"]),
        ("腾讯", ["腾讯", "tc_"]),
        ("吉比特", ["吉比特", "gb_"]),
        ("58同城", ["58同城", "58tc_"]),
        ("字节跳动", ["字节", "抖音", "豆包", "火山方舟", "bd_", "tiktok"]),
        ("韶音科技", ["韶音科技", "shokz"]),
        ("盛弘电气", ["盛弘电气", "sinexcel"]),
        ("华夏基金", ["华夏基金"]),
        ("光源资本", ["光源资本"]),
        ("兴银理财", ["兴银理财"]),
        ("中信资本", ["中信资本"]),
        ("国投证券", ["国投证券"]),
        ("中国银河证券", ["中国银河证券"]),
        ("越秀地产", ["越秀地产"]),
        ("申万宏源", ["申万宏源"]),
        ("财通资本", ["财通资本"]),
        ("玄元投资", ["玄元投资"]),
    ]
    haystack = "\n".join([title, text, path.name, stem])
    for company_name, keywords in guesses:
        if any(keyword.lower() in haystack.lower() for keyword in keywords):
            return company_name
    return "美团"


def _infer_job_id_from_path(path: Path) -> str:
    stem = path.stem
    prefixes = ["ali_", "anker_", "tc_", "ks_", "bd_", "58tc_", "gb_"]
    for prefix in prefixes:
        if stem.startswith(prefix):
            suffix = stem[len(prefix):].strip()
            return suffix or stem
    return stem


def _infer_source_from_raw(path: Path, company: str) -> str:
    stem = path.stem.lower()
    if stem.startswith("ali_") or company == "阿里巴巴":
        return "alibaba_raw_backfill"
    if stem.startswith("anker_") or company == "安克":
        return "anker_raw_backfill"
    if stem.startswith("tc_") or company == "腾讯":
        return "tencent_raw_backfill"
    if stem.startswith("ks_") or company == "快手":
        return "kuaishou_raw_backfill"
    if stem.startswith("bd_") or company == "字节跳动":
        return "bytedance_raw_backfill"
    if stem.startswith("58tc_") or company == "58同城":
        return "58tc_raw_backfill"
    if stem.startswith("gb_") or company == "吉比特":
        return "g-bits_raw_backfill"
    if company == "名创优品":
        return "miniso_raw_backfill"
    if company == "美团":
        return "meituan_raw_backfill"
    if company == "招银理财":
        return "cmbwm_raw_backfill"
    if company == "广发基金":
        return "gfund_raw_backfill"
    if company == "CVTE":
        return "cvte_raw_backfill"
    return "manual_raw_backfill"


def _infer_job_family_from_raw(title: str, text: str) -> str:
    merged = f"{title} {text}"
    if any(token in merged for token in ["算法", "研发", "开发", "工程师", "模型"]):
        return "AI/算法"
    if any(token in merged for token in ["量化", "分析师", "数据分析", "数据科学", "研究员", "策略研究"]):
        return "数据"
    if any(token in merged for token in ["产品经理", "产品策划", "产品运营", "产品实习", "产品"]):
        return "产品"
    return "其他"


def _infer_recruit_type_from_raw(title: str, text: str) -> str:
    merged = f"{title} {text}"
    if any(token in merged for token in ["实习", "暑期", "留用实习", "北斗实习"]):
        return "实习"
    if any(token in merged for token in ["校招", "27届"]):
        return "校招"
    if any(token in merged for token in ["专家", "高级"]):
        return "社招"
    return "unknown"


def _infer_bucket_and_reason(title: str, text: str) -> tuple[str, str]:
    merged = f"{title} {text}"
    strong_terms = PRIMARY_KEYWORDS + BACKUP_KEYWORDS + ADJACENT_KEYWORDS
    if any(term.lower() in merged.lower() for term in strong_terms):
        return "strong", "strong_keyword"
    return "review", "raw_backfill"


def build_structured_job_from_raw(path: Path) -> Dict[str, Any]:
    parsed = parse_raw_markdown(path)
    lines = _read_raw_lines(path)
    title = _clean_raw_title(parsed.get("title") or (lines[0] if lines else ""))
    text = parsed.get("text") or "\n".join(lines)
    company = _infer_company_from_raw(path, parsed, lines)
    city = _infer_city_from_lines(lines, parsed.get("city") or "")
    bucket, reason = _infer_bucket_and_reason(title, text)
    return {
        "job_id": _infer_job_id_from_path(path),
        "title": title,
        "company": company,
        "city": city,
        "recruit_type": _infer_recruit_type_from_raw(title, text),
        "job_family": _infer_job_family_from_raw(title, text),
        "source": _infer_source_from_raw(path, company),
        "source_url": "",
        "bucket": bucket,
        "reason": reason,
    }


def inventory_unlinked_raw_jobs(jobs_jsonl: Path, raw_dir: Path, today: date | None = None) -> Dict[str, Any]:
    jobs = load_jobs(jobs_jsonl)
    raw_index = load_raw_index(raw_dir, today=today)
    linked_raw = set()
    for job in jobs:
        match = link_raw(job, raw_index)
        if match:
            linked_raw.add(Path(match["raw_path"]).name)
    all_raw_paths = sorted(raw_dir.glob("*.md"))
    unlinked_paths = [path for path in all_raw_paths if path.name not in linked_raw]
    items: List[Dict[str, Any]] = []
    company_counter: Counter[str] = Counter()
    for path in unlinked_paths:
        parsed = parse_raw_markdown(path, today=today)
        lines = _read_raw_lines(path)
        title = _clean_raw_title(parsed.get("title") or (lines[0] if lines else ""))
        company = _infer_company_from_raw(path, parsed, lines)
        city = _infer_city_from_lines(lines, parsed.get("city") or "")
        inferable = bool(title and company and company != "unknown")
        items.append({
            "raw_file": path.name,
            "title": title,
            "company": company,
            "city": city,
            "inferable": inferable,
        })
        company_counter[company] += 1
    return {
        "job_count": len(jobs),
        "raw_count": len(all_raw_paths),
        "linked_raw_count": len(linked_raw),
        "unlinked_raw_count": len(unlinked_paths),
        "items": items,
        "by_company": dict(company_counter),
    }


def sync_unlinked_raw_jobs(jobs_jsonl: Path, raw_dir: Path, today: date | None = None) -> Dict[str, Any]:
    jobs = load_jobs(jobs_jsonl)
    inventory = inventory_unlinked_raw_jobs(jobs_jsonl, raw_dir, today=today)
    existing_ids = {_norm_text(job.get("job_id")) for job in jobs if _norm_text(job.get("job_id"))}
    existing_keys = {
        (
            _normalize_title(job.get("title")),
            _normalize_company(job.get("company")),
            _normalize_city(job.get("city")),
        )
        for job in jobs
    }
    added: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    item_by_name = {item["raw_file"]: item for item in inventory["items"]}
    for item in inventory["items"]:
        path = raw_dir / item["raw_file"]
        card = build_structured_job_from_raw(path)
        key = (
            _normalize_title(card.get("title")),
            _normalize_company(card.get("company")),
            _normalize_city(card.get("city")),
        )
        if not item["inferable"]:
            skipped.append({**item, "reason": "company_or_title_not_inferable"})
            continue
        if card["job_id"] in existing_ids or key in existing_keys:
            skipped.append({**item, "reason": "already_present_or_duplicate"})
            continue
        jobs.append(card)
        existing_ids.add(card["job_id"])
        existing_keys.add(key)
        added.append(card)
    if added:
        with jobs_jsonl.open("w", encoding="utf-8") as handle:
            for job in jobs:
                handle.write(json.dumps(job, ensure_ascii=False) + "\n")
    return {
        "added_count": len(added),
        "skipped_count": len(skipped),
        "added": added,
        "skipped": skipped,
        "before_unlinked_raw_count": inventory["unlinked_raw_count"],
    }


def _derive_keywords(job: Dict[str, Any], raw_match: Dict[str, Any] | None) -> List[str]:
    pieces: List[str] = []
    pieces.extend(_norm_list(job.get("keywords")))
    pieces.extend(_norm_list(job.get("requirements")))
    pieces.extend(_norm_list(job.get("responsibilities")))
    pieces.extend([_norm_text(job.get("title")), _norm_text(job.get("job_family")), _norm_text(job.get("reason"))])
    if raw_match:
        pieces.extend(raw_match.get("requirements", []))
        pieces.extend(raw_match.get("responsibilities", []))
        pieces.extend(raw_match.get("keywords", []))
    return _extract_terms_from_lines(pieces)


def _completeness(job: Dict[str, Any], raw_match: Dict[str, Any] | None) -> float:
    score = 0.0
    if _norm_text(job.get("job_id")):
        score += 0.15
    if _norm_text(job.get("city")):
        score += 0.1
    if _norm_text(job.get("source_url")):
        score += 0.1
    if raw_match:
        score += 0.2
    if raw_match and raw_match.get("requirements"):
        score += 0.2
    if raw_match and raw_match.get("responsibilities"):
        score += 0.15
    if raw_match and raw_match.get("deadline_date"):
        score += 0.05
    if raw_match and raw_match.get("keywords"):
        score += 0.05
    return round(min(score, 1.0), 4)


def _derive_track(text: str) -> str:
    if any(hint.lower() in text.lower() for hint in AI_ENGINEER_HINTS):
        return "ai_engineer"
    if any(hint.lower() in text.lower() for hint in QUANT_HINTS):
        return "quant_research"
    if any(hint.lower() in text.lower() for hint in AI_PRODUCT_HINTS):
        return "ai_pm"
    if any(hint.lower() in text.lower() for hint in ADJACENT_TRACK_HINTS):
        return "adjacent"
    return "other"


def _contains_any(text: str, keywords: Iterable[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword and keyword.lower() in lowered)


def _ratio(count: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(min(max(count / total, 0.0), 1.0), 4)


def _city_match(city: str, preferred_cities: List[str]) -> bool:
    if city == "unknown":
        return False
    return any(preferred in city for preferred in preferred_cities)


def _deadline_urgency(deadline_date: str, deadline_text: str, today: date) -> Tuple[float, str]:
    if deadline_date:
        try:
            parsed = datetime.strptime(deadline_date, "%Y-%m-%d").date()
        except ValueError:
            parsed = None
        if parsed:
            delta = (parsed - today).days
            if delta <= 0:
                return 1.0, "截止日期已到或非常接近"
            if delta <= 3:
                return 0.98, f"{delta}天内截止"
            if delta <= 7:
                return 0.9, f"{delta}天内截止"
            if delta <= 14:
                return 0.78, f"两周内截止"
            if delta <= 30:
                return 0.6, f"30天内截止"
            return 0.35, "有明确截止日期但不算近"
    if any(hint.lower() in deadline_text.lower() for hint in ["招满即止", "尽快", "asap", "rolling"]):
        return 0.72, "存在高时效文本信号"
    return 0.15, "未发现明确截止时间"


def _experience_fit(text: str, evidence_terms: List[str]) -> float:
    if not evidence_terms:
        return 0.0
    matches = _contains_any(text, evidence_terms)
    return _ratio(matches, min(len(evidence_terms), 40))


def _score_job(job: Dict[str, Any], prefs: UserPreferences, evidence_terms: List[str], today: date) -> Dict[str, Any]:
    title = _norm_text(job.get("title"))
    company = _norm_text(job.get("company"))
    city = _normalize_city(job.get("city"))
    job_family = _norm_text(job.get("job_family"))
    track = _norm_text(job.get("target_track"))
    keywords = _norm_list(job.get("keywords"))
    requirements = _norm_list(job.get("requirements"))
    responsibilities = _norm_list(job.get("responsibilities"))
    text = " ".join([title, company, city, job_family, " ".join(keywords), " ".join(requirements), " ".join(responsibilities)])

    penalties: Dict[str, str] = {}
    if any(hint in text for hint in EXPLICIT_EXCLUSION_HINTS):
        penalties["explicit_exclusion"] = "命中明确排除方向"
    if any(hint in text for hint in PURE_BIOLOGY_HINTS):
        penalties["pure_biology"] = "偏纯生物实验方向"
    if any(hint in text for hint in ADMIN_SUPPORT_HINTS):
        penalties["pure_admin"] = "偏纯行政支持方向"
    if prefs.preferred_cities and city != "unknown" and not _city_match(city, prefs.preferred_cities):
        penalties["city"] = f"城市 {city} 不在当前优先城市 {prefs.preferred_cities} 中"

    hard_constraints = 1.0
    if "explicit_exclusion" in penalties:
        hard_constraints = 0.0
    elif penalties:
        hard_constraints = max(0.15, 1.0 - 0.18 * len(penalties))

    primary_hits = _contains_any(text, prefs.primary_keywords + prefs.primary_families)
    backup_hits = _contains_any(text, prefs.backup_keywords + prefs.backup_families)
    adjacent_hits = _contains_any(text, prefs.adjacent_keywords)

    if track == "ai_engineer":
        track_fit = 1.0
    elif track == "quant_research":
        track_fit = 0.82
    elif track == "ai_pm":
        track_fit = 0.65
    elif track == "adjacent":
        track_fit = 0.6
    else:
        track_fit = 0.25 if primary_hits or backup_hits else 0.08

    skill_fit = min(1.0, primary_hits * 0.11 + backup_hits * 0.09 + adjacent_hits * 0.04)
    experience_fit = min(1.0, _experience_fit(text, evidence_terms) * 1.6)
    fintech_hits = _contains_any(text, FINTECH_HINTS)
    industry_fit = min(1.0, fintech_hits * 0.18 + (0.25 if track == "ai_engineer" else 0.0) + (0.35 if track == "quant_research" else 0.0))
    growth_fit = min(1.0, _contains_any(text, ["平台", "自动化", "agent", "workflow", "分析", "数据", "需求", "协作"]) * 0.12)

    cost_risk = 0.72
    if any(hint.lower() in text.lower() for hint in INTENSE_HINTS):
        cost_risk = 0.4
    if track == "other":
        cost_risk = min(cost_risk, 0.6)

    urgency_score, urgency_reason = _deadline_urgency(_norm_text(job.get("deadline_date")), _norm_text(job.get("deadline_text")), today)
    data_confidence = float(job.get("completeness_score") or 0.0)
    evidence_readiness = round(min(1.0, experience_fit * 0.7 + data_confidence * 0.3), 4)
    evidence_confidence = 1.0 if evidence_readiness >= 0.6 else 0.35 if evidence_readiness <= 0.2 else 0.65

    fit_score = round(
        hard_constraints * 0.18
        + track_fit * 0.2
        + skill_fit * 0.17
        + experience_fit * 0.15
        + industry_fit * 0.1
        + growth_fit * 0.1
        + cost_risk * 0.05
        + data_confidence * 0.05,
        4,
    )
    priority_score = round(
        fit_score * 0.72
        + urgency_score * 0.14
        + evidence_readiness * 0.09
        + data_confidence * 0.05,
        4,
    )

    strengths: List[str] = []
    risks: List[str] = []
    if track == "ai_engineer":
        strengths.append("主轨AI/算法工程方向")
    elif track == "quant_research":
        strengths.append("备选量化研究方向")
    elif track == "ai_pm":
        strengths.append("AI产品方向")
    elif track == "adjacent":
        strengths.append("相邻数据/平台方向")
    if fintech_hits:
        strengths.append("金融/投研语境")
    if experience_fit >= 0.6:
        strengths.append("证据库可支撑定制简历")
    if urgency_score >= 0.78:
        strengths.append("时效性高")
    if not strengths:
        strengths.append("基础信息可纳入统一排序")
    if "city" in penalties:
        risks.append("城市不在当前优先区")
    if data_confidence < 0.45:
        risks.append("JD信息较弱")
    if evidence_readiness < 0.45:
        risks.append("证据覆盖一般")
    if "pure_admin" in penalties:
        risks.append("行政支持色彩偏重")
    if "pure_biology" in penalties:
        risks.append("偏纯实验方向")
    if not risks:
        risks.append("无明显硬伤")

    return {
        "fit_score": fit_score,
        "priority_score": priority_score,
        "dimensions": {
            "hard_constraints": round(hard_constraints, 4),
            "track_fit": round(track_fit, 4),
            "skill_fit": round(skill_fit, 4),
            "experience_fit": round(experience_fit, 4),
            "industry_fit": round(industry_fit, 4),
            "growth_fit": round(growth_fit, 4),
            "cost_risk": round(cost_risk, 4),
            "deadline_urgency": round(urgency_score, 4),
            "data_confidence": round(data_confidence, 4),
            "evidence_readiness": round(evidence_readiness, 4),
            "evidence_confidence": round(evidence_confidence, 4),
        },
        "hard_constraint_penalties": penalties,
        "top_strengths": "；".join(strengths[:3]),
        "top_risks": "；".join(risks[:3]),
        "urgency_reason": urgency_reason,
    }


def _dedupe_group(job: Dict[str, Any]) -> str:
    source = _norm_text(job.get("source"))
    company = _normalize_company(job.get("company"))
    title = _normalize_title(job.get("title"))
    city = _normalize_city(job.get("city"))
    if _norm_text(job.get("source_url")):
        return f"{source}|{company}|{title}|{city}|{_norm_text(job.get('source_url'))}"
    return f"{source}|{company}|{title}|{city}"


def _apply_company_soft_cap(rows: List[Dict[str, Any]], max_per_company: int = 3) -> List[Dict[str, Any]]:
    grouped_counts: Dict[str, int] = {}
    adjusted: List[Dict[str, Any]] = []
    for row in rows:
        company = _norm_text(row.get("company")) or "unknown"
        count = grouped_counts.get(company, 0)
        new_row = dict(row)
        if count >= max_per_company:
            decay = 0.7 ** (count - max_per_company + 1)
            new_row["priority_score"] = round(float(row["priority_score"]) * decay, 4)
            penalty = new_row.get("hard_constraint_penalties") or {}
            penalty["company_overflow"] = f"{company} 第 {count + 1} 个岗位，priority_score × {decay:.2f}"
            new_row["hard_constraint_penalties"] = penalty
        adjusted.append(new_row)
        grouped_counts[company] = count + 1
    adjusted.sort(key=lambda item: item["priority_score"], reverse=True)
    return adjusted


def normalize_jobs(
    jobs: List[Dict[str, Any]],
    raw_index: Dict[str, Any],
    evidence_terms: List[str],
    prefs: UserPreferences,
    today: date | None = None,
) -> List[Dict[str, Any]]:
    today = today or date.today()
    normalized: List[Dict[str, Any]] = []
    for idx, job in enumerate(jobs, start=1):
        raw_match = link_raw(job, raw_index)
        city = _normalize_city(raw_match.get("city") if raw_match and raw_match.get("city") else job.get("city"))
        keywords = _derive_keywords(job, raw_match)
        requirements = raw_match.get("requirements", []) if raw_match else _norm_list(job.get("requirements"))
        responsibilities = raw_match.get("responsibilities", []) if raw_match else _norm_list(job.get("responsibilities"))
        deadline_text = raw_match.get("deadline_text", "") if raw_match else ""
        deadline_date = raw_match.get("deadline_date", "") if raw_match else ""
        deadline_confidence = raw_match.get("deadline_confidence", "none") if raw_match else "none"
        normalized_job_id = _norm_text(job.get("job_id")) or f"generated_{idx:04d}"
        record = {
            "row_id": idx,
            "job_id": _norm_text(job.get("job_id")),
            "normalized_job_id": normalized_job_id,
            "title": _norm_text(job.get("title")),
            "normalized_title": _normalize_title(job.get("title")),
            "company": _normalize_company(job.get("company")),
            "city": city,
            "recruit_type": _flatten_recruit_type(job.get("recruit_type")),
            "job_family": _norm_text(job.get("job_family")),
            "source": _norm_text(job.get("source")),
            "source_url": _norm_text(job.get("source_url")),
            "bucket": _norm_text(job.get("bucket")),
            "reason": _norm_text(job.get("reason")),
            "raw_path": raw_match.get("raw_path", "") if raw_match else "",
            "requirements": requirements,
            "responsibilities": responsibilities,
            "keywords": keywords,
            "deadline_text": deadline_text,
            "deadline_date": deadline_date,
            "deadline_confidence": deadline_confidence,
        }
        record["completeness_score"] = _completeness(job, raw_match)
        record["target_track"] = _derive_track(" ".join([record["title"], record["job_family"], " ".join(record["keywords"])]))
        record["dedupe_group"] = _dedupe_group(record)
        normalized.append({**record, **_score_job(record, prefs, evidence_terms, today)})
    primary_by_group: Dict[str, Dict[str, Any]] = {}
    for row in normalized:
        group = row["dedupe_group"]
        score = (
            float(row.get("completeness_score") or 0.0),
            1.0 if row.get("raw_path") else 0.0,
            1.0 if row.get("source_url") else 0.0,
            1.0 if row.get("job_id") else 0.0,
        )
        if group not in primary_by_group or score > primary_by_group[group]["_primary_score"]:
            primary_by_group[group] = {**row, "_primary_score": score}
    for row in normalized:
        row["is_primary_in_group"] = primary_by_group[row["dedupe_group"]]["row_id"] == row["row_id"]
    normalized.sort(key=lambda item: item["priority_score"], reverse=True)
    return _apply_company_soft_cap(normalized)


def _primary_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [row for row in rows if row.get("is_primary_in_group")]


def _top_primary(rows: List[Dict[str, Any]], predicate, limit: int) -> List[Dict[str, Any]]:
    result = [row for row in rows if row.get("is_primary_in_group") and predicate(row)]
    result.sort(key=lambda item: item["priority_score"], reverse=True)
    return result[:limit]


def _format_job_line(rank: int, row: Dict[str, Any]) -> str:
    deadline = row.get("deadline_date") or (row.get("deadline_confidence") if row.get("deadline_confidence") != "none" else "无")
    return (
        f"{rank}. {row['company']}｜{row['title']}｜{row['city']}｜"
        f"priority={row['priority_score']:.4f}｜fit={row['fit_score']:.4f}｜"
        f"track={row['target_track']}｜deadline={deadline}\n"
        f"   优势：{row['top_strengths']}\n"
        f"   风险：{row['top_risks']}"
    )


def _major_companies(rows: List[Dict[str, Any]], min_roles: int = 5) -> List[tuple[str, List[Dict[str, Any]]]]:
    by_company: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in _primary_rows(rows):
        by_company[row["company"]].append(row)
    majors = []
    for company, company_rows in by_company.items():
        if len(company_rows) < min_roles:
            continue
        company_rows.sort(key=lambda item: item["priority_score"], reverse=True)
        majors.append((company, company_rows))
    majors.sort(key=lambda item: (len(item[1]), item[1][0]["priority_score"]), reverse=True)
    return majors


def _role_reason_lines(row: Dict[str, Any]) -> List[str]:
    dims = row.get("dimensions", {})
    reasons: List[str] = []
    track = row.get("target_track")
    if track == "ai_engineer":
        reasons.append(f"主轨 AI/算法工程方向直接匹配，track_fit={dims.get('track_fit', 0):.2f}。")
    elif track == "quant_research":
        reasons.append(f"属于你的备选量化/研究方向，track_fit={dims.get('track_fit', 0):.2f}。")
    elif track == "ai_pm":
        reasons.append(f"属于 AI 产品方向，track_fit={dims.get('track_fit', 0):.2f}。")
    elif track == "adjacent":
        reasons.append(f"属于数据/平台相邻方向，可作为主轨外延岗位，track_fit={dims.get('track_fit', 0):.2f}。")
    if dims.get("evidence_readiness", 0.0) >= 0.6:
        reasons.append(f"现有经历能较好支撑定制简历，evidence_readiness={dims.get('evidence_readiness', 0):.2f}。")
    elif dims.get("evidence_readiness", 0.0) >= 0.45:
        reasons.append(f"现有证据有一定支撑，但改简历时仍需克制表述，evidence_readiness={dims.get('evidence_readiness', 0):.2f}。")
    if dims.get("industry_fit", 0.0) >= 0.35:
        reasons.append(f"岗位语境和你的金融/数据/平台叙事有连接，industry_fit={dims.get('industry_fit', 0):.2f}。")
    if dims.get("deadline_urgency", 0.0) >= 0.72:
        reasons.append(f"岗位具有时效性，{row.get('urgency_reason')}。")
    if dims.get("data_confidence", 0.0) < 0.45:
        reasons.append(f"但当前 JD 信息偏弱，data_confidence={dims.get('data_confidence', 0):.2f}，投前要人工复核。")
    penalties = row.get("hard_constraint_penalties", {})
    if "city" in penalties:
        reasons.append(f"主要硬伤是城市优先级一般：{penalties['city']}。")
    elif row.get("top_risks") and row.get("top_risks") != "无明显硬伤":
        reasons.append(f"当前主要风险：{row['top_risks']}。")
    return reasons[:5]


def _other_role_summary_lines(company: str, company_rows: List[Dict[str, Any]], top_n: int = 3) -> List[str]:
    others = company_rows[top_n:]
    if not others:
        return ["该公司主记录岗位数不多，Top 3 基本就是全部值得看的选项。"]
    soft_capped = sum(1 for row in others if "company_overflow" in (row.get("hard_constraint_penalties") or {}))
    weak_jd = sum(1 for row in others if row.get("dimensions", {}).get("data_confidence", 0.0) < 0.45)
    weak_evidence = sum(1 for row in others if row.get("dimensions", {}).get("evidence_readiness", 0.0) < 0.45)
    non_core = sum(1 for row in others if row.get("target_track") not in {"ai_engineer", "ai_pm", "adjacent", "quant_research"})
    city_penalty = sum(1 for row in others if "city" in (row.get("hard_constraint_penalties") or {}))
    lines: List[str] = []
    if soft_capped:
        lines.append(f"Top 3 之后的 {soft_capped} 个岗位已被同公司 soft cap 明显压分，所以就算 fit 不差，也不该优先挤占你的投递精力。")
    if weak_jd or weak_evidence:
        lines.append(f"其余岗位里有 {weak_jd} 个 JD 信息偏弱、{weak_evidence} 个证据覆盖偏弱，意味着你很难快速做出高质量定制。")
    if non_core:
        lines.append(f"另外有 {non_core} 个岗位已经偏工程/算法或非核心方向，离你当前主投叙事更远。")
    if city_penalty:
        lines.append(f"还有 {city_penalty} 个岗位带有城市优先级劣势，不值得在同公司内部排到更前。")
    near_misses = others[:3]
    if near_misses:
        lines.append("最接近但仍不如 Top 3 的岗位包括：" + "；".join(
            f"{row['title']}（priority={row['priority_score']:.4f}，风险：{row['top_risks']}）" for row in near_misses
        ) + "。")
    return lines[:4]


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    fieldnames = [
        "row_id", "job_id", "normalized_job_id", "title", "company", "city", "recruit_type", "job_family",
        "source", "target_track", "fit_score", "priority_score", "completeness_score", "raw_path",
        "deadline_date", "deadline_confidence", "top_strengths", "top_risks", "urgency_reason",
        "is_primary_in_group", "dedupe_group", "source_url",
    ] + [
        "hard_constraints", "track_fit", "skill_fit", "experience_fit", "industry_fit", "growth_fit",
        "cost_risk", "deadline_urgency", "data_confidence", "evidence_readiness", "evidence_confidence",
        "penalties_json", "keywords_json", "requirements_json", "responsibilities_json",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            dims = row.get("dimensions", {})
            writer.writerow({
                "row_id": row.get("row_id"),
                "job_id": row.get("job_id"),
                "normalized_job_id": row.get("normalized_job_id"),
                "title": row.get("title"),
                "company": row.get("company"),
                "city": row.get("city"),
                "recruit_type": row.get("recruit_type"),
                "job_family": row.get("job_family"),
                "source": row.get("source"),
                "target_track": row.get("target_track"),
                "fit_score": row.get("fit_score"),
                "priority_score": row.get("priority_score"),
                "completeness_score": row.get("completeness_score"),
                "raw_path": row.get("raw_path"),
                "deadline_date": row.get("deadline_date"),
                "deadline_confidence": row.get("deadline_confidence"),
                "top_strengths": row.get("top_strengths"),
                "top_risks": row.get("top_risks"),
                "urgency_reason": row.get("urgency_reason"),
                "is_primary_in_group": row.get("is_primary_in_group"),
                "dedupe_group": row.get("dedupe_group"),
                "source_url": row.get("source_url"),
                "hard_constraints": dims.get("hard_constraints"),
                "track_fit": dims.get("track_fit"),
                "skill_fit": dims.get("skill_fit"),
                "experience_fit": dims.get("experience_fit"),
                "industry_fit": dims.get("industry_fit"),
                "growth_fit": dims.get("growth_fit"),
                "cost_risk": dims.get("cost_risk"),
                "deadline_urgency": dims.get("deadline_urgency"),
                "data_confidence": dims.get("data_confidence"),
                "evidence_readiness": dims.get("evidence_readiness"),
                "evidence_confidence": dims.get("evidence_confidence"),
                "penalties_json": json.dumps(row.get("hard_constraint_penalties", {}), ensure_ascii=False),
                "keywords_json": json.dumps(row.get("keywords", []), ensure_ascii=False),
                "requirements_json": json.dumps(row.get("requirements", []), ensure_ascii=False),
                "responsibilities_json": json.dumps(row.get("responsibilities", []), ensure_ascii=False),
            })


def write_primary_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    write_csv(_primary_rows(rows), path)


def write_corpus_integrity_report(inventory: Dict[str, Any], path: Path, limit: int = 50) -> None:
    items = inventory.get("items", [])
    inferable = [item for item in items if item.get("inferable")]
    non_inferable = [item for item in items if not item.get("inferable")]
    company_counts = Counter(item.get("company") or "unknown" for item in items)
    lines = [
        "# 岗位语料完整性报告",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        f"- 结构化岗位卡数：{inventory.get('job_count', 0)}",
        f"- raw JD 总数：{inventory.get('raw_count', 0)}",
        f"- 已被当前岗位卡链接的 raw JD 数：{inventory.get('linked_raw_count', 0)}",
        f"- 未被纳入结构化岗位库的 raw JD 数：{inventory.get('unlinked_raw_count', 0)}",
        f"- 其中可自动推断公司并可回填的 raw JD 数：{len(inferable)}",
        f"- 其中仍需人工判断的 raw JD 数：{len(non_inferable)}",
        "",
        "## 公司分布",
        "",
    ]
    for company, count in company_counts.most_common():
        lines.append(f"- {company}: {count}")
    lines.extend(["", "## 可回填 raw JD 样例", ""])
    for item in inferable[:limit]:
        lines.append(f"- {item['company']}｜{item['title']}｜{item['city']}｜{item['raw_file']}")
    if non_inferable:
        lines.extend(["", "## 仍需人工判断的 raw JD 样例", ""])
        for item in non_inferable[:limit]:
            lines.append(f"- {item['title']}｜{item['city']}｜{item['raw_file']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_shortlist(rows: List[Dict[str, Any]], path: Path, limit: int = 15) -> List[Dict[str, Any]]:
    shortlist = [
        row for row in rows
        if row.get("is_primary_in_group")
        and row.get("dimensions", {}).get("evidence_readiness", 0.0) >= 0.35
        and row.get("target_track") in {"ai_engineer", "ai_pm", "quant_research", "adjacent"}
    ]
    shortlist.sort(key=lambda item: item["priority_score"], reverse=True)
    shortlist = shortlist[:limit]
    payload = [
        {
            "normalized_job_id": row["normalized_job_id"],
            "job_id": row.get("job_id"),
            "title": row["title"],
            "company": row["company"],
            "city": row["city"],
            "job_family": row["job_family"],
            "source": row["source"],
            "source_url": row["source_url"],
            "target_track": row["target_track"],
            "priority_score": row["priority_score"],
            "fit_score": row["fit_score"],
            "deadline_date": row.get("deadline_date"),
            "deadline_confidence": row.get("deadline_confidence"),
            "top_strengths": row.get("top_strengths"),
            "top_risks": row.get("top_risks"),
            "raw_path": row.get("raw_path"),
            "requirements": row.get("requirements", []),
            "responsibilities": row.get("responsibilities", []),
            "keywords": row.get("keywords", []),
            "dimensions": row.get("dimensions", {}),
        }
        for row in shortlist
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def write_big_company_report(rows: List[Dict[str, Any]], path: Path, top_n: int = 3, min_roles: int = 5) -> None:
    majors = _major_companies(rows, min_roles=min_roles)
    lines = [
        "# 大厂 Top 3 岗位分析",
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        f"- 大厂定义：去重主记录中岗位数 >= {min_roles} 的公司。",
        f"- 本次纳入公司数：{len(majors)}",
        f"- 每家公司展示最值得投递的 {top_n} 个岗位，并解释其余岗位为何不够优先。",
        "",
    ]
    for company, company_rows in majors:
        top_roles = company_rows[:top_n]
        lines.extend([
            f"## {company}",
            "",
            f"- 主记录岗位数：{len(company_rows)}",
            f"- 公司内最高 priority_score：{top_roles[0]['priority_score']:.4f}",
            "",
            f"### 最值得投递的 {top_n} 个岗位",
            "",
        ])
        for idx, row in enumerate(top_roles, start=1):
            lines.append(
                f"{idx}. {row['title']}｜{row['city']}｜priority={row['priority_score']:.4f}｜fit={row['fit_score']:.4f}｜track={row['target_track']}"
            )
            for reason in _role_reason_lines(row):
                lines.append(f"   - {reason}")
            lines.append("")
        lines.extend([
            "### 其他岗位为什么不够适合",
            "",
        ])
        for reason in _other_role_summary_lines(company, company_rows, top_n=top_n):
            lines.append(f"- {reason}")
        lines.extend(["", "---", ""])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_report(
    rows: List[Dict[str, Any]],
    path: Path,
    raw_count: int,
    evidence_term_count: int,
    primary_only: bool = False,
    original_total: int | None = None,
    unlinked_raw_count: int = 0,
) -> None:
    source_total = original_total if original_total is not None else len(rows)
    primary_rows = _primary_rows(rows)
    report_rows = primary_rows if primary_only else rows
    total = len(report_rows)
    duplicate_count = max(source_total - len(primary_rows), 0)
    raw_linked = sum(1 for row in report_rows if row.get("raw_path"))
    deadline_count = sum(1 for row in report_rows if row.get("deadline_date"))
    track_counter = Counter(row.get("target_track") for row in primary_rows)
    city_counter = Counter(row.get("city") for row in primary_rows)
    source_counter = Counter(row.get("source") for row in primary_rows)
    top50 = _top_primary(report_rows, lambda row: True, 50)
    top_ai = _top_primary(report_rows, lambda row: row.get("target_track") in {"ai_engineer", "ai_pm"}, 20)
    top_adjacent = _top_primary(report_rows, lambda row: row.get("target_track") == "adjacent", 20)
    top_quant = _top_primary(report_rows, lambda row: row.get("target_track") == "quant_research", 20)
    urgent = _top_primary(report_rows, lambda row: row.get("dimensions", {}).get("deadline_urgency", 0.0) >= 0.72, 20)
    high_score_low_evidence = _top_primary(
        report_rows,
        lambda row: row.get("fit_score", 0.0) >= 0.62 and row.get("dimensions", {}).get("evidence_readiness", 0.0) < 0.45,
        20,
    )
    avoid = _top_primary(report_rows, lambda row: "命中明确排除方向" in json.dumps(row.get("hard_constraint_penalties", {}), ensure_ascii=False), 20)

    title = "# 去重主记录岗位对比报告" if primary_only else "# 2421条岗位全量对比报告"
    method_lines = [
        "- 本次没有把2421条简单逐条长评，而是先做统一标准化，再给出 fit_score 和 priority_score。",
        "- fit_score 更接近“岗位本身是否适合你”；priority_score 额外考虑时效性、证据覆盖和数据完整度，更适合指导“先投谁”。",
        "- 城市偏好当前采用保守加权：广州 > 深圳，其余城市默认中性而非一票否决。",
        "- 对同公司过多高分岗位使用了 soft cap，避免同一家公司占满前列。",
    ]
    if primary_only:
        method_lines.insert(0, "- 本报告只保留每个 dedupe_group 的主记录，适合直接查看投递顺序。")
    if unlinked_raw_count:
        method_lines.append(f"- 当前仍有 {unlinked_raw_count} 份 raw JD 未进入结构化岗位库；若不先回填，这些岗位不会进入排序与报告。")

    lines = [
        title,
        "",
        f"生成日期：{date.today().isoformat()}",
        "",
        "## 一、数据质量总览",
        "",
        f"- 原始岗位总数：{source_total}",
        f"- 本报告纳入岗位数：{total}",
        f"- 去重后主记录数：{len(primary_rows)}",
        f"- 重复/镜像记录数：{duplicate_count}",
        f"- 成功链接 raw JD 的岗位数：{raw_linked}",
        f"- 可识别明确 deadline 的岗位数：{deadline_count}",
        f"- raw 文件总数：{raw_count}",
        f"- 未纳入结构化岗位库的 raw JD 数：{unlinked_raw_count}",
        f"- 简历证据词条数：{evidence_term_count}",
        "",
        "## 二、方法说明",
        "",
        *method_lines,
        "",
        "## 三、岗位池结构",
        "",
        f"- 赛道分布：{dict(track_counter)}",
        f"- Top 城市：{city_counter.most_common(10)}",
        f"- Top 来源：{source_counter.most_common(10)}",
        "",
        "## 四、Top 50 立即关注岗位",
        "",
    ]
    lines.extend(_format_job_line(idx, row) for idx, row in enumerate(top50, start=1))
    lines.extend(["", "## 五、Top 20 AI/算法岗位", ""])
    lines.extend(_format_job_line(idx, row) for idx, row in enumerate(top_ai, start=1))
    lines.extend(["", "## 六、Top 20 产品/数据相邻岗位", ""])
    lines.extend(_format_job_line(idx, row) for idx, row in enumerate(top_adjacent, start=1))
    lines.extend(["", "## 七、Top 20 量化/研究备选岗位", ""])
    lines.extend(_format_job_line(idx, row) for idx, row in enumerate(top_quant, start=1))
    lines.extend(["", "## 八、快截止或高时效岗位", ""])
    if urgent:
        lines.extend(_format_job_line(idx, row) for idx, row in enumerate(urgent, start=1))
    else:
        lines.append("- 当前能从本地 raw 文本中识别出的显式 deadline 较少，更多岗位仍需依赖 source 或人工复核。")
    lines.extend(["", "## 九、高分但证据不足的岗位", ""])
    if high_score_low_evidence:
        lines.extend(_format_job_line(idx, row) for idx, row in enumerate(high_score_low_evidence, start=1))
    else:
        lines.append("- 当前高分岗位大多已有可用证据覆盖，或证据覆盖不足的高分岗位数量不多。")
    lines.extend(["", "## 十、明确不建议优先投入的岗位类型", ""])
    if avoid:
        lines.extend(_format_job_line(idx, row) for idx, row in enumerate(avoid, start=1))
    else:
        lines.append("- 未出现大量命中明确排除规则的岗位，但仍应警惕纯行政支持、纯实验生物、强学术导向岗位。")
    lines.extend([
        "",
        "## 十一、行动建议",
        "",
        "1. 先围绕 Top 10–15 的主记录做投递动作，不要被重复镜像岗位分散注意力。",
        "2. 先处理 AI/算法岗和产品数据相邻岗位中 evidence_readiness 较高的岗位，这批最容易快速改出高质量简历。",
        "3. 对 deadline_confidence=none 但分数很高的岗位，建议在投递前人工打开原链接复核截止时间。",
        "4. 量化/研究备选岗位可保留为第二批，不必抢在第一批 AI/算法岗位之前全部处理。",
        "",
    ])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_batch(
    jobs_jsonl: Path,
    raw_dir: Path,
    evidence_jsonl: Path,
    output_dir: Path,
    sync_raw: bool = False,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    today = date.today()
    sync_summary: Dict[str, Any] | None = None
    if sync_raw:
        sync_summary = sync_unlinked_raw_jobs(jobs_jsonl, raw_dir, today=today)
    jobs = load_jobs(jobs_jsonl)
    raw_index = load_raw_index(raw_dir, today=today)
    evidence_terms = load_evidence_terms(evidence_jsonl)
    prefs = default_preferences()
    ranked = normalize_jobs(jobs, raw_index, evidence_terms, prefs, today=today)
    integrity = inventory_unlinked_raw_jobs(jobs_jsonl, raw_dir, today=today)
    stamp = today.strftime("%Y%m%d")
    csv_path = output_dir / f"job_ranking_{stamp}.csv"
    primary_csv_path = output_dir / f"job_ranking_primary_{stamp}.csv"
    report_path = output_dir / f"job_comparison_report_{stamp}.md"
    primary_report_path = output_dir / f"job_comparison_report_primary_{stamp}.md"
    big_company_report_path = output_dir / f"job_big_company_analysis_{stamp}.md"
    corpus_integrity_path = output_dir / f"job_corpus_integrity_{stamp}.md"
    shortlist_path = output_dir / f"job_shortlist_{stamp}.json"
    write_csv(ranked, csv_path)
    write_primary_csv(ranked, primary_csv_path)
    shortlist = write_shortlist(ranked, shortlist_path)
    write_report(
        ranked,
        report_path,
        raw_count=len(raw_index["items"]),
        evidence_term_count=len(evidence_terms),
        unlinked_raw_count=integrity["unlinked_raw_count"],
    )
    write_report(
        ranked,
        primary_report_path,
        raw_count=len(raw_index["items"]),
        evidence_term_count=len(evidence_terms),
        primary_only=True,
        original_total=len(ranked),
        unlinked_raw_count=integrity["unlinked_raw_count"],
    )
    write_big_company_report(ranked, big_company_report_path)
    write_corpus_integrity_report(integrity, corpus_integrity_path)
    return {
        "csv_path": str(csv_path),
        "primary_csv_path": str(primary_csv_path),
        "report_path": str(report_path),
        "primary_report_path": str(primary_report_path),
        "big_company_report_path": str(big_company_report_path),
        "corpus_integrity_path": str(corpus_integrity_path),
        "shortlist_path": str(shortlist_path),
        "shortlist_count": len(shortlist),
        "ranked_count": len(ranked),
        "primary_ranked_count": len(_primary_rows(ranked)),
        "unlinked_raw_count": integrity["unlinked_raw_count"],
        "sync_summary": sync_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch-rank the local job corpus and export report artifacts.")
    parser.add_argument("--jobs-jsonl", default="advisor_data/jobs/self/jobs.jsonl")
    parser.add_argument("--raw-dir", default="advisor_data/jobs/self/raw")
    parser.add_argument("--evidence-jsonl", default="advisor_data/resume/evidence.jsonl")
    parser.add_argument("--output-dir", default="outputs/jobs")
    parser.add_argument("--sync-raw", action="store_true", help="Backfill inferable raw-only job postings into jobs.jsonl before ranking.")
    args = parser.parse_args()
    result = run_batch(
        Path(args.jobs_jsonl),
        Path(args.raw_dir),
        Path(args.evidence_jsonl),
        Path(args.output_dir),
        sync_raw=args.sync_raw,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
