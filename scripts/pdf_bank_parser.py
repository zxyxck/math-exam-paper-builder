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
