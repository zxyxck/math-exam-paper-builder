---
name: math-exam-paper-builder
description: >
  基于「数学题库 Markdown」的组卷技能。当用户提供一本/多本数学做题本的
  章节 Markdown 提取文件（如《李林 880》第一章~第十二章 .md），或已归档的
  question_bank.json，并要求「组卷 / 出一套卷 / 生成模拟卷 / 模拟试卷 /
  按考纲抽题 / 换一组题 / 出 PDF 试卷 / 试卷留白 / 题号带索引 /
  验证题库完整性 / 修复坏题 / 用做题本 PDF 补齐选项 / 排除已用题 /
  重置组卷系统（清空已组卷题目记录，回到未组卷状态）」时触发。
  将题库 MD 解析为标准 JSON 题库 → 健康体检 → 按考纲 profile 抽题 →
  生成 LaTeX 试卷源 → xelatex 编译为 A4 留白 PDF（题目无答案，题号后标注
  「书·章·块·题型·题号」索引）。全部脚本仅依赖 Python 标准库与 TeX Live，
  跨 Agent 平台 / 跨 AI 可移植。
---

# Math Exam Paper Builder（数学组卷）

从「章节 Markdown 题库」到「A4 留白试卷 PDF」的完整组卷流水线。

## 1. 核心链路

```
12 章 MD 文件 ──S1 解析──▶ 章节 JSON ──S2 合并──▶ question_bank.json（唯一事实源）
                                                    │
                                                    ├─S3 健康体检（剔除 LaTeX 语法坏题）
                                                    ▼
                                              候选池（综合题块）
                                                    │
                                                    └─S4 抽题（按 profile + 排除已用）──▶ selectN.json
                                                                                              │
                                                    ┌─────────────────────────────────────────┘
                                                    ▼
                                        S5 build_exam_tex.py ──▶ 试卷.tex ──S6 xelatex×2──▶ 试卷.pdf
```

- **一次性的**：S1/S2 题库建设（MD → JSON）
- **每次组卷的**：S3 体检 → S4 抽题 → S5 组卷 → S6 编译
- 可选：S7 导出人读 `bank_md/`（每章带"本章题号索引"）

## 2. 环境依赖与安装

### 2.1 依赖总览

| 组件 | 版本要求 | 用途 | 是否必需 |
|---|---|---|---|
| Python | ≥ 3.9（标准库即可） | 解析/合并/体检/抽题/组卷脚本 | 必需 |
| TeX Live（xelatex） | 任意含 ctex 的发行版 | 编译 .tex → PDF | 出 PDF 必需；仅出 .tex 可免 |
| ctex 宏包 + fandol 字体 | TeX Live 自带 | 中文排版 | 必需（随 TeX Live） |
| pip 第三方包 | 无 | — | 不需要（零依赖） |

> **关键设计**：全部脚本只用 `argparse / json / re / os / sys / subprocess / glob / collections` 等标准库，
> **不安装任何 pip 包**。这是跨平台、跨 AI 高移植性的根基。

### 2.2 安装 Python（三平台）

```bash
# Ubuntu / Debian
sudo apt-get install -y python3 python3-venv

# macOS（Homebrew）
brew install python

# Windows
# 到 https://www.python.org/downloads/ 下载安装，勾选 "Add to PATH"
```

校验：

```bash
python3 --version   # 需要 ≥ 3.9
```

### 2.3 安装 TeX Live + 中文字体

```bash
# —— Ubuntu / Debian（约 1~2 GB，apt 装完自动注册 fandol 字体）
sudo apt-get update
sudo apt-get install -y texlive-xetex texlive-lang-chinese texlive-latex-extra

# —— macOS（Homebrew，两种选一）
brew install --cask mactex-no-gui        # 完整（推荐，含 ctex/fandol）
# 或最小化：brew install --cask basictex && sudo tlmgr update --self && sudo tlmgr install ctex fandol latexmk

# —— Windows
# 安装 TeX Live：下载 install-tl-windows.exe（https://tug.org/texlive/）
# 安装时选择 scheme-full 或至少勾选 collection-langchinese / collection-latexrecommended
```

**校验（三平台通用）**：

```bash
xelatex --version                              # 存在即 OK
kpsewhich ctexart.cls                          # 应输出 ctexart.cls 路径
kpsewhich fandol-song-clm.otf                  # 应输出字体路径（fontset=fandol 依赖）
```

若 `kpsewhich fandol-*` 无输出：`sudo tlmgr install fandol`（TeX Live 本地仓库）或重装 `texlive-lang-chinese`。

### 2.4 其他工具（可选）

```bash
pdftoppm -v   # poppler-utils：PDF 转 PNG 预览（排查排版用）
```

## 3. 配置说明

### 3.1 工作区目录结构

```
exam-workspace/
├── source/                      # 输入：章节 MD（用户提供）
│   ├── 880高数第一章.md
│   ├── 880高数第二章.md
│   └── ...（第3~12章）
├── bank/                        # S1 中间产物：每章一个 JSON
│   └── ch1.json ...
├── question_bank.json           # S2 产物：合并题库（唯一事实源）
├── bank_md/                     # S7 可选：人读导出
├── select.json / select2.json   # S4 产物：选题清单
├── exams/                       # S5/S6 产物：试卷 .tex + .pdf
└── scripts/                     # 本技能脚本（见 §4 复制）
```

### 3.2 章节 MD 输入格式约定

解析器 `parse_question_bank.py` 兼容以下格式（标题层级灵活，可有可无）：

```markdown
### 一、基础题                      # 或 "## 基础题" / "基础题"
#### （一）选择题                   # 或 "#### 一、选择题" / "选择题"
1.  题干……$公式$……
    A. 选项A    B. 选项B    C. 选项C    D. 选项D   # 可同行或分行
#### （二）填空题
1.  当 $x\to 0$ 时，…… \_\_\_\_   # 下划线或 \_ 表示填空横线
#### （三）解答题
1.  证明：……
    (I) 第一问……                   # (I)(II)(III) 或 ①②③ 为子问
### 二、综合题
……
### 三、拓展题
……
```

自动处理：
- **无题号**的题目自动按块内连续编号
- **缺"综合题"块标题**时，同一题型第二次出现自动切到综合题
- 公式支持 `$…$`、`\(…\)`、`\[…\]` 三种写法（原样保留进 LaTeX）

### 3.3 题库 JSON 结构（question_bank.json）

```json
{
  "source": ["880高数第一章.md", "880高数第二章.md", "..."],
  "questions": [
    {
      "book": "高数篇",          // 或 "线代篇"
      "chapter": 1,              // 1~12 整数
      "block": "综合题",          // 基础题 / 综合题 / 拓展题
      "qtype": "choice",         // choice / blank / solve
      "num": 3,                  // 题号（章内块内题型内）
      "qtype_cn": "一、选择",
      "stem": "设当 $x \\to 0$ 时，$\\alpha(x)=...$（ ）。",
      "options": {"A": "$-28$", "B": "$28$", "C": "$14$", "D": "$-14$"},
      "parts": null,             // 解答题子问 [{tag, text}]
      "answer": null,
      "tags": [],
      "note": "",      // 内容修复标记（源数据乱码/截断/选项错位的修复记录）
      "loc": [{"page": 2, "y0": 153.0}]   // 可选：PDF 定位
    }
  ]
}
```

### 3.4 选题清单 JSON 结构（selectN.json）

```json
{
  "header": {
    "exam": "全国硕士研究生招生考试",
    "title": "数学（二）模拟试卷（一）",
    "sub": "——精选自 880 题（A4 留白版）",
    "score_total": 150, "time": 180,
    "notes": ["一、考生应……", "二、答题时……", "三、本试卷共 22 题，……"]
  },
  "sections": {
    "choice": {"name": "一、选择题", "desc": "……共 50 分。"},
    "blank":  {"name": "二、填空题", "desc": "……共 30 分。"},
    "solve":  {"name": "三、解答题", "desc": "……共 70 分。"}
  },
  "questions": [
    {"id": 1, "kind": "choice", "score": 5, "chapter": 1, "block": "综合题",
     "qtype": "一、选择", "num": 3,
     "source": "高数篇·第一章·综合题·选择(3)", "考点": "综合题"}
  ]
}
```

`source` 是组卷脚本定位题目的唯一键，格式固定：`{书}·第{中文章}章·{块}·{选择|填空|解答}({题号})`。

### 3.5 考纲 profile（抽题配置）

内置在 `pick_from_bank.py` 的 `PROFILES` 字典，键为 `题型 → {章节号: 题数}`：

```python
PROFILES = {
    "数二标准": {                      # 22 题 = 选10 + 填6 + 解6，150 分 / 180 分钟
        "choice": {1: 2, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 8: 1, 11: 1},
        "blank":  {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 10: 1},
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 11: 1},
    },
    "数二真题": {                      # 严格对齐考研数二真题的学科占比：高数 80% / 线代 21.3%
        "choice": {1:1, 2:2, 3:1, 4:1, 5:1, 6:1, 8:1, 10:1, 11:1},   # 7 高数 + 3 线代
        "blank":  {1:1, 2:1, 3:1, 5:1, 6:1, 12:1},                    # 5 高数 + 1 线代
        "solve":  {1:1, 2:1, 3:1, 5:1, 6:1, 11:1},                    # 5 高数 + 1 线代
    },
    "高数全": {...}                     # 高数 6 章全覆盖的专项卷
    "数二轮换": {...}                   # 线代 7~12 章跨卷轮换 + 题型配额灵活（见下）
}
```

**「数二轮换」profile**（不强求对齐真题格式）：高数固定 17 题占大头（选择 7 + 填空 5 + 解答 5），
线代 5 题（选择 3 + 填空 1 + 解答 1）在 7~12 章之间轮换：

```python
"数二轮换": {
    "title": "数学（二）模拟试卷",
    "score_total": 150, "time": 180,
    "choice": {1: 1, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1},   # 高数 7
    "blank":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},          # 高数 5
    "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},          # 高数 5
    # 线代轮换块：chapters 为轮换池，kinds 为题型配额（总数 = 每卷线代题数）
    "xian": {"chapters": [7, 8, 9, 10, 11, 12],
              "kinds": [("choice", 3), ("blank", 1), ("solve", 1)]},
}
```

轮换规则（脚本自动处理）：
1. 从 `--exclude` 清单统计已覆盖过的线代章节，**优先抽未覆盖章节**（保证多卷覆盖全部线代章）；
   未覆盖章节不足时，再补已用章节（新一轮轮换）。
2. 每卷线代各章的**题型随机分配**（哪章出选择/填空/解答不固定）。
3. 章节-题型配额不足时自动告警，不强制填满。

**「数二真题」profile 的分值核算**：

| 题型 | 高数 | 线代 | 合计 |
|---|---|---|---|
| 选择 10×5 | 7×5=35 | 3×5=15 | 50 |
| 填空 6×5 | 5×5=25 | 1×5=5 | 30 |
| 解答 6（共 70） | 5 题 | 1 题 | 70 |
| **合计** | **120（80%）** | **32（21.3%）** | **152**（卷面标注 150） |

证明题数量由 `--max-proofs` 控制（默认 2）。新增 profile：在 `pick_from_bank.py` 的 `PROFILES` 中追加即可。

## 4. 脚本部署（移植第一步）

将 §附录 中的 **6 个脚本**保存为 `scripts/` 下的同名文件（文件名必须一致，脚本间有相互 import）：

```
scripts/
├── parse_question_bank.py   # S1 解析
├── merge_banks.py           # S2 合并
├── export_bank.py           # S7 可选导出
├── bank_health.py           # S3 健康体检（被 pick_from_bank import）
├── pick_from_bank.py        # S4 抽题
├── build_exam_tex.py        # S5/S6 组卷 + 编译
└── _verify_scan.py          # S8 可选完整性扫描（结构/内容/源数据质量）
（可选）pdf_bank_parser.py   # 解析做题本 PDF 提取文本（补选项用）
```

校验部署：

```bash
cd exam-workspace/scripts
python3 bank_health.py --help >/dev/null && echo OK
python3 build_exam_tex.py --help >/dev/null && echo OK
python3 pick_from_bank.py --help >/dev/null && echo OK
```

## 5. 工作流（逐步执行）

约定 `WORKDIR=exam-workspace`，以下命令均在其下执行。

### S1 解析：MD → 章节 JSON

```bash
python3 scripts/parse_question_bank.py \
    "source/880高数第一章.md" --book 高数篇 -o bank/ch1.json
# 文件名含 "第X章" 时 --chapter 可省略；否则显式加 --chapter 1
```

循环处理 12 个章节文件（高数 1-6 章 `--book 高数篇`，线代 7-12 章 `--book 线代篇`）。

### S2 合并：章节 JSON → question_bank.json

```bash
python3 scripts/merge_banks.py bank/ch1.json bank/ch2.json ... -o question_bank.json
# 或目录批量：python3 scripts/merge_banks.py bank/ -o question_bank.json
```

### S3 健康体检

```bash
python3 scripts/bank_health.py question_bank.json
# 输出：总题数: N | 坏题数: M；坏题列出 书/章/块/题型/题号/原因
```

坏题会被 S4 自动排除。**如需修复坏题**：对照用户原始 MD 手动改 `question_bank.json` 中对应题目的 `stem` 后重新体检。

### S3.5 完整性验证（可选但推荐，源数据质量差时必做）

```bash
python3 scripts/_verify_scan.py question_bank.json   # 结构/内容/源数据质量三类扫描
```

扫描覆盖：字段缺失、空题干、题号连续性、重复 key、选择题选项缺失/不足、填空横线、
子问、真截断、乱码（如 `a<02)` 应为 `a<0<b`）、选项串行错位。发现的问题分两类处理：
- **可安全修复**（乱码恢复、题干补全、选项从错位行还原）：直接改 `question_bank.json`，
  在 `note` 字段记录修复内容；
- **无法复原**（选项缺失且无权威来源）：列入排除清单 `content_bad.json`（伪 select 格式，
  仅含 `questions[].source`），组卷时 `--exclude` 自动避开。

> 常见源数据坑：选择题缺选项行、解答题题干截断（`$` 未闭合）、题干拼接错乱
> （前段+后段来自不同题）、填空/解答内容误标为选择题。修复原则：以用户提供的
> 权威源（原书 LaTeX / 做题本 PDF）为准，交叉验证答案。

### S4 抽题：生成 selectN.json

```bash
# 卷一（新卷）：（有排除清单时务必带上）
python3 scripts/pick_from_bank.py question_bank.json --seed 42 --exclude content_bad.json --no 1 -o select.json

# 卷二（避开卷一已用题）：
python3 scripts/pick_from_bank.py question_bank.json --seed 20260819 \
    --exclude select.json --no 2 -o select2.json

# 卷三（避开前两卷 + 固定种子可复现）：
python3 scripts/pick_from_bank.py question_bank.json --seed 20260819 \
    --exclude select.json --exclude select2.json --no 3 -o select3.json
```

参数说明：

| 参数 | 含义 |
|---|---|
| `--seed N` | 随机种子；固定后同参数结果可复现（同题同序） |
| `--exclude f.json` | 排除已用题（可多次传），避免跨卷重复 |
| `--block 综合题` | 抽题块（综合题 / 基础题 / 拓展题） |
| `--no N` | 卷号，标题显示（一）（二）（三）… |
| `--profile` | 考纲 profile，默认 `数二标准`，另有 `数二真题`（高数 80%/线代 21.3%）、`高数全` |
| `--max-proofs N` | 同一试卷证明题数量上限（默认 2，对齐考研数二真题约束）。设 0 禁止，负数不限 |

### S4.1 重置组卷系统（清空已组卷题目记录）

当用户说「重置组卷系统 / 清空已选题 / 回到未组卷状态」时，**删除所有 `selectN.json`**
（抽题生成的**已组卷题目记录 / 跨卷排除清单**），即可清空"已选题限额"，让题库回到
从未组过卷的状态——下一次抽题不带 `--exclude` 即全量可选，且不会与历史卷重复。

```bash
rm -f select*.json      # 删除已组卷题目记录（select1.json ~ selectN.json）
# 可选：同时清空已生成的试卷产物（保留空的 exams/ 输出目录即可）
rm -f exams/*
```

> 说明：`selectN.json` 是唯一的"已选题"状态载体；`question_bank.json` / `content_bad.json`
> / 脚本 / 题库源数据均不受影响。重置后首次组卷从 `select1.json` 重新开始
> （见 §8 移植清单与 MIGRATE.md「日常组卷命令 · 重置组卷系统」）。

### S5 组卷：select → 试卷.tex

```bash
python3 scripts/build_exam_tex.py \
    --select select2.json --bank question_bank.json \
    -o "exams/数二模拟卷(二)_LaTeX.tex"
# 默认同时编译 PDF；仅要 .tex 加 --no-pdf
```

试卷版式（内置，无需配置）：
- `ctexart` + `fontset=fandol`，A4，11pt，页边距 2.0/2.2cm
- 卷头：考试名 / 标题 / 副标题 / 满分时间 / 注意事项三条
- 选择题：题号加粗，选项 (A)(B)(C)(D) 每行两个 `\hfill` 排布
- 填空题：`\_\_\_\_`（≥2 个 `\_`）自动转真横线 `\underline{\hspace{2.5cm}}`
- 解答题：`stem` 引语 + **`parts` 子问**（(I)(II)... 逐行缩进渲染）+ 纯留白（`\vspace{4.5cm}`，不画框），便于手写
- **`parts` 通用渲染（所有题型）**：选择题的命题列表（①②③④…）、填空题的条件列表、解答题子问（(I)(II)…）均逐行缩进渲染在 `stem` 之后。条件型选择题（如"下列命题正确的是"）若不渲染命题列表会表现为「题目缺条件」——此问题已在 §8.7 修复（`build_exam_tex.py` 现对所有题型通用渲染 `parts`）
- **题号后索引**：灰色小字 `（高数·第一章·综合·选择3）` = 书·章·块·题型·题号

### S6 编译（build_exam_tex.py 已自动调用）

```bash
cd exams
xelatex -interaction=nonstopmode -halt-on-error "数二模拟卷(二)_LaTeX.tex"   # 跑两遍
```

产物：`数二模拟卷(二)_LaTeX.pdf`（A4，约 5~6 页）。

### S7 可选：导出人读题库

```bash
python3 scripts/export_bank.py question_bank.json -o bank_md/
# 每章一个 MD，开头带「本章题号索引」：基础题：选择 1、2…；综合：选择 1…
```

## 6. 自动处理的"坑"（勿手工干预）

组卷脚本已内置，新增题库时请保持其开启：

| # | 问题 | 处理 |
|---|---|---|
| 1 | 公式三种风格 `$…$` / `\(…\)` / `\[…\]` | 统一识别，公式段原样保留，只转义正文 |
| 2 | 填空下划线 `\_\_\_\_`（公式内外） | 替换为 `\underline{\hspace{2.5cm}}` |
| 3 | 带圈数字 `①-⑳`（fandol 缺失） | 替换为 `(1)(2)…` |
| 4 | 选项混入题干（如 `…条件( ). A. ①成立; B. ④成立; …`） | `split_inline_options` 自动拆为 (A)(B)(C)(D) |
| 5 | 坏题（cases/pmatrix 不配对、$ 不配对、公式外裸 &） | S3 体检发现，S4 自动排除 |
| 6 | 题干/选项含 `& # % _ { } ~ ^` 等 LaTeX 特殊字符 | 正文段自动转义 |
| 7 | 题号为 Markdown 加粗 `**1.**`（非 `1.`） | NUM_RE 兼容 `**N.**` / `(N)` / `N.` 三种格式 |
| 8 | 选项/子问行以全角空格 `\u3000` 缩进 | 正则用 `[\s\u3000]*` 匹配行首 |
| 9 | 正则双重转义破坏分组（`\\(` 多一层反斜杠） | 字符类匹配括号：`[（(]...（x）[)）]` 或仔细校验捕获组编号 |
| 10 | 源数据版本错位（同章节两版题号/内容不同） | 以用户权威源重建该章节，勿按题号直接套选项 |
| 11 | 选题卷中混入无选项选择题 | S3.5 扫描 + `content_bad.json` 排除清单 |

## 7. 故障排查

| 现象 | 原因 | 处理 |
|---|---|---|
| `Misplaced alignment tab character &` | 题库有公式外裸 `&`（坏题） | S3 体检定位，从 select 剔除或修数据 |
| `Missing character ... U+2460 (①)` | 带圈数字 | 已自动替换为 (1)…；若仍出现说明题在公式内，替换该题数据 |
| `fontspec error: font not found` | fandol 未装 | `sudo tlmgr install fandol` 或重装 `texlive-lang-chinese` |
| `xelatex: command not found` | TeX Live 未装 | 见 §2.3 |
| 编译输出 `No pages of output` + `!` | .tex 有语法错误 | 看日志尾部具体行；多为坏题，S4 加 `--exclude` 或修数据 |
| 答题区显示细长竖条 | 旧版 `\fbox+\parbox` 塌缩 | 使用本 skill 内置 `\framebox[\textwidth]{\rule{0pt}{H}}`（现已改纯留白，无此问题） |
| 题号索引缺失 | select 的 `source` 格式不对 | 检查 §3.4 的 source 格式约定 |
| 选择题/填空题「题目缺条件」（只有引语、无命题列表 ①②③④） | `build_exam_tex.py` 旧版仅给解答题渲染 `parts` | 已修复：现对所有题型通用渲染 `parts`，见 §8 8.7 |

## 8. 跨平台 / 跨 Agent 移植清单

迁到新机器或新 Agent 平台时：

1. **复制**：`scripts/` 6 个脚本（+ 可选 `_verify_scan.py`/`pdf_bank_parser.py`）+
   `question_bank.json`（或 `source/*.md`）+ `content_bad.json`（排除清单）
2. **装环境**：Python ≥ 3.9 + TeX Live（见 §2），跑 §4 校验三条命令
3. **自检**（可选，约 1 分钟）：
   ```bash
   python3 scripts/bank_health.py question_bank.json        # 期望 坏题数 ≤ 3
   python3 scripts/pick_from_bank.py question_bank.json --seed 1 -o /tmp/_t.json
   python3 scripts/build_exam_tex.py --select /tmp/_t.json --bank question_bank.json -o /tmp/_t.tex
   ```
   无报错且生成 `/tmp/_t.pdf` 即移植成功
4. **触发方式**：任意 Agent 读到本文件 frontmatter 的 `description` 即可在用户说"组卷/出卷/模拟卷"时按 §5 执行

## 9. 输出规范（与用户约定一致）

- 试卷 PDF：A4、题目留白、**无答案**
- 题号索引：`（高数·第一章·综合·选择3）` 灰色小字，紧跟题号
- 同时交付 `.tex` 源文件（用户可二次编辑）
- 卷与卷不重复：每次抽题带上 `--exclude` 前几卷的 select 清单

---

## 附录：脚本源码（完整）

> 以下 6 个脚本为 skill 的完整实现，逐字保存为 `scripts/` 下对应文件名。
> 版权与用法见各脚本 docstring。脚本间依赖：`pick_from_bank.py` import `bank_health.py`。

### 附录 A：parse_question_bank.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_question_bank.py — 把「880 提取版」Markdown 解析为标准题库 JSON

输入格式（模板见 question_template.md）：
    ### 一、基础题 / ### 二、综合题 / ### 三、拓展题      -> block
    #### （一）选择题 / （二）填空题 / （三）解答题        -> qtype
    1.  题干...                                          -> 题号 + 题干
        A. ... B. ... C. ... D. ...                      -> 选项（同行或分行）
        (I) ... / ① ...                                   -> 子问 parts

用法:
  python parse_question_bank.py <input.md> -o bank/ch1.json [--chapter 1] [--book 高数篇]
  python parse_question_bank.py <input.md> -o bank/ch1.json --merge pos.json
"""
import argparse
import json
import os
import re

BLOCK_RE = re.compile(r"^#{1,4}\s*(一、基础题|二、综合题|三、拓展题|基础题|综合题|拓展题)")
QTYPE_RE = re.compile(
    r"^#{0,4}\s*\*{0,2}\s*"
    r"(?:[（(](一|二|三)、?[)）]|[一二三]、|\d+[.、．])?\s*"
    r"(选择题|填空题|解答题)\s*\*{0,2}")
NUM_RE = re.compile(r"^\s*(?:\*\*(\d+)[.、．]\*\*\s*|\((\d+)\)\s*|(\d+)[.、．]\s*)?(.*)$")
OPT_RE = re.compile(r"^[\s\u3000]*([A-D])[.、．]\s*(.*)$")
SUB_RE = re.compile(r"^[\s\u3000]*([（(]\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\s*[)）]|[①②③④⑤⑥⑦⑧⑨⑩])\s*(.*)$")

CN_QTYPE = {"选择题": "choice", "填空题": "blank", "解答题": "solve"}
QTYPE_CN = {"choice": "一、选择", "blank": "二、填空", "solve": "三、解答"}


def split_options(text):
    """同一行多个选项 A. .. B. .. C. .. D. .. 拆开"""
    parts = re.split(r"(?=[A-D][.、．])", text)
    out = []
    for p in parts:
        m = re.match(r"^([A-D])[.、．]\s*(.*)$", p.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def parse_md(path, chapter, book):
    cur_block, cur_qtype, cur = None, None, None
    seen_types = set()  # 用于缺「综合题」标题时的自动切块
    questions = []

    def close():
        nonlocal cur
        if cur is not None:
            q = cur["q"]
            q["stem"] = cur["stem"].strip()
            if cur["parts"]:
                q["parts"] = cur["parts"]
            questions.append(q)
            cur = None

    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stripped = line.strip()
        # 分隔线
        if stripped == "---" or re.match(r"^[-=]{3,}$", stripped):
            continue
        # 块标题
        m = BLOCK_RE.match(line)
        if m:
            close()
            t = m.group(1)
            cur_block = {"一、基础题": "基础题", "二、综合题": "综合题", "三、拓展题": "拓展题"}.get(t, t)
            cur_qtype = None
            seen_types = set()
            continue
        # 题型标题
        m = QTYPE_RE.match(line)
        if m:
            close()
            qt = CN_QTYPE.get(m.group(2))
            if cur_block == "基础题" and qt in seen_types:
                cur_block = "综合题"
                seen_types = set()
            seen_types.add(qt)
            cur_qtype = qt
            continue
        # 题号行（支持 **N.** 、(N)、N. 三种格式）
        m = NUM_RE.match(line)
        if m and (m.group(1) or m.group(2) or m.group(3)):
            close()
            num = int(m.group(1) or m.group(2) or m.group(3))
            q = {"book": book, "chapter": chapter, "block": cur_block,
                 "qtype": cur_qtype, "num": num,
                 "qtype_cn": QTYPE_CN.get(cur_qtype),
                 "stem": "", "options": {}, "parts": None,
                 "answer": None, "tags": [], "note": ""}
            cur = {"q": q, "stem": (m.group(4) or "").strip(), "parts": []}
            continue
        if cur is None:
            # 无题号则自动编号（如拓展题直接跟题干）
            if cur_qtype and stripped and not stripped.startswith(("#", "*", "-", ">")):
                nums = [q["num"] for q in questions
                        if q["block"] == cur_block and q["qtype"] == cur_qtype]
                num = (max(nums) + 1) if nums else 1
                q = {"book": book, "chapter": chapter, "block": cur_block,
                     "qtype": cur_qtype, "num": num,
                     "qtype_cn": QTYPE_CN.get(cur_qtype),
                     "stem": "", "options": {}, "parts": None,
                     "answer": None, "tags": [], "note": ""}
                cur = {"q": q, "stem": stripped, "parts": []}
            continue
        # 选项
        opt_pairs = split_options(line)
        if opt_pairs:
            for k, v in opt_pairs:
                if k not in cur["q"]["options"]:
                    cur["q"]["options"][k] = v
            continue
        # 子问
        m = SUB_RE.match(line)
        if m:
            cur["parts"].append({"tag": m.group(1), "text": m.group(2)})
            continue
        # 其他：续接题干（题干多行）或续接最后一个 part
        if cur["parts"]:
            cur["parts"][-1]["text"] += " " + stripped
        else:
            cur["stem"] += " " + stripped
    close()
    return questions


def merge_pos(questions, pos_path):
    """把 pos.json 的位置信息（page/y0）关联进题库（可选）"""
    pos = json.load(open(pos_path, encoding="utf-8"))
    idx = {}
    for q in pos.get("questions", []):
        key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
        idx.setdefault(key, []).append(q)
    for q in questions:
        key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
        locs = idx.get(key)
        q["loc"] = [{"page": l["page"], "y0": l["y0"]} for l in locs] if locs else []
    return questions


def main():
    ap = argparse.ArgumentParser(description="解析 880 提取版 Markdown 为题库 JSON")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--chapter", type=int, default=None)
    ap.add_argument("--book", default="高数篇")
    ap.add_argument("--merge", default=None, help="pos.json 路径，关联位置信息")
    args = ap.parse_args()

    chapter = args.chapter
    if chapter is None:
        m = re.search(r"第([一二三四五六七八九十]+)章", os.path.basename(args.input))
        if m:
            cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                  "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
            chapter = cn.get(m.group(1))
    if chapter is None:
        ap.error("无法从文件名推断章节，请用 --chapter 指定")

    questions = parse_md(args.input, chapter, args.book)
    if args.merge:
        questions = merge_pos(questions, args.merge)

    out = {"source": os.path.basename(args.input),
           "book": args.book, "chapter": chapter,
           "questions": questions}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    from collections import Counter
    c = Counter((q["block"], q["qtype"]) for q in questions)
    print(f"共 {len(questions)} 题")
    for k in sorted(c):
        print(f"  {k[0]} {k[1]}: {c[k]}")


if __name__ == "__main__":
    main()
```

### 附录 B：merge_banks.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_banks.py — 合并多个章节题库 JSON 为一个 question_bank.json

用法:
  python merge_banks.py bank/ch1.json bank/ch2.json ... -o question_bank.json
  python merge_banks.py bank/ -o question_bank.json   # 目录下所有 JSON
"""
import argparse
import glob
import json
import os


def main():
    ap = argparse.ArgumentParser(description="合并章节题库")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            files += sorted(glob.glob(os.path.join(inp, "*.json")))
        else:
            files.append(inp)

    out_base = os.path.abspath(args.output)
    base_qs, base_src, rest = [], [], []
    for f in files:
        if os.path.abspath(f) == out_base:
            # 输出文件自身作为基线（增量合并场景）
            try:
                b0 = json.load(open(f, encoding="utf-8"))
                base_qs = b0.get("questions", [])
                base_src = b0.get("source", [])
                print(f"[merge] 基线: {os.path.basename(f)} ({len(base_qs)} 题)")
            except Exception as e:
                print(f"[warn] 读取基线失败: {e}")
        else:
            rest.append(f)
    if not rest and not base_qs:
        ap.error("没有可合并的输入文件")

    merged = {"source": list(base_src), "questions": list(base_qs)}
    seen = set((q["book"], q["chapter"], q["block"], q["qtype"], q["num"]) for q in base_qs)
    for f in rest:
        b = json.load(open(f, encoding="utf-8"))
        for q in b.get("questions", []):
            key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
            if key in seen:
                print(f"[skip] 重复 {key}")
                continue
            seen.add(key)
            merged["questions"].append(q)
        if b.get("source"):
            src = b["source"] if isinstance(b["source"], list) else [b["source"]]
            merged["source"].extend(src)

    merged["questions"].sort(key=lambda q: (q["book"], q["chapter"],
                                            {"基础题": 0, "综合题": 1, "拓展题": 2}[q["block"]],
                                            {"choice": 0, "blank": 1, "solve": 2}[q["qtype"]],
                                            q["num"]))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print(f"[merge] {len(merged['questions'])} 题 -> {args.output}")


if __name__ == "__main__":
    main()
```

### 附录 C：export_bank.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
export_bank.py — 把 question_bank.json 导出为「人读」Markdown
每章一个文件，开头带「本章题号索引」：块 → 题型 → 题号（无页码）。

用法:
  python export_bank.py question_bank.json -o bank_md/
"""
import argparse
import json
import os

CN_QT = {"choice": "选择题", "blank": "填空题", "solve": "解答题"}
CN_QT_SHORT = {"choice": "选择", "blank": "填空", "solve": "解答"}
BLOCK_ORDER = ["基础题", "综合题", "拓展题"]
QTYPE_ORDER = ["choice", "blank", "solve"]


def chapter_index_line(chapter_qs):
    lines = ["## 本章题号索引", ""]
    for blk in BLOCK_ORDER:
        blk_qs = [q for q in chapter_qs if q["block"] == blk]
        if not blk_qs:
            continue
        parts = []
        for qt in QTYPE_ORDER:
            nums = sorted(q["num"] for q in blk_qs if q["qtype"] == qt)
            if nums:
                parts.append(f"{CN_QT_SHORT[qt]} " + "、".join(str(n) for n in nums))
        if parts:
            lines.append(f"- **{blk}**：{' ；'.join(parts)}")
    return "\n".join(lines)


def render_question(q):
    lines = [f"**{q['num']}.** {q['stem'].strip()}"]
    if q.get("options"):
        opts = "　".join(f"{k}. {v}" for k, v in sorted(q["options"].items()))
        lines.append(f"　　{opts}")
    if q.get("parts"):
        for p in q["parts"]:
            lines.append(f"　　{p['tag']} {p['text'].strip()}")
    if q.get("answer"):
        lines.append(f"　　**答案**：{q['answer']}")
    if q.get("tags"):
        lines.append(f"　　_考点：{'、'.join(q['tags'])}_")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="导出可读题库 Markdown")
    ap.add_argument("input", help="question_bank.json")
    ap.add_argument("-o", "--output", default="bank_md")
    args = ap.parse_args()

    bank = json.load(open(args.input, encoding="utf-8"))
    qs = bank["questions"]
    os.makedirs(args.output, exist_ok=True)

    from collections import OrderedDict
    books = OrderedDict()
    for q in qs:
        books.setdefault(q["book"], {}).setdefault(q["chapter"], []).append(q)

    index = []
    for book, chapters in books.items():
        for ch in sorted(chapters):
            chapter_qs = chapters[ch]
            fname = f"{book}_{ch}.md"
            out = [f"# {book} 第{ch}章", "", chapter_index_line(chapter_qs), ""]
            for blk in BLOCK_ORDER:
                blk_qs = [q for q in chapter_qs if q["block"] == blk]
                if not blk_qs:
                    continue
                out.append(f"## {blk}")
                out.append("")
                for qt in QTYPE_ORDER:
                    qt_qs = [q for q in blk_qs if q["qtype"] == qt]
                    if not qt_qs:
                        continue
                    out.append(f"### {CN_QT[qt]}")
                    out.append("")
                    for q in qt_qs:
                        out.append(render_question(q))
                        out.append("")
            with open(os.path.join(args.output, fname), "w", encoding="utf-8") as f:
                f.write("\n".join(out))
            index.append((book, ch, len(chapter_qs), fname))

    idx_lines = ["# 题库索引", ""]
    for book, ch, n, fname in index:
        ch_qs = books[book][ch]
        idx_part = chapter_index_line(ch_qs).replace("## 本章题号索引", "").strip()
        idx_lines.append(f"## {book} 第{ch}章（{n} 题） — [{fname}]({fname})")
        idx_lines.append("")
        idx_lines.append(idx_part)
        idx_lines.append("")
    with open(os.path.join(args.output, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(idx_lines))

    print(f"已导出 {len(index)} 个章节文件 -> {args.output}/")
    for book, ch, n, fname in index:
        print(f"  {book} 第{ch}章: {n} 题 -> {fname}")


if __name__ == "__main__":
    main()
```

### 附录 D：bank_health.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""bank_health.py — 题库 LaTeX 语法健康检查，供抽题/组卷复用。

返回问题列表；空列表表示健康。坏题应被抽题脚本排除。
"""
import json
import re

MATH_SEG = re.compile(r'\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\]', re.S)
ENVS = ['cases', 'pmatrix', 'vmatrix', 'bmatrix', 'array', 'aligned', 'matrix', 'dcases']


def check_text(t):
    issues = []
    st = t.get('stem') or ''
    for env in ENVS:
        if st.count(r'\begin{' + env + '}') != st.count(r'\end{' + env + '}'):
            issues.append(f'{env} 不配对')
    if st.count('$') % 2 != 0:
        issues.append('$ 不配对')
    stripped = MATH_SEG.sub('', st)
    if '&' in stripped:
        issues.append('公式外裸 &')
    if r'\begin' in stripped or r'\end' in stripped:
        issues.append('公式外裸 begin/end')
    for opt in (t.get('options') or {}).values():
        if str(opt).count('$') % 2 != 0:
            issues.append('选项 $ 不配对')
            break
    return issues


def is_bad(t):
    return bool(check_text(t))


def scan(bank):
    bad = []
    for q in bank:
        iss = check_text(q)
        if iss:
            bad.append((q['book'], q['chapter'], q['block'], q['qtype'], q['num'], iss))
    return bad


if __name__ == '__main__':
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else 'question_bank.json'
    bank = json.load(open(path, encoding='utf-8'))
    if isinstance(bank, dict):
        bank = bank['questions']
    bad = scan(bank)
    print(f'总题数: {len(bank)} | 坏题数: {len(bad)}')
    for b in bad:
        print(' ', b)
```

### 附录 E：pick_from_bank.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pick_from_bank.py — 从题库 JSON 按考纲 profile 抽题，生成 selectN.json

用法:
  python pick_from_bank.py question_bank.json -o select.json
  python pick_from_bank.py question_bank.json --seed 42 -o select.json
  python pick_from_bank.py question_bank.json --exclude select1.json --exclude select2.json -o select3.json

特性:
  - 自动排除 LaTeX 语法坏题（复用 bank_health.is_bad）
  - 自动排除 --exclude 指定清单中已用过的题（避免跨卷重复）
  - 固定 --seed 可复现同一套卷子
  - 默认只在「综合题」块抽题（可 --block 调整）
"""
import argparse
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bank_health import is_bad

CN_STR = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
          '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
CN_NUM = {v: k for k, v in CN_STR.items()}
QT_CN = {'choice': '选择', 'blank': '填空', 'solve': '解答'}
QTYPE_CN = {'choice': '一、选择', 'blank': '二、填空', 'solve': '三、解答'}
QTYPE_CN_FULL = {'choice': '一、选择题', 'blank': '二、填空题', 'solve': '三、解答题'}

PROFILES = {
    "数二标准": {
        "title": "数学（二）模拟试卷",
        "score_total": 150, "time": 180,
        # 章 -> 题数（选择 10 + 填空 6 + 解答 6 = 22 题）
        # 线代覆盖 8/10/11/12 章（二次型 12 章已入库可用）
        "choice": {1: 1, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 8: 1, 11: 1, 12: 1},
        "blank":  {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 10: 1},
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 12: 1},
    },
    "高数全": {
        "title": "数学（二）高数专项模拟",
        "score_total": 100, "time": 120,
        "choice": {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 2},   # 共 10
        "blank":  {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1},   # 共 6
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},         # 共 5
    },
}

SEC_DESC = {
    'choice': '在每小题给出的四个选项中，只有一项符合题目要求。',
    'blank': '请将答案写在题中横线上。',
    'solve': '解答应写出文字说明、证明过程或演算步骤。',
}
SEC_SCORE = {'choice': '本大题共 10 小题，每小题 5 分，共 50 分。',
             'blank': '本大题共 6 小题，每小题 5 分，共 30 分。',
             'solve': '本大题共 6 小题，共 70 分。'}


def parse_source(src):
    """'高数篇·第一章·综合题·选择(3)' -> (book, chapter, block, qtype, num)"""
    m = re.match(r'(.+?)·第(.+?)章·(.+?)·(选择|填空|解答)\((\d+)\)', src)
    if not m:
        return None
    book, ch, block, qt, num = m.groups()
    return book, CN_STR[ch], block, {'选择': 'choice', '填空': 'blank', '解答': 'solve'}[qt], int(num)


def build_source(book, ch, block, qt, num):
    return f"{book}·第{CN_NUM[ch]}章·{block}·{QT_CN[qt]}({num})"


def load_bank(path):
    data = json.load(open(path, encoding='utf-8'))
    return data['questions'] if isinstance(data, dict) else data


def collect_excluded(exclude_paths):
    """读若干 selectN.json，收集已用题 (book,chapter,block,qtype,num) 集合"""
    used = set()
    for p in exclude_paths or []:
        sel = json.load(open(p, encoding='utf-8'))
        for q in sel['questions']:
            key = parse_source(q['source'])
            if key:
                used.add(key)
    return used


def main():
    ap = argparse.ArgumentParser(description='按考纲 profile 从题库抽题')
    ap.add_argument('bank', help='question_bank.json 路径')
    ap.add_argument('--profile', '-p', default='数二标准', choices=list(PROFILES.keys()))
    ap.add_argument('--seed', type=int, default=None, help='随机种子，固定后结果可复现')
    ap.add_argument('--exclude', action='append', default=[], help='排除清单（selectN.json），可多次传入')
    ap.add_argument('--block', default='综合题', help='抽题块：综合题 / 基础题 / 拓展题')
    ap.add_argument('--skip-bad', action='store_true', default=True, help='排除 LaTeX 语法坏题（默认开）')
    ap.add_argument('--no-skip-bad', dest='skip_bad', action='store_false')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--title', default=None, help='试卷标题，默认用 profile.title')
    ap.add_argument('--no', type=int, default=1, help='卷号（标题里显示（一）（二）…）')
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    bank = load_bank(args.bank)
    profile = PROFILES[args.profile]
    used = collect_excluded(args.exclude)

    # 候选池
    pool = {}
    for q in bank:
        if q['block'] != args.block:
            continue
        if args.skip_bad and is_bad(q):
            continue
        key = (q['book'], q['chapter'], q['block'], q['qtype'], q['num'])
        if key in used:
            continue
        pool.setdefault((q['chapter'], q['qtype']), []).append(key)

    # 抽题
    picked, missing = [], []
    for kind in ('choice', 'blank', 'solve'):
        cfg = profile.get(kind)
        if not cfg:
            continue
        for ch, n in sorted(cfg.items()):
            if n == 0:
                continue
            c = list(pool.get((ch, kind), []))
            random.shuffle(c)
            got = c[:n]
            if len(got) < n:
                missing.append((ch, kind, n, len(got)))
            picked.extend(got)

    if missing:
        print('[warn] 部分章节题数不足：', missing, file=sys.stderr)
    if not picked:
        print('[error] 未抽到任何题，请检查题库/排除清单/块', file=sys.stderr)
        sys.exit(1)

    # 组装 select.json
    cn_no = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    title = args.title or profile['title']
    qs, i = [], 1
    for kind in ('choice', 'blank', 'solve'):
        for key in sorted(picked, key=lambda k: (k[3], k[1], k[4])):
            if key[3] != kind:
                continue
            qs.append({'id': i, 'kind': kind,
                       'score': 12 if kind == 'solve' else 5,
                       'chapter': key[1], 'block': key[2],
                       'qtype': QTYPE_CN[kind], 'num': key[4],
                       'source': build_source(*key), '考点': key[2]})
            i += 1

    sel = {
        'header': {
            'exam': '全国硕士研究生招生考试',
            'title': f'{title}（{cn_no[args.no]}）',
            'sub': '——精选自 880 题（A4 留白版）',
            'score_total': profile.get('score_total', 150),
            'time': profile.get('time', 180),
            'notes': [
                '一、考生应在答题卡指定位置上用黑色字迹的钢笔或签字笔填写姓名、准考证号和得分。',
                '二、答题时，答案须用黑色字迹的钢笔或签字笔写在答题卡上，写在试卷上或草稿纸上的答案无效。',
                f'三、本试卷共 {len(qs)} 题，满分 {profile.get("score_total", 150)} 分，考试时间 {profile.get("time", 180)} 分钟。',
            ],
        },
        'sections': {
            'choice': {'name': QTYPE_CN_FULL['choice'], 'desc': SEC_DESC['choice'] + SEC_SCORE['choice']},
            'blank':  {'name': QTYPE_CN_FULL['blank'],  'desc': SEC_DESC['blank'] + SEC_SCORE['blank']},
            'solve':  {'name': QTYPE_CN_FULL['solve'],  'desc': SEC_DESC['solve'] + SEC_SCORE['solve']},
        },
        'questions': qs,
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(sel, f, ensure_ascii=False, indent=1)
    print(f'[pick] {len(qs)} 题 -> {args.output}')
    for kind in ('choice', 'blank', 'solve'):
        sub = [q for q in qs if q['kind'] == kind]
        if sub:
            print(f'  {kind}: {len(sub)} 题 -> ' + '; '.join(q['source'].replace(args.block + '·', '') for q in sub))


if __name__ == '__main__':
    main()
```

### 附录 F：build_exam_tex.py

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_exam_tex.py — 从 question_bank.json 按 select.json 清单直接以 LaTeX 组卷

用法:
  python build_exam_tex.py --select select.json --bank question_bank.json -o 试卷.tex

输出:
  试卷.tex（ctexart，xelatex 编译）+ 试卷.pdf（若 xelatex 可用；--no-pdf 只出 .tex）
"""
import argparse
import json
import re
import subprocess
import sys

CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
      '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
QT = {'选择': 'choice', '填空': 'blank', '解答': 'solve'}
SEC_SCORE = {'choice': '每小题 5 分，共 50 分',
             'blank': '每小题 5 分，共 30 分',
             'solve': '共 70 分'}
SEC_DESC = {
    'choice': '在每小题给出的四个选项中，只有一项符合题目要求。',
    'blank': '请将答案写在题中横线上。',
    'solve': '解答应写出文字说明、证明过程或演算步骤。',
}

MATH_RE = re.compile(r'(\$\$.*?\$\$|\$[^$]*\$|\\\(.*?\\\)|\\\[.*?\\\])', re.S)


def _blank_line(m):
    return r'\underline{\hspace{2.5cm}}'


def tex_escape_text(s):
    """只转义公式段（$...$ / $$...$$ / \\(...\\) / \\[...\\]）之外的文本，公式原样保留。"""
    parts = MATH_RE.split(s)
    out = []
    for p in parts:
        if not p:
            continue
        m = MATH_RE.fullmatch(p)
        if m:  # 公式段：原样保留，仅把 2+ 连续下划线（含 \_）替换为填空横线
            p = re.sub(r'(?:_|\\_){2,}', _blank_line, p)
            out.append(p)
        else:
            # 填空横线（转义前占位，避免 \ 被二次转义）→ 最后还原为真正的横线
            p = re.sub(r'(?:_|\\_){3,}', '\x00', p)
            # 孤立的 $ 兜底转义（防止裸 $ 破坏编译）
            p = re.sub(r'(?<!\$)\$(?!\$)', r'\\$', p)
            p = p.replace('\\', r'\textbackslash{}')
            p = p.replace('&', r'\&').replace('#', r'\#').replace('%', r'\%')
            p = p.replace('{', r'\{').replace('}', r'\}')
            p = p.replace('~', r'\textasciitilde{}').replace('^', r'\textasciicircum{}')
            p = p.replace('_', r'\_')
            # 带圈数字 → (n)（避免 CJK 字体缺失）
            for i, ch in enumerate('①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳', 1):
                p = p.replace(ch, f'({i})')
            p = p.replace('\x00', r'\underline{\hspace{2.5cm}}')
            out.append(p)
    return ''.join(out)


def split_inline_options(stem):
    """options 缺失时，从题干尾部提取 'A. xxx; B. xxx; C. xxx; D. xxx' 式选项。

    返回 (clean_stem, options_dict 或 None)
    """
    m = re.search(r'\s*[（(]?\s*([A-D])\s*[.、．]\s*', stem)
    if not m:
        return stem, None
    head = stem[:m.start()].rstrip()
    tail = stem[m.start():]
    opts = {}
    for seg in re.split(r'[;；]|\s+(?=[A-D]\s*[.、．])', tail):
        mm = re.match(r'\s*[（(]?\s*([A-D])\s*[.、．]\s*(.*)$', seg, re.S)
        if mm:
            opts[mm.group(1)] = mm.group(2).strip()
    if len(opts) >= 2:
        return head, opts
    return stem, None


def build_tex(sel, bank, out_path):
    idx = {}
    for q in bank['questions']:
        idx[(q['book'], q['chapter'], q['block'], q['qtype'], q['num'])] = q

    picked, warn = [], []
    for q in sel['questions']:
        m = re.match(r'(.+?)·第(.+?)章·(.+?)·(选择|填空|解答)\((\d+)\)', q['source'])
        if not m:
            warn.append(f"source 无法解析: {q['source']}")
            continue
        book, ch, block, qt, num = m.groups()
        key = (book, CN[ch], block, QT[qt], int(num))
        if key not in idx:
            warn.append(f"题库中缺失: {q['source']}")
            continue
        picked.append((q, idx[key]))
    if not picked:
        print('[错误] 没有可用的题', file=sys.stderr)
        sys.exit(1)

    h = sel['header']
    groups = {'choice': [], 'blank': [], 'solve': []}
    for q, t in picked:
        groups[q['kind']].append((q, t))

    lines = []
    lines.append(r'\documentclass[UTF8,fontset=fandol,a4paper,11pt]{ctexart}')
    lines.append(r'\usepackage{amsmath,amssymb}')
    lines.append(r'\usepackage{geometry}')
    lines.append(r'\geometry{top=2.2cm,bottom=2.2cm,left=2.0cm,right=2.0cm}')
    lines.append(r'\usepackage{enumitem}')
    lines.append(r'\usepackage{fancyhdr}')
    lines.append(r'\pagestyle{fancy}\fancyhf{}')
    lines.append(r'\fancyhead[C]{\small ' + h['title'] + '}')
    lines.append(r'\fancyfoot[C]{\small 第 \thepage\ 页}')
    lines.append(r'\usepackage{xcolor}')
    lines.append(r'\begin{document}')
    lines.append('')
    # 标题区
    lines.append(r'\begin{center}')
    lines.append(r'{\Large\bfseries ' + h.get('exam', '全国硕士研究生招生考试') + r'}\\[4pt]')
    lines.append(r'{\LARGE\bfseries ' + h['title'] + r'}\\[4pt]')
    lines.append(r'{\normalsize ' + h.get('sub', '') + r'}\\[4pt]')
    lines.append(r'{\normalsize（满分 ' + str(h['score_total']) + ' 分，考试时间 ' + str(h['time']) + ' 分钟）}')
    lines.append(r'\end{center}')
    lines.append(r'\vspace{2pt}')
    # 注意事项
    lines.append(r'\noindent\rule{\textwidth}{0.6pt}')
    for i, n in enumerate(h.get('notes', []), 1):
        pre = '注意事项：' if i == 1 else ''
        lines.append(r'\noindent{\small ' + pre + tex_escape_text(n) + r'}\\')
    lines.append(r'\noindent\rule{\textwidth}{0.6pt}')
    lines.append(r'\vspace{6pt}')
    lines.append('')

    sec_names = {'choice': '一、选择题', 'blank': '二、填空题', 'solve': '三、解答题'}
    for kind in ['choice', 'blank', 'solve']:
        lines.append(r'\noindent{\bfseries ' + sec_names[kind] + '（' + SEC_SCORE[kind] + '）}')
        lines.append(r'\begin{quote}\small ' + SEC_DESC[kind] + r'\end{quote}')
        lines.append(r'\begin{enumerate}[label=\textbf{\arabic*.},leftmargin=2.2em,itemsep=10pt]')
        for q, t in groups[kind]:
            stem = tex_escape_text(t['stem'])
            opts = t.get('options') or {}
            if kind == 'choice' and not opts:
                # 选项被合并进题干的题：从尾部拆分
                clean_stem, split_opts = split_inline_options(t['stem'])
                if split_opts:
                    stem = tex_escape_text(clean_stem)
                    opts = split_opts
            # 题号后索引标注：高数·第一章·综合·选择3
            m = re.match(r'(.+?)·第(.+?)章·(.+?)·(选择|填空|解答)\((\d+)\)', q['source'])
            idx_tag = ''
            if m:
                book, ch, block, qt, num = m.groups()
                book_short = '高数' if '高数' in book else '线代'
                block_short = block.replace('题', '')
                idx_tag = f"（{book_short}·{ch}·{block_short}·{qt}{num}）"
            lines.append(r'\item ' + (r'{\small\color{gray} ' + idx_tag + r'}' if idx_tag else '') + stem)
            if kind == 'choice' and opts:
                labels = ['A', 'B', 'C', 'D']
                opt_lines = []
                for j in range(0, len(labels), 2):
                    pair = []
                    for lb in labels[j:j + 2]:
                        if lb in opts:
                            pair.append(r'(' + lb + r')\; ' + tex_escape_text(opts[lb]))
                    if pair:
                        opt_lines.append(r'\quad ' + r'\hfill '.join(pair) + r'\\')
                lines.append(r'\begin{quote}\small')
                lines.extend(opt_lines)
                lines.append(r'\end{quote}')
            if kind == 'solve':
                # 解答题纯留白（不画框）
                lines.append(r'\par\vspace{4.5cm}')
        lines.append(r'\end{enumerate}')
        lines.append(r'\newpage' if kind != 'solve' else '')
        lines.append('')

    lines.append(r'\end{document}')
    tex = '\n'.join(lines)
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(tex)
    print(f'[build-tex] 共 {len(picked)} 题 -> {out_path}')
    for w in warn:
        print(f'  [warn] {w}')
    return out_path, picked


def compile_pdf(tex_path):
    """xelatex 编译两遍（目录/引用），返回 PDF 路径。"""
    import os
    outdir = os.path.dirname(tex_path) or '.'
    base = os.path.splitext(os.path.basename(tex_path))[0]
    cmd = ['xelatex', '-interaction=nonstopmode', '-halt-on-error',
           '-output-directory=' + outdir, tex_path]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    except FileNotFoundError:
        print('[warn] 未找到 xelatex，跳过 PDF 编译（已生成 .tex 源文件）')
        return None
    pdf = os.path.join(outdir, base + '.pdf')
    if os.path.exists(pdf):
        # 第二遍确保交叉引用正确
        subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        print(f'[compile] -> {pdf}')
        return pdf
    # 失败时输出日志尾部
    tail = [l for l in r.stdout.splitlines() if l.strip()][-40:]
    print('[compile] 失败，日志尾部：')
    print('\n'.join(tail))
    return None


def main():
    ap = argparse.ArgumentParser(description='LaTeX 组卷')
    ap.add_argument('--select', required=True)
    ap.add_argument('--bank', required=True)
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--no-pdf', action='store_true', help='只生成 .tex 不编译')
    args = ap.parse_args()

    sel = json.load(open(args.select, encoding='utf-8'))
    bank = json.load(open(args.bank, encoding='utf-8'))
    tex_path, _ = build_tex(sel, bank, args.output)
    if not args.no_pdf:
        compile_pdf(tex_path)


if __name__ == '__main__':
    main()
```

### 附录 G：pdf_bank_parser.py（可选：解析做题本 PDF 提取文本）

```python
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""解析 880 线代篇做题本 PDF 提取文本 -> 结构化题目清单（供差异分析与补全）"""
import re, json, sys

CH_CN = {'七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
QTYPE_CN = {'选择题': 'choice', '填空题': 'blank', '解答题': 'solve'}
BLOCKS = ('基础题', '综合题', '拓展题')
QTYPES = ('选择题', '填空题', '解答题')


def parse(path):
    lines = open(path, encoding='utf-8').read().split('\n')
    # 正文起点：第一个完全等于 "第七章 行列式" 的行（目录行带页码，不含）
    start = None
    for i, l in enumerate(lines):
        if l.strip() == '第七章 行列式':
            start = i
            break
    if start is None:
        return []
    chapter = block = qtype = None
    qs, cur = [], None

    def close():
        nonlocal cur
        if cur:
            cur['stem'] = re.sub(r'[\s\u3000]+', ' ', cur['stem']).strip()
            qs.append(cur)
            cur = None

    def feed_opts(cur, s):
        """统一处理行首/行内选项标签切分：无标签->追加当前；有标签->按标签归属"""
        tags = list(re.finditer(r'(?:^|\b)([A-D])\.\s*', s))
        if not tags:
            if cur['cur_opt']:
                cur['opts'][cur['cur_opt']] += ' ' + s.strip()
            else:
                cur['stem'] += ' ' + s
            return
        if tags[0].start() > 0 and cur['cur_opt']:
            cur['opts'][cur['cur_opt']] += ' ' + s[:tags[0].start()].strip()
        for i, m in enumerate(tags):
            end = tags[i + 1].start() if i + 1 < len(tags) else len(s)
            cur['opts'].setdefault(m.group(1), '')
            cur['opts'][m.group(1)] += ' ' + s[m.end():end].strip()
            cur['cur_opt'] = m.group(1)

    for i, l in enumerate(lines[start:], start):
        s = l.strip()
        if not s or '公众号' in s or '版 880' in s or ('· 第' in s and '页' in s) or s == '\f':
            continue
        m = re.match(r'^第([一二三四五六七八九十]+)章\s*(.*)$', s)
        if m:
            close()
            chapter = CH_CN[m.group(1)]
            block = qtype = None
            continue
        if s in BLOCKS:
            close()
            block = s
            qtype = None
            continue
        if block == '拓展题' and qtype is None:
            qtype = 'solve'
        m = re.match(r'^[一二三四五六]、(.{3})$', s)
        if m and m.group(1) in QTYPES:
            close()
            qtype = QTYPE_CN[m.group(1)]
            continue
        m = re.match(r'^\((\d+)\)\s*(.*)$', s)
        if m:
            close()
            num = int(m.group(1))
            cur = {'chapter': chapter, 'block': block, 'qtype': qtype,
                   'num': num, 'stem': m.group(2), 'opts': {}, 'cur_opt': None}
            continue
        # 选项/题干续行统一处理（行首/行内 A-D. 标签自动切分）
        if cur is not None:
            feed_opts(cur, s)
            continue
    close()
    return qs


if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else 'source/pdf_线代篇.txt'
    qs = parse(path)
    print(f'共解析 {len(qs)} 题')
    from collections import Counter
    c = Counter((q['chapter'], q['block'], q['qtype']) for q in qs)
    for k in sorted(c):
        print(' ', k, ':', c[k])
    json.dump(qs, open('/tmp/pdf_qs.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
```
