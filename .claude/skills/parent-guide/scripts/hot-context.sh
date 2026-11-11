#!/usr/bin/env bash
# Aggregate hot context from child.json (~30 lines, for the L1 fast path).
# Usage: hot-context.sh [data_dir]   (default: ./data)
# Contract: child.json field structure is this script's contract --
# renaming fields requires updating this script (and vice versa).
set -euo pipefail
DATA_DIR="${1:-./data}"
exec python3 - "$DATA_DIR/child.json" <<'PY'
import json, os, sys
from datetime import date

with open(sys.argv[1], encoding="utf-8") as f:
    doc = json.load(f)
key = next(k for k in doc if not k.startswith("_"))
c = doc[key]

today = date.today()
b = date.fromisoformat(c["birthdate"])
months = (today.year - b.year) * 12 + (today.month - b.month) - (today.day < b.day)
season = ["冬", "冬", "春", "春", "春", "夏", "夏", "夏", "秋", "秋", "秋", "冬"][today.month - 1]

p = c.get("profile", {})
ph = {"安抚物(如有)", "孩子小名", "主要照顾人与分工", "过敏史(食物/药物/湿疹;没有写无)"}
caregivers = p.get("caregivers", "-")
comfort = p.get("comfortObject", "-")
allergies = p.get("allergies", "")
if caregivers in ph or not str(caregivers).strip():
    caregivers = "未填"
if comfort in ph or not str(comfort).strip():
    comfort = "未填"
allergies = "" if allergies in ph else str(allergies).strip()
print(f"== {c['name']} 热区 | {today} ==")
print(f"月龄:{months} 个月(生日 {c['birthdate']})| 今日季节:{season}")
print(f"照顾:{caregivers} | 安抚物:{comfort}")
if allergies:
    print(f"过敏史:{allergies}(用药/新食物引入前先对照)")
print(f"当前重点:{'、'.join(c.get('currentFocus', []))}")

# milestone status: latest assessed month-age at/below current age (gap visibility)
ms = c.get("milestones") or {}
ks = sorted(int(k) for k in ms if str(k).isdigit())
if not ks:
    print("里程碑:未盘点(首次发育话题先做基线盘点,Run update-child.py set-milestone 落档)")
else:
    fit = [k for k in ks if k <= months]
    mk = (fit or ks)[-1]
    pack = ms[str(mk)]
    it = pack.get("items", [])
    cnt = {s: sum(1 for x in it if x.get("status") == s) for s in ("ok", "watch", "todo")}
    ap = f",盘于{pack['assessed']}" if pack.get("assessed") else ""
    print(f"里程碑:{mk}月已盘{ap} 已会{cnt['ok']}/观察{cnt['watch']}/未现{cnt['todo']}"
          f"(L3 对照变化;重盘整组覆盖)")

# profile snapshot staleness (mechanical, 2026-10-14): watch fields whose
# _asOf (last checked-at date, stamped by update-child.py) is >6 months old.
# gender/childcarePlan/siblings are excluded -- static fact / own anticipatory
# nudges / structural fact. No _asOf entry = never migrated or never filled:
# nothing to judge, stay silent.
WATCH = (("temperament", "气质"), ("language", "语言"), ("comfortObject", "安抚物"),
         ("caregivers", "照料"), ("familyNotes", "家庭口径"), ("allergies", "过敏"),
         ("healthNotes", "健康"),
         ("preferences.books", "绘本"), ("preferences.activities", "活动"),
         ("sleep.note", "睡眠"))
asof = p.get("_asOf") or {}
stale = []
for f, lab in WATCH:
    d = str(asof.get(f) or "")
    if not d:
        continue
    try:
        age = (today - date.fromisoformat(d)).days
    except ValueError:
        continue
    if age > 183:
        stale.append(lab)
if stale:
    print(f"画像:{'/'.join(stale)}超 6 月未核实——大体检顺带刷新;"
          f"对话中对过现值未变则 set-profile --verify 刷核实时间")
print()
# strategy-patterns layer (distilled at half-year checkups): only surfaces
# when the file exists -- no file, no line (hot zone stays minimal for L1).
pat = os.path.join(os.path.dirname(sys.argv[1]), "patterns.md")
if os.path.exists(pat):
    with open(pat, encoding="utf-8") as f:
        n = sum(1 for _ in f)
    print(f"规律层:patterns.md({n} 行)——选策略前先读,失效清单=禁用项")
    print()
print("[问题]")
live = [x for x in c.get("issues", []) if x.get("status") != "resolved"]
if not live:
    print("(无在管问题;聊到持续议题时 add-issue 开题,相关记录挂 --issue)")
for x in live:
    iid, nm, st = x.get("id", "?"), x.get("name", ""), x.get("status", "?")
    opened = str(x.get("opened", ""))
    day_str = f"自{opened}" if opened else ""
    try:
        d = date(today.year, *(int(p) for p in opened.split("-")))
        n = (today - d).days + 1
        if 0 < n <= 999:
            day_str = f"第{n}天"
    except ValueError:
        pass
    print(f"- {iid} {nm} [{st}] {day_str} —— {str(x.get('summary', ''))[:40]}")
    bits = []
    if x.get("pendingCare"):
        bits.append(f"就医待办:{x['pendingCare']}")
    fus = [f for f in c.get("followups", [])
           if f.get("status", "pending") == "pending" and iid in (f.get("issues") or [])]
    if fus:
        fu = min(fus, key=lambda f: str(f.get("due", "")))
        due_str = ""
        try:
            fd = date(today.year, *(int(p) for p in str(fu["due"]).split("-")))
            left = (fd - today).days
            due_str = f"(剩{left}天)" if left >= 0 else "(已到期)"
        except ValueError:
            pass
        bits.append(f"下一回访 {fu['due']}{due_str}:{str(fu.get('topic', ''))[:20]}")
    if bits:
        print("  " + " | ".join(bits))
if c.get("activeConcerns"):
    print("(检测到旧 activeConcerns:已废弃,迁到 issues 后清空)")
print()
# insights(孩子模型洞察,2026-11-11):假设级,只作判断参考;过窗=发育性过期,
# 重验(review-insight)前不得当依据引用——这是 R0/R1 风险(发育性混淆/确认循环)
# 的机械触发器。无洞察不打印整段(热区保持最小)。
if c.get("insights"):
    print("[洞察](假设级,只作参考;过窗须重验后才能引用)")
    for x in c.get("insights", []):
        if x.get("status") != "active":
            continue    # superseded/expired 留档作历史,热区只看在管
        w = x.get("window") or [None, None]
        tag = f"(窗 {w[0]}-{w[1]} 月)"
        try:
            if months > int(w[1]):
                tag = f"(窗 {w[0]}-{w[1]} 月,已过窗——review-insight 重验,重验前不得引用)"
        except (TypeError, ValueError):
            pass
        print(f"- {x.get('id', '?')} {x.get('topic', '')}:{x.get('statement', '')}{tag}")
    print()
print("[活跃策略]")
for s in c.get("strategies", []):
    print(f"- {s['id']} {s['name']}:{s['applied']}")
    print(f"  回访:{s['followup']} [{s['status']}]")
print()
print("[挂起]")
for s in c.get("suspended", []):
    print(f"- ({s['since']}) {s['topic']} —— {s['status']}")
print()
print("[试验]")
for e in c.get("experiments", []):
    print(f"- ({e['since']}) {e['name']}:{e['detail']}")
print()
print("[待回访]")
for fu in c.get("followups", []):
    if fu.get("status", "pending") != "pending":
        continue    # done/skipped 留档作历史,热区只看在管的
    print(f"- {fu['due']} {fu['topic']} [{fu['status']}]")
print()
print("[前瞻提醒](已认领,到期临近)")
for r in c.get("reminders", []):
    if r.get("status") == "pending":
        print(f"- {r['due']} {r['topic']} [{r.get('source', '')}]")
print()
print("[近期事件]")
for n in c.get("notes", [])[-3:]:
    d = str(n.get("date", ""))
    shown = d if n.get("precision", "day") == "day" else f"≈{d}"
    tags = n.get("tags") or []
    tagpart = f" [{'/'.join(tags)}]" if tags else ""
    print(f"- ({shown}){tagpart} {n['text']}")
PY
