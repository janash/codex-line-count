#!/usr/bin/env python3
"""Count repository lines of code by language using extension mapping.

This script reproduces the same approach used in the terminal:
- enumerate files from `rg --files` when available
- map extensions to language names
- count physical lines (newline count, like `wc -l`)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections import defaultdict
from pathlib import Path


EXTENSION_MAP = {
    ".py": "Python",
    ".pyx": "Cython",
    ".pxd": "Cython",
    ".pxi": "Cython",
    ".c": "C",
    ".h": "C++",
    ".hpp": "C++",
    ".hh": "C++",
    ".hxx": "C++",
    ".cpp": "C++",
    ".cc": "C++",
    ".cxx": "C++",
    ".f90": "Fortran",
    ".f95": "Fortran",
    ".f03": "Fortran",
    ".f": "Fortran",
    ".sh": "Shell",
    ".bash": "Shell",
    ".ps1": "PowerShell",
    ".rst": "reStructuredText",
    ".md": "Markdown",
    ".toml": "TOML",
    ".yaml": "YAML",
    ".yml": "YAML",
    ".json": "JSON",
    ".ini": "Config",
    ".cfg": "Config",
    ".conf": "Config",
    ".cmake": "CMake",
    ".mk": "Makefile",
    ".ipynb": "Jupyter Notebook",
    ".txt": "Text",
}

ROOT_FILENAME_MAP = {
    "CMakeLists.txt": "CMake",
    "Makefile": "Makefile",
}

CODE_LANGUAGES = {"Python", "C++", "Cython", "C", "Fortran"}


def run_file_list_command(root: Path, command: list[str]) -> list[Path] | None:
    try:
        proc = subprocess.run(command, cwd=root, check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None

    entries = [entry for entry in proc.stdout.split(b"\x00") if entry]
    return [Path(entry.decode("utf-8", errors="surrogateescape")) for entry in entries]


def list_files(root: Path) -> list[Path]:
    files = run_file_list_command(root, ["rg", "--files", "-0"])
    if files is not None:
        return files

    files = run_file_list_command(root, ["git", "ls-files", "-z"])
    if files is not None:
        return files

    out: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        if ".git" in dirnames:
            dirnames.remove(".git")
        for filename in filenames:
            full = Path(dirpath) / filename
            out.append(full.relative_to(root))
    return out


def language_for_path(path: Path) -> str | None:
    if path.as_posix() in ROOT_FILENAME_MAP:
        return ROOT_FILENAME_MAP[path.as_posix()]
    return EXTENSION_MAP.get(path.suffix.lower())


def count_newlines(path: Path) -> int:
    # Match `wc -l`: count newline bytes, not logical text lines.
    total = 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            total += chunk.count(b"\n")
    return total


def format_table(rows: list[tuple[str, int]]) -> str:
    width = max(len(lang) for lang, _ in rows)
    return "\n".join(f"{lang:<{width}}  {lines:>8}" for lang, lines in rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root (default: auto-detected project root).",
    )
    parser.add_argument(
        "--code-only",
        action="store_true",
        help="Print only code language totals (Python/C++/Cython/C/Fortran).",
    )
    parser.add_argument(
        "--include-self",
        action="store_true",
        help="Include this script in counting when it is under --root.",
    )
    args = parser.parse_args()

    root = args.root.resolve()
    if not root.exists():
        print(f"error: root does not exist: {root}", file=sys.stderr)
        return 2

    totals: dict[str, int] = defaultdict(int)
    self_path = Path(__file__).resolve()
    for rel_path in list_files(root):
        lang = language_for_path(rel_path)
        if not lang:
            continue
        full_path = root / rel_path
        if not args.include_self and full_path.resolve() == self_path:
            continue
        if not full_path.is_file():
            continue
        totals[lang] += count_newlines(full_path)

    if not totals:
        print("No matching files found.")
        return 1

    if args.code_only:
        rows = sorted(
            ((lang, lines) for lang, lines in totals.items() if lang in CODE_LANGUAGES),
            key=lambda item: item[1],
            reverse=True,
        )
    else:
        rows = sorted(totals.items(), key=lambda item: item[1], reverse=True)

    grand_total = sum(lines for _, lines in rows)
    rows.append(("TOTAL", grand_total))
    print(format_table(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
