#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pick_from_bank.py — 从题库 JSON 按考纲 profile 抽题，生成 selectN.json

用法:
  python pick_from_bank.py question_bank.json -o select.json
  python pick_from_bank.py question_bank.json --seed 42 -o select.json
  python pick_from_bank.py question_bank.json --exclude select1.json --exclude select2.json -o select3.json

特性:
  - 自动排除 LaTeX 语法坏题（复用 bank_health.is_bad）
  - 自动排除 --exclude 指定清单中已用过的题（避免跨卷重复）
  - 固定 --seed 可复现同一套卷子
  - 默认只在「综合题」块抽题（可 --block 调整）
"""
import argparse
import json
import os
import random
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bank_health import is_bad

CN_STR = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6,
          '七': 7, '八': 8, '九': 9, '十': 10, '十一': 11, '十二': 12}
CN_NUM = {v: k for k, v in CN_STR.items()}
QT_CN = {'choice': '选择', 'blank': '填空', 'solve': '解答'}
QTYPE_CN = {'choice': '一、选择', 'blank': '二、填空', 'solve': '三、解答'}
QTYPE_CN_FULL = {'choice': '一、选择题', 'blank': '二、填空题', 'solve': '三、解答题'}

# 证明题识别：stem 含这些关键词的解答题视为证明题。
# 覆盖「证明」「试证」「设…证明」「…证明：」等常见写法。
PROOF_RE = re.compile(r'证明|试证|验证')

# 高数篇章节号 1-6；线代篇章节号 7-12（与题库一致）。
GAOSH_CHS = {1, 2, 3, 4, 5, 6}
XIANDAI_CHS = {7, 8, 9, 10, 11, 12}

PROFILES = {
    "数二标准": {
        "title": "数学（二）模拟试卷",
        "score_total": 150, "time": 180,
        # 章 -> 题数（选择 10 + 填空 6 + 解答 6 = 22 题）
        # 线代覆盖 8/10/11/12 章（二次型 12 章已入库可用）
        "choice": {1: 1, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 8: 1, 11: 1, 12: 1},
        "blank":  {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 10: 1},
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 12: 1},
    },
    # 「数二真题」profile：严格对齐考研数二真题的学科占比与题型数量。
    # 选择 10×5=50、填空 6×5=30、解答 6 题共 70 分（卷面标注），
    # 满分 150。学科占比：高数 7+5+5=17 题 / 120 分（80%），线代 3+1+1=5 题 / 30 分（20%）。
    # 章节配额基于题库容量设计：填空避开容量仅 4 道的高数4章，改用高数6章（10 道）。
    # 证明题上限默认 2 道（见 --max-proofs）。
    "数二真题": {
        "title": "数学（二）模拟试卷",
        "score_total": 150, "time": 180,
        # 选择题 10 题：高数 7 + 线代 3
        "choice": {1: 1, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1, 8: 1, 10: 1, 11: 1},
        # 填空题 6 题：高数 5 + 线代 1。
        # 章节配额需避开容量已被前序卷耗尽的章节（高数4/5章、线代10章填空已用光），
        # 故高数填空分布在高数1/2/3/6，其中高数3章配 2 道（容量充足）；线代留 1 道在12章。
        "blank":  {1: 1, 2: 1, 3: 2, 6: 1, 12: 1},
        # 解答题 6 题：高数 5 + 线代 1
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1, 11: 1},
    },
    "高数全": {
        "title": "数学（二）高数专项模拟",
        "score_total": 100, "time": 120,
        "choice": {1: 2, 2: 2, 3: 2, 4: 1, 5: 1, 6: 2},   # 共 10
        "blank":  {1: 1, 2: 1, 3: 1, 4: 1, 5: 1, 6: 1},   # 共 6
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},         # 共 5
    },
    # 「数二轮换」profile：不强求对齐真题格式。
    # 高数固定 17 题（选择 7 + 填空 5 + 解答 5）占大头；
    # 线代 5 题（选择 3 + 填空 1 + 解答 1）在 7~12 章之间轮换：
    #   优先抽「未被历卷覆盖过的章节」，配额不足时再补已用章节，保证多卷覆盖所有线代章；
    #   每卷线代各章的题型分配随机（哪章出选择/填空/解答不固定）。
    "数二轮换": {
        "title": "数学（二）模拟试卷",
        "score_total": 150, "time": 180,
        "choice": {1: 1, 2: 2, 3: 1, 4: 1, 5: 1, 6: 1},   # 高数 7
        "blank":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},          # 高数 5
        "solve":  {1: 1, 2: 1, 3: 1, 5: 1, 6: 1},          # 高数 5
        # 线代轮换块：chapters 为轮换池，kinds 为题型配额（总数=每卷线代题数）
        "xian": {"chapters": [7, 8, 9, 10, 11, 12],
                  "kinds": [("choice", 3), ("blank", 1), ("solve", 1)]},
    },
}

SEC_DESC = {
    'choice': '在每小题给出的四个选项中，只有一项符合题目要求。',
    'blank': '请将答案写在题中横线上。',
    'solve': '解答应写出文字说明、证明过程或演算步骤。',
}
SEC_SCORE = {'choice': '本大题共 10 小题，每小题 5 分，共 50 分。',
             'blank': '本大题共 6 小题，每小题 5 分，共 30 分。',
             'solve': '本大题共 6 小题，共 70 分。'}


def parse_source(src):
    """'高数篇·第一章·综合题·选择(3)' -> (book, chapter, block, qtype, num)"""
    m = re.match(r'(.+?)·第(.+?)章·(.+?)·(选择|填空|解答)\((\d+)\)', src)
    if not m:
        return None
    book, ch, block, qt, num = m.groups()
    return book, CN_STR[ch], block, {'选择': 'choice', '填空': 'blank', '解答': 'solve'}[qt], int(num)


def build_source(book, ch, block, qt, num):
    return f"{book}·第{CN_NUM[ch]}章·{block}·{QT_CN[qt]}({num})"


def load_bank(path):
    data = json.load(open(path, encoding='utf-8'))
    return data['questions'] if isinstance(data, dict) else data


def collect_excluded(exclude_paths):
    """读若干 selectN.json，收集已用题 (book,chapter,block,qtype,num) 集合"""
    used = set()
    for p in exclude_paths or []:
        sel = json.load(open(p, encoding='utf-8'))
        for q in sel['questions']:
            key = parse_source(q['source'])
            if key:
                used.add(key)
    return used


def is_proof(q):
    """判断一道题是否为证明题：stem 含「证明/试证/验证」关键词。

    用于解答题分区抽题，保证同一试卷证明题数量 ≤ 上限（默认 2）。
    业务规则来源：考研数二真题同一试卷证明题一般不超过两道。
    """
    stem = q.get('stem') or ''
    return bool(PROOF_RE.search(stem))


def correct_quota(got, cands, n, quota, key2blk, excluded=()):
    """块配额校正：把 got 中「配额已耗尽 / 被 excluded 排除」的题替换为后续候选里
    配额可用且未被排除的题。

    用于 --mix 混合抽题（如综合 17 + 基础 4 + 拓展 1）。无替代时保留原题（保题量优先）。
    excluded：该阶段不允许出现的块（如拓展题只在解答题阶段开放，模拟压轴位置）。
    """
    taken = set(got)
    fixed = []
    for key in got:
        blk = key2blk.get(key)
        if blk is not None and blk not in excluded and quota.get(blk, 0) > 0:
            quota[blk] -= 1
            fixed.append(key)
        else:
            for k2, _ in cands:
                b2 = key2blk.get(k2)
                if (k2 not in taken and b2 is not None and b2 not in excluded
                        and quota.get(b2, 0) > 0):
                    taken.add(k2)
                    quota[b2] -= 1
                    fixed.append(k2)
                    break
            else:
                fixed.append(key)  # 无可用替代：保留原题
    return fixed[:n]


def main():
    ap = argparse.ArgumentParser(description='按考纲 profile 从题库抽题')
    ap.add_argument('bank', help='question_bank.json 路径')
    ap.add_argument('--profile', '-p', default='数二标准', choices=list(PROFILES.keys()))
    ap.add_argument('--seed', type=int, default=None, help='随机种子，固定后结果可复现')
    ap.add_argument('--exclude', action='append', default=[], help='排除清单（selectN.json），可多次传入')
    ap.add_argument('--block', default='综合题', help='抽题块：综合题 / 基础题 / 拓展题')
    ap.add_argument('--mix', nargs='*', default=[],
                    help='块混合配额，如 --mix 基础题:4 拓展题:1（综合题自动 = 总配额 - 其余；'
                         '不传则全部从 --block 指定块抽）')
    ap.add_argument('--topic', nargs='*', default=[],
                    help='知识点选题，如 --topic 极限与连续:3 特征值与相似:2，'
                         '可限题型 --topic 一元积分:3:solve（题型 choice/blank/solve 或 选择/填空/解答）；'
                         'topic 题替换同章同题型题位，题位不足时附加（总题数增加）；主题见 topic_tags.json')
    ap.add_argument('--tags', default=None, help='知识点标签文件（默认 bank 同目录 topic_tags.json）')
    ap.add_argument('--skip-bad', action='store_true', default=True, help='排除 LaTeX 语法坏题（默认开）')
    ap.add_argument('--no-skip-bad', dest='skip_bad', action='store_false')
    ap.add_argument('-o', '--output', required=True)
    ap.add_argument('--title', default=None, help='试卷标题，默认用 profile.title')
    ap.add_argument('--no', type=int, default=1, help='卷号（标题里显示（一）（二）…）')
    ap.add_argument('--max-proofs', type=int, default=2,
                    help='同一试卷证明题数量上限（默认 2，对齐考研数二真题约束；'
                         '设为 0 禁止证明题，负数或大数表示不限制）')
    args = ap.parse_args()

    if args.seed is not None:
        random.seed(args.seed)

    bank = load_bank(args.bank)
    profile = PROFILES[args.profile]
    used = collect_excluded(args.exclude)
    max_proofs = args.max_proofs

    # --mix 块配额：{'基础题': 4, '拓展题': 1}；综合题配额自动 = 总配额 - 其余。
    # 总配额 = profile 各题型题数之和 + 线代轮换题数（若有）。
    mix = {}
    for m in args.mix:
        blk, _, n = m.partition(':')
        if blk not in ('基础题', '综合题', '拓展题'):
            ap.error(f'--mix 块名必须是 基础题/综合题/拓展题: {m}')
        mix[blk] = mix.get(blk, 0) + int(n)
    total_quota = sum(sum(cfg.values()) for cfg in
                      (profile.get(k) for k in ('choice', 'blank', 'solve')) if cfg)
    xian_cfg = profile.get('xian')
    if xian_cfg:
        total_quota += sum(n for _, n in xian_cfg['kinds'])
    mix.setdefault('综合题', max(0, total_quota - sum(mix.values())))

    # 抽题结果容器（profile/xian/压轴 抽满 total_quota，topic 题随后替换入位）
    picked, missing = [], []

    # --topic 知识点选题：{'极限与连续': 3, '特征值与相似': 2}
    # topic 题先抽（自动避开已用/坏题）并计入 used，profile 不再抽到它们；
    # 抽完后替换卷中同章同题型（或同题型卷末）的题位，总题数不变。
    topic = {}
    for t in args.topic:
        parts = t.split(':')
        name = parts[0]
        n = int(parts[1])
        kind = parts[2] if len(parts) > 2 else None
        if kind is not None:
            kind = {'选择': 'choice', '填空': 'blank', '解答': 'solve'}.get(kind, kind)
        topic[name] = (topic.get(name, (0, None))[0] + n, kind)
    topic_kind = {name: k for name, (_, k) in topic.items()}
    # 题库索引（topic 抽题/证明题校验用）
    bank_by_key = {}
    for q in bank:
        bank_by_key[(q['book'], q['chapter'], q['block'], q['qtype'], q['num'])] = q
    topic_keys = []
    if topic:
        tags_path = args.tags or os.path.join(
            os.path.dirname(os.path.abspath(args.bank)), 'topic_tags.json')
        tags = json.load(open(tags_path, encoding='utf-8'))
        for name, (n, kind) in topic.items():
            cands = []
            for src in tags.get(name, []):
                key = parse_source(src)
                if key is None or key in used:
                    continue
                q = bank_by_key.get(key)
                if q is None or (args.skip_bad and is_bad(q)):
                    continue
                if kind is not None and key[3] != kind:
                    continue
                cands.append((key, q))
            random.shuffle(cands)
            got = [k for k, _ in cands[:n]]
            if len(got) < n:
                missing.append((name, 'topic', n, len(got)))
            topic_keys.extend(got)
            used.update(got)
            if got:
                print('[topic] ' + '、'.join(build_source(*k) for k in got))

    # 候选池：保留题对象引用，用于证明题识别。
    # pool[(章, 题型)] = [(key, q), ...]；key2blk[key] = 块名（供 --mix 配额校正）
    pool = {}
    key2blk = {}
    for q in bank:
        if q['block'] != args.block:
            continue
        if args.skip_bad and is_bad(q):
            continue
        key = (q['book'], q['chapter'], q['block'], q['qtype'], q['num'])
        if key in used:
            continue
        pool.setdefault((q['chapter'], q['qtype']), []).append((key, q))
        key2blk[key] = q['block']

    # 非 --block 块的候选（--mix 混合抽题时用）：key2blk 同时记录这些块
    if mix:
        for q in bank:
            if q['block'] == args.block or q['block'] not in mix:
                continue
            if args.skip_bad and is_bad(q):
                continue
            key = (q['book'], q['chapter'], q['block'], q['qtype'], q['num'])
            if key in used:
                continue
            pool.setdefault((q['chapter'], q['qtype']), []).append((key, q))
            key2blk[key] = q['block']

    # 压轴候选池：位置锚定卷末高数解答，题源二选一——
    # 1) --mix 含拓展配额时：解答拓展题（高数+线代 41 道，旧语义）；
    # 2) 否则：全部解答题（高数+线代，任意块，共 429 道）——出完为止，不限定拓展。
    pool_ext_solve = []    # 解答拓展题候选
    pool_final_solve = []  # 全部解答题候选
    if mix:
        for q in bank:
            if q['qtype'] != 'solve':
                continue
            if args.skip_bad and is_bad(q):
                continue
            key = (q['book'], q['chapter'], q['block'], q['qtype'], q['num'])
            if key in used:
                continue
            if q['block'] == '拓展题':
                pool_ext_solve.append((key, q))
            pool_final_solve.append((key, q))

    # 抽题
    proof_keys = set()  # 已抽到的证明题 key 集合
    for kind in ('choice', 'blank', 'solve'):
        cfg = profile.get(kind)
        if not cfg:
            continue
        for ch, n in sorted(cfg.items()):
            if n == 0:
                continue
            cands = list(pool.get((ch, kind), []))
            random.shuffle(cands)
            if kind == 'solve' and max_proofs >= 0:
                # 解答题：正常抽，但证明题数量受全卷上限约束。
                # 策略：遍历 shuffle 后的候选，逐个纳入；证明题仅在配额内纳入，
                #       超配额的证明题跳过，改用后续非证明题补位。
                got = []
                for key, q in cands:
                    if len(got) >= n:
                        break
                    if is_proof(q):
                        if len(proof_keys) < max_proofs:
                            got.append(key)
                            proof_keys.add(key)
                        # 超配额的证明题跳过，继续找非证明题
                    else:
                        got.append(key)
                # 若仍不足 n，放开配额用剩余证明题补（保题量优先）
                if len(got) < n:
                    for key, q in cands:
                        if len(got) >= n:
                            break
                        if key not in got and key not in proof_keys:
                            got.append(key)
                            if is_proof(q):
                                proof_keys.add(key)
                c_keys = got
            else:
                c_keys = [k for k, _ in cands[:n]]
            # --mix 块配额校正：拓展题不参与普通替换（压轴在最后统一处理）
            if mix:
                c_keys = correct_quota(c_keys, cands, n, mix, key2blk,
                                       excluded=('拓展题',))
            if len(c_keys) < n:
                missing.append((ch, kind, n, len(c_keys)))
            picked.extend(c_keys)

    # 线代轮换块（profile 含 "xian" 键时）：
    # 1) 从历卷排除清单统计已覆盖过的线代章节，优先抽未覆盖章节（轮换覆盖 7~12）；
    # 2) 每卷线代题型配额按随机顺序分配给所选章节（章节-题型对应不固定）。
    xian = profile.get('xian')
    if xian:
        used_ch = {key[1] for key in used if key[0] == '线代篇'}
        n_total = sum(n for _, n in xian['kinds'])
        fresh = [c for c in xian['chapters'] if c not in used_ch]
        rest = [c for c in xian['chapters'] if c in used_ch]
        random.shuffle(fresh)
        random.shuffle(rest)
        chapters = (fresh + rest)[:n_total]
        kinds = []
        for k, n in xian['kinds']:
            kinds += [k] * n
        random.shuffle(kinds)
        for ch, kind in zip(chapters, kinds):
            cands = list(pool.get((ch, kind), []))
            random.shuffle(cands)
            got = [k for k, _ in cands[:1]]
            if mix:
                # 线代轮换块：拓展题（压轴）只允许出现在高数解答，避免压轴固定在线代末题
                got = correct_quota(got, cands, 1, mix, key2blk,
                                   excluded=('拓展题',))
            if len(got) < 1:
                missing.append((ch, kind, 1, 0))
            picked.extend(got)
        print(f'[xian] 线代轮换章节: ' + '、'.join(f'第{c}章' for c in sorted(chapters)),
              '| 题型分配: ' + '、'.join(f'第{c}章-{k}' for c, k in zip(chapters, kinds)))

    # --topic 题归位：替换卷中「同章同题型」的题位（无则同题型卷末），
    # 被替换题归还块配额；总题数保持 total_quota。
    if topic_keys:
        for tk in topic_keys:
            cand = None
            for i, k in enumerate(picked):
                if k[3] == tk[3] and k[1] == tk[1] and k not in topic_keys:
                    cand = i
                    break
            if cand is None:
                for i in range(len(picked) - 1, -1, -1):
                    if picked[i][3] == tk[3] and picked[i] not in topic_keys:
                        cand = i
                        break
            if cand is not None:
                ob = key2blk.get(picked[cand])
                if ob:
                    mix[ob] = mix.get(ob, 0) + 1  # 归还被替换题的配额
                picked[cand] = tk
            else:
                picked.append(tk)  # 该题型题位不足：附加（总题数增加）

    # 压轴（卷末最后一道解答题）：--mix 时从解答池抽 1 道替换之。
    # 题源：--mix 含拓展配额时取解答拓展题；否则取全部解答题（高数+线代任意块，
    #       不考虑是不是拓展题，只要是解答题就行）。位置 = 卷末最后一道解答题。
    if mix:
        if mix.get('拓展题', 0) > 0:
            exts = [k for k, _ in pool_ext_solve]
        else:
            exts = [k for k, _ in pool_final_solve]
        if exts:
            random.shuffle(exts)
            solves = [k for k in picked if k[3] == 'solve' and k not in topic_keys]
            if solves:
                last = max(solves, key=lambda k: (k[1], k[4]))
                if last != exts[0]:
                    ob = key2blk.get(last)
                    if ob:
                        mix[ob] = mix.get(ob, 0) + 1  # 归还被替换题的配额
                    picked[picked.index(last)] = exts[0]
                    print(f'[final] 压轴(卷末解答): {build_source(*exts[0])}')

    if missing:
        print('[warn] 部分章节题数不足：', missing, file=sys.stderr)
    if not picked:
        print('[error] 未抽到任何题，请检查题库/排除清单/块', file=sys.stderr)
        sys.exit(1)

    # 证明题数量校验
    picked_set = set(picked)
    picked_qs = [q for q in bank if (q['book'], q['chapter'], q['block'], q['qtype'], q['num']) in picked_set]
    n_proofs = sum(1 for q in picked_qs if q['qtype'] == 'solve' and is_proof(q))
    if max_proofs >= 0 and n_proofs > max_proofs:
        print(f'[warn] 证明题 {n_proofs} 道，超过上限 {max_proofs}，请检查题库或扩大候选', file=sys.stderr)
    print(f'[proof] 本卷证明题 {n_proofs} 道（上限 {max_proofs if max_proofs >= 0 else "不限"}）')

    # 块分布统计（--mix 混合抽题时直观确认）
    blk_cnt = Counter(q['block'] for q in picked_qs)
    if mix:
        print('[mix] 块分布: ' + '、'.join(f'{b} {n} 题' for b, n in blk_cnt.items()))

    # 组装 select.json
    cn_no = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
    title = args.title or profile['title']
    qs, i = [], 1
    for kind in ('choice', 'blank', 'solve'):
        for key in sorted(picked, key=lambda k: (k[3], k[1], k[4])):
            if key[3] != kind:
                continue
            qs.append({'id': i, 'kind': kind,
                       'score': 12 if kind == 'solve' else 5,
                       'chapter': key[1], 'block': key[2],
                       'qtype': QTYPE_CN[kind], 'num': key[4],
                       'source': build_source(*key)})
            i += 1

    sel = {
        'header': {
            'exam': '全国硕士研究生招生考试',
            'title': f'{title}（{cn_no[args.no]}）',
            'sub': '——精选自 880 题（A4 留白版）',
            'score_total': profile.get('score_total', 150),
            'time': profile.get('time', 180),
            'notes': [
                '一、考生应在答题卡指定位置上用黑色字迹的钢笔或签字笔填写姓名、准考证号和得分。',
                '二、答题时，答案须用黑色字迹的钢笔或签字笔写在答题卡上，写在试卷上或草稿纸上的答案无效。',
                f'三、本试卷共 {len(qs)} 题，满分 {profile.get("score_total", 150)} 分，考试时间 {profile.get("time", 180)} 分钟。',
            ],
        },
        'sections': {
            'choice': {'name': QTYPE_CN_FULL['choice'], 'desc': SEC_DESC['choice'] + SEC_SCORE['choice']},
            'blank':  {'name': QTYPE_CN_FULL['blank'],  'desc': SEC_DESC['blank'] + SEC_SCORE['blank']},
            'solve':  {'name': QTYPE_CN_FULL['solve'],  'desc': SEC_DESC['solve'] + SEC_SCORE['solve']},
        },
        'questions': qs,
    }
    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(sel, f, ensure_ascii=False, indent=1)
    print(f'[pick] {len(qs)} 题 -> {args.output}')
    for kind in ('choice', 'blank', 'solve'):
        sub = [q for q in qs if q['kind'] == kind]
        if sub:
            print(f'  {kind}: {len(sub)} 题 -> ' + '; '.join(q['source'].replace(args.block + '·', '') for q in sub))


if __name__ == '__main__':
    main()
