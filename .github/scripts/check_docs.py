"""The usage guide may not drift from the API it describes.

    python .github/scripts/check_docs.py

Checks, against the tsubasa that is installed:
  * every ```python block in docs/USAGE.md compiles;
  * every `tsubasa.<name>` the guide uses exists;
  * every field the guide's `Result` table names is a real `Result` field.

The runnable examples in examples/ are executed separately. This covers the parts
of the guide that are prose: a renamed field or function fails here, not in a
reader's editor.
"""
import importlib
import io
import os
import re
import sys

import tsubasa

GUIDE = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "USAGE.md")


def main():
    text = io.open(GUIDE, encoding="utf-8").read()
    problems = []

    blocks = re.findall(r"```python\n(.*?)```", text, re.S)
    for number, block in enumerate(blocks, 1):
        try:
            compile(block, "docs/USAGE.md, python block %d" % number, "exec")
        except SyntaxError as exc:
            problems.append("python block %d does not compile: %s" % (number, exc))

    for name in sorted(set(re.findall(r"\btsubasa\.([A-Za-z_]\w*)", text))):
        if hasattr(tsubasa, name):
            continue
        try:
            importlib.import_module("tsubasa." + name)
        except ImportError:
            problems.append("the guide uses tsubasa.%s, which does not exist" % name)

    marker = "| `Result` field | Holds |"
    if marker not in text:
        problems.append("the guide no longer has its Result field table")
    else:
        table = text.split(marker, 1)[1].split("\n\n", 1)[0]
        named = set()
        for row in table.splitlines():
            if row.startswith("| `"):
                named.update(re.findall(r"`(\w+)`", row.split("|")[1]))
        real = set(tsubasa.Result.__slots__) | set(
            n for n, v in vars(tsubasa.Result).items() if isinstance(v, property))
        for field in sorted(named - real):
            problems.append("the Result table names `%s`, which Result does not have"
                            % field)
        if len(named) < 10:
            problems.append("only %d fields were read from the Result table, so "
                            "this check proves little" % len(named))

    for problem in problems:
        if os.environ.get("GITHUB_ACTIONS"):
            print("::error title=docs/USAGE.md::%s" % problem)
        else:
            print("PROBLEM:", problem)
    print("%d python blocks, %d problems" % (len(blocks), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
