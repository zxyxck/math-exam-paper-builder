#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
tag_bank.py — 按关键词规则给题库打知识点标签，生成 topic_tags.json

知识点池供 pick_from_bank.py 的 --topic 使用（如 --topic 极限:3 特征值:2）。

用法:
  python3 tag_bank.py question_bank.json -o topic_tags.json

输出格式:
  {"极限与连续": ["高数篇·第一章·综合题·选择(3)", ...], ...}

规则说明:
  - 匹配题干的 stem + 选项文本
  - 一题可命中多个主题（如「矩阵的秩」同时命中 矩阵 与 向量组 的秩）
  - 规则按数二考纲主题设计，可在 TOPICS 中增删
"""
import argparse
import json
import os
import re

# 主题 -> 关键词列表（命中任一关键词即打标；'re:' 前缀表示正则）
# 注意：用精确词避免泛词误命中（如「二重特征值」≠「二重积分」，「微分方程」≠「一元微分」）
TOPICS = {
    '极限与连续': ['极限', 'lim', '洛必达', '等价无穷小', '无穷小', '无穷大',
               '间断', '连续', '零点'],
    '一元微分': ['导数', '切线', '法线', '单调', '极值', '最值',
             '凹凸', '拐点', '中值定理', '罗尔', '拉格朗日', '柯西',
             '泰勒', '麦克劳林', '渐近线', '导函数'],
    '一元积分': ['定积', '不定积', '原函数', '变上限', '反常', '广义积分',
             '分部积分', '换元积分', '积分中值', '积分的', r're:\\int(?![^$]*\\\\int)'],
    '多元微分': ['偏导', '全微分', '梯度', '方向导数', '多元函数', '多元', '∂'],
    '二重积分': ['二重积', '累次', '交换积分次序', '曲顶柱体', '∫∫', '∬',
              r're:\\iint'],
    '微分方程': ['微分方程', '通解', '特解', '齐次方程', '伯努利',
             '可分离变量', '一阶线性', '二阶常系数', '特征方程', "y''", "y'="],
    '行列式': ['行列式', 'det', '余子式', '代数余子式'],
    '矩阵': ['矩阵', '逆矩阵', '伴随矩阵', '初等变换', '初等矩阵', '秩'],
    '向量组': ['向量组', '线性相关', '线性无关', '线性表示',
            '极大线性无关组', '向量'],
    '线性方程组': ['方程组', '基础解系', '解的结构', '克拉默', '唯一解',
              '无穷多解', '无解', '同解'],
    '特征值与相似': ['特征值', '特征向量', '相似', '对角化', '实对称'],
    '二次型': ['二次型', '正定', '合同', '规范形', '惯性指数'],
}

QT_CN = {'choice': '选择', 'blank': '填空', 'solve': '解答'}
CN_NUM = {1: '一', 2: '二', 3: '三', 4: '四', 5: '五', 6: '六',
          7: '七', 8: '八', 9: '九', 10: '十', 11: '十一', 12: '十二'}


def source_of(q):
    return (f"{q['book']}·第{CN_NUM[q['chapter']]}章·{q['block']}·"
            f"{QT_CN[q['qtype']]}({q['num']})")


def main():
    ap = argparse.ArgumentParser(description='按关键词规则给题库打知识点标签')
    ap.add_argument('bank', help='question_bank.json 路径')
    ap.add_argument('-o', '--output', default='topic_tags.json')
    args = ap.parse_args()

    data = json.load(open(args.bank, encoding='utf-8'))
    qs = data['questions'] if isinstance(data, dict) else data

    tags = {t: [] for t in TOPICS}
    no_tag = []
    for q in qs:
        text = (q.get('stem') or '') + ''.join((q.get('options') or {}).values())
        hit = []
        for t, kws in TOPICS.items():
            for kw in kws:
                if kw.startswith('re:'):
                    if re.search(kw[3:], text):
                        hit.append(t)
                        break
                elif kw in text:
                    hit.append(t)
                    break
        src = source_of(q)
        # 互斥：二重积分题不算一元积分（如含 \iint 与 \int 混合的证明题）
        if '一元积分' in hit and ('二重积分' in hit or len(re.findall(r'\\int', text)) >= 2):
            hit.remove('一元积分')
        if not hit:
            no_tag.append(src)
            continue
        for t in hit:
            tags[t].append(src)

    with open(args.output, 'w', encoding='utf-8') as f:
        json.dump(tags, f, ensure_ascii=False, indent=1)

    print(f'[tag] 共 {len(qs)} 题 -> {args.output}')
    for t, srcs in sorted(tags.items(), key=lambda kv: -len(kv[1])):
        print(f'  {t:<8} {len(srcs)} 题')
    print(f'[tag] 未命中任何主题: {len(no_tag)} 题')
    if no_tag[:5]:
        print('  例:', no_tag[:5])


if __name__ == '__main__':
    main()
