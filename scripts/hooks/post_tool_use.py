"""Hook: PostToolUse - Check if web tool results contain source links."""
import re
import sys


def main():
    result = sys.stdin.read()
    url_pattern = r"https?://[^\s<>\"]+"
    has_urls = bool(re.search(url_pattern, result))
    print(f"SOURCE_CHECK: {'has_sources' if has_urls else 'needs_sources'}")
    sys.exit(0)


if __name__ == "__main__":
    main()
