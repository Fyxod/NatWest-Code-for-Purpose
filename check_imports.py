"""Automated import order checker."""

import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))

STDLIB = {
    "__future__",
    "asyncio",
    "base64",
    "contextlib",
    "copy",
    "datetime",
    "gc",
    "io",
    "itertools",
    "json",
    "math",
    "mimetypes",
    "os",
    "pathlib",
    "pickle",
    "platform",
    "re",
    "shutil",
    "sqlite3",
    "subprocess",
    "sys",
    "tempfile",
    "threading",
    "time",
    "traceback",
    "typing",
    "unittest",
    "urllib",
    "uuid",
    "xml",
}

THIRDPARTY = {
    "aiofiles",
    "bcrypt",
    "bs4",
    "bson",
    "dotenv",
    "easyocr",
    "fastapi",
    "fitz",
    "google",
    "httpx",
    "jwt",
    "langchain_chroma",
    "langchain_core",
    "langchain_huggingface",
    "langchain_ollama",
    "langchain_text_splitters",
    "langgraph",
    "markdown",
    "matplotlib",
    "nltk",
    "numpy",
    "openai",
    "openpyxl",
    "pandas",
    "PIL",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "pymongo",
    "pytesseract",
    "requests",
    "sentence_transformers",
    "socketio",
    "starlette",
    "tavily",
    "tiktoken",
    "uvicorn",
}

LOCAL = {"agent", "app", "core"}


def get_pkg(line):
    line = line.strip()
    m = re.match(r"^from\s+(\S+)\s+import", line)
    if m:
        return m.group(1).split(".")[0]
    m = re.match(r"^import\s+(\S+)", line)
    if m:
        return m.group(1).split(".")[0].rstrip(",")
    return None


def classify(pkg):
    if pkg in STDLIB:
        return "stdlib"
    if pkg in THIRDPARTY:
        return "thirdparty"
    if pkg in LOCAL:
        return "local"
    return "unknown"


def check_file(filepath):
    issues = []
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return issues

    import_lines = []
    in_imports = False
    for i, line in enumerate(lines[:80]):
        stripped = line.strip()
        if stripped.startswith("#") or stripped == "":
            import_lines.append((i + 1, "", "blank_or_comment", stripped))
            if in_imports:
                continue
            else:
                continue
        if stripped.startswith("import ") or stripped.startswith("from "):
            pkg = get_pkg(stripped)
            if pkg:
                cat = classify(pkg)
                import_lines.append((i + 1, pkg, cat, stripped))
                in_imports = True
            continue
        # Special: matplotlib.use("Agg") right after matplotlib import
        if "matplotlib.use" in stripped:
            import_lines.append((i + 1, "", "blank_or_comment", stripped))
            continue
        # If we hit non-import, non-blank, non-comment after seeing imports, stop
        if in_imports:
            break

    # Filter to just import entries
    imports_only = [
        (ln, pkg, cat, raw)
        for ln, pkg, cat, raw in import_lines
        if cat not in ("blank_or_comment",)
    ]

    if not imports_only:
        return issues

    # Check 1: group ordering (stdlib -> thirdparty -> local)
    group_order = {"stdlib": 0, "thirdparty": 1, "local": 2, "unknown": 1}
    last_group = -1
    for ln, pkg, cat, raw in imports_only:
        g = group_order.get(cat, 1)
        if g < last_group:
            issues.append(
                f'  Line {ln}: {cat} import "{raw}" appears after a later group'
            )
        last_group = max(last_group, g)

    # Check 2: alphabetical within each group (consecutive runs)
    prev_cat = None
    prev_pkg_lower = None
    prev_raw = None
    prev_ln = None
    for ln, pkg, cat, raw in imports_only:
        if cat == prev_cat:
            if pkg.lower() < prev_pkg_lower:
                issues.append(
                    f'  Line {ln}: "{raw}" should come before "{prev_raw}" (alphabetical in {cat})'
                )
        prev_cat = cat
        prev_pkg_lower = pkg.lower()
        prev_raw = raw
        prev_ln = ln

    # Check 3: duplicates
    seen_raw = set()
    for ln, pkg, cat, raw in imports_only:
        if raw in seen_raw:
            issues.append(f'  Line {ln}: duplicate import "{raw}"')
        seen_raw.add(raw)

    # Check 4: blank line separators between groups
    prev_cat = None
    prev_line_no = None
    for ln, pkg, cat, raw in import_lines:
        if cat == "blank_or_comment":
            continue
        if prev_cat and cat != prev_cat:
            # Check if there's a blank line between prev_line_no and ln
            has_blank = False
            for check_ln, _, check_cat, check_raw in import_lines:
                if (
                    prev_line_no < check_ln < ln
                    and check_cat == "blank_or_comment"
                    and check_raw == ""
                ):
                    has_blank = True
                    break
            if not has_blank:
                issues.append(
                    f"  Line {ln}: missing blank line separator before {cat} group"
                )
        prev_cat = cat
        prev_line_no = ln

    # Check unknown packages
    for ln, pkg, cat, raw in imports_only:
        if cat == "unknown":
            issues.append(
                f'  Line {ln}: unknown package "{pkg}" in "{raw}" - cannot classify'
            )

    return issues


all_clean = True
for root, dirs, files in os.walk(BASE):
    dirs[:] = [
        d for d in dirs if d not in ("__pycache__", "parthenv", "node_modules", ".git")
    ]
    for fname in sorted(files):
        if not fname.endswith(".py"):
            continue
        fpath = os.path.join(root, fname)
        rel = os.path.relpath(fpath, BASE)
        issues = check_file(fpath)
        if issues:
            all_clean = False
            print(f"\n{rel}:")
            for i in issues:
                print(i)

if all_clean:
    print("All files clean.")
