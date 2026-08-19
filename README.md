# Math Exam Paper Builder（数学组卷）

从「章节 Markdown 题库」到「A4 留白试卷 PDF」的完整组卷流水线。
零依赖（Python 标准库 + TeX Live），跨 Agent 平台 / 跨 AI 可移植。

## 核心链路

```
章节 MD ──S1 解析──▶ 章节 JSON ──S2 合并──▶ question_bank.json（唯一事实源）
                                              │
                                              ├─S3 健康体检（剔除 LaTeX 语法坏题）
                                              ▼
                                        候选池（综合题块）
                                              │
                                              └─S4 抽题（按 profile + 排除已用）──▶ selectN.json
                                                                                        │
                                                                                        ▼
                                        S5 build_exam_tex.py ──▶ 试卷.tex ──S6 xelatex×2──▶ 试卷.pdf
```

## 快速开始

```bash
# 1. 安装依赖（Ubuntu/Debian）
sudo apt-get install -y python3 texlive-xetex texlive-lang-chinese

# 2. 准备题库：source/ 下放章节 Markdown（格式见 README-SKILL.md §3.2），然后：
python3 scripts/parse_question_bank.py "source/高数篇_第一章.md" --book 高数篇 -o bank/ch1.json
python3 scripts/merge_banks.py bank/ -o question_bank.json

# 3. 健康体检
python3 scripts/bank_health.py question_bank.json

# 4. 抽题并组卷（默认 profile「数二标准」，22 题 / 150 分 / 180 分钟）
python3 scripts/pick_from_bank.py question_bank.json --seed 42 --no 1 -o select.json
python3 scripts/build_exam_tex.py --select select.json --bank question_bank.json -o exams/试卷.tex
```

产物：A4 留白 PDF（题目无答案，题号后标注「书·章·块·题型·题号」索引）+ 可二次编辑的 `.tex` 源文件。

## 脚本一览

| 脚本 | 用途 |
|---|---|
| `parse_question_bank.py` | S1：章节 MD → 章节 JSON |
| `merge_banks.py` | S2：章节 JSON → question_bank.json |
| `bank_health.py` | S3：LaTeX 语法健康体检（坏题自动排除） |
| `pick_from_bank.py` | S4：按考纲 profile 抽题（支持跨卷排除、固定种子复现） |
| `build_exam_tex.py` | S5/S6：组卷 .tex + xelatex 编译 PDF |
| `export_bank.py` | S7（可选）：导出人读题库 MD |
| `_verify_scan.py` | S8（可选）：结构/内容/源数据质量扫描 |
| `pdf_bank_parser.py` | 可选：解析做题本 PDF 提取文本（补选项用） |

## 考纲 profile

内置 `数二标准`（22 题/150 分）、`数二真题`（高数 80% + 线代 21.3%）、`高数全`（高数专项），
可在 `pick_from_bank.py` 的 `PROFILES` 中自行追加。

## 文档

- 完整工作流 / 输入格式 / 故障排查：`README-SKILL.md`
- 跨机器 / 跨 Agent 移植：`MIGRATE.md`

## 许可

MIT License。**注意：本仓库不含任何题库内容**（`question_bank.json` / `source/` 已被
.gitignore 排除）——请使用你自己的题目数据。
