#!/usr/bin/env python3
"""Shared helpers for the software-copyright skill scripts."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Iterable

PLACEHOLDER_RE = re.compile(
    r"(?:【[^】]*(?:待补充|请填写|软件全称|著作权人|YYYY|示例)[^】]*】|"
    r"\b(?:TODO|TBD|FIXME|CHANGEME)\b|<[^>]*(?:fill|replace|todo)[^>]*>)",
    re.IGNORECASE,
)


def load_config(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    text = path.read_text(encoding="utf-8")
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise RuntimeError("YAML 配置需要安装 PyYAML；也可改用 JSON 配置。") from exc
        data = yaml.safe_load(text)
    else:
        data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("配置文件根节点必须是对象。")
    return data


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def latex_escape(value: Any) -> str:
    text = "" if value is None else str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(ch, ch) for ch in text)


def latex_paragraph(value: Any) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    paragraphs = [latex_escape(p.strip()) for p in re.split(r"\n\s*\n", text) if p.strip()]
    return "\n\n".join(paragraphs)


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def run_command(
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 300,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=timeout,
        check=False,
        env={**os.environ, "LC_ALL": os.environ.get("LC_ALL", "C.UTF-8")},
    )
    if check and proc.returncode != 0:
        raise RuntimeError(f"命令执行失败 ({proc.returncode}): {' '.join(args)}\n{proc.stdout}")
    return proc


def get_nested(data: dict[str, Any], dotted: str, default: Any = None) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def has_placeholder(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (dict, list)):
        return any(has_placeholder(v) for v in (value.values() if isinstance(value, dict) else value))
    return bool(PLACEHOLDER_RE.search(str(value)))


def nonempty(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def unique_preserve_order(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out
