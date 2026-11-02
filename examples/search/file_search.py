"""Small foreground workload: deterministic Unicode-aware text-file search."""

import sys
from pathlib import Path


def search(root, query):
    root = Path(root)
    return [path.relative_to(root).as_posix() for path in sorted(root.rglob("*.txt"))
            if query.casefold() in path.read_text(encoding="utf-8").casefold()]


if __name__ == "__main__":
    for match in search(sys.argv[1], sys.argv[2]):
        print(match)
