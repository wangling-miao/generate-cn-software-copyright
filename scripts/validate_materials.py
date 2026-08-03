#!/usr/bin/env python3
"""Validate generated Chinese software-copyright identification materials."""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from common import (
    command_exists,
    get_nested,
    has_placeholder,
    load_config,
    run_command,
    save_json,
    sha256_text,
)

REQUIRED_FIELDS = (
    "software.full_name",
    "software.short_name",
    "software.version",
    "software.copyright_owner",
    "software.completion_date",
    "software.software_type",
    "software.runtime_platform",
    "software.main_technology",
    "software.access_method",
    "software.target_users",
    "project.hardware_environment",
    "project.software_environment",
    "project.network_environment",
    "project.installation",
    "project.startup",
    "document.overview",
    "document.problem",
    "document.components",
    "document.typical_workflow",
    "document.business_result",
)

HIGH_CONFIDENCE_SECRET_PATTERNS = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("generic-bearer", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b", re.I)),
)

LOW_CONFIDENCE_SECRET_PATTERNS = (
    ("password-assignment", re.compile(r"(?i)\b(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{6,}['\"]")),
    ("api-key-assignment", re.compile(r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
)


@dataclass
class Finding:
    severity: str
    code: str
    message: str
    path: str | None = None
    detail: Any = None


class Validator:
    def __init__(self, project: Path, config: Path, output: Path, mode: str, strict: bool):
        self.project = project
        self.config_path = config
        self.output = output
        self.submission = output / "submission"
        self.audit = output / "audit"
        self.mode = mode
        self.strict = strict
        self.cfg = load_config(config)
        self.findings: list[Finding] = []
        self.metrics: dict[str, Any] = {}

    def add(self, severity: str, code: str, message: str, path: Path | str | None = None, detail: Any = None) -> None:
        if self.strict and severity == "warning":
            severity = "error"
        self.findings.append(Finding(severity, code, message, str(path) if path else None, detail))

    def validate_config(self) -> None:
        for field in REQUIRED_FIELDS:
            value = get_nested(self.cfg, field)
            if value is None or str(value).strip() == "":
                self.add("error", "CONFIG_MISSING", f"缺少必填配置：{field}", self.config_path)
            elif has_placeholder(value):
                self.add("error", "CONFIG_PLACEHOLDER", f"必填配置仍是占位内容：{field}", self.config_path)
        if has_placeholder(self.cfg):
            sev = "error" if self.mode == "final" else "warning"
            self.add(sev, "CONFIG_HAS_PLACEHOLDER", "配置中仍存在待填写占位符。", self.config_path)
        version = str(get_nested(self.cfg, "software.version", ""))
        if version and not re.fullmatch(r"[Vv]?\d+(?:\.\d+){0,3}(?:[-+._A-Za-z0-9]*)?", version):
            self.add("warning", "VERSION_FORMAT", f"版本号格式不常见：{version}", self.config_path)
        modules = get_nested(self.cfg, "document.modules", []) or []
        main_interface = get_nested(self.cfg, "document.main_interface", {}) or {}
        count = len(modules) + (1 if main_interface else 0)
        self.metrics["documented_interfaces"] = count
        if count < 3:
            self.add("warning", "TOO_FEW_MODULES", "建议至少说明 3 个真实界面或核心功能模块。", self.config_path)

    def load_json(self, path: Path) -> dict[str, Any] | list[Any] | None:
        if not path.exists():
            self.add("error", "MISSING_AUDIT_FILE", f"缺少审计文件：{path.name}", path)
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            self.add("error", "INVALID_JSON", f"JSON 文件无法解析：{exc}", path)
            return None

    def validate_source(self) -> None:
        manifest_raw = self.load_json(self.audit / "source-manifest.json")
        if not isinstance(manifest_raw, dict):
            return
        manifest = manifest_raw
        selected_path = self.submission / "source-code.txt"
        full_path = self.audit / "full-source.txt"
        if not selected_path.exists():
            self.add("error", "SOURCE_MISSING", "缺少 source-code.txt。", selected_path)
            return
        selected_text = selected_path.read_text(encoding="utf-8", errors="replace")
        selected_lines = selected_text.splitlines()
        selected_count = len(selected_lines)
        expected = int(manifest.get("selected_source", {}).get("line_count", -1))
        self.metrics["selected_source_lines"] = selected_count
        if selected_count != expected:
            self.add("error", "SOURCE_LINE_MISMATCH", f"源码行数与清单不一致：实际 {selected_count}，清单 {expected}。", selected_path)
        expected_hash = manifest.get("selected_source", {}).get("sha256")
        normalized = "\n".join(selected_lines) + ("\n" if selected_lines else "")
        if expected_hash and sha256_text(normalized) != expected_hash:
            self.add("error", "SOURCE_HASH_MISMATCH", "source-code.txt 已在生成后被修改，哈希与清单不一致。", selected_path)

        lines_per_page = int(manifest.get("selected_source", {}).get("lines_per_page", 50))
        max_pages = int(manifest.get("selected_source", {}).get("max_pages", 60))
        max_lines = lines_per_page * max_pages
        total = int(manifest.get("full_source", {}).get("line_count", 0))
        self.metrics["full_source_lines"] = total
        self.metrics["source_expected_pages"] = max(1, math.ceil(max(selected_count, 1) / lines_per_page))
        if selected_count > max_lines:
            self.add("error", "SOURCE_TOO_LONG", f"程序鉴别材料超过 {max_pages} 页/{max_lines} 行。", selected_path)
        if total > max_lines and selected_count != max_lines:
            self.add("error", "FRONT_BACK_SELECTION", f"源程序超过 {max_pages} 页时，应交存前后各 30 页，共 {max_lines} 行。", selected_path)
        if total <= max_lines and selected_count != total:
            self.add("error", "FULL_SOURCE_REQUIRED", "源程序不足 60 页时应提交全部源程序。", selected_path)
        if total < max_lines:
            self.add("warning", "SOURCE_UNDER_60_PAGES", f"源程序不足 60 页，当前按规定提交全部 {total} 行。", selected_path)
        if selected_count == 0:
            self.add("error", "SOURCE_EMPTY", "未收集到可提交的原创源程序。", selected_path)

        if full_path.exists():
            full_lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
            ranges = manifest.get("selected_source", {}).get("ranges", [])
            rebuilt: list[str] = []
            try:
                for r in ranges:
                    rebuilt.extend(full_lines[int(r["full_start"]) - 1 : int(r["full_end"])])
                if rebuilt != selected_lines:
                    self.add("error", "SELECTION_NOT_CONTIGUOUS", "源码不等于清单声明的连续前段/后段选择结果。", selected_path)
            except Exception as exc:
                self.add("error", "INVALID_SELECTION_RANGES", f"源码选择区间无效：{exc}", self.audit / "source-manifest.json")

        included = manifest.get("included_files", [])
        self.metrics["included_source_files"] = len(included)
        for item in included:
            rel = str(item.get("path", ""))
            low = rel.lower()
            if any(part in low.split("/") for part in ("vendor", "node_modules", "third_party", "generated")):
                self.add("warning", "THIRD_PARTY_OR_GENERATED", f"疑似纳入第三方或生成代码：{rel}", self.audit / "source-manifest.json")

        for name, rx in HIGH_CONFIDENCE_SECRET_PATTERNS:
            matches = list(rx.finditer(selected_text))
            if matches:
                self.add("error", "SECRET_HIGH_CONFIDENCE", f"源码中发现高置信度敏感信息：{name}。", selected_path, {"count": len(matches)})
        for name, rx in LOW_CONFIDENCE_SECRET_PATTERNS:
            matches = list(rx.finditer(selected_text))
            if matches:
                self.add("warning", "SECRET_POSSIBLE", f"源码中可能包含敏感配置：{name}，请人工核对。", selected_path, {"count": len(matches)})
        long_lines = [i + 1 for i, line in enumerate(selected_lines) if len(line.expandtabs(4)) > 180]
        if long_lines:
            self.add("warning", "SOURCE_LONG_LINES", "部分源码行过长，PDF 中可能换行并影响每页 50 行的可读性。", selected_path, {"count": len(long_lines), "examples": long_lines[:20]})

    def validate_tex(self) -> None:
        sw = self.cfg.get("software", {})
        full_name = str(sw.get("full_name", ""))
        version = str(sw.get("version", ""))
        owner = str(sw.get("copyright_owner", ""))
        for name in ("程序鉴别材料.tex", "文档鉴别材料.tex"):
            path = self.submission / name
            if not path.exists():
                self.add("error", "TEX_MISSING", f"缺少 {name}。", path)
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            if has_placeholder(text) or "@@" in text:
                sev = "error" if self.mode == "final" else "warning"
                self.add(sev, "TEX_PLACEHOLDER", f"{name} 仍存在占位符或模板标记。", path)
            if full_name and full_name not in text:
                self.add("error", "NAME_INCONSISTENT", f"{name} 未包含配置中的软件全称。", path)
            if version and version not in text:
                self.add("error", "VERSION_INCONSISTENT", f"{name} 未包含配置中的版本号。", path)
            if name.startswith("文档") and owner and owner not in text:
                self.add("error", "OWNER_INCONSISTENT", "文档鉴别材料未包含配置中的著作权人。", path)
            if "\\fancyhead[R]" not in text:
                self.add("error", "PAGE_NUMBER_MISSING", f"{name} 未配置右上角页码。", path)

    def validate_images(self) -> None:
        raw = self.load_json(self.audit / "image-manifest.json")
        if not isinstance(raw, list):
            return
        missing = 0
        valid = 0
        for item in raw:
            if item.get("missing"):
                missing += 1
                sev = "error" if self.mode == "final" else "warning"
                self.add(sev, "SCREENSHOT_MISSING", f"缺少真实截图：{item.get('module', '未命名模块')}", item.get("source"))
                continue
            output = Path(str(item.get("output", "")))
            if not output.exists():
                self.add("error", "SCREENSHOT_COPY_MISSING", "截图清单记录的输出文件不存在。", output)
                continue
            valid += 1
            width = int(item.get("width", 0) or 0)
            height = int(item.get("height", 0) or 0)
            if width and height and (width < 640 or height < 360):
                self.add("warning", "SCREENSHOT_LOW_RESOLUTION", f"截图分辨率偏低：{width}×{height}。", output)
            if get_nested(self.cfg, "output.grayscale_screenshots", True) and item.get("output_mode") not in {"1", "L", None}:
                self.add("warning", "SCREENSHOT_NOT_GRAYSCALE", "截图未转换为黑白/灰度。", output)
        self.metrics["screenshots_valid"] = valid
        self.metrics["screenshots_missing"] = missing
        if valid < 3:
            self.add("warning", "TOO_FEW_SCREENSHOTS", "建议至少提供 3 张能够证明真实功能的运行截图。", self.submission / "images")

    def pdf_info(self, path: Path) -> tuple[int | None, list[tuple[float, float]], list[str], list[bool]]:
        pages: int | None = None
        sizes: list[tuple[float, float]] = []
        page_texts: list[str] = []
        page_has_images: list[bool] = []
        try:
            from pypdf import PdfReader  # type: ignore

            reader = PdfReader(str(path))
            pages = len(reader.pages)
            for page in reader.pages:
                box = page.mediabox
                sizes.append((float(box.width), float(box.height)))
                try:
                    page_texts.append(page.extract_text() or "")
                except Exception:
                    page_texts.append("")
                has_image = False
                try:
                    resources = page.get("/Resources")
                    if resources:
                        resources = resources.get_object()
                        xobjects = resources.get("/XObject")
                        if xobjects:
                            xobjects = xobjects.get_object()
                            for obj in xobjects.values():
                                resolved = obj.get_object()
                                if resolved.get("/Subtype") == "/Image":
                                    has_image = True
                                    break
                except Exception:
                    has_image = False
                page_has_images.append(has_image)
            return pages, sizes, page_texts, page_has_images
        except Exception:
            pass
        if command_exists("pdfinfo"):
            proc = run_command(["pdfinfo", str(path)], timeout=60)
            m = re.search(r"^Pages:\s+(\d+)", proc.stdout, re.M)
            if m:
                pages = int(m.group(1))
        return pages, sizes, page_texts, page_has_images

    def validate_pdfs(self) -> None:
        build = self.load_json(self.audit / "build-record.json")
        if isinstance(build, dict) and build.get("compile_requested"):
            for item in build.get("compilations", []):
                if not item.get("success"):
                    self.add("error", "LATEX_COMPILE_FAILED", f"LaTeX 编译失败：{item.get('tex')}", self.audit / str(item.get("log", "")))
        expected_program_pages = int(self.metrics.get("source_expected_pages", 0) or 0)
        for name in ("程序鉴别材料.pdf", "文档鉴别材料.pdf"):
            path = self.submission / name
            if not path.exists():
                self.add("error", "PDF_MISSING", f"缺少编译后的 {name}。", path)
                continue
            pages, sizes, texts, image_flags = self.pdf_info(path)
            self.metrics[name] = {"pages": pages, "size_bytes": path.stat().st_size}
            if pages is None:
                self.add("warning", "PDF_PAGE_COUNT_UNAVAILABLE", f"无法读取 {name} 页数，请安装 pypdf 或 pdfinfo。", path)
                continue
            if name.startswith("程序") and expected_program_pages and pages != expected_program_pages:
                self.add("error", "PROGRAM_PAGE_COUNT", f"程序 PDF 应为 {expected_program_pages} 页，实际为 {pages} 页。", path)
            if name.startswith("文档") and pages > 60:
                self.add("error", "DOCUMENT_OVER_60_PAGES", "文档超过 60 页，应改为前后各连续 30 页的交存版本。", path)
            if pages <= 0:
                self.add("error", "PDF_EMPTY", f"{name} 没有有效页面。", path)
            for idx, (w, h) in enumerate(sizes, start=1):
                if w > h:
                    self.add("error", "PDF_NOT_PORTRAIT", f"第 {idx} 页不是纵向页面。", path)
                if not (585 <= w <= 605 and 832 <= h <= 852):
                    self.add("warning", "PDF_NOT_A4", f"第 {idx} 页尺寸疑似不是 A4：{w:.1f}×{h:.1f} pt。", path)
            if texts:
                blank = [
                    i + 1
                    for i, text in enumerate(texts)
                    if len(re.sub(r"\s+", "", text)) < 10
                    and not (i < len(image_flags) and image_flags[i])
                ]
                if blank:
                    self.add("warning", "PDF_NEAR_BLANK_PAGES", "PDF 中存在接近空白且不含图片的页面。", path, {"pages": blank[:20]})
                sw = self.cfg.get("software", {})
                joined = "\n".join(texts)
                if command_exists("pdftotext"):
                    extracted = run_command(["pdftotext", str(path), "-"], timeout=120)
                    if extracted.returncode == 0 and extracted.stdout.strip():
                        joined = extracted.stdout
                for field, label in (("full_name", "软件全称"), ("version", "版本号")):
                    value = str(sw.get(field, ""))
                    if value and value not in joined:
                        self.add("warning", "PDF_TEXT_EXTRACTION_MISMATCH", f"PDF 文本层未检出{label}；可能是字体编码问题，也可能信息不一致。", path)

        doc_pdf = self.submission / "文档鉴别材料.pdf"
        if doc_pdf.exists() and command_exists("pdftotext"):
            proc = run_command(["pdftotext", "-layout", str(doc_pdf), "-"], timeout=120)
            pages = proc.stdout.split("\f")
            counts = [len([line for line in p.splitlines() if line.strip()]) for p in pages if p.strip()]
            self.metrics["document_nonblank_text_lines_per_page"] = counts
            _, _, _, doc_image_flags = self.pdf_info(doc_pdf)
            sparse = [
                i + 1
                for i, count in enumerate(counts)
                if count < 20 and not (i < len(doc_image_flags) and doc_image_flags[i])
            ]
            if sparse:
                self.add("warning", "DOCUMENT_TEXT_DENSITY", "部分不含图片的文档页文本行数较少，应检查是否存在空白或排版异常。", doc_pdf, {"pages": sparse[:20], "counts": counts})

    def write_reports(self) -> tuple[int, int, int]:
        counts = {sev: sum(1 for f in self.findings if f.severity == sev) for sev in ("error", "warning", "info")}
        report = {
            "status": "fail" if counts["error"] else "pass",
            "mode": self.mode,
            "strict": self.strict,
            "project": str(self.project),
            "config": str(self.config_path),
            "output": str(self.output),
            "summary": counts,
            "metrics": self.metrics,
            "findings": [asdict(f) for f in self.findings],
        }
        save_json(self.audit / "validation-report.json", report)

        lines = [
            "# 软件著作权材料校验报告",
            "",
            f"- 结论：**{'未通过' if counts['error'] else '通过'}**",
            f"- 模式：`{self.mode}`",
            f"- 错误：{counts['error']}",
            f"- 警告：{counts['warning']}",
            "",
            "## 关键指标",
            "",
        ]
        for key, value in self.metrics.items():
            lines.append(f"- `{key}`：{json.dumps(value, ensure_ascii=False)}")
        lines.extend(["", "## 检查结果", ""])
        if not self.findings:
            lines.append("未发现错误或警告。")
        else:
            for f in self.findings:
                icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(f.severity, "-")
                lines.append(f"### {icon} {f.code}")
                lines.append("")
                lines.append(f.message)
                if f.path:
                    lines.append(f"\n文件：`{f.path}`")
                if f.detail is not None:
                    lines.append(f"\n详情：`{json.dumps(f.detail, ensure_ascii=False)}`")
                lines.append("")
        (self.audit / "validation-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        return counts["error"], counts["warning"], counts["info"]

    def run(self) -> int:
        self.validate_config()
        self.validate_source()
        self.validate_tex()
        self.validate_images()
        self.validate_pdfs()
        errors, warnings, _ = self.write_reports()
        print(f"校验完成：错误 {errors}，警告 {warnings}")
        print(f"报告：{self.audit / 'validation-report.md'}")
        return 1 if errors else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--config", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("draft", "final"), default="final")
    parser.add_argument("--strict", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    validator = Validator(
        args.project.resolve(), args.config.resolve(), args.output.resolve(), args.mode, args.strict
    )
    return validator.run()


if __name__ == "__main__":
    raise SystemExit(main())
