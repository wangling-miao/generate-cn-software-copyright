#!/usr/bin/env python3
"""Validate this Agent Skill package itself."""
from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

REQUIRED = (
    "SKILL.md",
    "README.md",
    "agents/openai.yaml",
    "scripts/build_materials.py",
    "scripts/validate_materials.py",
    "assets/templates/program-identification.tex.tpl",
    "assets/templates/document-identification.tex.tpl",
    "examples/software-copyright.example.json",
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.skill.resolve()
    errors: list[str] = []
    for rel in REQUIRED:
        if not (root / rel).is_file():
            errors.append(f"缺少文件：{rel}")

    skill_md = root / "SKILL.md"
    if skill_md.exists():
        text = skill_md.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
        if not m:
            errors.append("SKILL.md 缺少合法 YAML frontmatter。")
        else:
            front = m.group(1)
            names = re.findall(r"^([A-Za-z0-9_-]+):", front, re.M)
            if set(names) != {"name", "description"}:
                errors.append("SKILL.md frontmatter 只能包含 name 和 description。")
            nm = re.search(r"^name:\s*([^\n]+)$", front, re.M)
            if not nm:
                errors.append("SKILL.md 缺少 name。")
            else:
                name = nm.group(1).strip().strip('"\'')
                if not re.fullmatch(r"[a-z0-9-]{1,63}", name):
                    errors.append(f"技能名不合法：{name}")
                if root.name != name:
                    errors.append(f"目录名 {root.name} 必须与技能名 {name} 一致。")
            if not re.search(r"^description:\s*\S", front, re.M):
                errors.append("SKILL.md 缺少 description。")

    for path in (root / "scripts").glob("*.py"):
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            errors.append(f"Python 语法错误：{path.name}:{exc.lineno} {exc.msg}")

    templates = {
        "program": (root / "assets/templates/program-identification.tex.tpl", {"@@SOFTWARE_NAME@@", "@@SOFTWARE_VERSION@@", "@@TOTAL_PAGES@@", "@@CODE_PAGES@@"}),
        "document": (root / "assets/templates/document-identification.tex.tpl", {"@@SOFTWARE_NAME@@", "@@SOFTWARE_VERSION@@", "@@DOCUMENT_BODY@@"}),
    }
    for label, (path, tokens) in templates.items():
        if path.exists():
            text = path.read_text(encoding="utf-8")
            missing = [t for t in tokens if t not in text]
            if missing:
                errors.append(f"{label} 模板缺少标记：{', '.join(missing)}")

    if errors:
        print("Skill 校验失败：")
        for err in errors:
            print(f"- {err}")
        return 1
    print(f"Skill 校验通过：{root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
