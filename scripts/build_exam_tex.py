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
            # 阈值取 2，与公式段一致：题库约定填空为 2+ 个 \_（如 \_\_\_），
            # 若取 3 会导致非公式段内「2 个 \_」的填空漏转成乱码。
            p = re.sub(r'(?:_|\\_){2,}', '\x00', p)
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
            # 子问 / 命题列表（parts）：
            #  - 选择题：题干后的 ①②③④ 命题条件，不渲染则题目"缺条件"
            #  - 解答题：(I)(II)... 子问，不渲染则题目不全
            # 之前只给解答题渲染 parts，导致条件型选择题（如"下列命题正确的是"）
            # 抽中后丢失命题列表。现统一对所有题型渲染 parts。
            parts = t.get('parts')
            if parts:
                for p in parts:
                    tag = p.get('tag', '') or ''
                    ptext = tex_escape_text(p.get('text', '') or '')
                    lines.append(r'\par\quad ' + tag + (' ' if tag else '') + ptext)
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
                # 解答题纯留白（不画框）；parts 子问已由上方通用逻辑渲染
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
