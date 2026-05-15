"""Hook: Stop - Enforce session archival before ending."""
import json
import os
import sys

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STATE_PATH = os.path.join(BASE, "advisor_data", "state", "state.json")


def read_state():
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"archive_state": "clean"}


def main():
    state = read_state()
    archive_state = state.get("archive_state", "clean")

    if archive_state == "archived":
        print("Session properly archived. Safe to end.")
        sys.exit(0)
    elif archive_state == "in_progress":
        print("WARNING: Archive is in progress. Wait for completion.")
        sys.exit(1)
    elif archive_state == "dirty":
        print("WARNING: Session has substantive content but has not been archived. Run /close-session first.")
        sys.exit(1)
    else:
        # "clean" — no mechanism yet to auto-detect substantive content,
        # so allow stop. Future: PreToolUse/UserPromptSubmit hooks should
        # set archive_state to "dirty" when substantive interaction occurs.
        sys.exit(0)


if __name__ == "__main__":
    main()
