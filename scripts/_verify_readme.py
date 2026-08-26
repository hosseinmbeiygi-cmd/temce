"""Quick verify README structure."""
import io
import sys

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

with open("README.md", encoding="utf-8") as f:
    content = f.read()
lines = content.split("\n")
print(f"Total lines: {len(lines)}")
print(f"Top-level sections (## ): {content.count(chr(10) + '## ')}")
print(f"Details blocks: {content.count('<details>')}")
print(f"Mermaid diagrams: {content.count('```mermaid')}")
print(f"Table rows (| ...): {sum(1 for line in lines if line.startswith('| '))}")

# Check for ---## collision
collision = content.count("---##")
print(f"---## collision: {collision}")

# Check first and last sections
first_section = next((i+1 for i, line in enumerate(lines) if line.startswith("## ")), "?")
last_section = None
for i, line in enumerate(lines):
    if line.startswith("## "):
        last_section = (i+1, line)
print(f"First section: line {first_section}")
print(f"Last section: line {last_section[0]} - {last_section[1][:40]}")
