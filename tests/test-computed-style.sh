#!/usr/bin/env bash
# 计算值全页扫 e2e(2026-11-11):静态门禁(check-card-style)的盲区=声明顺序/
# 特异性/继承链事故——「代码里写的值」合法但「实际渲染的值」违规(tgl 判例:写了
# 12.5px 实渲染 16px)。本测试借 App.vue 的 #style-sweep 探针起服务真渲染,
# headless Chrome --dump-dom 后断言隐藏节点里的违规清单为空。
# 防假绿:金丝雀=探针节点必须存在且为合法 JSON(探针没跑=FAIL,不是 PASS)。
# Run: bash tests/test-computed-style.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

CHROME=""
for c in "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
         "$(command -v google-chrome || true)" "$(command -v chromium || true)"; do
    [ -n "$c" ] && [ -x "$c" ] && CHROME="$c" && break
done
if [ -z "$CHROME" ]; then
    echo "SKIP: 计算值全页扫(未找到 Chrome/Chromium)"
    exit 0
fi

FIXDIR="$ROOT/tests/fixtures/cnpunct-e2e"   # 全卡型金丝雀 fixture(只读复用)
PORT=8798
python3 "$ROOT/server.py" --port "$PORT" --data "$FIXDIR" >/dev/null 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
for i in $(seq 1 40); do
    curl -s -o /dev/null "http://localhost:$PORT/" && break
    sleep 0.25
done

# 渲染完成判据=探针节点存在(防「页面没渲染完就 dump」的假绿);重试至多 3 次
OUT=/tmp/computed-sweep-dom.html
PROBE_OK=0
for attempt in 1 2 3; do
    curl -s -o /dev/null "http://localhost:$PORT/"    # 预热
    sleep 1
    "$CHROME" --headless=new --disable-gpu --virtual-time-budget=12000 \
        --dump-dom "http://localhost:$PORT/#style-sweep" > "$OUT" 2>/dev/null
    if grep -q 'id="style-sweep-result"' "$OUT" 2>/dev/null; then
        PROBE_OK=1; break
    fi
done
kill "$SRV" 2>/dev/null || true
wait "$SRV" 2>/dev/null || true
trap - EXIT   # 卸 trap 防 kill 死进程污染退出码(判例:EXIT trap 污染)
if [ "$PROBE_OK" != 1 ]; then
    echo "FAIL: 计算值全页扫 3 次尝试均未见探针节点(服务/浏览器竞态或探针未挂)"
    exit 1
fi

python3 - "$OUT" <<'PY'
import json, re, sys
html = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r'<pre id="style-sweep-result"[^>]*>(.*?)</pre>', html, re.S)
if not m:
    print("FAIL: 探针节点存在但未捕获到内容")
    sys.exit(1)
try:
    data = json.loads(m.group(1).strip().replace("&quot;", '"'))
except ValueError:
    print("FAIL: 探针输出不是合法 JSON")
    sys.exit(1)
if data.get("violations"):
    print("FAIL: 计算值全页扫发现违规(实际渲染值出字阶/字重白名单):")
    for v in data["violations"]:
        print("  -", v)
    sys.exit(1)
print("PASS: 计算值全页扫(真渲染,字号/字重白名单零违规)")
PY
