#!/usr/bin/env bash
# Daily-tip candidate signals (daily 档): mechanical extraction only --
# today/overdue followups, pending-care age, claimed-reminder distance,
# issue how-lists (action rotation keys), next milestone checkpoint, and
# the 7-day dedup history. Selection/wording/activity composition stay on
# the read side (references/daily.md). Structure to scripts, semantics to
# humans.
# Usage:
#   daily-tips.sh [data_dir]                            # candidate signals
#   daily-tips.sh record [data_dir] cat:key[:main] ...  # record today's tips
#     cat: closedloop|action|anticipatory|milestone|activity|readaloud|weekly
#     :main marks the single headline tip; same-day re-record overwrites.
# Contract: child.json field structure is this script's contract --
# renaming fields requires updating this script (and vice versa).
set -euo pipefail

if [ "${1:-}" = "record" ]; then
  shift
  DATA_DIR="${1:-./data}"
  [ -d "$DATA_DIR" ] || { echo "FAIL: data dir not found: $DATA_DIR" >&2; exit 1; }
  [ $# -ge 2 ] || { echo "usage: daily-tips.sh record [data_dir] cat:key[:main] ..." >&2; exit 1; }
  shift
  exec python3 - "$DATA_DIR/daily-tips.json" "$@" <<'PYREC'
import json, sys
from datetime import date

path, entries = sys.argv[1], sys.argv[2:]
CATS = ("closedloop", "action", "anticipatory", "milestone", "activity",
        "readaloud", "weekly")
today = date.today().isoformat()
out, keys, mains = [], [], []
for e in entries:
    parts = e.split(":")
    if len(parts) not in (2, 3) or parts[0] not in CATS or not parts[1]:
        sys.exit(f"FAIL: bad entry '{e}' (want cat:key[:main], cat in {CATS})")
    if len(parts) == 3 and parts[2] != "main":
        sys.exit(f"FAIL: bad entry '{e}' (third field may only be 'main')")
    if parts[1] in keys:
        sys.exit(f"FAIL: duplicate key '{parts[1]}' in one day")
    if len(parts) == 3:
        if mains:
            sys.exit(f"FAIL: more than one :main ('{mains[0]}' and '{parts[1]}')")
        mains.append(parts[1])
    out.append({"category": parts[0], "key": parts[1], "main": len(parts) == 3})
    keys.append(parts[1])

try:
    with open(path, encoding="utf-8") as f:
        doc = json.load(f)
except FileNotFoundError:
    doc = {"days": {}}
if not isinstance(doc.get("days"), dict):
    sys.exit("FAIL: daily-tips.json malformed (want {\"days\": {...}})")
doc["days"][today] = out
doc["days"] = {d: doc["days"][d] for d in sorted(doc["days"])}
with open(path, "w", encoding="utf-8") as f:
    json.dump(doc, f, ensure_ascii=False, indent=1)
    f.write("\n")
print(f"已记录 {today}({len(out)} 条,主推 {len(mains)}):")
for t in out:
    tag = " [主推]" if t["main"] else ""
    print(f"- {t['category']}:{t['key']}{tag}")
PYREC
  exit 0
fi

DATA_DIR="${1:-./data}"
[ -f "$DATA_DIR/child.json" ] || { echo "FAIL: child.json not found in $DATA_DIR" >&2; exit 1; }
exec python3 - "$DATA_DIR/child.json" "$DATA_DIR/daily-tips.json" <<'PY'
import json, os, sys
from datetime import date, timedelta

with open(sys.argv[1], encoding="utf-8") as f:
    doc = json.load(f)
key = next(k for k in doc if not k.startswith("_"))
c = doc[key]

today = date.today()
b = date.fromisoformat(c["birthdate"])
months = (today.year - b.year) * 12 + (today.month - b.month) - (today.day < b.day)
season = ["冬", "冬", "春", "春", "春", "夏", "夏", "夏", "秋", "秋", "秋", "冬"][today.month - 1]
weekday = "一二三四五六日"[today.weekday()]

def parse_day(s):
    # "MM-DD" (current year, same convention as hot-context.sh) or "YYYY-MM-DD"
    s = str(s or "").strip()
    if not s:
        return None
    try:
        if len(s) == 5:
            return date(today.year, *(int(p) for p in s.split("-")))
        return date.fromisoformat(s)
    except ValueError:
        return None

print(f"== 每日贴士候选 | {today} 周{weekday} ==")
print(f"月龄:{months} 个月 | 季节:{season} | 生日:{c['birthdate']}")
p = c.get("profile", {})
if p.get("caregivers"):
    print(f"照顾(按档案原文,不做星期推断):{str(p['caregivers'])[:60]}")
print()
print("[素材](活动/观察点组合用)")
print(f"当前重点:{'、'.join(c.get('currentFocus', [])) or '-'}")
prefs = p.get("preferences") or {}
bk = str(prefs.get("books", "") or "")[:40]
ac = str(prefs.get("activities", "") or "")[:40]
if bk or ac:
    print(f"偏好:{'书 ' + bk if bk else ''}{' | 玩 ' + ac if ac else ''}")
tp = str(p.get("temperament", "") or "")[:60]
if tp:
    print(f"气质:{tp}")
print()
print("[近期事件](编排参考:晨醒/夜醒/新事件可挂活动或观察点)")
notes = c.get("notes", [])[-3:]
if not notes:
    print("(无)")
for n in notes:
    d = str(n.get("date", ""))
    shown = d if n.get("precision", "day") == "day" else f"≈{d}"
    tags = n.get("tags") or []
    tagpart = f" [{'/'.join(tags)}]" if tags else ""
    print(f"- ({shown}){tagpart} {str(n.get('text', ''))[:100]}")
print()

fus = [f for f in c.get("followups", []) if f.get("status", "pending") == "pending"]
due_today = [f for f in fus if (parse_day(f.get("due")) or today) == today]
overdue = [f for f in fus if parse_day(f.get("due")) and parse_day(f["due"]) < today]
upcoming = [f for f in fus if parse_day(f.get("due")) and parse_day(f["due"]) > today]
print("[到期回访](closedloop 首选:今天 > 过期近 > 过期久)")
if not (due_today or overdue):
    print("(今日无到期/过期回访)")
for f in due_today:
    print(f"- {f.get('due')} {str(f.get('topic', ''))[:30]} [到期今天]")
for f in sorted(overdue, key=lambda f: parse_day(f["due"]), reverse=True):
    left = (today - parse_day(f["due"])).days
    print(f"- {f.get('due')} {str(f.get('topic', ''))[:30]} [过期{left}天·轻提]")
for f in sorted(upcoming, key=lambda f: parse_day(f["due"])):
    left = (parse_day(f["due"]) - today).days
    print(f"- {f.get('due')} {str(f.get('topic', ''))[:30]} [距{left}天·预告即可]")
print()

print("[就医待办](pendingCare)")
care = [x for x in c.get("issues", []) if x.get("status") != "resolved" and x.get("pendingCare")]
if not care:
    print("(无)")
for x in care:
    d = parse_day(x.get("opened"))
    n = f" 第{(today - d).days + 1}天" if d else ""
    print(f"- {x.get('id')} {x.get('name')}{n} —— {str(x['pendingCare'])[:50]}")
print()

print("[认领前瞻](reminders;≤14 天才值得占贴士位,远的过滤)")
rems = [r for r in c.get("reminders", []) if r.get("status") == "pending"]
if not rems:
    print("(无)")
for r in rems:
    d = parse_day(r.get("due"))
    if not d:
        print(f"- {r.get('due')} {str(r.get('topic', ''))[:30]} [日期无法解析]")
        continue
    left = (d - today).days
    tag = "临近" if 0 <= left <= 14 else ("已过期" if left < 0 else "远·过滤")
    print(f"- {r.get('due')} {str(r.get('topic', ''))[:30]} [{tag}]")
print("(日历节点[流感季/疫苗档/体检档]由 AI 读 anticipatory.md 按今天匹配,脚本不内置)")
print()

print("[执行素材](action 轮换:how 序号即去重 key,如 P1-how3)")
live = [x for x in c.get("issues", []) if x.get("status") != "resolved"]
if not live:
    print("(无在管问题)")
for x in live:
    how = (x.get("brief") or {}).get("how") or []
    if how:
        print(f"- {x.get('id')} {x.get('name')} how {len(how)} 条:")
        for i, h in enumerate(how, 1):
            print(f"  how{i} {str(h)[:24]}")
strats = [s for s in c.get("strategies", []) if s.get("status") == "active"]
if strats:
    print(f"- 活跃策略:{'/'.join(s.get('id', '?') + ' ' + str(s.get('name', ''))[:12] for s in strats)}"
          " (无 issue how 绑定时读 child.json 策略区取执行素材)")
print()

ms = c.get("milestones") or {}
ks = sorted(int(k) for k in ms if str(k).isdigit())
nxt = next((m for m in (24, 30, 36, 48, 60) if m > months), None)
print("[检查点]")
if nxt:
    done = f";档案已盘 {'/'.join(str(k) for k in ks)} 月" if ks else ""
    print(f"- 下一档 {nxt} 月,距 {nxt - months} 个月{done}")
else:
    print(f"- 已过 60 月检查点线(档案已盘 {'/'.join(str(k) for k in ks)} 月)")
print()

print("[近7天贴士](去重:同 key 不复出)")
hist_path = sys.argv[2]
shown = False
if os.path.exists(hist_path):
    try:
        with open(hist_path, encoding="utf-8") as f:
            hist = json.load(f)
        days = hist.get("days") or {}
        for d in sorted(days):
            dd = parse_day(d)
            if dd and 0 <= (today - dd).days <= 7:
                parts = []
                for t in days[d]:
                    tag = "主推 " if t.get("main") else ""
                    parts.append(f"{tag}{t.get('category')}:{t.get('key')}")
                print(f"- {d} {' | '.join(parts)}")
                shown = True
    except (json.JSONDecodeError, AttributeError):
        print("FAIL: daily-tips.json malformed", file=sys.stderr)
        sys.exit(1)
if not shown:
    print("(无记录——近 7 天首次生成)")
PY
