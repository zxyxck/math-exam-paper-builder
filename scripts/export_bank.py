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
