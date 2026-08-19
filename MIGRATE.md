# 880 组卷系统移植指南

## 一、包内文件清单

| 文件 | 用途 | 必带 |
|---|---|---|
| `scripts/*.py`（8个） | 组卷流水线（S1解析~S8验证 + PDF解析） | ✅ |
| `question_bank.json` | 题库事实源（930 题，含全部修复） | ✅ |
| `content_bad.json` | 排除清单（1 题，组卷必须 --exclude） | ✅ |
| `verify_report.md` | 完整性验证记录（可追溯修复历史） | 可选 |
| `source/线代篇_第十二章_完整版.md` | 第12章权威源（重建基准） | 可选 |
| `exams/*.pdf` | 已出试卷样例 | 可选 |
| ~~`select*.json`~~ | 已从包中移除——移植后从零抽题，不继承原主的已用题 | 无 |

> 如需完整源 MD（12章）重新解析，另复制 `/workspace/source/` 全部文件。
> 如移植到新 AI 平台，还需携带技能文件 `/skills/math-exam-paper-builder/SKILL.md`（含全部脚本源码+工作流说明）。

## 二、目标环境要求

- Python ≥ 3.9（**仅标准库**，零 pip 依赖）
- TeX Live（出 PDF 必需）：xelatex + ctex + fandol 字体
- （可选）poppler-utils（pdftotext/pdftoppm，PDF 解析/预览用）

### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y python3 texlive-xetex texlive-lang-chinese poppler-utils
```

### macOS（Homebrew）
```bash
brew install python3
brew install --cask mactex-no-gui   # 或 basictex + tlmgr install ctex fandol
```

### Windows
- 安装 Python（勾选 Add to PATH）
- 安装 TeX Live：https://tug.org/texlive/ （scheme-full 或含 collection-langchinese）

## 三、移植步骤

```bash
# 1. 解压
mkdir -p 880exam && tar xzf 880组卷_移植包.tar.gz -C 880exam
cd 880exam

# 2. 校验脚本可运行
python3 scripts/bank_health.py --help >/dev/null 2>&1 && echo "bank_health OK"
python3 scripts/pick_from_bank.py --help >/dev/null 2>&1 && echo "pick OK"
python3 scripts/build_exam_tex.py --help >/dev/null 2>&1 && echo "build OK"

# 3. 校验环境
xelatex --version >/dev/null && kpsewhich ctexart.cls >/dev/null && echo "TeX OK"

# 4. 自检（1 分钟）
python3 scripts/bank_health.py question_bank.json          # 期望: 坏题数 0
python3 scripts/pick_from_bank.py question_bank.json --seed 1 --exclude content_bad.json -o /tmp/_t.json
python3 scripts/build_exam_tex.py --select /tmp/_t.json --bank question_bank.json -o /tmp/_t.tex
# 无报错且生成 /tmp/_t.pdf 即移植成功
```

## 四、日常组卷命令

```bash
# 抽题（新卷）—— 务必带排除清单
python3 scripts/pick_from_bank.py question_bank.json \
    --seed 20260819 --exclude content_bad.json --exclude select.json ... -o select_new.json

# 组卷 + 编译 PDF（自动）
# 注意：build_exam_tex.py 已修复：
#   (1) 解答题自动渲染 parts 子问（(I)(II)...）
#   (2) 填空横线阈值已统一为 ≥2 个 \_（非公式段不再漏转）
python3 scripts/build_exam_tex.py \
    --select select_new.json --bank question_bank.json -o "exams/模拟卷_LaTeX.tex"
```

### 数二真题模式（高数 80% / 线代 21.3%）

```bash
# 使用数二真题 profile，严格对齐考研数二真题的学科占比
python3 scripts/pick_from_bank.py question_bank.json \
    --profile 数二真题 \
    --seed 20260819 --exclude content_bad.json --exclude select1.json --exclude select2.json \
    --max-proofs 2 --no 6 -o select6.json
# 分值：选择 7+3 / 填空 5+1 / 解答 5+1 = 高数 120 分(80%) + 线代 32 分(21.3%)
# --max-proofs 2：同一试卷证明题不超过 2 道（业务规则：考研数二真题约束）
```

### 重置组卷系统（清空已组卷题目记录）

当用户说「重置组卷系统 / 清空已选题」时，删除所有 `selectN.json` 即可清空"已选题限额"，
回到未组卷状态（下一次抽题全量可选、不与历史卷重复）：

```bash
rm -f select*.json        # 删除已组卷题目记录（select1.json ~ selectN.json）
# 如需同时清掉已出试卷：rm -f exams/*
```

> 注意：`selectN.json` 是唯一的已选题状态载体；题库、坏题清单、脚本不受影响。
> 该触发行为亦写入 `README-SKILL.md` frontmatter（`重置组卷系统` 触发词）与 §4.1。

## 五、参数速查

- `--seed N`：固定种子可复现同卷
- `--exclude f.json`：排除已用题（可多次）
- `--block 综合题`：抽题块（默认综合题）
- `--profile`：数二标准（默认） / 数二真题（高数80%线代21.3%） / 高数全（内置）
- `--max-proofs N`：证明题上限（默认 2，对齐考研数二真题约束；0=禁止，负数=不限）
- `--no-pdf`：只出 .tex
- 新增 profile：编辑 `scripts/pick_from_bank.py` 的 `PROFILES` 字典

## 六、故障排查

| 现象 | 处理 |
|---|---|
| `xelatex: command not found` | 装 TeX Live（见第二节） |
| `fontspec error: font not found` | `sudo tlmgr install fandol` |
| PDF 里中文缺失/方块 | 确认用 xelatex 编译（ctexart） |
| 抽题数不足 | 检查 --exclude 是否过多，或题库章节题数 |
| `Misplaced alignment tab` | 题库有坏题，跑 bank_health 定位后从 select 剔除 |
| 解答题题目不全（只有引语无子问） | 已修复：build_exam_tex.py 现在渲染 `parts` 子问 |
| 填空处出现 `\textbackslash{}` 乱码 | 已修复：填空横线阈值已统一为 ≥2 个 `\_` |
| 选择题「题目缺条件」（无命题列表 ①②③④） | build_exam_tex.py 旧版仅给解答题渲染 `parts` | 已修复：现对所有题型通用渲染 `parts`；见 verify_report 8.7 |
| 第9题（线代10·综合·选择9）选项 D 公式损坏 | 源题库数据损坏（非脚本问题） | 已修复：按用户源题恢复选项 D 为秩等式；见 verify_report 8.8 |
| 证明题数量超过 2 道 | 用 `--max-proofs 2`（默认）；或编辑 profile 改章节分布避开证明题密集章节 |
| 学科占比偏离（高数<78% 或 >82%） | 切换 `--profile 数二真题`；或调整 PROFILES 中高数/线代章节配额 |
