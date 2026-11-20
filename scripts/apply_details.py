#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把“详解”批量写入单卷 Markdown / 阅读版 HTML / docs 镜像。

用法：
    python3 scripts/apply_details.py --vol 卷二 --details details-02.json

details JSON 形如：
    [{"char": "身", "text": "形：…… 辞：…… 变：…… 义：……"}, …]   # 12 条，按本卷字序

行为：
  1. Markdown：在每字“**字源**：……”段之后插入（或替换）“**详解**：……”，位于“**一字一世界**”之前；
  2. 阅读版 HTML：在 `<div class="label">字源</div><p>…</p>` 之后插入（或替换）
     `<div class="label">详解</div><p>…</p>`，行内同排，风格与卷一一致；
  3. 卷首标语：Markdown 更新为“一图一字 · 一字一详解 · 一字一世界 · 一字一智慧”，
     HTML 封面 sub 更新为“一图一字 · 一字一详解”；
  4. 卷末补“## 说明”（仅当尚无该节），措辞与卷一一致；
  5. `cp` 阅读版 HTML 到 docs/volumes/vXX.html（逐字节一致）。
不做事：不改动图片、图注、释文、版权行、字数统计以外的任何正文。
"""
import argparse, html as htmlmod, json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGLINE_MD = "> 一图一字 · 一字一详解 · 一字一世界 · 一字一智慧"
NOTE = ("## 说明\n\n本卷十二字已补齐“一图一字一详解”的体例：每字一图、一段字源、一段详解、"
        "一世界、一智慧，并附该片释文摘句。详解所据为字形库、合集号与该片释文；"
        "拓片—摹本的逐字对照仍待补，凡未取得高清原拓与同版摹本的字，继续标“待补”。\n")

CN_NUM = "一二三四五六七八九十"


def vol_num(name):
    """把“卷二十一”“卷七十七”一类卷名转成阿拉伯数字。"""
    m = re.search(r"卷([一二三四五六七八九十]+)", name)
    if not m:
        raise SystemExit(f"无法从卷名取卷号：{name}")
    d = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
    s = m.group(1)
    if "十" not in s:
        return d[s]
    left, _, right = s.partition("十")
    tens = d[left] if left else 1
    ones = d[right] if right else 0
    return tens * 10 + ones


def patch_md(path, details):
    text = open(path, encoding="utf-8").read()
    if TAGLINE_MD not in text:
        text = re.sub(r"\n> 一字一世界 · 一字一智慧\n", "\n" + TAGLINE_MD + "\n", text, count=1)

    parts = re.split(r"\n(?=## )", text)
    done = 0
    for i, part in enumerate(parts):
        if not re.match(r"## [一二三四五六七八九十]+ · ", part):
            continue
        head = part.split("\n")[0]
        char = head.split("·")[1].strip()
        item = details.get(char)
        if not item:
            continue
        body = item.strip()
        if "**详解**：" in part:
            part = re.sub(r"\*\*详解\*\*：.*?\n", "**详解**：" + body + "\n", part)
        else:
            m = re.search(r"\*\*字源\*\*：.*\n", part)
            if not m:
                raise SystemExit(f"{path} 的“{char}”缺字源段")
            part = part[:m.end()] + "\n**详解**：" + body + "\n" + part[m.end():]
        parts[i] = part
        done += 1
    if done != len(details):
        missing = [c for c in details if c not in [p.split("\n")[0].split("·")[1].strip()
                                                   for p in parts if re.match(r"## [一二三四五六七八九十]+ · ", p)]]
        print(json.dumps({"md_written": done, "missing": missing}, ensure_ascii=False))
    text = "\n".join(parts)
    if "## 说明" not in text:
        text = text.rstrip("\n") + "\n\n" + NOTE
    open(path, "w", encoding="utf-8").write(text)
    return done


def patch_html(path, details):
    text = open(path, encoding="utf-8").read()
    if '<div class="sub">一图一字 · 一字一详解</div>' not in text:
        text = text.replace('<div class="sub">一字一世界 · 一字一智慧</div>',
                            '<div class="sub">一图一字 · 一字一详解</div>')

    # 以字头定位每段：<article class="entry" id="vXeN"> … <h2 class="zi">字</h2>
    entries = list(re.finditer(r'<article class="entry"[^>]*>(?:(?!</article>).)*</article>', text, re.S))
    if len(entries) != 12:
        raise SystemExit(f"{path} 命中 {len(entries)} 个 article，应为 12")
    done, out = 0, []
    last = 0
    for m in entries:
        blk = m.group(0)
        cm = re.search(r'<h2 class="zi">(.*?)</h2>', blk)
        char = re.sub(r"<.*?>", "", cm.group(1)).strip() if cm else ""
        item = details.get(char)
        if item:
            esc = htmlmod.escape(item.strip(), quote=False)
            new = f'<div class="label">详解</div><p>{esc}</p>'
            if '<div class="label">详解</div>' in blk:
                blk = re.sub(r'<div class="label">详解</div><p>.*?</p>', new, blk, count=1)
            else:
                pm = re.search(r'<div class="label">字源</div><p>.*?</p>', blk)
                if not pm:
                    raise SystemExit(f"{path} 的“{char}”缺字源节点")
                blk = blk[:pm.end()] + new + blk[pm.end():]
            done += 1
        out.append(text[last:m.start()])
        out.append(blk)
        last = m.end()
    out.append(text[last:])
    open(path, "w", encoding="utf-8").write("".join(out))
    return done


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--vol", required=True, help="卷名，如 卷二")
    ap.add_argument("--details", required=True, help="12 条详解的 JSON")
    a = ap.parse_args()

    n = vol_num(a.vol)
    v = f"{n:02d}"
    md = os.path.join(ROOT, "book", f"润泽说-道可道之甲骨文·{a.vol}.md")
    htm = os.path.join(ROOT, "book", f"润泽说-道可道之甲骨文·{a.vol}·阅读版.html")
    docs = os.path.join(ROOT, "docs", "volumes", f"v{v}.html")

    raw = json.load(open(a.details, encoding="utf-8"))
    dups = [c for c in {d["char"] for d in raw} if [d["char"] for d in raw].count(c) > 1]
    details = {d["char"]: d["text"] for d in raw}
    md_n = patch_md(md, details)
    html_n = patch_html(htm, details)
    # 保留站点镜像原有 SEO 元信息：先把它并回阅读版，再整文件复制，
    # 这样 docs 与阅读版一致，同时 canonical / OG / JSON-LD 不丢。
    seo_note = "unchanged"
    if os.path.exists(docs):
        doc = open(docs, encoding="utf-8").read()
        link = doc.find('<link rel="canonical"')
        end = doc.find('</script>', link) + len('</script>') if link >= 0 else -1
        if link >= 0 and end > link:
            blk = doc[link:end].replace("一字一世界 · 一字一智慧",
                                        "一图一字 · 一字一详解 · 一字一世界 · 一字一智慧")
            body = open(htm, encoding="utf-8").read()
            if 'rel="canonical"' not in body:
                body = body.replace("</head>", blk + "</head>", 1)
                open(htm, "w", encoding="utf-8").write(body)
                seo_note = "injected"
            else:
                seo_note = "already-present"
    shutil.copyfile(htm, docs)

    report = {"vol": a.vol, "md_patched": md_n, "html_patched": html_n, "seo": seo_note,
              "duplicate_chars": dups, "docs": docs,
              "md": md, "html": htm}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    md_total = open(md, encoding="utf-8").read().count("**详解**")
    html_total = open(htm, encoding="utf-8").read().count('<div class="label">详解</div>')
    if md_n != len(details) or html_n != len(details) or md_total != 12 or html_total != 12:
        print(json.dumps({"md_patched": md_n, "html_patched": html_n,
                          "md_total": md_total, "html_total": html_total,
                          "expected": len(details)}, ensure_ascii=False))
        sys.exit(1)


if __name__ == "__main__":
    main()
