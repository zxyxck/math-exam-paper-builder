#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
batch_papers.py — 一键批量组卷：循环出 N 卷，自动排除已用题并编译 PDF

用法:
  # 从当前已有卷之后连出 3 套（自动 --exclude 所有历史卷 + content_bad.json）
  python3 scripts/batch_papers.py --papers 3 --profile 数二轮换 --mix 基础题:4

  # 指定起始种子（可复现）：每卷 seed = --seed-base + 卷号偏移
  python3 scripts/batch_papers.py --papers 2 --seed-base 20260901 --no-pdf

特性:
  - 自动识别已有 select*.json（select1.json、select2.json…），从下一卷续出
  - 每卷自动携带全部历史卷作 --exclude（跨卷零重复）
  - 生成 selectN.json + exams/数二模拟卷(N)_LaTeX.tex + .pdf
  - 全部参数透传 pick_from_bank.py / build_exam_tex.py（--profile / --mix / --block / --max-proofs）
"""
import argparse
import glob
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WORKDIR = os.path.dirname(HERE)
PICK = os.path.join(HERE, 'pick_from_bank.py')
BUILD = os.path.join(HERE, 'build_exam_tex.py')
BAD = os.path.join(WORKDIR, 'content_bad.json')

CN_NO = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']


def existing_papers():
    """已有卷号列表：select1.json=1, select2.json=2, ..."""
    nums = []
    for f in glob.glob(os.path.join(WORKDIR, 'select*.json')):
        m = re.match(r'select(\d+)\.json$', os.path.basename(f))
        if m:
            nums.append(int(m.group(1)))
    return sorted(nums)


def run(cmd, label):
    print(f'── {label} ──')
    r = subprocess.run(cmd, cwd=WORKDIR)
    if r.returncode != 0:
        print(f'[error] {label} 失败（exit {r.returncode}）', file=sys.stderr)
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description='一键批量组卷（自动排除已用题）')
    ap.add_argument('--papers', '-n', type=int, required=True, help='本次要出的卷数')
    ap.add_argument('--seed-base', type=int, default=20260901, help='种子基数，第 k 卷 seed = base + k')
    ap.add_argument('--profile', '-p', default='数二轮换')
    ap.add_argument('--mix', nargs='*', default=[], help='块混合配额，透传，如 基础题:4')
    ap.add_argument('--block', default='综合题')
    ap.add_argument('--max-proofs', type=int, default=None)
    ap.add_argument('--no-pdf', action='store_true', help='只生成 .tex，不编译 PDF')
    args = ap.parse_args()

    if args.papers < 1:
        ap.error('--papers 至少为 1')

    start = (existing_papers()[-1] + 1) if existing_papers() else 1
    print(f'[batch] 已有卷: {existing_papers() or "无"} | 本次出卷 {start} ~ {start + args.papers - 1}')

    for i in range(args.papers):
        no = start + i
        sel = f'select{no}.json'
        seed = args.seed_base + (no - 1)

        # 排除清单：content_bad + 全部历史卷
        excludes = []
        if os.path.exists(BAD):
            excludes.append(BAD)
        for n in existing_papers():
            f = f'select{n}.json'
            if os.path.exists(os.path.join(WORKDIR, f)):
                excludes.append(f)

        cmd = [sys.executable, PICK, 'question_bank.json',
               '--profile', args.profile, '--seed', str(seed), '--no', str(no),
               '-o', sel]
        for e in excludes:
            cmd += ['--exclude', e]
        for m in args.mix:
            cmd += ['--mix', m]
        if args.block != '综合题':
            cmd += ['--block', args.block]
        if args.max_proofs is not None:
            cmd += ['--max-proofs', str(args.max_proofs)]
        run(cmd, f'抽题 第{no}卷（seed={seed}）')

        tex = os.path.join(WORKDIR, 'exams', f'数二模拟卷({CN_NO[no]})_LaTeX.tex')
        cmd2 = [sys.executable, BUILD, '--select', sel, '--bank', 'question_bank.json',
                '-o', tex]
        if args.no_pdf:
            cmd2.append('--no-pdf')
        run(cmd2, f'组卷 第{no}卷')
        # 下一轮循环重新 glob，自动把本卷纳入 exclude

    print(f'[batch] 完成：共出 {args.papers} 套（第 {start} ~ {start + args.papers - 1} 卷）')
    print(f'[batch] 下一卷起，exclude 会自动带上本次新卷')


if __name__ == '__main__':
    main()
