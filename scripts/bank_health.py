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
