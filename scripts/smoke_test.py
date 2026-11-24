#!/usr/bin/env python3
"""Run a self-contained end-to-end smoke test for the skill."""
from __future__ import annotations

import argparse
import json
import os
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


def check_output_safety(cmd: list[str], project: Path) -> None:
    output = project / "copyright-materials"
    output.mkdir()
    saved = output / "existing.txt"
    saved.write_bytes(b"do not overwrite")
    occupied_file = project / "already-a-file"
    occupied_file.write_bytes(b"do not overwrite")

    def run(*extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd + list(extra), capture_output=True, text=True, env=env, timeout=60)

    rejected = [(), ("--output", str(occupied_file)), ("--output", str(project.parent))]
    dangling = project / "dangling"
    link_target = project / "should-not-be-created"
    symlink_created = False
    try:
        dangling.symlink_to(link_target, target_is_directory=True)
    except (OSError, NotImplementedError) as exc:
        print(f"Skipping symlink regression (unsupported): {exc}")
    else:
        symlink_created = True
        rejected.append(("--output", str(dangling)))

    for flags in rejected:
        proc = run("--no-compile", "--no-validate", *flags)
        if proc.returncode != 2 or "输出路径已存在" not in proc.stderr or "材料已生成" in proc.stdout:
            raise RuntimeError(f"Unsafe output was not refused: {flags!r}\n{proc.stdout}\n{proc.stderr}")
    if saved.read_bytes() != b"do not overwrite" or occupied_file.read_bytes() != b"do not overwrite":
        raise RuntimeError("Occupied output contents changed.")
    if link_target.exists() or (symlink_created and not dangling.is_symlink()):
        raise RuntimeError("Dangling output symlink or its target changed.")

    fresh = project / "fresh-parent/fresh"
    proc = run("--no-compile", "--no-validate", "--output", str(fresh))
    fresh_source = fresh / "submission/source-code.txt"
    if proc.returncode != 0 or not fresh_source.is_file():
        raise RuntimeError(f"Fresh output failed.\n{proc.stdout}\n{proc.stderr}")
    original = fresh_source.read_bytes()
    proc = run("--no-compile", "--no-validate", "--output", str(fresh))
    if proc.returncode != 2 or fresh_source.read_bytes() != original:
        raise RuntimeError("A second run reused the previously generated output.")

    failed = project / "failed-output"
    # Hide XeLaTeX without modifying the machine or exercising real data.
    empty_path = project / "empty-path"
    empty_path.mkdir()
    env = dict(os.environ, PATH=str(empty_path))
    proc = run("--compile", "--no-validate", "--output", str(failed), env=env)
    record = json.loads((failed / "audit/build-record.json").read_text(encoding="utf-8"))
    if (proc.returncode == 0 or "材料已生成" in proc.stdout
            or "LaTeX 编译失败" not in proc.stderr
            or [item.get("success") for item in record["compilations"]] != [False, False]):
        raise RuntimeError(f"Compile failure was not reported.\n{proc.stdout}\n{proc.stderr}")
    invalid = project / "invalid-output"
    proc = run("--no-compile", "--validate", "--strict", "--output", str(invalid))
    report = json.loads((invalid / "audit/validation-report.json").read_text(encoding="utf-8"))
    if (proc.returncode == 0 or "材料已生成" in proc.stdout
            or "材料未通过校验" not in proc.stderr
            or not (report["summary"]["error"] or report["summary"]["warning"])):
        raise RuntimeError(f"Validation failure was not reported.\n{proc.stdout}\n{proc.stderr}")
    if saved.read_bytes() != b"do not overwrite" or fresh_source.read_bytes() != original:
        raise RuntimeError("A failing build modified other outputs.")
    print("Output safety checks passed.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-safety-only", action="store_true", help="skip full PDF compilation")
    args = parser.parse_args()
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
        check_output_safety(cmd, project)
        if args.output_safety_only:
            return 0
        cmd.extend(("--output", "full-smoke"))
        proc = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(proc.stdout)
        if proc.returncode != 0:
            print("Smoke test failed.", file=sys.stderr)
            return proc.returncode
        report = json.loads((project / "full-smoke/audit/validation-report.json").read_text(encoding="utf-8"))
        if report["summary"]["error"] != 0:
            print("Smoke test generated validation errors.", file=sys.stderr)
            return 1
        program_pdf = project / "full-smoke/submission/程序鉴别材料.pdf"
        document_pdf = project / "full-smoke/submission/文档鉴别材料.pdf"
        if not program_pdf.exists() or not document_pdf.exists():
            print("Smoke test PDFs missing.", file=sys.stderr)
            return 1
        print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
