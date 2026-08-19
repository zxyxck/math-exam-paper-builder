#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
merge_banks.py — 合并多个章节题库 JSON 为一个 question_bank.json

用法:
  python merge_banks.py bank/ch1.json bank/ch2.json ... -o question_bank.json
  python merge_banks.py bank/ -o question_bank.json   # 目录下所有 JSON
"""
import argparse
import glob
import json
import os


def main():
    ap = argparse.ArgumentParser(description="合并章节题库")
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            files += sorted(glob.glob(os.path.join(inp, "*.json")))
        else:
            files.append(inp)

    out_base = os.path.abspath(args.output)
    base_qs, base_src, rest = [], [], []
    for f in files:
        if os.path.abspath(f) == out_base:
            # 输出文件自身作为基线（增量合并场景）
            try:
                b0 = json.load(open(f, encoding="utf-8"))
                base_qs = b0.get("questions", [])
                base_src = b0.get("source", [])
                print(f"[merge] 基线: {os.path.basename(f)} ({len(base_qs)} 题)")
            except Exception as e:
                print(f"[warn] 读取基线失败: {e}")
        else:
            rest.append(f)
    if not rest and not base_qs:
        ap.error("没有可合并的输入文件")

    merged = {"source": list(base_src), "questions": list(base_qs)}
    seen = set((q["book"], q["chapter"], q["block"], q["qtype"], q["num"]) for q in base_qs)
    for f in rest:
        b = json.load(open(f, encoding="utf-8"))
        for q in b.get("questions", []):
            key = (q["book"], q["chapter"], q["block"], q["qtype"], q["num"])
            if key in seen:
                print(f"[skip] 重复 {key}")
                continue
            seen.add(key)
            merged["questions"].append(q)
        if b.get("source"):
            src = b["source"] if isinstance(b["source"], list) else [b["source"]]
            merged["source"].extend(src)

    merged["questions"].sort(key=lambda q: (q["book"], q["chapter"],
                                            {"基础题": 0, "综合题": 1, "拓展题": 2}[q["block"]],
                                            {"choice": 0, "blank": 1, "solve": 2}[q["qtype"]],
                                            q["num"]))
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=1)
    print(f"[merge] {len(merged['questions'])} 题 -> {args.output}")


if __name__ == "__main__":
    main()
