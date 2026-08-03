# 中国软件著作权材料生成 Skill

这是一个供 Codex、ChatGPT Agent 或其他兼容 Agent Skills 标准的智能体使用的技能包。它会读取真实代码仓库，生成并校验两类常用软著鉴别材料：

- 程序鉴别材料：源码排版的 LaTeX 和 PDF；
- 文档鉴别材料：软件说明文档、真实截图、LaTeX 和 PDF。

它不是一个只替换标题的模板，而是包含“仓库分析、源码筛选、文档生成、截图整理、LaTeX 编译、Python 校验、审计报告”的完整流程。

## 目录说明

```text
generate-cn-software-copyright/
├── SKILL.md                       Agent 执行规则
├── README.md                      本说明文件
├── agents/openai.yaml             Codex/ChatGPT 界面元数据
├── assets/templates/              两份 LaTeX 模板
├── examples/                      完整配置示例
├── references/                    法规基线、配置和仓库分析说明
├── scripts/build_materials.py     生成、编译并触发校验
├── scripts/validate_materials.py  软著材料校验器
├── scripts/validate_skill.py      Skill 包结构校验器
└── scripts/smoke_test.py          自包含冒烟测试
```

## 安装

### Codex

把整个目录放入：

```text
${CODEX_HOME:-~/.codex}/skills/generate-cn-software-copyright/
```

也可以将 ZIP 上传或通过产品中的 Skills/Plugins 功能安装。安装后新建会话或重启 Codex，使技能重新发现。

### 其他 Agent

只要该 Agent 支持以目录形式加载 `SKILL.md`、脚本和资源文件，就可以直接安装整个目录。不要只复制 `SKILL.md`，否则模板和 Python 脚本会缺失。

## 环境要求

基础生成仅需要 Python 3.10+。完整校验建议安装：

```bash
python -m pip install -r requirements.txt
```

编译 PDF 还需要：

- XeLaTeX；
- 中文 LaTeX 支持（通常由 TeX Live 的 `ctex` 提供）；
- 推荐安装 `pdfinfo` 和 `pdftotext`，用于页数和文本密度辅助检查。

Ubuntu/WSL 可参考：

```bash
sudo apt update
sudo apt install -y texlive-xetex texlive-lang-chinese poppler-utils
python -m pip install -r requirements.txt
```

## 快速使用

### 1. 准备配置

复制示例：

```bash
cp examples/software-copyright.example.json /你的项目/software-copyright.json
```

修改为目标软件的真实信息。至少要确认：

- 软件全称、简称、版本；
- 著作权人；
- 开发完成日期和发表状态；
- 真实技术栈、运行环境和启动方式；
- 已经实现的主要功能；
- 真实运行截图。

著作权人、完成日期和权属关系不能由 Agent 根据 Git 用户名、域名或公司名称猜测。

### 2. 生成材料

在 Skill 根目录运行：

```bash
python scripts/build_materials.py \
  --project /你的项目 \
  --config /你的项目/software-copyright.json \
  --mode final \
  --compile \
  --validate
```

默认输出到项目中的 `copyright-materials/`：

```text
copyright-materials/
├── submission/
│   ├── source-code.txt
│   ├── 程序鉴别材料.tex
│   ├── 程序鉴别材料.pdf
│   ├── 文档鉴别材料.tex
│   ├── 文档鉴别材料.pdf
│   └── images/
└── audit/
    ├── full-source.txt
    ├── source-manifest.json
    ├── image-manifest.json
    ├── build-record.json
    ├── validation-report.json
    ├── validation-report.md
    └── *-xelatex.log
```

`submission/` 是拟提交内容；`audit/` 用于内部审阅和追溯，不建议直接作为登记附件上传。

## 源码如何选择

脚本默认：

1. Git 项目只读取 Git 跟踪文件；
2. 排除依赖、vendor、node_modules、构建产物、自动生成代码、测试代码、测试数据、二进制文件、环境文件和密钥；
3. 按 `priority_globs` 和路径稳定排序；
4. 将多文件源码合并，并记录每个文件的哈希和行号范围；
5. 合并后超过 3000 行时，选择前 1500 行和后 1500 行；
6. 不足 3000 行时提交全部源码。

不要为了凑满 3000 行把第三方库、生成代码、测试夹具或无关配置纳入材料。源程序不足 60 页时，提交全部是正常情况。

## Python 校验器检查什么

`validate_materials.py` 会检查：

- 配置必填项和残留占位符；
- 软件名称、版本、著作权人在 TeX 中是否一致；
- 源码总行数、选取行数、前后段连续性和 SHA-256；
- 是否错误纳入依赖、生成代码或敏感文件；
- 私钥、访问令牌、密码或 API Key 的高风险特征；
- 截图是否真实存在、分辨率是否过低、是否完成灰度转换；
- XeLaTeX 是否编译成功；
- PDF 是否存在、页数是否正确、是否为 A4 纵向、是否存在近空白页；
- 文档超过 60 页、程序 PDF 页数不符等问题；
- 文档每页文本密度的辅助提示。

它会同时生成：

- `validation-report.json`：适合 CI、Agent 或其他程序读取；
- `validation-report.md`：适合人工审阅。

有 `error` 时脚本以非零状态退出。有 `warning` 时默认仍可退出 0；使用 `--strict` 可让警告也导致失败。

## draft 与 final

- `draft`：允许暂缺截图或部分说明，但报告会明确警告；
- `final`：缺截图、占位符、编译失败、页数错误和信息不一致会作为阻断错误。

即使校验器显示通过，也应人工逐页查看两份 PDF，确认没有截断、乱码、错误截图、敏感数据和明显排版问题。

## 常见问题

### 1. 为什么没有收集到源码？

检查：

- 扩展名是否在 `source.extensions` 中；
- `include_globs` 是否过窄；
- 文件是否被 Git 跟踪；
- 文件是否被识别为测试、生成代码或第三方代码。

详细排除原因在 `audit/source-manifest.json` 的 `rejected_files` 中。

### 2. 为什么程序 PDF 不是 60 页？

源程序不足 3000 行时会提交全部，所以页数可以少于 60 页。源程序超过 3000 行而 PDF 不是 60 页，则属于错误。

### 3. 截图一定要黑白吗？

脚本默认把截图复制为灰度 PNG，以适配传统黑白材料要求。原始截图不会被修改。

### 4. 可以直接改生成后的 TeX 吗？

可以做临时排版调整，但下一次生成会覆盖。内容性修改应优先回写配置或改进生成脚本，然后重新构建和校验。

### 5. 能否处理例外交存或涉密软件？

当前版本只覆盖普通交存。例外交存、封存、涉密、军用软件或复杂权属情形需要单独确认规则，不应直接套用本 Skill。

## 自检

修改 Skill 后运行：

```bash
python scripts/validate_skill.py .
python scripts/smoke_test.py
```

## 重要说明

本 Skill 是材料整理、排版和工程校验工具，不构成法律意见，也不能保证登记机构一定受理或发证。提交前应以中国版权保护中心和受理机构的最新要求为准。

## 持续集成

仓库内置 GitHub Actions。每次推送和 Pull Request 都会运行 Skill 结构校验与自包含冒烟测试：

```bash
python scripts/validate_skill.py .
python scripts/smoke_test.py
```

## 许可证

本项目采用 [MIT License](LICENSE)。法规说明和生成结果仅用于材料整理与工程校验，不构成法律意见。
