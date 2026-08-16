#!/usr/bin/env python3
"""X投稿用記事の文体チェック。使い方: python3 check_style.py diary/YYYY-MM-DD-X投稿用.md"""
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()

problems = []
if "僕" in text:
    problems.append(f"『僕』が{text.count('僕')}箇所(ひらがなの『ぼく』にする)")
if re.search(r"^#|\*\*|\[.+\]\(", text, re.M):
    problems.append("マークダウン記法が混入(Xでは記号がそのまま見える)")
if re.search(r"[\U0001F300-\U0001FAFF]", text):
    problems.append("絵文字が混入")
if re.search(r"---\n", text[:10]):
    problems.append("frontmatterが付いている(コピペ用なので外す)")
for bad, good in [("阿弥陀様", "阿弥陀さま"), ("仏様", "仏さま"), ("下さい", "ください"), ("出来る", "できる")]:
    if bad in text:
        problems.append(f"『{bad}』→『{good}』")

warnings = []
sents = [s.strip() for s in re.split(r"(?<=[。?])", text) if s.strip() and "⸻" not in s and "http" not in s]
lengths = sorted(len(s) for s in sents)
median = lengths[len(lengths) // 2]
short = sum(1 for x in lengths if x <= 15) / len(lengths)


def tail(s: str) -> str:
    for e in ["ですね。", "ました。", "ません。", "でしょうか。", "のです。", "です。", "ます。", "でした。"]:
        if s.endswith(e):
            return e
    return "他"


tails = [tail(s) for s in sents]
dup = sum(1 for i in range(1, len(tails)) if tails[i] == tails[i - 1] and tails[i] != "他")
if dup:
    warnings.append(f"隣接する同一語尾が{dup}箇所")
if not 14 <= median <= 34:
    warnings.append(f"文長の中央値{median}字(目安14〜34字)")

chars = len(text.replace("\n", ""))
print(f"文字数{chars} / 文数{len(sents)} / 中央値{median}字 / 短文率{short:.0%}")
if chars > 1600:
    warnings.append(f"長め({chars}字。目安800〜1,200字)")

# 口語のリズムを優先するため、語尾・文長は警告どまり(exit 0)。
# 「僕」・マークダウン・絵文字などの表記エラーだけが修正必須(exit 1)。
if warnings:
    print("参考(直すかは文脈判断):")
    for w in warnings:
        print(" ~", w)
if problems:
    print("要修正:")
    for p in problems:
        print(" -", p)
    sys.exit(1)
print("文体チェックOK")
