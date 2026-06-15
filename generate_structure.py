import os
from pathlib import Path

TREE_FILE = "tree.txt"


def read_tree():
    with open(TREE_FILE, encoding="utf-8") as f:
        return f.readlines()


def depth(line):
    level = 0
    i = 0

    while True:
        if line.startswith("│   ", i) or line.startswith("    ", i):
            level += 1
            i += 4
        else:
            break

    return level


def clean_name(line):
    line = line.replace("├──", "")
    line = line.replace("└──", "")
    return line.strip()


def parse_tree(lines):

    stack = []
    paths = []

    for idx, raw in enumerate(lines):
        if "──" not in raw:
            continue

        d = depth(raw)
        name = clean_name(raw)

        while len(stack) > d:
            stack.pop()

        stack.append(name)

        path = Path(*stack)

        paths.append((idx + 1, path))

    return paths


def validate(paths):

    seen = {}

    for line, p in paths:
        if p in seen:
            print(f"Duplicate path at line {line}: {p}")
            return False

        seen[p] = line

    return True


def progress(i, total):

    width = 40
    filled = int(width * (i / total))

    bar = "█" * filled + "-" * (width - filled)

    print(f"\r[{bar}] {i}/{total}", end="", flush=True)


def create(paths):

    total = len(paths)

    for i, (line, p) in enumerate(paths, 1):
        path = Path(p)

        if str(path).endswith("/"):
            if path.exists() and path.is_file():
                path.unlink()

            path.mkdir(parents=True, exist_ok=True)

        else:
            parent = path.parent

            if parent.exists() and parent.is_file():
                print(f"\nConflict at line {line}: parent is file -> {parent}")
                parent.unlink()

            parent.mkdir(parents=True, exist_ok=True)

            if not path.exists():
                path.touch()

        progress(i, total)

    print()


def print_tree(start):

    for root, _dirs, files in os.walk(start):
        level = root.replace(start, "").count(os.sep)
        indent = " " * 4 * level

        print(f"{indent}{os.path.basename(root)}/")

        subindent = " " * 4 * (level + 1)

        for f in files:
            print(f"{subindent}{f}")


def main():

    if not os.path.exists(TREE_FILE):
        print("tree.txt not found")
        return

    print("Reading tree.txt")

    lines = read_tree()

    print("Parsing tree")

    paths = parse_tree(lines)

    print("Validating tree")

    if not validate(paths):
        return

    print("Total paths:", len(paths))

    print("Creating structure")

    create(paths)

    root = str(paths[0][1]).split(os.sep)[0]

    print("\nProject tree:\n")

    print_tree(root)


if __name__ == "__main__":
    main()
