"""Hook: UserPromptSubmit - lightweight advisory reminder.

This hook intentionally avoids owning intent classification or hidden workflow control.
It only emits small reminders that keep the assistant aligned with project rules.
"""
import sys


def main():
    prompt = sys.stdin.read()
    lower = prompt.lower()

    reminders = []

    if any(k in lower for k in ["岗位", "jd", "job", "offer", "求职", "面试", "公司"]):
        reminders.append("REMINDER: Job facts belong in structured job storage, not general memory.")

    if any(k in lower for k in ["焦虑", "崩溃", "抑郁", "绝望", "想死", "不想活"]):
        reminders.append("REMINDER: Check safety risk before any other advisory module.")

    if reminders:
        for line in reminders:
            print(line)
    sys.exit(0)


if __name__ == "__main__":
    main()
