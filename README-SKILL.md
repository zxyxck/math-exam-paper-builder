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
├── select1.json / select2.json   # S4 产物：选题清单
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

**块混合抽题 `--mix`**（模拟真题难度梯度：送分/中等/压轴）：

```bash
python3 scripts/pick_from_bank.py question_bank.json \
    --mix 基础题:4 拓展题:1 --no 4 -o select4.json
```

- `--mix 块:题数` 可传多组；**综合题配额自动 = 总配额 − 其余块**（如 22 题卷 → 综合 18 + 基础 4）
- 基础题（送分）随机分布到各章各题型
- **压轴（卷末最后一道解答题）**：题源 = 高数和线代的**全部解答题池**（429 道，综合/基础/拓展不限，
  不考虑是不是拓展题，只要是解答题就行）——位置固定在卷末，题源用完为止；
  若 `--mix` 传了拓展题配额则压轴优先取解答拓展题（旧语义）
- 各块题目按全局配额随机分布，块配额不足时自动告警
- 不传 `--mix` 时行为不变（全部从 `--block` 指定块抽，默认综合题）

## 4. 脚本部署（移植第一步）

直接复制 `scripts/` 目录即可（文件名与相互 import 关系已就绪）：

```
scripts/
├── parse_question_bank.py   # S1 解析
├── merge_banks.py           # S2 合并
├── export_bank.py           # S7 可选导出
├── bank_health.py           # S3 健康体检（被 pick_from_bank import）
├── pick_from_bank.py        # S4 抽题
├── build_exam_tex.py        # S5/S6 组卷 + 编译
├── batch_papers.py          # 一键批量组卷（自动排除已用题，循环出 N 卷）
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
python3 scripts/pick_from_bank.py question_bank.json --seed 42 --exclude content_bad.json --no 1 -o select1.json

# 卷二（避开卷一已用题）：
python3 scripts/pick_from_bank.py question_bank.json --seed 20260819 \
    --exclude select1.json --no 2 -o select2.json

# 卷三（避开前两卷 + 固定种子可复现）：
python3 scripts/pick_from_bank.py question_bank.json --seed 20260819 \
    --exclude select1.json --exclude select2.json --no 3 -o select3.json
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
| `--mix 块:题数` | 块混合配额，可多次传（如 `--mix 基础题:4 拓展题:1`）；综合题自动 = 总配额 − 其余 |
| `--topic 主题:题数` | 知识点选题，可多次传（如 `--topic 极限与连续:3 特征值与相似:2`）；先抽指定主题题并替换入卷（同章同题型位置），其余按 profile 补齐，总题数不变 |
| `--tags 文件` | 知识点标签文件（默认 bank 同目录 `topic_tags.json`，由 `tag_bank.py` 生成） |

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

### S4.2 一键批量组卷（推荐）

```bash
# 从当前已有卷之后连出 3 套（自动排除所有历史卷 + content_bad.json，跨卷零重复）
python3 scripts/batch_papers.py --papers 3 --profile 数二轮换 --mix 基础题:4

# 只出 .tex 不编译 PDF；指定种子基数（每卷 seed = base + 卷号偏移，可复现）
python3 scripts/batch_papers.py --papers 2 --seed-base 20260901 --no-pdf
```

- 自动识别已有 `select*.json`（`select1.json`、`select2.json`…），从下一卷续出
- 每卷自动携带全部历史卷作 `--exclude`，且本轮新卷自动纳入下一轮排除
- 参数透传：`--profile` / `--mix` / `--block` / `--max-proofs` / `--no-pdf`

### S4.3 知识点选题（--topic）

不想让系统全权选题时，可指定**知识点**及题数，具体抽哪道仍由系统决定：

```bash
# 先打知识点标签（一次性，生成 topic_tags.json，12 个主题）
python3 scripts/tag_bank.py question_bank.json -o topic_tags.json

# 卷子里要有 3 道极限 + 2 道特征值，其余按 profile 自动补齐（总题数不变）
python3 scripts/pick_from_bank.py question_bank.json --profile 数二轮换 --mix 基础题:4 \
    --topic 极限与连续:3 特征值与相似:2 --seed 20260920 --no 1 -o select1.json
```

- 主题清单见 `topic_tags.json`（极限与连续 / 一元微分 / 一元积分 / 多元微分 / 二重积分 / 微分方程 / 行列式 / 矩阵 / 向量组 / 线性方程组 / 特征值与相似 / 二次型），一题可命中多主题
- topic 题自动避开已用/坏题，替换入卷的**同章同题型**题位（无则同题型卷末），不改变 22 题结构与分值
- 主题不存在或题数不足时告警，不影响其余题位；`--tags` 可换标签文件

**纯知识点卷 `--topic-only`**（整张卷只由指定主题组成，不按 profile 补题）：

```bash
# 默认结构 选10+填6+解6，主题间按池容量自然混合（如 一元积分14 + 特征值8）
python3 scripts/pick_from_bank.py question_bank.json --topic-only \
    --topic 一元积分 特征值与相似 --seed 20260930 --no 2 -o select2.json

# 指定主题比例（可再限题型）：
python3 scripts/pick_from_bank.py question_bank.json --topic-only \
    --topic 一元积分:11 特征值与相似:11 --no 3 -o select3.json
```

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

1. **复制**：`scripts/` 全部脚本 + `question_bank.json`（或 `source/*.md`）+ `content_bad.json`（排除清单）
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
