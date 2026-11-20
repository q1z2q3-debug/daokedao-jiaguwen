#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""单卷“一图一字一详解”结构校验器。

用法：
    python3 scripts/validate_volume.py --md <卷X.md> --html <卷X·阅读版.html> --docs docs/volumes/vXX.html [--git-ref HEAD]

检查项：
  1. Markdown：12 个“字源”、12 个“详解”、12 个“一字一世界”、12 个“一字一智慧”、12 条拓片行；
  2. 每字顺序：字源 → 详解 → 一字一世界；
  3. 每条详解 195—310 字（目标 200—300），且“形、辞、变、义”四层齐备、顺序正确；
  4. 12 条详解互不重复；
  5. HTML：12 个“详解”标签、12 个“字源”标签，div/p 标签开闭平衡；
  6. HTML 与 Markdown 的详解正文逐条一致；
  7. 图片/字形数量与 git 基线一致（默认 HEAD）；
  8. docs 镜像与阅读版 HTML 逐字节一致。
退出码 0 全过，1 有硬错误，2 有警告（均打印 JSON）。
"""
import argparse, hashlib, json, re, subprocess, sys

CN = "一二三四五六七八九十"


def md_sections(text):
    parts = re.split(r"\n## ", text)
    return ["## " + p for p in parts]


def extract(md, key):
    return re.findall(key + r"：(.*?)(?:\n|$)", md)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--md", required=True)
    ap.add_argument("--html", required=True)
    ap.add_argument("--docs", required=True)
    ap.add_argument("--git-ref", default="HEAD")
    a = ap.parse_args()

    errors, warns, stats = [], [], {}

    with open(a.md, encoding="utf-8") as f:
        md = f.read()
    with open(a.html, encoding="utf-8") as f:
        html = f.read()

    stats["md_chars"] = len(md)

    # ---------- 1. 结构计数 ----------
    stats["字形复写"] = md.count("**字形 · 复写**")
    if stats["字形复写"] == 0:
        warns.append("本卷无“字形 · 复写”段（卷一格式），跳过该项；卷二至卷十一应为 12")
    elif stats["字形复写"] != 12:
        errors.append(f"Markdown 字形复写 {stats['字形复写']}，应为 12")
    for key, want, label in [
        ("**字源**", 12, "字源"),
        ("**详解**", 12, "详解"),
        ("**一字一世界**", 12, "一字一世界"),
        ("**一字一智慧**", 12, "一字一智慧"),
    ]:
        n = md.count(key)
        stats[label] = n
        if n != want:
            errors.append(f"Markdown {label} 数量 {n}，应为 12")
    n = len(re.findall(r"^(?:拓片：|片号：)", md, re.M))
    stats["拓片行"] = n
    if n not in (12, 24):
        errors.append(f"Markdown 拓片/片号行 {n}，应为 12（卷二起）或 24（卷一格式）")

    # ---------- 2. 顺序 ----------
    secs = [s for s in md_sections(md) if re.match(r"## [一二三四五六七八九十]+ · ", s)]
    stats["md_sections"] = len(secs)
    if len(secs) != 12:
        errors.append(f"Markdown 字条 {len(secs)}，应为 12")
    for s in secs:
        head = s.split("\n")[0]
        p_src = s.find("**字源**")
        p_det = s.find("**详解**")
        p_w = s.find("**一字一世界**")
        if not (0 < p_src < p_det < p_w):
            errors.append(f"{head} 顺序错误：字源={p_src} 详解={p_det} 一世界={p_w}")

    # ---------- 3. 详解字数与四层 ----------
    bodies = re.findall(r"\*\*详解\*\*：(.*?)(?:\n|$)", md)
    stats["详解条数"] = len(bodies)
    stats["详解字数"] = []
    for i, b in enumerate(bodies, 1):
        b = b.strip()
        stats["详解字数"].append(len(b))
        if len(b) < 195 or len(b) > 310:
            warns.append(f"第{i}条详解 {len(b)} 字，超出 195—310")
        order = [b.find(k) for k in ("形：", "辞：", "变：", "义：")]
        if any(x < 0 for x in order) or not all(order[i] < order[i + 1] for i in range(3)):
            errors.append(f"第{i}条详解缺“形/辞/变/义”四层或顺序错：{order}")
        if b.startswith("形：") is False:
            errors.append(f"第{i}条详解未以“形：”开头")
    if len(set(bodies)) != len(bodies):
        errors.append("Markdown 存在重复的详解段落")

    # ---------- 3b. 证据边界：详解不得出现本卷未见片号，不得整段照抄字源 ----------
    outside = md
    for b in bodies:
        outside = outside.replace(b, "")
    known_pieces = set(re.findall(r"合\d+(?:正|反|甲|乙)?", outside)) | \
                  set(re.findall(r"英藏\d+", outside)) | \
                  set(re.findall(r"record \d+", outside))
    stats["本卷片号"] = sorted(known_pieces)
    for i, b in enumerate(bodies, 1):
        cited = set(re.findall(r"合\d+(?:正|反|甲|乙)?", b)) | \
                set(re.findall(r"英藏\d+", b)) | \
                set(re.findall(r"record \d+", b))
        missing = sorted(cited - known_pieces)
        if missing:
            errors.append(f"第{i}条详解引用本卷未见片号：{missing}（疑似虚构，须删或改“待核”")

    srcs = re.findall(r"\*\*字源\*\*：(.*?)(?:\n|$)", md)
    for i, (b, src) in enumerate(zip(bodies, srcs), 1):
        if src.strip() and src.strip() in b:
            errors.append(f"第{i}条详解整段照抄字源")
            continue
        # 最长公共子串（长度 ≥40 视为过度复用）
        n = len(src)
        for L in range(min(60, n), 39, -1):
            hit = False
            for k in range(0, n - L + 1):
                if src[k:k + L] and src[k:k + L] in b:
                    hit = True
                    break
            if hit:
                warns.append(f"第{i}条详解与字源有 ≥{L} 字连续重合，请检查是否复述过多")
                break

    # ---------- 4. HTML 计数与标签平衡 ----------
    stats["html_详解标签"] = html.count('<div class="label">详解</div>')
    stats["html_字源标签"] = html.count('<div class="label">字源</div>')
    stats["html_一世界标签"] = html.count('<div class="label">一字一世界</div>')
    if stats["html_详解标签"] != 12:
        errors.append(f"HTML 详解标签 {stats['html_详解标签']}，应为 12")
    if stats["html_字源标签"] != 12:
        errors.append(f"HTML 字源标签 {stats['html_字源标签']}，应为 12")
    if stats["html_一世界标签"] != 12:
        errors.append(f"HTML 一字一世界标签 {stats['html_一世界标签']}，应为 12")

    for tag, pat_open, pat_close in [
        ("div", r"<div[ >]", "</div>"),
        ("p", r"<p[ >]", "</p>"),
        ("figure", r"<figure[ >]", "</figure>"),
        ("section", r"<section[ >]", "</section>"),
    ]:
        o, c = len(re.findall(pat_open, html)), html.count(pat_close)
        stats[f"{tag}_open"], stats[f"{tag}_close"] = o, c
        if o != c:
            errors.append(f"HTML <{tag}> 开 {o} / 闭 {c} 不平衡")

    # ---------- 5. HTML 与 MD 详解一致 ----------
    html_bodies = re.findall(r'<div class="label">详解</div><p>(.*?)</p>', html)
    stats["html_详解正文"] = len(html_bodies)
    if len(html_bodies) != len(bodies):
        errors.append(f"HTML 详解正文 {len(html_bodies)} 条，Markdown {len(bodies)} 条")
    else:
        for i, (h, m) in enumerate(zip(html_bodies, bodies), 1):
            if h.strip() != m.strip():
                errors.append(f"第{i}条详解 HTML 与 Markdown 不一致")

    # ---------- 6. 图片/字形数量与基线一致 ----------
    def count_media(s):
        return {
            "img": len(re.findall(r"<img[ >]", s)),
            "svg": len(re.findall(r"<svg[ >]", s)),
            "figure": len(re.findall(r"<figure[ >]", s)),
            "plate": s.count('class="plate"'),
        }

    now = count_media(html)
    stats["media_now"] = now
    if "字形复写" and stats["字形复写"] == 12:
        try:
            repo = subprocess.run(
                ["git", "-C", str(__import__("os").path.dirname(a.html)), "rev-parse", "--show-toplevel"],
                capture_output=True, text=True, check=True,
            ).stdout.strip()
            import os as _os
            path_in_repo = _os.path.relpath(_os.path.abspath(a.html), repo)
            base = subprocess.run(
                ["git", "-C", repo, "show", f"{a.git_ref}:{path_in_repo}"],
                capture_output=True, text=True, check=True,
            ).stdout
            stats["media_base"] = count_media(base)
            for k, v in now.items():
                if stats["media_base"].get(k) != v:
                    errors.append(f"图片/字形 {k} 数量 {v}，基线 {stats['media_base'].get(k)}")
        except subprocess.CalledProcessError as e:
            warns.append(f"取 git 基线失败（{e}），跳过图片数量比对")
    else:
        warns.append("卷一格式，跳过图片数量基线比对")

    # ---------- 7. docs 镜像一致 ----------
    def md5(p):
        with open(p, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()

    try:
        h1, h2 = md5(a.html), md5(a.docs)
        stats["md5_book"], stats["md5_docs"] = h1, h2
        if h1 != h2:
            errors.append(f"docs 镜像不一致：book={h1} docs={h2}")
    except FileNotFoundError as e:
        errors.append(f"docs 镜像缺失：{e}")

    print(json.dumps({"ok": not errors, "errors": errors, "warnings": warns, "stats": stats},
                     ensure_ascii=False, indent=2))
    sys.exit(1 if errors else (2 if warns else 0))


if __name__ == "__main__":
    main()
