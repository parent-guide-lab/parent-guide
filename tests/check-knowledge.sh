#!/usr/bin/env bash
# Structural assertions for the knowledge base (fail fast, repeatable).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
K="$ROOT/knowledge"

for f in milestones.md sleep.md nutrition.md emotion.md activities.md tantrum-cdc.md anticipatory.md weaning.md toilet.md growth.md child-mind.md eczema.md newborn.md screen.md toys.md fears.md books.md praise.md honesty.md social.md english.md math.md thinking-training.md yuwen.md; do
  [ -f "$K/$f" ] || { echo "FAIL: knowledge/$f missing"; exit 1; }
done

# provenance trio (source + ingest date + verification method) in every knowledge file header
for f in milestones.md sleep.md nutrition.md emotion.md activities.md tantrum-cdc.md anticipatory.md weaning.md toilet.md growth.md child-mind.md eczema.md newborn.md screen.md toys.md fears.md books.md praise.md honesty.md social.md english.md math.md thinking-training.md yuwen.md; do
  head -12 "$K/$f" | grep -q "入库" || { echo "FAIL: $f header lacks ingest-date line (入库)"; exit 1; }
  head -12 "$K/$f" | grep -q "核对=" || { echo "FAIL: $f header lacks verification method (核对=)"; exit 1; }
done

# gap backlog: cross-conversation record that feeds batch corpus work
[ -f "$K/BACKLOG.md" ] || { echo "FAIL: knowledge/BACKLOG.md missing"; exit 1; }
grep -q "| 日期 |" "$K/BACKLOG.md" || { echo "FAIL: BACKLOG.md lacks table header"; exit 1; }

# closed set: knowledge root holds only official files; self-built goes to knowledge/user/
# (must stay in sync with the publish.sh whitelist)
for f in "$K"/*.md; do
  case "$(basename "$f")" in
    milestones.md|sleep.md|nutrition.md|emotion.md|activities.md|tantrum-cdc.md|anticipatory.md|weaning.md|toilet.md|growth.md|child-mind.md|eczema.md|newborn.md|screen.md|toys.md|fears.md|books.md|praise.md|honesty.md|social.md|english.md|math.md|thinking-training.md|yuwen.md|README.md|LICENSE.md|BACKLOG.md) ;;
    *) echo "FAIL: unknown root knowledge file '$f' — official set is closed; register it in publish.sh+here, or move it to knowledge/user/ (self-built layer)"; exit 1 ;;
  esac
done
# self-built layer: convention doc exists (ships; content under user/ never does)
[ -f "$K/user/README.md" ] || { echo "FAIL: knowledge/user/README.md (self-built layer convention) missing"; exit 1; }

# knowledge.json (in-app panel's official-section data) must mirror the closed
# set above — build-site.py TOPICS is the single source, this catches drift
# the same way check-growth-ref.sh pins the md table to the curve card
[ -f "$ROOT/site/knowledge.json" ] || { echo "FAIL: site/knowledge.json missing (run scripts/build-site.sh)"; exit 1; }
python3 - "$ROOT" << 'EOF'
import json, pathlib, sys
root = pathlib.Path(sys.argv[1])
OFFICIAL = {"milestones.md", "sleep.md", "nutrition.md", "emotion.md", "activities.md",
            "tantrum-cdc.md", "anticipatory.md", "weaning.md", "toilet.md", "growth.md",
            "child-mind.md", "eczema.md", "newborn.md", "screen.md", "toys.md", "fears.md", "books.md",
            "praise.md", "honesty.md", "social.md", "english.md", "math.md",
            "thinking-training.md", "yuwen.md",
            "quickref.md"}  # quickref lives in site-src/, not knowledge/
REMAP = {"tantrum-cdc": "tantrum"}  # only non-same-name site page
GROUPS = {"健康与身体", "喂养与睡眠", "习惯与界限", "情绪与行为", "发育与玩耍", "参考", "速查"}
topics = json.loads((root / "site/knowledge.json").read_text("utf-8"))
files = {t["file"] for t in topics}
if files != OFFICIAL:
    sys.exit(f"FAIL: knowledge.json file set drifted: +{sorted(files - OFFICIAL)} -{sorted(OFFICIAL - files)}")
slugs = {t["slug"] for t in topics}
want_slugs = {REMAP.get(f[:-3], f[:-3]) for f in OFFICIAL if f != "quickref.md"} | {"quick-ref"}
if slugs != want_slugs:
    sys.exit(f"FAIL: knowledge.json slug set drifted: {sorted(slugs)}")
for t in topics:
    if t.get("group") not in GROUPS:
        sys.exit(f"FAIL: knowledge.json topic has unknown/missing group: {t.get('file')} -> {t.get('group')}")
qr = next(t for t in topics if t["file"] == "quickref.md")
if qr["group"] != "速查":
    sys.exit(f"FAIL: quickref must be pinned group 速查, got {qr['group']}")
# groups must be contiguous (TOPICS rows cluster by design; sidebar order derives)
seen, prev = set(), None
for t in topics:
    g = t["group"]
    if g != prev:
        if g in seen:
            sys.exit(f"FAIL: knowledge.json group '{g}' not contiguous (TOPICS rows must cluster by group)")
        seen.add(g); prev = g
for t in topics:
    if not (t.get("title") and t.get("hook") and t.get("src")):
        sys.exit(f"FAIL: knowledge.json entry incomplete: {t.get('file')}")
# every slug needs a literal redirect line in build-site.sh AND a rendered page in
# site/ — regression guard (2026-10-15: praise/honesty/social shipped in
# TOPICS+knowledge.json but the wrapper's literal redirect lines were forgotten,
# so index linked to 404s and no gate caught it). scripts/ does not ship to the
# public repo, so the redirect-line check runs only where the file exists; the
# page-existence check is universal (site/ is distributed).
import re as _re
sh_path = root / "scripts/build-site.sh"
sh = sh_path.read_text("utf-8") if sh_path.exists() else None
for s in sorted(want_slugs):
    if sh is not None and not _re.search(_re.escape('"$R"') + r"\s+" + _re.escape(s) + r"\s*>", sh):
        sys.exit(f"FAIL: build-site.sh lacks redirect line for slug '{s}' (wrapper uses literal per-page redirects: add the line when adding a TOPICS entry)")
    if not (root / "site" / f"{s}.html").exists():
        sys.exit(f"FAIL: site/{s}.html missing (run scripts/build-site.sh)")
EOF

M="$K/milestones.md"
# attribution + public-domain note
grep -q "CDC" "$M" && grep -q "公有领域" "$M" || { echo "FAIL: CDC attribution/public-domain note missing"; exit 1; }
# 11 fully-verified checkpoints + the 15-month explanatory stub
for age in "## 2 个月" "## 4 个月" "## 6 个月" "## 9 个月" "## 12 个月" "## 15 个月" "## 18 个月" "## 2 岁" "## 2 岁半" "## 3 岁" "## 4 岁" "## 5 岁"; do
  grep -q "^$age" "$M" || { echo "FAIL: section '$age' missing"; exit 1; }
done
# four domains per full section
DOMAIN_COUNT=$(grep -c "^\*\*社交/情感\|^\*\*语言/沟通\|^\*\*认知\|^\*\*动作/身体发育" "$M")
[ "$DOMAIN_COUNT" -ge 44 ] || { echo "FAIL: expected >=44 domain headings (11 sections x 4), got $DOMAIN_COUNT"; exit 1; }
# 15-month stub must be explicit about deferral (no invented items)
grep -q "M6.1" "$M" || { echo "FAIL: 15-month section must defer completion to M6.1"; exit 1; }
# generic act-early guidance present
grep -q "何时联系医生" "$M" || { echo "FAIL: act-early guidance missing"; exit 1; }

for f in sleep.md nutrition.md; do
  grep -q "原创综述" "$K/$f" || { echo "FAIL: $f must declare itself a self-written review"; exit 1; }
done

echo "PASS: knowledge base structure OK (milestones 11 verified sections + 15mo stub; sleep, nutrition, emotion, activities reviews)"
