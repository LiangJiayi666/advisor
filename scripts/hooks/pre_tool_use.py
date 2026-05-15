"""Hook: PreToolUse - Remind about source attribution for web tools."""
import sys


def main():
    _ = sys.stdin.read()
    print("REMINDER: All web research must include source links. Distinguish verified facts from model inferences.")
    sys.exit(0)


if __name__ == "__main__":
    main()
