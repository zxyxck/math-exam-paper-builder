#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
parse_question_bank.py — 把「880 提取版」Markdown 解析为标准题库 JSON

输入格式（模板见 question_template.md）：
    ### 一、基础题 / ### 二、综合题 / ### 三、拓展题      -> block
    #### （一）选择题 / （二）填空题 / （三）解答题        -> qtype
    1.  题干...                                          -> 题号 + 题干
        A. ... B. ... C. ... D. ...                      -> 选项（同行或分行）
        (I) ... / ① ...                                   -> 子问 parts

用法:
  python parse_question_bank.py <input.md> -o bank/ch1.json [--chapter 1] [--book 高数篇]
  python parse_question_bank.py <input.md> -o bank/ch1.json --merge pos.json
"""
import argparse
import json
import os
import re

BLOCK_RE = re.compile(r"^#{1,4}\s*(一、基础题|二、综合题|三、拓展题|基础题|综合题|拓展题)")
QTYPE_RE = re.compile(
    r"^#{0,4}\s*\*{0,2}\s*"
    r"(?:[（(](一|二|三)、?[)）]|[一二三]、|\d+[.、．])?\s*"
    r"(选择题|填空题|解答题)\s*\*{0,2}")
NUM_RE = re.compile(r"^\s*(?:\*\*(\d+)[.、．]\*\*\s*|\((\d+)\)\s*|(\d+)[.、．]\s*)?(.*)$")
OPT_RE = re.compile(r"^[\s\u3000]*([A-D])[.、．]\s*(.*)$")
SUB_RE = re.compile(r"^[\s\u3000]*([（(]\s*(?:I|II|III|IV|V|VI|VII|VIII|IX|X)\s*[)）]|[①②③④⑤⑥⑦⑧⑨⑩])\s*(.*)$")

CN_QTYPE = {"选择题": "choice", "填空题": "blank", "解答题": "solve"}
QTYPE_CN = {"choice": "一、选择", "blank": "二、填空", "solve": "三、解答"}


def split_options(text):
    """同一行多个选项 A. .. B. .. C. .. D. .. 拆开"""
    parts = re.split(r"(?=[A-D][.、．])", text)
    out = []
    for p in parts:
        m = re.match(r"^([A-D])[.、．]\s*(.*)$", p.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def parse_md(path, chapter, book):
    cur_block, cur_qtype, cur = None, None, None
    seen_types = set()  # 用于缺「综合题」标题时的自动切块
    questions = []

    def close():
        nonlocal cur
        if cur is not None:
            q = cur["q"]
            q["stem"] = cur["stem"].strip()
            if cur["parts"]:
                q["parts"] = cur["parts"]
            questions.append(q)
            cur = None

    for raw in open(path, encoding="utf-8"):
        line = raw.rstrip("\n")
        if not line.strip():
            continue
        stripped = line.strip()
        # 分隔线
        if stripped == "---" or re.match(r"^[-=]{3,}$", stripped):
            continue
        # 块标题
        m = BLOCK_RE.match(line)
        if m:
            close()
            t = m.group(1)
            cur_block = {"一、基础题": "基础题", "二、综合题": "综合题", "三、拓展题": "拓展题"}.get(t, t)
            cur_qtype = None
            seen_types = set()
            continue
        # 题型标题
        m = QTYPE_RE.match(line)
        if m:
            close()
            qt = CN_QTYPE.get(m.group(2))
            if cur_block == "基础题" and qt in seen_types:
                cur_block = "综合题"
                seen_types = set()
            seen_types.add(qt)
            cur_qtype = qt
            continue
        # 题号行（支持 **N.** 、(N)、N. 三种格式）
        m = NUM_RE.match(line)
        if m and (m.group(1) or m.group(2) or m.group(3)):
            close()
            num = int(m.group(1) or m.group(2) or m.group(3))
            q = {"book": book, "chapter": chapter, "block": cur_block,
                 "qtype": cur_qtype, "num": num,
                 "qtype_cn": QTYPE_CN.get(cur_qtype),
                 "stem": "", "options": {}, "parts": None,
                 "answer": None, "tags": [], "note": ""}
            cur = {"q": q, "stem": (m.group(4) or "").strip(), "parts": []}
            continue
        if cur is None:
            # 无题号则自动编号（如拓展题直接跟题干）
            if cur_qtype and stripped and not stripped.startswith(("#", "*", "-", ">")):
                nums = [q["num"] for q in questions
                        if q["block"] == cur_block and q["qtype"] == cur_qtype]
                num = (max(nums) + 1) if nums else 1
                q = {"book": book, "chapter": chapter, "block": cur_block,
                     "qtype": cur_qtype, "num": num,
                     "qtype_cn": QTYPE_CN.get(cur_qtype),
                     "stem": "", "options": {}, "parts": None,
                     "answer": None, "tags": [], "note": ""}
                cur = {"q": q, "stem": stripped, "parts": []}
            continue
        # 选项
        opt_pairs = split_options(line)
        if opt_pairs:
            for k, v in opt_pairs:
                if k not in cur["q"]["options"]:
                    cur["q"]["options"][k] = v
            continue
        # 子问
        m = SUB_RE.match(line)
        if m:
            cur["parts"].append({"tag": m.group(1), "text": m.group(2)})
            continue
        # 其他：续接题干（题干多行）或续接最后一个 part
        if cur["parts"]:
            cur["parts"][-1]["text"] += " " + stripped
        else:
            cur["stem"] += " " + stripped
    close()
    return questions


def merge_pos(questions, pos_path):
    """把 pos.json 的位置信息（page/y0）关联进题库（可选）"""
    pos = json.load(open(pos_path, encoding="utf-8"))
    idx = {}
    for q in pos.get("questions", []):
        key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
        idx.setdefault(key, []).append(q)
    for q in questions:
        key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
        locs = idx.get(key)
        q["loc"] = [{"page": l["page"], "y0": l["y0"]} for l in locs] if locs else []
    return questions


def main():
    ap = argparse.ArgumentParser(description="解析 880 提取版 Markdown 为题库 JSON")
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--chapter", type=int, default=None)
    ap.add_argument("--book", default="高数篇")
    ap.add_argument("--merge", default=None, help="pos.json 路径，关联位置信息")
    args = ap.parse_args()

    chapter = args.chapter
    if chapter is None:
        m = re.search(r"第([一二三四五六七八九十]+)章", os.path.basename(args.input))
        if m:
            cn = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6,
                  "七": 7, "八": 8, "九": 9, "十": 10, "十一": 11, "十二": 12}
            chapter = cn.get(m.group(1))
    if chapter is None:
        ap.error("无法从文件名推断章节，请用 --chapter 指定")

    questions = parse_md(args.input, chapter, args.book)
    if args.merge:
        questions = merge_pos(questions, args.merge)

    out = {"source": os.path.basename(args.input),
           "book": args.book, "chapter": chapter,
           "questions": questions}
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)

    from collections import Counter
    c = Counter((q["block"], q["qtype"]) for q in questions)
    print(f"共 {len(questions)} 题")
    for k in sorted(c):
        print(f"  {k[0]} {k[1]}: {c[k]}")


if __name__ == "__main__":
    main()
