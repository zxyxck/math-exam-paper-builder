# 880 组卷系统移植指南（速查版）

> 完整工作流 / 格式约定 / 故障排查见 **[README-SKILL.md](README-SKILL.md)**，本文件只保留移植要点。

## 一、包内文件清单

| 文件 | 用途 | 必带 |
|---|---|---|
| `scripts/*.py`（9 个） | 组卷流水线（解析~批量组卷 + PDF 解析） | ✅ |
| `question_bank.json` | 题库事实源 | ✅ |
| `content_bad.json` | 排除清单（组卷必须 `--exclude`） | ✅ |
| `source/*.md` | 章节源 MD（重新解析用） | 可选 |
| `exams/*.pdf` | 已出试卷样例 | 可选 |
| ~~`select*.json`~~ | 移植后从零抽题，不继承原主已用题 | 无 |

> 迁移到新 AI 平台时还需携带技能文件 `/skills/math-exam-paper-builder/SKILL.md`。

## 二、目标环境

- Python ≥ 3.9（**仅标准库**，零 pip 依赖）
- TeX Live（出 PDF 必需）：xelatex + ctex + fandol 字体，安装见 README-SKILL §2
- 轻量替代：TinyTeX（~100MB）`wget -qO- https://yihui.org/tinytex/install-bin-unix.sh | sh` + `tlmgr install ctex enumitem fancyhdr`

## 三、移植步骤

```bash
# 1. 校验脚本
python3 scripts/bank_health.py --help >/dev/null 2>&1 && echo "bank_health OK"
python3 scripts/pick_from_bank.py --help >/dev/null 2>&1 && echo "pick OK"
python3 scripts/build_exam_tex.py --help >/dev/null 2>&1 && echo "build OK"

# 2. 校验 TeX 环境
kpsewhich ctexart.cls >/dev/null && echo "TeX OK"

# 3. 自检（约 1 分钟）
python3 scripts/bank_health.py question_bank.json          # 期望: 坏题数 0
python3 scripts/pick_from_bank.py question_bank.json --seed 1 --exclude content_bad.json -o /tmp/_t.json
python3 scripts/build_exam_tex.py --select /tmp/_t.json --bank question_bank.json -o /tmp/_t.tex
# 无报错且生成 /tmp/_t.pdf 即移植成功
```

## 四、日常组卷命令

```bash
# 一键批量出 N 套（推荐）：自动排除历史卷，跨卷零重复
python3 scripts/batch_papers.py --papers 3 --profile 数二轮换 --mix 基础题:4

# 单卷抽题：务必带排除清单
python3 scripts/pick_from_bank.py question_bank.json \
    --profile 数二轮换 --seed 20260819 --mix 基础题:4 \
    --exclude content_bad.json --exclude select1.json --exclude select2.json --no 6 -o select6.json

# 组卷 + 编译 PDF（build_exam_tex.py 自动调 xelatex）
python3 scripts/build_exam_tex.py --select select6.json --bank question_bank.json -o "exams/数二模拟卷(六)_LaTeX.tex"
```

### 重置组卷系统（清空已组卷题目记录）

```bash
rm -f select*.json   # 删除已组卷记录 → 回到未组卷状态（全量可选）
rm -f exams/*        # 可选：同时清空已出试卷
```

> `selectN.json` 是唯一的"已选题"状态载体；题库 / 坏题清单 / 脚本不受影响。

## 五、参数速查

| 参数 | 含义 |
|---|---|
| `--profile` | `数二标准`（默认）/ `数二真题`（高数80%·线代21.3%）/ `高数全` / `数二轮换`（线代 7~12 章轮换） |
| `--mix 块:题数` | 块混合配额，如 `基础题:4`（综合题自动 = 总配额 − 其余；压轴 = 卷末解答题，题源全部解答池） |
| `--seed N` | 固定种子可复现 |
| `--exclude f.json` | 排除已用题（可多次） |
| `--max-proofs N` | 证明题上限（默认 2；0=禁止，负数=不限） |
| `--no-pdf` | 只出 .tex |
| 新增 profile | 编辑 `scripts/pick_from_bank.py` 的 `PROFILES` 字典 |
