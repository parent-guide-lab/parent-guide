#!/usr/bin/env bash
# Typography+style gate: mechanically enforce the A·graph-paper design system
# (design-system.json) on web/src so new/edited components cannot drift.
# 2026-10-21 起扫描范围从 cards/ 扩到整个 web/src(全部 .vue + style.css),
# 并把排版规范(docs/typography-spec-2026-10-21.md)纳入机械门禁。
# Rules (deliberately mechanical; project rule: structure to scripts, semantics
# to humans):
#   1. <style> colors: hex only #fff/#ffffff (everything else via CSS vars);
#      rgba only white/graph-blue families —— 仅 cards/(历史疆界;面板/遮罩层
#      的存量色 2026-10-21 记为已知债务,见 docs/typography-spec 遗留节)
#   2. card-header <h3> lines must not contain emoji —— 全部文件
#   3. border-radius values <= 12px —— 仅 cards/
#   4. no linear-gradient —— 仅 cards/
#   4b. no modern color functions (oklch/oklab/lch/lab/color-mix/color()) —— 仅
#       cards/;2026-10-22 引入 garden web-design-engineer 时补的漏点:该 skill
#       主推 oklch() 派生色,裸函数会绕过 hex/rgba 白名单
#   5. font-size whitelist = 字阶 9 档 + 6px SVG 特例 —— **全部文件**(含内联 style)
#   6. font-weight whitelist 400/500/600/700 —— **全部文件**(600=拍板 4b 保留)
#   7. letter-spacing whitelist(2026-10-23 token 化:徽章 .04/卡头 .06/卡内标签
#      .08/详情与分享层小节标题 .2/serif 数字补偿 -.01~-.02/0=显式重置)—— 全部文件
# Run: bash tests/check-card-style.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/web/src"

python3 - "$SRC" << 'PY'
import re, sys, pathlib, unicodedata

files = sorted(pathlib.Path(sys.argv[1]).rglob("*.vue")) + [pathlib.Path(sys.argv[1]) / "style.css"]
assert files, "no source files found"
problems = []

EMOJI_RANGES = ((0x1F300, 0x1FAFF), (0x2600, 0x27BF), (0x2B00, 0x2BFF))
HEX_ALLOW = {"#fff", "#ffffff"}
RGBA_ALLOW = re.compile(r"rgba\(\s*(255\s*,\s*255\s*,\s*255|90\s*,\s*130\s*,\s*180)\b")

def has_emoji(s):
    return any(any(lo <= ord(c) <= hi for lo, hi in EMOJI_RANGES) for c in s)

for p in files:
    text = p.read_text(encoding="utf-8")
    is_card = p.parent.name == "cards"   # 颜色/圆角/渐变=卡片区旧疆界;字阶=全站
    # isolate the <style scoped> block (template colors are data, not styling)
    m = re.search(r"<style[^>]*>(.*?)</style>", text, re.S)
    style = m.group(1) if m else ""
    if is_card:
        for hexv in re.findall(r"#[0-9a-fA-F]{3,8}\b", style):
            if hexv.lower() not in HEX_ALLOW:
                problems.append(f"{p.name}: style 裸 hex {hexv} -- 用 CSS 变量(白名单仅 #fff)")
        for rgba in re.findall(r"rgba?\([^)]*\)", style):
            if rgba.startswith("rgb(") or not RGBA_ALLOW.search(rgba):
                problems.append(f"{p.name}: style 非白名单 rgba {rgba} -- 仅 255,255,255 / 90,130,180 系")
        for br in re.findall(r"border-radius:\s*([\d.]+)px", style):
            if float(br) > 12:
                problems.append(f"{p.name}: border-radius {br}px > 12(图纸风=方角,禁胶囊)")
        if "linear-gradient" in style:
            problems.append(f"{p.name}: linear-gradient 禁用(图纸风=平面)")
        # 新色彩函数同罪:颜色只走 CSS 变量,oklch 类派生色会绕过 hex/rgba 白名单
        for fn in re.findall(r"(?:oklch|oklab|lch|lab|color-mix)\s*\(|(?<![\w-])color\s*\(", style):
            problems.append(f"{p.name}: 色彩函数 {fn}… 禁用 -- 颜色只走 CSS 变量")
    # card headers: <h3> opening lines carry no emoji
    for line in text.splitlines():
        if "<h3" in line and has_emoji(line):
            problems.append(f"{p.name}: 卡头含 emoji -- {line.strip()[:50]}")
    # typography scale whitelist (2026-10-21 规范,design-system.json typography.scale;
    # 6px=GrowthCard SVG 刻度特例;覆盖 style 块与模板内联 style)
    FS_ALLOW = {"6", "10.5", "11.5", "12.5", "14", "15", "16", "20", "22", "24", "27", "54"}
    fs_hits = re.findall(r"font-size:\s*([\d.]+)px", style)
    fs_hits += [m2 for s2 in re.findall(r'style="([^"]*)"', text)
                for m2 in re.findall(r"font-size:\s*([\d.]+)px", s2)]
    for fs in fs_hits:
        if fs not in FS_ALLOW:
            problems.append(f"{p.name}: 字号 {fs}px 不在字阶白名单(10.5/11.5/12.5/14/15/16/20/22/24/27/54)")
    # font-weight whitelist (拍板 4b:600 保留但禁 300/800/900 类新增)
    FW_ALLOW = {"400", "500", "600", "700"}
    for fw in re.findall(r"font-weight:\s*(\d+)", style):
        if fw not in FW_ALLOW:
            problems.append(f"{p.name}: 字重 {fw} 不在白名单(400/500/600/700)")
    # letter-spacing whitelist (2026-10-23 token 化收口,A3;同字号覆盖 style 与内联)
    LS_ALLOW = {"-.02em", "-.01em", "0", ".04em", ".06em", ".08em", ".2em"}
    ls_hits = re.findall(r"letter-spacing:\s*(-?[\d.]+em)", style)
    ls_hits += [m2 for s2 in re.findall(r'style="([^"]*)"', text)
                for m2 in re.findall(r"letter-spacing:\s*(-?[\d.]+em)", s2)]
    for ls in ls_hits:
        if ls not in LS_ALLOW:
            problems.append(f"{p.name}: 字距 {ls} 不在白名单(-.02/-.01/0/.04/.06/.08/.2em)")

if problems:
    print("FAIL: 排版/风格门禁发现问题:")
    for x in problems:
        print("  -", x)
    sys.exit(1)
vue_n = len([f for f in files if f.suffix == '.vue'])
print(f"PASS: typography+style OK ({vue_n} vue + style.css, 规范白名单全绿)")
PY
