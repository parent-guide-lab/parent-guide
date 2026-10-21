#!/usr/bin/env bash
# Unit test for daily-tips.sh (signal mode + record mode) against fixtures.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SCRIPT="$ROOT/skills/parent-guide/scripts/daily-tips.sh"
FIX="$ROOT/tests/fixtures/test-env/data"

# --- signal mode on fixture (no daily-tips.json yet) ---
OUT="$(bash "$SCRIPT" "$FIX")"
printf '%s\n' "$OUT" | grep -q "每日贴士候选"  || { echo "FAIL: no header"; exit 1; }
printf '%s\n' "$OUT" | grep -q "\[到期回访\]"   || { echo "FAIL: no followup section"; exit 1; }
printf '%s\n' "$OUT" | grep -q "\[就医待办\]"   || { echo "FAIL: no pending-care section"; exit 1; }
printf '%s\n' "$OUT" | grep -q "P1"             || { echo "FAIL: no issue id"; exit 1; }
printf '%s\n' "$OUT" | grep -q "how1"           || { echo "FAIL: no how rotation keys"; exit 1; }
printf '%s\n' "$OUT" | grep -q "anticipatory.md" || { echo "FAIL: no calendar-node handoff line"; exit 1; }
printf '%s\n' "$OUT" | grep -q "\[检查点\]"     || { echo "FAIL: no checkpoint line"; exit 1; }
printf '%s\n' "$OUT" | grep -q "无记录"          || { echo "FAIL: no empty-history line"; exit 1; }
printf '%s\n' "$OUT" | grep -q "\[近期事件\]"    || { echo "FAIL: no recent-events section"; exit 1; }

# --- record + dedup replay in a writable copy ---
T="$(mktemp -d)"
cp "$FIX/child.json" "$T/"
bash "$SCRIPT" record "$T" closedloop:P1-followup:main action:P1-how2 activity:water-play \
  || { echo "FAIL: record failed"; exit 1; }
[ -f "$T/daily-tips.json" ] || { echo "FAIL: daily-tips.json not created"; exit 1; }
python3 - "$T/daily-tips.json" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1], encoding="utf-8"))
days = doc["days"]
assert len(days) == 1, f"want 1 day, got {list(days)}"
tips = list(days.values())[0]
assert [t["key"] for t in tips] == ["P1-followup", "P1-how2", "water-play"]
assert sum(1 for t in tips if t["main"]) == 1 and tips[0]["main"]
print("record structure OK")
PY

OUT="$(bash "$SCRIPT" "$T")"
printf '%s\n' "$OUT" | grep -q "主推 closedloop:P1-followup" || { echo "FAIL: history replay missing main flag"; exit 1; }
printf '%s\n' "$OUT" | grep -q "action:P1-how2" || { echo "FAIL: history replay missing entry"; exit 1; }
printf '%s\n' "$OUT" | grep -q "无记录" && { echo "FAIL: empty-history line with history present"; exit 1; }

# --- same-day re-record overwrites ---
bash "$SCRIPT" record "$T" milestone:m32-script activity:leaf-sort
OUT="$(bash "$SCRIPT" "$T")"
printf '%s\n' "$OUT" | grep -q "P1-how2" && { echo "FAIL: overwrite left stale entries"; exit 1; }
printf '%s\n' "$OUT" | grep -q "milestone:m32-script" || { echo "FAIL: overwrite entry missing"; exit 1; }

# --- 7-day window: entries older than 7 days are not replayed ---
python3 - "$T/daily-tips.json" <<'PY'
import json, sys
from datetime import date, timedelta
p = sys.argv[1]
doc = json.load(open(p, encoding="utf-8"))
old = (date.today() - timedelta(days=10)).isoformat()
doc["days"][old] = [{"category": "activity", "key": "ancient-game", "main": False}]
json.dump(doc, open(p, "w", encoding="utf-8"), ensure_ascii=False)
PY
OUT="$(bash "$SCRIPT" "$T")"
printf '%s\n' "$OUT" | grep -q "ancient-game" && { echo "FAIL: >7d entry replayed"; exit 1; }

# --- validation: two mains / bad category / dup key all fail fast ---
if bash "$SCRIPT" record "$T" a:1:main b:2:main 2>/dev/null; then
  echo "FAIL: two mains accepted"; exit 1
fi
if bash "$SCRIPT" record "$T" bogus:key1 2>/dev/null; then
  echo "FAIL: bad category accepted"; exit 1
fi
if bash "$SCRIPT" record "$T" activity:dup action:dup 2>/dev/null; then
  echo "FAIL: duplicate key accepted"; exit 1
fi

# --- malformed history file: signal mode must fail loudly, not limp on ---
echo "not json" > "$T/daily-tips.json"
if bash "$SCRIPT" "$T" 2>/dev/null; then
  echo "FAIL: malformed daily-tips.json not caught"; exit 1
fi

rm -rf "$T"

# --- feishu push: dry-run needs no webhook config, title from # heading ---
F="$(mktemp)"
printf '# 今日贴士 · 2026-10-20 周二 · 桃子 30 月龄 · 秋\n\n🔔 主推内容一行。\n\n依据:fixture\n' > "$F"
CARD="$(python3 "$ROOT/skills/parent-guide/scripts/feishu-tip.py" "$F" --dry-run)"
printf '%s\n' "$CARD" | grep -q '"msg_type": "interactive"' || { echo "FAIL: no interactive card"; exit 1; }
printf '%s\n' "$CARD" | grep -q "今日贴士 · 2026-10-20" || { echo "FAIL: title not from heading"; exit 1; }
printf '%s\n' "$CARD" | grep -q "主推内容一行" || { echo "FAIL: body not in card"; exit 1; }
if printf '%s\n' "$CARD" | grep -q "^# "; then { echo "FAIL: heading leaked into body"; exit 1; }; fi
rm -f "$F"

echo "PASS: daily-tips (signal + record + dedup window + validation + feishu dry-run)"
