"""Hook: SessionStart - Load advisor context for new session."""
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_PATH = os.path.join(BASE, "advisor_data", "state", "state.json")
ARCHIVES_DIR = os.path.join(BASE, "advisor_data", "archives")
MEMORIES_PATH = os.path.join(BASE, "advisor_data", "memories", "memory.jsonl")
PRISM_DIR = os.path.join(BASE, "advisor_data", "profiles", "prism")


def read_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def read_recent_archives(n=3):
    if not os.path.isdir(ARCHIVES_DIR):
        return []
    all_files = []
    for root, _dirs, filenames in os.walk(ARCHIVES_DIR):
        for fname in filenames:
            if fname.endswith((".md", ".json")):
                full = os.path.join(root, fname)
                try:
                    mtime = os.path.getmtime(full)
                    all_files.append((full, mtime))
                except OSError:
                    pass
    all_files.sort(key=lambda x: x[1], reverse=True)
    result = []
    for full, _ in all_files[:n]:
        try:
            with open(full, "r", encoding="utf-8") as f:
                rel = os.path.relpath(full, ARCHIVES_DIR)
                result.append({"file": rel, "content": f.read()[:500]})
        except Exception:
            pass
    return result


def read_recent_memories(n=20):
    try:
        with open(MEMORIES_PATH, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
    except FileNotFoundError:
        return []
    entries = []
    for line in lines[-n:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return entries


def check_prism_profile():
    if not os.path.isdir(PRISM_DIR):
        return None
    for f in os.listdir(PRISM_DIR):
        if f.endswith(".json"):
            return os.path.join(PRISM_DIR, f)
    return None


def main():
    state = read_json(STATE_PATH)
    archives = read_recent_archives()
    memories = read_recent_memories()
    prism_file = check_prism_profile()

    last_date = state.get("last_session_date") or "N/A"
    last_topic = state.get("recent_topics", ["N/A"])[-1] if state.get("recent_topics") else "N/A"
    topics = state.get("recent_topics", [])
    prism_status = "loaded" if prism_file else "not loaded"

    mem_summary = "none"
    if memories:
        tags = set()
        for m in memories[:5]:
            if isinstance(m, dict):
                for t in m.get("tags", []):
                    tags.add(t)
                if "kind" in m:
                    tags.add(m["kind"])
        mem_summary = ", ".join(tags) if tags else f"{len(memories)} entries"

    archive_summary = "none"
    if archives:
        archive_summary = ", ".join(a["file"] for a in archives)

    print("=== Advisor Session Context ===")
    print(f"Last session: {last_date} - {last_topic}")
    print(f"Recent topics: {topics}")
    print(f"Recent archives: {archive_summary}")
    print(f"Prism profile: {prism_status}")
    print(f"Recent memories summary: {mem_summary}")
    print("===")
    sys.exit(0)


if __name__ == "__main__":
    main()
