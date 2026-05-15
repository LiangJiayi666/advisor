"""Hook: UserPromptSubmit - Classify user intent and recommend skills."""
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMORIES_PATH = os.path.join(BASE, "advisor_data", "memories", "memory.jsonl")

KEYWORDS = {
    "prism_reading": ["prism"],
    "job_research": ["JD", "岗位", "招聘", "面试", "公司", "offer", "薪资", "跳槽", "求职", "校招", "社招"],
    "consultation": ["焦虑", "压力", "烦", "累", "难受", "迷茫", "抑郁", "不开心", "崩溃", "失眠"],
}

SKILL_MAP = {
    "prism_reading": ["prism-reading"],
    "job_research": ["job-research"],
    "consultation": ["advisor-intake"],
    "mixed": ["advisor-intake", "prism-reading", "job-research"],
    "general": [],
}


def classify(prompt):
    prompt_lower = prompt.lower()
    matched = set()
    for category, kws in KEYWORDS.items():
        for kw in kws:
            if kw in prompt_lower:
                matched.add(category)
                break
    if len(matched) > 1:
        return "mixed"
    if len(matched) == 1:
        return matched.pop()
    return "general"


def get_memory_hint():
    try:
        with open(MEMORIES_PATH, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return "no memories"
    if not lines:
        return "no memories"
    try:
        last = json.loads(lines[-1])
        tags = last.get("tags")
        if tags and isinstance(tags, list):
            return ", ".join(tags)
        kind = last.get("kind")
        if kind:
            return kind
        return "recent entry available"
    except (json.JSONDecodeError, IndexError):
        return f"{len(lines)} entries"


def main():
    prompt = sys.stdin.read()
    category = classify(prompt)
    skills = SKILL_MAP.get(category, [])
    mem_hint = get_memory_hint()

    print(f"DETECTED_INTENT: {category}")
    print(f"RECOMMENDED_SKILLS: {skills}")
    print(f"RELEVANT_MEMORIES: {mem_hint}")
    sys.exit(0)


if __name__ == "__main__":
    main()
