#!/usr/bin/env python3
"""Run a self-contained end-to-end smoke test for the skill."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


def write_demo_source(root: Path) -> None:
    src = root / "src"
    src.mkdir(parents=True)
    lines = ["package demo", "", "// DemoService contains deterministic sample code."]
    for i in range(1, 3201):
        lines.append(f"func Operation{i:04d}() int {{ return {i} }}")
    (src / "main.go").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_images(root: Path) -> None:
    shots = root / "screenshots"
    shots.mkdir(parents=True)
    try:
        from PIL import Image, ImageDraw  # type: ignore
    except ImportError as exc:
        raise RuntimeError("smoke_test 需要 Pillow。") from exc
    for i, title in enumerate(("Dashboard", "Tasks", "Members", "Statistics"), start=1):
        image = Image.new("RGB", (1280, 720), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((50, 50, 1230, 670), outline="black", width=4)
        draw.text((100, 100), f"Real smoke-test screenshot: {title}", fill="black")
        draw.text((100, 180), f"Module {i}", fill="black")
        image.save(shots / f"{i:02d}-{'dashboard' if i == 1 else ['tasks','members','statistics'][i-2]}.png")


def main() -> int:
    skill_root = Path(__file__).resolve().parents[1]
    example = json.loads((skill_root / "examples/software-copyright.example.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory(prefix="soft-copyright-smoke-") as tmp:
        project = Path(tmp) / "project"
        project.mkdir()
        write_demo_source(project)
        write_images(project)
        config = project / "software-copyright.json"
        example["output"]["directory"] = "copyright-materials"
        config.write_text(json.dumps(example, ensure_ascii=False, indent=2), encoding="utf-8")
        cmd = [
            sys.executable,
            str(skill_root / "scripts/build_materials.py"),
            "--project",
            str(project),
            "--config",
            str(config),
            "--mode",
            "final",
            "--compile",
            "--validate",
        ]
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(proc.stdout)
        if proc.returncode != 0:
            print("Smoke test failed.", file=sys.stderr)
            return proc.returncode
        report = json.loads((project / "copyright-materials/audit/validation-report.json").read_text(encoding="utf-8"))
        if report["summary"]["error"] != 0:
            print("Smoke test generated validation errors.", file=sys.stderr)
            return 1
        program_pdf = project / "copyright-materials/submission/程序鉴别材料.pdf"
        document_pdf = project / "copyright-materials/submission/文档鉴别材料.pdf"
        if not program_pdf.exists() or not document_pdf.exists():
            print("Smoke test PDFs missing.", file=sys.stderr)
            return 1
        print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
