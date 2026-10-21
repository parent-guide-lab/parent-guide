#!/usr/bin/env bash
# cnpunct(排版规范 8b)fixture 测试:CJK 邻接半角标点转全角;英文语境/行内代码/
# md 链接保护。双实现中的 Python 侧(knowledge_render.cnpunct,服务 app 知识面板
# 与 site 构建);JS 侧(util.cnpunct)由浏览器侧验证覆盖。
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

python3 - "$ROOT" << 'PY'
import sys
sys.path.insert(0, sys.argv[1])
from knowledge_render import cnpunct, md_to_html

cases = [
    # (输入, 期望)
    ("睡眠规律比「几点睡」更重要:每天入睡时间稳定", "睡眠规律比「几点睡」更重要：每天入睡时间稳定"),
    ("其一;其二", "其一；其二"),
    ("口径(AAP, 2019)。", "口径（AAP, 2019）。"),          # 外全内半(CY/T 154 夹英文)
    ("d=0.39, p<0.05", "d=0.39, p<0.05"),                   # 纯英文语境不动
    ("10-17 与 2026-10-21", "10-17 与 2026-10-21"),
    ("14:30 开饭", "14:30 开饭"),                             # 数字间冒号不动
    ("详见 https://a.com 的说明", "详见 https://a.com 的说明"),
    ("看看 `font-size: 13px` 的写法", "看看 `font-size: 13px` 的写法"),  # 行内代码保护
    ("「哭了不能抱,会惯坏」是误区——可以抱着他,同时坚持不给那块糖",
     "「哭了不能抱，会惯坏」是误区——可以抱着他，同时坚持不给那块糖"),
    ("处理见 §3 晨醒)", "处理见 §3 晨醒）"),                  # 前邻中文标点判定
]
for src, want in cases:
    got = cnpunct(src)
    assert got == want, f"cnpunct({src!r})\n  got  {got!r}\n  want {want!r}"
print(f"PASS: cnpunct {len(cases)} fixtures")

# md_to_html 集成:链接语法完好 + 正文转换生效
html = md_to_html("# T\n\n见[中文](https://a.com/x)的说明:口径(AAP, 2019)。\n")
assert '<a href="https://a.com/x">中文</a>的说明：口径（AAP, 2019）。' in html, html
# 代码块整体不动
html2 = md_to_html("# T\n\n```\nfont-size: 13px; color: red\n```\n")
assert "font-size: 13px; color: red" in html2 and "；" not in html2, html2
print("PASS: md_to_html 集成(链接/代码块保护)")
PY
