from __future__ import annotations

import sys

MESSAGE = (
    "production/run.py is deprecated and intentionally blocks execution. "
    "Use `aiprod production preflight` followed by "
    "`aiprod production execute --receipt <path>`."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
