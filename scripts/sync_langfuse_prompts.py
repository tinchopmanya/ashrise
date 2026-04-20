from __future__ import annotations

import sys

from ashrise.langfuse_support import sync_prompts


def main() -> int:
    try:
        results = sync_prompts()
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    for item in results:
        print(f"{item['status']}: {item['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
