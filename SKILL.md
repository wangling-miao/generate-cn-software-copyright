---
name: generate-cn-software-copyright
description: Generate and validate Chinese computer software copyright registration identification materials from a real code repository, including the program source-code material and software documentation material in LaTeX/PDF. Use when asked to prepare, update, audit, standardize, or package Chinese software copyright (软著/软件著作权) materials, source-code pages, operation manuals, screenshots, or submission-ready identification documents. Analyze the repository, exclude third-party/generated/test/secret content, use real screenshots and verified facts, compile with XeLaTeX, and run the bundled Python validators before claiming completion.
---

# Generate Chinese Software Copyright Materials

Produce two evidence-based artifacts from the same software version:

1. `程序鉴别材料` from original source code.
2. `文档鉴别材料` from the software's real functions, operation flow, runtime environment, and screenshots.

Use the bundled scripts and templates rather than recreating them.

## Non-negotiable rules

- Never invent the copyright owner, completion date, publication status, software name, version, ownership relationship, or registration facts.
- Never describe planned, stubbed, disconnected, or unverified functions as completed.
- Never use AI-generated mock interfaces, design drafts, unrelated pictures, or empty pages as runtime screenshots.
- Never include secrets, private keys, `.env` files, real personal data, third-party dependencies, vendored code, or generated code in the submitted source material.
- Keep the software name and version exactly identical across configuration, TeX headers, PDFs, application form, and any other registration material.
- Treat validator errors as blocking. Do not claim a final deliverable while any error remains.
- Read `references/legal-and-format-requirements.md` when rules, page counts, special deposit, or submission format matter.

## Workflow

### 1. Inspect the repository

Read only the files needed to establish the software's real identity, architecture, startup method, routes, interfaces, modules, data flow, permissions, security, and screenshots. Follow `references/repository-workflow.md`.

Use repository evidence before asking questions. Ask only for legal/business facts that cannot be established safely. When those facts are missing, generate `draft` output and explicitly list the missing fields.

### 2. Create the configuration

Copy `examples/software-copyright.example.json` to a project-local file such as `software-copyright.json`, then replace every example value with facts for the target software. Read `references/configuration.md` for field semantics.

For source ordering, set `source.priority_globs` so entrypoints and core original business code appear before peripheral files. Do not broaden extensions merely to reach 3000 lines.

### 3. Obtain real screenshots

Start the software using verified repository instructions. Capture the main interface and major feature flows. Remove or mask personal data and credentials. Keep screenshot paths in the configuration.

For CLI/API/library software, use genuine terminal output, API debugging output, or a real example program. Do not fabricate GUI screens.

### 4. Build the materials

Run from this skill directory or call the script by absolute path:

```bash
python scripts/build_materials.py \
  --project /absolute/path/to/repository \
  --config /absolute/path/to/software-copyright.json \
  --mode final \
  --compile \
  --validate
```

Choose a dedicated output path that does not exist yet. The default is `copyright-materials/`; for another run, specify a fresh path with `--output`, such as `--output copyright-materials-v2`. Do not remove an occupied directory to retry. A failed run may leave partial files in its new output directory for troubleshooting.

Use `--mode draft` only when required legal data or screenshots are intentionally incomplete. The build script will:

- collect Git-tracked original source files deterministically;
- exclude common dependency, generated, test, fixture, binary, and secret files;
- merge source with file markers and select all lines or the first/last 1500 lines as applicable;
- generate program and documentation TeX files from the bundled templates;
- copy screenshots, converting them to grayscale by default;
- compile both TeX files twice with XeLaTeX;
- run the material validator.

### 5. Review validator output

Read both:

- `audit/validation-report.md`
- `audit/validation-report.json`

Also inspect `audit/source-manifest.json`, `audit/image-manifest.json`, and both generated PDFs page by page.

Fix every error. Resolve or disclose each warning. Re-run the build into a fresh output directory after changes. Do not patch generated TeX as the primary fix because those edits do not carry over into a rebuild.

### 6. Deliver

Deliver only the reviewed files from `submission/` that the recipient needs. Keep `audit/` local for internal review: it contains the full merged source selection, a copy of the input configuration, and build logs. Never submit, commit, or share the entire output directory. Clearly state:

- software full name and version;
- program and documentation page counts;
- selected/full source line counts;
- number of screenshots;
- validator result and remaining warnings;
- any unverified or missing legal facts.

Do not call the result “submission-ready” unless final-mode validation has zero errors and the PDFs have been visually reviewed.

## Direct validation

After manual edits or when checking an existing output directory, run:

```bash
python scripts/validate_materials.py \
  --project /absolute/path/to/repository \
  --config /absolute/path/to/software-copyright.json \
  --output /absolute/path/to/copyright-materials \
  --mode final
```

Use `--strict` when every warning should fail CI.

## Package self-check

When modifying this skill, run:

```bash
python scripts/validate_skill.py .
python scripts/smoke_test.py
```
