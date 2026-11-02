from file_search import search

cases = [
    ("corpus", "efficient", ["one.txt", "three.txt"]),
    ("corpus", "STRASSE", ["two.txt"]),
    ("corpus", "missing phrase", []),
]
for root, query, expected in cases:
    actual = search(root, query)
    if actual != expected:
        raise SystemExit(f"{query!r}: expected {expected!r}, received {actual!r}")
print("3 declared search checks passed")
