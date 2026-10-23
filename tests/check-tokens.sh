#!/usr/bin/env bash
# token sync + contrast gate(2026-10-21):design-system.json = 色板单一来源。
# ①同步:web/src/style.css :root 与 design-system.json color 逐值一致
#   (site 不查——build-site.py 直接从 json 生成,结构上不可能分叉);
# ②对比度:文字色于白底(卡面)≥4.5;状态色于各自浅底 ≥4.5(WCAG AA 正文线;
#   2026-10-21 状态色已按双场景达标取值)。
# 已知边界(不设门,review 纪律):sub 不落 accent-soft 底(4.39,用 ink-blue 代替)。
# Run: bash tests/check-tokens.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$ROOT" << 'PY'
import json, re, sys, pathlib

root = pathlib.Path(sys.argv[1])
ds = json.loads((root / "design-system.json").read_text("utf-8"))
light, sem = ds["color"]["light"], ds["color"]["semantic"]
ident = ds["color"].get("identity", {})
css = (root / "web/src/style.css").read_text("utf-8")
m = re.search(r":root\s*\{(.*?)\}", css, re.S)
assert m, "style.css :root not found"
cv = dict(re.findall(r"(--[\w-]+):\s*([^;]+);", m.group(1)))

problems = []
sync = [("--bg", light["bg"]), ("--card", light["card"]), ("--ink", light["fg"]),
        ("--ink-blue", light["primary"]), ("--sub", light["muted"]),
        ("--accent", light["accent"]), ("--accent-soft", light["accentSoft"]),
        ("--line", light["border"]), ("--grid", light["grid"]),
        ("--grid-line", light["gridLine"]), ("--hint", light["hint"]),
        ("--ok", sem["ok"]), ("--watch", sem["watch"]),
        ("--todo", sem["todo"]), ("--err", sem["err"]),
        # D 分享层奶油纸 + B 身份色(2026-10-23;identity 仅真新色相,复用族不重复设 token)
        ("--cream", light["cream"]), ("--cream-line", light["creamLine"]),
        ("--cream-grid", light["creamGrid"]), ("--cream-band", light["creamBand"]),
        ("--id-violet", ident.get("violet", "")), ("--id-teal", ident.get("teal", "")),
        ("--id-violet-bg", ident.get("violetBg", "")),
        ("--id-teal-bg", ident.get("tealBg", ""))]
for var, want in sync:
    got = cv.get(var, "").strip()
    if got.lower() != str(want).lower():
        problems.append(f"色板分叉: style.css {var}={got} != design-system {want}")

def lum(hexc):
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    f = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ratio(fg, bg):
    l1, l2 = sorted([lum(fg), lum(bg)], reverse=True)
    return (l1 + 0.05) / (l2 + 0.05)

def hx(v):
    v = v.strip()
    assert v.startswith("#") and len(v) == 7, f"非 hex 色值: {v}"
    return v

pairs = ([("正文/强调/辅助/状态 于卡面(白底)", hx(cv[v]), light["card"], 4.5)
          for v in ("--ink", "--ink-blue", "--sub", "--err", "--ok", "--watch", "--todo")]
         + [("hint 于提示底", hx(cv["--hint"]), hx(cv["--accent-soft"]), 4.5)]
         + [(f"{v} 于其浅底", hx(cv[v]), hx(cv[f"{v}-bg"]), 4.5)
            for v in ("--ok", "--watch", "--todo", "--err")]
         # B 身份色(2026-10-23 入册+卡面落地):白底 + 各自浅底双场景,与状态色同纪律
         + [(f"身份 {v} 于白底", hx(cv[v]), light["card"], 4.5)
            for v in ("--id-violet", "--id-teal")]
         + [(f"身份 {v} 于其浅底", hx(cv[v]), hx(cv[f"{v}-bg"]), 4.5)
            for v in ("--id-violet", "--id-teal")]
         + [("hint 于台账浅底", hx(cv["--hint"]), hx(cv["--hint-bg"]), 4.5)]
         # 档案墨蓝卡头(2026-10-23 补拍):ink-blue 于 accent-soft,复用族不设新 token
         + [("身份 ink-blue 于档案浅底", hx(cv["--ink-blue"]), hx(cv["--accent-soft"]), 4.5)]
         # D 分享层(2026-10-23):家人卡文字色于奶油纸传阅品底
         + [(f"D {v} 于奶油纸", hx(cv[v]), hx(cv["--cream"]), 4.5)
            for v in ("--ink", "--ink-blue", "--sub", "--todo", "--hint", "--watch", "--ok")])
for name, fg, bg, need in pairs:
    r = ratio(fg, bg)
    if r < need:
        problems.append(f"对比度不足: {name} {fg} on {bg} = {r:.2f} < {need}")

if problems:
    print("FAIL: token 同步/对比度门禁发现问题:")
    for x in problems:
        print("  -", x)
    sys.exit(1)
print(f"PASS: tokens synced + contrast OK ({len(sync)} 色值同步, {len(pairs)} 配对 ≥4.5)")
PY
