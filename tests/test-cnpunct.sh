#!/usr/bin/env bash
# cnpunct(排版规范 8b)fixture 测试:CJK 邻接半角标点转全角;英文语境/行内代码/
# md 链接保护。双实现中的 Python 侧(knowledge_render.cnpunct,服务 app 知识面板
# 与 site 构建);JS 侧(util.cnpunct)由浏览器侧验证覆盖。
# 前端静态扫描(2026-10-24 增补):扫 web/src 模板文本节点与字符串字面量里的
# CJK 邻接半角标点——8b 首轮只接了 4 个组件,静态文案与内建卡自由文本字段成了
# 漏网重灾区;本门禁防回归。{{插值}}/${插值} 置换为占位符(插值内容由渲染层
# cnpunct 兜底,字面扫描判不了邻接);白名单仅收「非展示用途」字符串,须注理由
# (如与档案模板逐字对账的占位匹配串)。
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
    ("口径(AAP, 2019)。", "口径（AAP, 2019）。"),          # 外全(CY/T 154 夹英文;闭括号后随全角句号→补齐全角)
    ("顺序每晚一致(约30-40min):洗漱", "顺序每晚一致（约30-40min）：洗漱"),  # 链式缺口:闭括号补第三遍
    ("免费(停会员业务);A3 Pro", "免费（停会员业务）；A3 Pro"),  # 链式缺口二层:不动点迭代(真实档案判例)
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

# ── 前端静态扫描 ──────────────────────────────────────────────
python3 - "$ROOT" << 'PY'
import re, sys, glob
root = sys.argv[1]

CN = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
PAT = re.compile('(?:(' + CN + ')([,;:!?()])|([,;:!?()])(' + CN + '))')
PH = '\ue000'  # 插值/标签占位:邻接语义视作「未知」,不算 CJK 也不算标点

# 白名单两条通道,新条目必须注理由,且优先考虑改代码。
#   FILE:整文件豁免——纯数据源,8b「半角源不动」,消费它的渲染点已接 cnpunct。
ALLOW_FILE = {
    'web/src/data/ticker-tips.js':
        '速记 tips 数据源,TickerBar 以 cnpunct(tip.t) 归一后展示',
    'web/src/lib/anticipatory-ref.js':
        '前瞻节点表数据源,name/note 经 AnticipatoryCard cnpunct 归一后展示',
}
#   LINE:行级豁免(键=预处理后整行 strip)——档案占位对账串/正则等代码语境。
ALLOW_LINE = {
    ('web/src/components/cards/ProfileCard.vue',
     "const P = new Set(['语言发展一句话', '气质特点一句话', '安抚物(如有)',"):
        '与 child.json 模板占位逐字对账的匹配串,非展示文本',
    ('web/src/components/cards/ProfileCard.vue',
     "'家庭管教口径、长辈观点等背景', '过敏史(食物/药物/湿疹;没有写无)',"): '同上',
    ('web/src/components/cards/ProfileCard.vue', "'兄弟姐妹(没有写无)',"): '同上',
    ('web/src/components/cards/ProfileCard.vue',
     "'长期健康背景(湿疹体质/哮喘/反复中耳炎/手术史;没有写无)',"): '同上',
    ('web/src/lib/util.js', "const m = cnpunct(seg).match(/^([^：]{1,8})：/)"):
        "segLabel 分段正则,代码语境非展示",
    ('web/src/components/cards/FocusCard.vue',
     "const m = String(t || '').split(/[:：]/)"):
        "splitTopic 冒号切分正则,代码语境非展示",
}

def preprocess(src):
    keep_nl = lambda m: PH + '\n' * m.group(0).count('\n')
    src = re.sub(r'<!--.*?-->', keep_nl, src, flags=re.S)     # 模板注释(保行号)
    src = re.sub(r'/\*.*?\*/', lambda m: '\n' * m.group(0).count('\n'),
                 src, flags=re.S)                             # 块注释
    src = src.replace('://', ':@/@')                          # 先保 URL,防行注释误吞
    src = re.sub(r'(?m)(?<!:)//(?!/).*$', '', src)            # 行注释
    src = src.replace(':@/@', '://')
    src = re.sub(r'\{\{.*?\}\}', keep_nl, src, flags=re.S)    # 模板插值→占位
    src = re.sub(r'\$\{[^}]*\}', keep_nl, src)                # JS 模板串插值→占位
    return src

bad = 0
files = sorted(glob.glob(root + '/web/src/**/*.vue', recursive=True)
               + glob.glob(root + '/web/src/**/*.js'))
for f in files:
    rel = f[len(root) + 1:]
    if rel in ALLOW_FILE:
        continue
    src = preprocess(open(f).read())
    # 单遍逐行:字符串字面量/属性值/模板文本都在行内,邻接语义天然保留;
    # 代码行 CJK 只出现在字符串里,行扫描不会误伤纯代码。
    for no, ln in enumerate(src.split('\n'), 1):
        if (rel, ln.strip()) in ALLOW_LINE:
            continue
        for m in PAT.finditer(ln):
            print(f'FAIL {rel}:{no} …{m.group(0)}…')
            bad += 1

if bad:
    print(f'FAIL: 前端静态扫描 {bad} 处 CJK 邻接半角标点'
          '(渲染点接 cnpunct;静态中文文案直接写全角)')
    sys.exit(1)
print(f'PASS: 前端静态扫描(web/src 全量 0 处;白名单 FILE {len(ALLOW_FILE)}'
      f'/LINE {len(ALLOW_LINE)})')
PY

# ── e2e 对抗档真渲染(2026-10-24 增补):静态扫描的盲区=插值内容({{x}} 被占位),
# 「新组件渲染数据字段忘了接 cnpunct」正是 8b 首轮漏网的真实成因。本节把每个
# 自由文本字段都塞进半角标点金丝雀的 fixture 起服务真渲染,DOM 逐文本节点断言:
# 0 处 CJK 邻接半角 + 金丝雀已转全角(防 fixture 没渲染导致 0 命中的假绿)。
CHROME=""
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "$(command -v google-chrome || true)" "$(command -v chromium || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && CHROME="$c" && break
done
if [ -z "$CHROME" ]; then
    echo "SKIP: e2e 对抗档真渲染(未找到 Chrome/Chromium)"
    exit 0
fi

FIXDIR="$ROOT/tests/fixtures/cnpunct-e2e"
PORT=8799
python3 "$ROOT/server.py" --port "$PORT" --data "$FIXDIR" >/dev/null 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 40); do
    curl -s -o /dev/null "http://localhost:$PORT/" && break
    sleep 0.25
done

# 服务冷启动+Chrome 虚拟时间竞态(publish 电池下首启慢):预热后重试至多 3 次,
# 以「金丝雀全角形态已出现在 DOM」为渲染完成判据——否则宁可 FAIL 不出假绿。
CANARY_CONVERTED='半角（金丝雀），冒号：测试；问？叹！'
DUMP_OK=0
for attempt in 1 2 3; do
    curl -s -o /dev/null "http://localhost:$PORT/"    # 预热
    sleep 1
    "$CHROME" --headless=new --disable-gpu --virtual-time-budget=12000 \
        --dump-dom "http://localhost:$PORT/" > /tmp/cnpunct-e2e-dom.html 2>/dev/null
    if grep -q "$CANARY_CONVERTED" /tmp/cnpunct-e2e-dom.html 2>/dev/null; then
        DUMP_OK=1; break
    fi
done
kill "$SRV" 2>/dev/null || true
wait "$SRV" 2>/dev/null || true
trap - EXIT   # 服务已收尾,卸掉 trap 防 kill 死进程污染退出码
if [ "$DUMP_OK" != 1 ]; then
    echo "FAIL: e2e 对抗档 3 次尝试均未渲染出金丝雀(服务/浏览器竞态或渲染层未接)"
    exit 1
fi

python3 - << 'PY'
import re
from html.parser import HTMLParser

CN = r'[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]'
PAT = re.compile('(?:(' + CN + ')([,;:!?()])|([,;:!?()])(' + CN + '))')
CONVERTED = '半角（金丝雀），冒号：测试；问？叹！'

class P(HTMLParser):
    def __init__(self):
        super().__init__(); self.bad = []; self.skip = 0; self.text = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.skip = max(0, self.skip - 1)
    def handle_data(self, d):
        if self.skip: return
        self.text.append(d)
        for m in PAT.finditer(d):
            self.bad.append((m.group(0), d[max(0, m.start()-14):m.end()+14].strip()))

html = open('/tmp/cnpunct-e2e-dom.html').read()
assert len(html) > 50000, f'页面疑似未渲染(dump 仅 {len(html)} 字节)'
p = P(); p.feed(html)
joined = ''.join(p.text)
assert CONVERTED in joined, \
    '金丝雀全角形态未出现——fixture 没渲染或渲染层没接 cnpunct(假绿保护触发)'
if p.bad:
    for frag, ctx in p.bad[:15]:
        print(f'FAIL e2e …{frag}…  ←「{ctx}」')
    raise SystemExit(f'FAIL: e2e 对抗档真渲染 {len(p.bad)} 处 CJK 邻接半角标点残留'
                     '(有渲染点漏接 cnpunct,看上下文定位组件)')
print('PASS: e2e 对抗档真渲染(全字段半角金丝雀 fixture,DOM 文本节点 0 残留+正向断言命中)')
PY
