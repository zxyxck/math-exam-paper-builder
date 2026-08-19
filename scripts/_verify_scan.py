#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""题目完整性验证（完整版）：输出结构、内容、源数据质量三类报告"""
import json, re
from collections import Counter
bank = json.load(open('/workspace/question_bank.json', encoding='utf-8'))['questions']
N = len(bank)
R = []  # 报告行

def rpt(s):
    R.append(s)

# ---------- 结构完整性 ----------
rpt("="*64)
rpt("【一、结构完整性】")
rpt("="*64)
# 1. 必填字段
missing_field = []
for q in bank:
    for f in ('book','chapter','block','qtype','num','stem','qtype_cn'):
        if f not in q or q[f] is None:
            missing_field.append((q, f))
rpt(f"1) 必填字段缺失: {len(missing_field)} 题")
for q, f in missing_field[:10]:
    rpt(f"   {q['book']} 第{q['chapter']}章 {q['block']} {q['qtype']}{q['num']}: 缺 {f}")

# 2. 空题干
empty_stem = [q for q in bank if not str(q['stem']).strip()]
rpt(f"2) 空题干: {len(empty_stem)} 题")
for q in empty_stem[:10]:
    rpt(f"   {q['book']} 第{q['chapter']}章 {q['block']} {q['qtype']}{q['num']}")

# 3. 题号连续性（每 书/章/块/题型 内 1..N）
from collections import defaultdict
seq = defaultdict(list)
for q in bank:
    seq[(q['book'], q['chapter'], q['block'], q['qtype'])].append(q['num'])
seq_issues = []
for k, nums in seq.items():
    for i, n in enumerate(sorted(nums), 1):
        if n != i:
            seq_issues.append((k, i, n))
            break
rpt(f"3) 题号不连续(起始缺口): {len(seq_issues)} 组")
for k, expect, got in seq_issues[:10]:
    rpt(f"   {k}: 期望 {expect} 实际 {got}")

# 4. 重复 key
dup = []
seen = set()
for q in bank:
    k = (q['book'], q['chapter'], q['block'], q['qtype'], q['num'])
    if k in seen: dup.append(k)
    seen.add(k)
rpt(f"4) 重复题目key: {len(dup)}")

# ---------- 内容完整性 ----------
rpt("")
rpt("="*64)
rpt("【二、内容完整性】")
rpt("="*64)

# 5. 选择题选项
no_opt, less_opt = [], []
for q in bank:
    if q['qtype'] != 'choice': continue
    n = len(q.get('options') or {})
    if n == 0: no_opt.append(q)
    elif n < 4: less_opt.append((q, n))
rpt(f"5) 选择题无选项: {len(no_opt)} | 选项<4个: {len(less_opt)}")
for q in no_opt:
    rpt(f"   [无选项] {q['book']} 第{q['chapter']}章 {q['block']} 选择{q['num']}: {q['stem'][:40]}")
for q, n in less_opt:
    rpt(f"   [仅{n}项] {q['book']} 第{q['chapter']}章 {q['block']} 选择{q['num']}: {q['stem'][:40]}")

# 6. 填空题横线
no_line = []
for q in bank:
    if q['qtype'] != 'blank': continue
    txt = q['stem'] + ''.join((q.get('options') or {}).values())
    if not re.search(r'(?:_|\\_){2,}|underline', txt):
        no_line.append(q)
rpt(f"6) 填空题无横线: {len(no_line)}")
for q in no_line[:10]:
    rpt(f"   {q['book']} 第{q['chapter']}章 {q['block']} 填空{q['num']}: {q['stem'][:40]}")

# 7. 子问
bad_parts = 0
for q in bank:
    if q.get('parts'):
        for p in q['parts']:
            if not p.get('tag') or not str(p.get('text') or '').strip():
                bad_parts += 1
rpt(f"7) 子问缺失tag/text: {bad_parts}")

# ---------- 源数据质量（语法正常但内容可疑） ----------
rpt("")
rpt("="*64)
rpt("【三、源数据质量：语法正常但内容可疑】")
rpt("="*64)

# 8. 真截断：$ 奇数（S3 已查）、明确悬空结尾
def dangling(t):
    issues = []
    if t.count('$') % 2 == 1: issues.append('$奇数')
    if re.search(r'\\begin\{[a-z]+\}\s*$', t): issues.append('begin悬空')
    if re.search(r'\\frac\s*$|\\sqrt\s*$|\\int\s*$', t): issues.append('命令悬空')
    if re.search(r'\$\\[a-zA-Z]+\s*$', t): issues.append('$内命令悬空')
    return issues

dang = []
for q in bank:
    txt = q['stem'] + ''.join((q.get('options') or {}).values())
    iss = dangling(txt)
    if iss: dang.append((q, iss))
rpt(f"8) 真截断/悬空: {len(dang)}")
for q, iss in dang[:15]:
    rpt(f"   {q['book']} 第{q['chapter']}章 {q['block']} {q['qtype']}{q['num']} {iss}: ...{q['stem'][-30:]}")

# 9. 乱码特征
garb = []
for q in bank:
    txt = q['stem']
    if re.search(r'[a-zA-Z]<[0-9]{2}\)', txt): garb.append((q, '数字粘连(如a<02)'))
    if re.search(r'\\u[0-9a-fA-F]{4}', txt): garb.append((q, '未转义unicode'))
    if re.search(r'当 \$0[^<]', txt): garb.append((q, '当$0后缺<'))
rpt(f"9) 疑似乱码: {len(garb)}")
for q, why in garb[:15]:
    rpt(f"   {q['book']} 第{q['chapter']}章 {q['block']} {q['qtype']}{q['num']} [{why}]")

# 10. 选项内容可疑（含题干碎片/串行）
sus_opt = []
for q in bank:
    opts = q.get('options') or {}
    for k, v in opts.items():
        if re.search(r'[（(]?\s*[A-D]\s*[.、．]', v):  # 选项里又含选项标记 = 串行
            sus_opt.append((q, k, v))
rpt(f"10) 选项内嵌选项标记(疑似串行): {len(sus_opt)}")
for q, k, v in sus_opt[:10]:
    rpt(f"    {q['book']} 第{q['chapter']}章 {q['block']} 选择{q['num']} 选项{k}: {v[:40]}")

# ---------- 汇总 ----------
rpt("")
rpt("="*64)
rpt("【汇总】")
rpt("="*64)
rpt(f"总题数: {N}")
rpt(f"  结构: 字段缺失 {len(missing_field)} | 空题干 {len(empty_stem)} | 题号缺口 {len(seq_issues)} | 重复 {len(dup)}")
rpt(f"  内容: 无选项选择 {len(no_opt)} | 选项不足 {len(less_opt)} | 填空无横线 {len(no_line)} | 子问缺失 {bad_parts}")
rpt(f"  质量: 真截断 {len(dang)} | 乱码 {len(garb)} | 选项串行 {len(sus_opt)}")

print('\n'.join(R))
