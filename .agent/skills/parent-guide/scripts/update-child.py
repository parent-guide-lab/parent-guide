#!/usr/bin/env python3
"""Deterministic writer for child.json (closed-loop record keeping).

Writing the archive by free-form language is the weakest link observed in
GREEN retest runs: content was legal but id assignment and field style
drifted across conversations. This script makes every mutation
deterministic: id continuation, field normalization, validation,
atomic write with one-generation backup, and duplicate guards.

Usage (run from anywhere; paths parameterized):
  update-child.py [--data DIR] <action> [options]
Actions:
  init          --name --birthdate --caregivers [--temperament] [--focus a,b]
                  create the archive skeleton (guided onboarding; refuses
                  to overwrite an existing real archive)
  add-strategy  --name --applied [--started MM-DD]   new strategy, auto id
  add-followup  --due MM-DD --topic                  append follow-up (dup-guarded)
  add-note      --date MM-DD --text                  append journal note
  mark-revisited --id --result [--status effective|partial|ineffective]
  set-status    --id --status active|suspended|absorbed|ineffective [--note]
  propose-insight --topic --statement --anchor .. [--anchor ..] --window 起,止
                  [--issue P1]   child-model insight proposal: ledger only,
                  parent confirms before it enters the archive (提议-人审)
  confirm-insight --id [--topic/--statement/--anchor/--window overrides]
                  write the proposed insight into child.json (家长确认=门)
  reject-insight --id [--reason]   log the rejection (ledger only; id 占号不复用)
  review-insight --id --verdict reaffirm|revise|drop [--window/--statement/
                  --anchor/--superseded-by/--note]   re-validation at window end
  insight-stats  proposal-ledger rates (驳回率/过窗滞留; 机械计量非 AI 自报)

MM-DD arguments also accept YYYY-MM-DD (auto year-stripped on write), so a
caller passing full dates still produces a check-clean archive.

Every action prints an evidence summary -- the agent quotes it as proof the
record was written (evidence before claims).

Profile snapshot versioning (2026-10-14): set-profile appends the old value to
child.profileHistory (append-only, {date,field,from,to}) and stamps
profile._asOf[field] = today; --verify stamps _asOf without changing the value
(compared-and-unchanged also refreshes it, closing the freshness loop --
hot-context surfaces fields not verified for >PROFILE_STALE_DAYS).

Structure-change SOP (child.json has four mirrors; keep them in sync):
  1. skills/parent-guide/data-templates/child.json  -- the template users copy
  2. skills/parent-guide/scripts/hot-context.sh     -- reader (contract in header)
  3. THIS FILE: STRUCT constants + _check rules      -- writer + validator
  4. web/src/components/cards/                       -- renderer (defensive reads,
     NO red light there -- eyeball after changes)
  Then run: bash tests/test-hot-context.sh && bash tests/test-update-child.sh
  (the red lights for renames/removals live in these two suites + the
  publish gate's `check` on fixtures).
"""
import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

# ═══ STRUCT: field-structure contract (single point of truth) ═══
# Change the structure here FIRST, then walk the SOP above. Enums below are
# shared by write actions and `check`, so they can never drift apart.
VALID_STATUS = {"active", "effective", "partial", "ineffective", "suspended", "absorbed"}
MILESTONE_STATUS = {"ok", "watch", "todo"}
ISSUE_STATUS = {"active", "watching", "resolved"}   # docs/specs/issue-tracking-v1.md
# insights(孩子模型洞察,2026-11-11):提议-人审+台账回路,协议=conversation.md §2.9,
# 调研=docs/skill-self-evolution-research-2026-11-11.md(拆件:SkillEvo 证据边界/合并不
# 补丁 + SkillOpt validation-gated + ExpeL 池操作)。依据档恒为【推断】个案观察,不入字段。
INSIGHT_STATUS = {"active", "superseded", "expired"}
INSIGHT_VERDICTS = {"reaffirm", "revise", "drop"}
INSIGHT_BLACKLIST = re.compile(
    r"(天生|生来|一直都是|从来都|就是个|定型了|慢热型|高需求型|难养型|易养型"
    r"|天使宝宝|魔鬼宝宝|[内外向慢热高需难易敏感固执胆小大胆]{1,3}型)")
INSIGHT_MAX_TOPIC = 20      # 字;话题短语
INSIGHT_MAX_STATEMENT = 100 # 字;一句假设级表述
INSIGHT_MAX_ANCHOR = 60     # 字;单条观察锚
TIME_OF_DAY = re.compile(r"^(\d{1,2}):(\d{1,2})$")  # note.time HH:MM(可选,容忍 9:5)


def _norm_time(v):
    """--time 容忍 9:5 这类单数位,存零填充 HH:MM;非法值原样返回交上层拒绝。"""
    m = TIME_OF_DAY.match(str(v or ""))
    if m and int(m.group(1)) < 24 and int(m.group(2)) < 60:
        return f"{int(m.group(1)):02d}:{int(m.group(2)):02d}"
    return None
NOTE_PRECISION = {"day", "week", "month"}
DATE_FULL = re.compile(r"^\d{4}-\d{2}-\d{2}$")   # birthdate
DATE_SHORT = re.compile(r"^\d{2}-\d{2}$")        # MM-DD everywhere else
# template placeholder values: "not filled yet" is guidance, not an error
PLACEHOLDERS = {"MM-DD", "YYYY-MM-DD", "HH:MM", "女|男",
                "effective|partial|ineffective", "孩子小名",
                "绘本偏好", "活动偏好", "气质特点一句话", "语言发展一句话",
                "家庭管教口径、长辈观点等背景",
                "过敏史(食物/药物/湿疹;没有写无)",
                "兄弟姐妹(没有写无)",
                "长期健康背景(湿疹体质/哮喘/反复中耳炎/手术史;没有写无)"}
# profile snapshot contract: what set-profile may touch, and which of those
# fields hot-context watches for staleness (gender/childcarePlan/siblings are
# excluded from the watch -- static facts / own anticipatory nudges /
# structural fact; siblings joined 2026-10-14, healthNotes same day --
# long-term health backdrop beside allergies, see docs/profile-fields-research)
PROFILE_FIELDS = ("gender", "caregivers", "language", "temperament", "comfortObject",
                  "familyNotes", "childcarePlan", "allergies", "siblings", "healthNotes",
                  "preferences.books", "preferences.activities", "sleep.note")
PROFILE_STALE_DAYS = 183   # 半年大体检节奏:超 6 月未核实给机械提示
SLEEP_NOTE_PH = "睡眠目标与趋势一句话"
# ═══ end STRUCT ═══


def _today():
    return date.today().strftime("%m-%d")


def _norm_short(v):
    """MM-DD fields also accept YYYY-MM-DD and store it year-stripped:
    conversation-side callers habitually pass full dates (field-test finding
    2026-10-07); anything else still lands in check's problem list."""
    v = str(v or "")
    return v[5:] if DATE_FULL.match(v) else v


def _norm_reminder_due(v):
    """reminders[].due: near-term nodes stay MM-DD, cross-year nodes (入园/
    疫苗季) keep YYYY-MM-DD verbatim -- year-stripping here is what turned
    2027-06-07 into a 06-07 that every reader parsed as this-year and
    rendered months-overdue (2026-10-10 dogfooding bug report)."""
    v = str(v or "")
    return v if DATE_FULL.match(v) else _norm_short(v)


def _days_ago(n):
    from datetime import timedelta
    return (date.today() - timedelta(days=n)).isoformat()


def _profile_get(child, field):
    if field == "sleep.note":
        return child.get("sleep", {}).get("note")
    if field.startswith("preferences."):
        return (child.get("profile", {}).get("preferences") or {}).get(field.split(".", 1)[1])
    return child.get("profile", {}).get(field)


def _profile_set(child, field, value):
    if field == "sleep.note":
        child.setdefault("sleep", {})["note"] = value
    elif field.startswith("preferences."):
        child.setdefault("profile", {}).setdefault("preferences", {})[field.split(".", 1)[1]] = value
    else:
        child.setdefault("profile", {})[field] = value


def _profile_is_real(value):
    v = str(value or "").strip()
    return bool(v) and v not in PLACEHOLDERS and v != SLEEP_NOTE_PH


def _stamp_asof(child, field):
    child.setdefault("profile", {}).setdefault("_asOf", {})[field] = date.today().isoformat()


def _ensure_profile_asof(child):
    """Backfill profile._asOf for real values written before the field existed
    (2026-10-14 schema). Baseline = today: real write dates are unknowable, so
    staleness counting starts at migration -- never invented. Add-only; an
    existing entry is never overwritten. Runs before every save, which makes
    any write action migrate an old archive transparently."""
    prof = child.setdefault("profile", {})
    asof = prof.setdefault("_asOf", {})
    for f in PROFILE_FIELDS:
        if f not in asof and _profile_is_real(_profile_get(child, f)):
            asof[f] = date.today().isoformat()


def _months_at(birthdate, on_date):
    """Whole months between birthdate and on_date (both YYYY-MM-DD); 0 if unknown."""
    try:
        b = date.fromisoformat(birthdate)
        d = date.fromisoformat(on_date)
    except ValueError:
        return 0
    return max(0, (d.year - b.year) * 12 + (d.month - b.month) - (d.day < b.day))


def _load(path):
    doc = json.loads(path.read_text("utf-8"))
    key = next(k for k in doc if not k.startswith("_"))
    return doc, key, doc[key]


def _save(path, doc):
    """Atomic write with one-generation backup (bak replaced each save)."""
    backup = path.with_suffix(".json.bak")
    if path.exists():
        backup.write_text(path.read_text("utf-8"), encoding="utf-8")
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _next_strategy_id(child):
    nums = [int(m.group(1)) for s in child.get("strategies", [])
            for m in [re.match(r"S(\d+)$", str(s.get("id", "")))] if m]
    return f"S{max(nums, default=0) + 1}"


def _bump_evidence(evidence):
    m = re.search(r"回访 ×(\d+)", evidence or "")
    n = int(m.group(1)) + 1 if m else 1
    return f"回访 ×{n}"


def _next_issue_id(child):
    nums = [int(m.group(1)) for x in child.get("issues", [])
            for m in [re.match(r"P(\d+)$", str(x.get("id", "")))] if m]
    return f"P{max(nums, default=0) + 1}"


def _find_issue(child, iid):
    it = next((x for x in child.get("issues", []) if x.get("id") == iid), None)
    if it is None:
        known = ";".join(str(x.get("id", "?")) for x in child.get("issues", [])) or "(无)"
        return None, f"ERROR: issue {iid} not found | 现有:{known}"
    return it, None


def _validated_issues(child, ids):
    """--issue 参数校验:返回去重列表;None=挂了不存在的问题。"""
    if not ids:
        return []
    known = {x.get("id") for x in child.get("issues", [])}
    if any(i not in known for i in ids):
        return None
    return list(dict.fromkeys(ids))


def _find_note(child, spec):
    """--note 定位:YYYY-MM-DD:前缀;零命中/撞车都报错(撞车列候选)。"""
    d, _, prefix = spec.partition(":")
    prefix = prefix.strip()
    if not prefix:
        return None, f"ERROR: --note 须为 YYYY-MM-DD:前缀(现在是 {spec!r})"
    hits = [n for n in child.get("notes", [])
            if n.get("date") == d and str(n.get("text", "")).startswith(prefix)]
    if not hits:
        same = [f"  {n.get('date')}:{str(n.get('text', ''))[:20]}"
                for n in child.get("notes", []) if n.get("date") == d]
        return None, (f"ERROR: 没有匹配的 note {spec!r}"
                      + ("\n当天候选:\n" + "\n".join(same) if same else "(该日期无 note)"))
    if len(hits) > 1:
        return None, (f"ERROR: 前缀撞车({len(hits)} 条),加长前缀重试:\n"
                      + "\n".join(f"  {h.get('text', '')[:30]}" for h in hits))
    return hits[0], None


# ═══ insights:提议-人审+台账(docs/skill-self-evolution-research-2026-11-11)═══

def _insight_log_path(data_dir):
    return Path(data_dir) / "insights-log.jsonl"


def _append_log(data_dir, entry):
    with _insight_log_path(data_dir).open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _read_log_full(data_dir):
    """读洞察台账,返回(条目列表, 坏行数)。坏行跳过不炸(台账只计量,
    读失败不挡档案动作)——但坏行数必须可见(insight-stats 显示),
    不静默吞:计量失真要能被发现。"""
    p = _insight_log_path(data_dir)
    if not p.exists():
        return [], 0
    out, bad = [], 0
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            bad += 1
    return out, bad


def _read_log(data_dir):
    return _read_log_full(data_dir)[0]


def _next_insight_id(child, used_ids):
    """I<N> 连续且不复用——被拒提议的 id 也占号(台账可追溯到提议总量)。"""
    nums = [int(m.group(1)) for x in child.get("insights", [])
            for m in [re.match(r"I(\d+)$", str(x.get("id", "")))] if m]
    nums += [int(m.group(1)) for i in used_ids
             for m in [re.match(r"I(\d+)$", str(i))] if m]
    return f"I{max(nums, default=0) + 1}"


def _parse_window(v):
    """--window "30,42" -> [30, 42];非两整数返回 None 交上层拒绝。"""
    parts = str(v or "").split(",")
    if len(parts) != 2:
        return None
    try:
        return [int(parts[0].strip()), int(parts[1].strip())]
    except ValueError:
        return None


def _insight_problems(topic, statement, anchors, window):
    """洞察三硬纪律机械校验(fail fast;对应协议 §2.9):①假设级语言(定性
    黑名单拦截)②观察锚 ≥1 条(证据边界:只从已观察事实提炼)③月龄窗必填
    (发育性过期:洞察属于月龄段而非永远成立)。返回(问题列表, 清洗后锚)。"""
    problems = []
    topic = str(topic or "").strip()
    statement = str(statement or "").strip()
    if not topic:
        problems.append("topic 必填(主题短语)")
    elif len(topic) > INSIGHT_MAX_TOPIC:
        problems.append(f"topic 须 ≤{INSIGHT_MAX_TOPIC} 字(现在是 {len(topic)} 字)")
    if not statement:
        problems.append("statement 必填(一句假设级表述)")
    elif len(statement) > INSIGHT_MAX_STATEMENT:
        problems.append(f"statement 须 ≤{INSIGHT_MAX_STATEMENT} 字(现在是 {len(statement)} 字)")
    else:
        hit = INSIGHT_BLACKLIST.search(statement)
        if hit:
            problems.append(f"statement 含定性标签表述「{hit.group(0)}」——洞察只写假设级"
                            "(「可能与…有关,待观察」),不做定性结论(协议 §2.9)")
    clean_anchors = [str(a).strip() for a in (anchors or []) if str(a).strip()]
    if not clean_anchors:
        problems.append("anchors 必填 ≥1 条观察锚(日期+白描短句)——无锚洞察不进档案")
    for a in clean_anchors:
        if len(a) > INSIGHT_MAX_ANCHOR:
            problems.append(f"锚「{a[:16]}…」超 {INSIGHT_MAX_ANCHOR} 字,精简后重试")
    if (not isinstance(window, list) or len(window) != 2
            or not all(isinstance(w, int) for w in window)):
        problems.append("window 必填且为 [起月龄,止月龄] 两个整数(如 --window 30,42)")
    elif window[0] > window[1]:
        problems.append(f"window 起月龄 {window[0]} > 止月龄 {window[1]}")
    elif window[0] < 0 or window[1] > 72:
        problems.append(f"window 须在 0-72 月内(0-5 岁适配范围;现在是 {window})")
    return problems, clean_anchors


def execute(argv=None):
    ap = argparse.ArgumentParser(prog="update-child.py")
    ap.add_argument("--data", default="./data", help="data directory (default ./data)")
    sub = ap.add_subparsers(dest="action", required=True)

    p = sub.add_parser("add-strategy")
    p.add_argument("--name", required=True)
    p.add_argument("--applied", required=True)
    p.add_argument("--started", default=None, help="MM-DD (YYYY-MM-DD auto-normalized)")
    p.add_argument("--issue", action="append", default=None,
                   help="挂到问题 P 号(可重复;先 add-issue)")

    p = sub.add_parser("add-followup")
    p.add_argument("--due", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--issue", action="append", default=None,
                   help="挂到问题 P 号(可重复;先 add-issue)")

    p = sub.add_parser("add-growth", help="append a height/weight measurement "
                       "(growth.records; same-date re-entry replaces -- growth "
                       "curves compare against WS/T 423-2022 bands, see "
                       "knowledge/growth.md)")
    p.add_argument("--date", required=True, help="YYYY-MM-DD (measurement day)")
    p.add_argument("--height", default=None, help="cm, e.g. 92.5")
    p.add_argument("--weight", default=None, help="kg, e.g. 13.2")

    p = sub.add_parser("add-note")
    p.add_argument("--date", default=None,
                   help="YYYY-MM-DD (preferred) or MM-DD (current year assumed)")
    p.add_argument("--approx-days", default=None,
                   help="fuzzy recollection: N days ago; precision auto-graded "
                   "(<=7 day, <=21 week, else month) -- never invent exactness")
    p.add_argument("--tags", default=None, help="comma-separated event tags")
    p.add_argument("--text", required=True)
    p.add_argument("--time", default=None,
                   help="HH:MM 当天时刻(可选;同日多条精确排序用;不知道就不填,不编造)")
    p.add_argument("--title", default=None,
                   help="一句话标题(可选,<=25 字;时间轴扫读层,原文进展开)")
    p.add_argument("--issue", action="append", default=None,
                   help="挂到问题 P 号(可重复;先 add-issue)")

    p = sub.add_parser("mark-revisited")
    p.add_argument("--id", required=True)
    p.add_argument("--result", required=True)
    p.add_argument("--status", default=None, choices=["effective", "partial", "ineffective"])

    p = sub.add_parser("add-reminder")
    p.add_argument("--due", required=True,
                   help="近程 MM-DD;跨年节点直接给 YYYY-MM-DD(年份原样保留)")
    p.add_argument("--topic", required=True)
    p.add_argument("--source", required=True, help="e.g. 疫苗/入园准备/自定义")

    p = sub.add_parser("set-reminder-status")
    p.add_argument("--due", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--status", required=True, choices=["pending", "done", "skipped"])

    p = sub.add_parser("set-followup-status", help="retire a followup after the "
                       "revisit happens (done/skipped stay as history, cards "
                       "and hot context only show pending -- overdue red badges "
                       "must not pile up forever)")
    p.add_argument("--due", required=True)
    p.add_argument("--topic", required=True)
    p.add_argument("--status", required=True, choices=["pending", "done", "skipped"])

    p = sub.add_parser("set-status")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=sorted(VALID_STATUS))
    p.add_argument("--note", default=None)

    p = sub.add_parser("set-milestone", help="record an L3 assessment for one "
                      "month-age: whole-set replace (re-assessment overwrites)")
    p.add_argument("--months", required=True, type=int)
    p.add_argument("--items", required=True,
                   help='JSON array [{"domain","text","status":ok|watch|todo},...]')
    p.add_argument("--source", default=None, help="e.g. CDC X 岁检查表")

    p = sub.add_parser("set-focus", help="replace currentFocus wholesale "
                      "(derived from conversation evidence; empty = all resolved)")
    p.add_argument("--items", required=True, help="comma-separated; empty string clears")

    p = sub.add_parser("add-issue")
    p.add_argument("--name", required=True)
    p.add_argument("--status", required=True, choices=["active", "watching"],
                   help="开题只允许 active/watching;resolved 走 set-issue-status 且须用户拍板")
    p.add_argument("--summary", required=True, help="当前状态一句话(详情页当前状态卡主体)")
    p.add_argument("--opened", default=None, help="MM-DD 默认今天;补开历史问题时用")
    p.add_argument("--judged", default=None, help="MM-DD 判定确立日(时间轴大节点)")
    p.add_argument("--pending-care", default=None, help="待办就医动作;存在=红")
    p.add_argument("--what", default=None, help="brief.what:这是什么问题(判定与现状)")
    p.add_argument("--why", action="append", default=None, help="为什么这么做:一条一传")
    p.add_argument("--how", action="append", default=None, help="怎么做:一条一传")
    p.add_argument("--redline", default=None, help="出现即就医/评估的红线")
    p.add_argument("--source", action="append", default=None,
                   help="依据来源:一条一传(机构/知识页+细则一句,分享卡尾渲染)")

    p = sub.add_parser("set-issue-status")
    p.add_argument("--id", required=True)
    p.add_argument("--status", required=True, choices=sorted(ISSUE_STATUS))

    p = sub.add_parser("set-issue-brief")
    p.add_argument("--id", required=True)
    p.add_argument("--name", default=None, help="命名纠正(改显示名,不动内容)")
    p.add_argument("--summary", default=None)
    p.add_argument("--what", default=None)
    p.add_argument("--why", action="append", default=None,
                   help="整组覆盖;传空串清空该节")
    p.add_argument("--how", action="append", default=None)
    p.add_argument("--redline", default=None)
    p.add_argument("--source", action="append", default=None,
                   help="依据来源整组覆盖;传空串清空")
    p.add_argument("--pending-care", default=None, help="传 none 清除")
    p.add_argument("--judged", default=None)

    p = sub.add_parser("link-issue", help="回顾补挂/误挂纠正")
    p.add_argument("--id", required=True)
    p.add_argument("--note", action="append", default=None,
                   help="YYYY-MM-DD:前缀(前缀>=8字;撞车报错列候选)")
    p.add_argument("--strategy", action="append", default=None, help="如 S4")
    p.add_argument("--followup", action="append", default=None, help="MM-DD:topic")
    p.add_argument("--remove", action="store_true")

    p = sub.add_parser("set-note-time", help="补记历史 note 的时刻(问题时间轴同日排序)")
    p.add_argument("--note", required=True, help="YYYY-MM-DD:前缀(同 link-issue 定位)")
    p.add_argument("--time", required=True, help="HH:MM(事件发生时刻,用户口径)")

    p = sub.add_parser("set-note-title", help="补记历史 note 的一句话标题(时间轴扫读层)")
    p.add_argument("--note", required=True, help="YYYY-MM-DD:前缀(同 link-issue 定位)")
    p.add_argument("--title", required=True, help="一句话标题,<=25 字,意思不变")

    p = sub.add_parser("propose-insight", help="propose a child-model insight "
                       "(ledger only; parent confirms before it enters the archive)")
    p.add_argument("--topic", required=True, help="主题短语 ≤20 字")
    p.add_argument("--statement", required=True,
                   help="一句假设级表述 ≤100 字;定性标签(「X型/天生」类)会被拒绝")
    p.add_argument("--anchor", action="append", required=True,
                   help="观察锚:日期+白描短句,一条一传,≥1 条必填")
    p.add_argument("--window", required=True, help="月龄窗 起,止(如 30,42;0-72)")
    p.add_argument("--issue", action="append", default=None, help="挂到问题,如 P1")

    p = sub.add_parser("confirm-insight", help="家长确认后把提议写入档案;不带修订参数"
                       "=按提议原样,给了=以确认口径为准")
    p.add_argument("--id", required=True)
    p.add_argument("--topic", default=None)
    p.add_argument("--statement", default=None)
    p.add_argument("--anchor", action="append", default=None,
                   help="给了=整组覆盖提议锚")
    p.add_argument("--window", default=None)
    p.add_argument("--issue", action="append", default=None)

    p = sub.add_parser("reject-insight", help="驳回提议:只进台账(档案不动);"
                       "id 占号不复用")
    p.add_argument("--id", required=True)
    p.add_argument("--reason", default="", help="驳回原因=提炼纪律的校准数据")

    p = sub.add_parser("review-insight", help="窗口到期重验(热区会提示过窗洞察)")
    p.add_argument("--id", required=True)
    p.add_argument("--verdict", required=True, choices=sorted(INSIGHT_VERDICTS),
                   help="reaffirm=仍成立延窗(须 --window 新窗)/revise=修订表述或锚"
                        "(须 --statement 和/或 --anchor)/drop=废弃"
                        "(默认 expired;--superseded-by 指向新洞察则 superseded)")
    p.add_argument("--window", default=None)
    p.add_argument("--statement", default=None)
    p.add_argument("--anchor", action="append", default=None)
    p.add_argument("--superseded-by", dest="superseded_by", default=None)
    p.add_argument("--note", default="")

    p = sub.add_parser("insight-stats", help="台账计量:提议/确认/驳回/重验与过窗滞留"
                       "(机械计数,不由 AI 自报)")

    p = sub.add_parser("check", help="validate the archive: required fields, date "
                  "formats (YYYY-MM-DD / MM-DD), status enums, numeric fields, "
                  "id uniqueness; human-readable problem list")

    p = sub.add_parser("init", help="create the archive skeleton via guided "
                  "onboarding; refuses to overwrite an existing real archive")
    p.add_argument("--name", required=True)
    p.add_argument("--birthdate", required=True)
    p.add_argument("--caregivers", required=True)
    p.add_argument("--gender", default=None, help="optional, first-round question")
    p.add_argument("--temperament", default=None)
    p.add_argument("--focus", default=None, help="comma-separated currentFocus items")

    p = sub.add_parser("set-profile", help="update one whitelisted profile field "
                      "(guided onboarding follow-up; replaces manual JSON edits). "
                      "Value changes append the old value to profileHistory; "
                      "--verify only stamps the checked-at date")
    p.add_argument("--field", required=True,
                   choices=sorted(PROFILE_FIELDS))
    p.add_argument("--value", default=None,
                   help="new value (omitted only with --verify)")
    p.add_argument("--verify", action="store_true",
                   help="对过现值未变:只刷 profile._asOf,不动值不追加历史")

    args = ap.parse_args(argv)
    path = Path(args.data) / "child.json"
    template = Path(__file__).parent.parent / "data-templates" / "child.json"

    # init works on a missing file or an unfilled template; never on real data
    if args.action == "init":
        if not DATE_FULL.match(args.birthdate):
            return 1, "ERROR: --birthdate must be YYYY-MM-DD"
        existing = None
        if path.exists():
            try:
                _, _, existing = _load(path)
            except (OSError, ValueError, StopIteration):
                return 1, f"ERROR: {path} exists but is unreadable; fix or remove it first"
            if str(existing.get("name", "")) not in PLACEHOLDERS and str(existing.get("name", "")).strip():
                return 1, (f"ERROR: 档案已存在(孩子:{existing.get('name')}),init 拒绝覆盖;"
                           "如确要重建,请先手动删除/移走 child.json(备份在 .bak)")
        doc = json.loads(template.read_text("utf-8"))
        key = next(k for k in doc if not k.startswith("_"))
        child = doc[key]
        child["name"] = args.name
        child["birthdate"] = args.birthdate
        child["profile"]["caregivers"] = args.caregivers
        if args.gender:
            child["profile"]["gender"] = args.gender
        if args.temperament:
            child["profile"]["temperament"] = args.temperament
        child["currentFocus"] = [f.strip() for f in (args.focus or "").split(",") if f.strip()]
        # drop teaching samples from the template: a fresh archive starts empty
        for section in ("strategies", "suspended", "experiments", "followups", "notes",
                         "reminders", "issues", "insights"):
            child[section] = []
        child.pop("activeConcerns", None)   # 已废弃(issues 取代)
        child["milestones"] = {}
        child["sleep"] = {"days": [], "note": ""}
        _ensure_profile_asof(child)
        problems, _ph = _check(child)
        if problems:
            return 1, "ERROR: init produced an invalid archive:\n" + "\n".join(problems)
        _save(path, doc)
        return 0, (f"recorded archive for {args.name}(birthday {args.birthdate}, "
                   f"caregivers: {args.caregivers}) | saved {path.name} (backup: child.json.bak) "
                   f"| 建议接着跑: hot-context 看一眼系统眼里的孩子")

    try:
        doc, key, child = _load(path)
    except (OSError, ValueError, StopIteration) as e:
        return 1, f"ERROR: cannot load {path}: {e}"

    if args.action == "insight-stats":
        log, bad_lines = _read_log_full(Path(args.data))
        n = {k: sum(1 for e in log if e.get("action") == k)
             for k in ("proposed", "confirmed", "rejected", "reviewed")}
        ins = child.get("insights", [])
        st = {k: sum(1 for x in ins if x.get("status") == k) for k in sorted(INSIGHT_STATUS)}
        months_now = _months_at(str(child.get("birthdate") or ""), date.today().isoformat())
        overdue = [str(x.get("id")) for x in ins
                   if x.get("status") == "active" and isinstance(x.get("window"), list)
                   and len(x["window"]) == 2 and months_now > x["window"][1]]
        rate = f"驳回率 {n['rejected']}/{n['proposed']}" if n["proposed"] else "驳回率 -(尚无提议)"
        lines = [f"洞察台账:提议 {n['proposed']}·确认 {n['confirmed']}·驳回 {n['rejected']}"
                 f"·重验 {n['reviewed']}({rate})",
                 f"在档 {len(ins)} 条(active {st['active']}/superseded {st['superseded']}"
                 f"/expired {st['expired']};当前 {months_now} 月龄)"]
        if bad_lines:
            lines.append(f"⚠️ 台账坏行 {bad_lines} 条已跳过(计量分母可能失真,"
                         "检查 insights-log.jsonl)")
        if overdue:
            lines.append(f"过窗滞留 {len(overdue)} 条:{','.join(overdue)}——"
                         "review-insight 重验(引用过窗洞察前先重验)")
        else:
            lines.append("过窗滞留:无")
        return 0, "\n".join(lines)

    if args.action == "add-strategy":
        linked = _validated_issues(child, args.issue)
        if linked is None:
            return 1, f"ERROR: --issue 挂了不存在的问题:{'/'.join(args.issue)}(先 add-issue)"
        sid = _next_strategy_id(child)
        started = _norm_short(args.started) or _today()
        rec = {"id": sid, "name": args.name, "applied": args.applied,
               "started": started, "followup": "",
               "evidence": "回访 ×0", "status": "active"}
        if linked:
            rec["issues"] = linked
        child.setdefault("strategies", []).append(rec)
        msg = f"recorded strategy {sid}「{args.name}」(started {started}, status active)"

    elif args.action == "add-followup":
        linked = _validated_issues(child, args.issue)
        if linked is None:
            return 1, f"ERROR: --issue 挂了不存在的问题:{'/'.join(args.issue)}(先 add-issue)"
        due = _norm_short(args.due)
        items = child.setdefault("followups", [])
        if any(f.get("due") == due and f.get("topic") == args.topic for f in items):
            return 1, f"ERROR: followup {due}「{args.topic}」already exists (idempotency guard)"
        rec = {"due": due, "topic": args.topic, "status": "pending"}
        if linked:
            rec["issues"] = linked
        items.append(rec)
        msg = f"recorded followup {due}「{args.topic}」"

    elif args.action == "add-growth":
        if args.height is None and args.weight is None:
            return 1, "ERROR: give --height and/or --weight (at least one)"
        try:
            h = round(float(args.height), 1) if args.height is not None else None
            w = round(float(args.weight), 1) if args.weight is not None else None
        except ValueError:
            return 1, "ERROR: --height/--weight must be numbers (cm / kg)"
        if h is not None and not (30 <= h <= 160):
            return 1, f"ERROR: height {h}cm out of plausible range (30-160)"
        if w is not None and not (1 <= w <= 60):
            return 1, f"ERROR: weight {w}kg out of plausible range (1-60)"
        # 换算月龄带进记录,曲线卡与对照免得各自重算
        months = _months_at(child.get("birthdate", ""), args.date)
        rec = {"date": args.date}
        if h is not None: rec["height"] = h
        if w is not None: rec["weight"] = w
        rec["months"] = months
        records = child.setdefault("growth", {}).setdefault("records", [])
        replaced = next((r for r in records if r.get("date") == args.date), None)
        if replaced:
            records[records.index(replaced)] = rec
            msg = (f"replaced growth record {args.date}: "
                   f"{('身高 %.1fcm ' % h) if h else ''}{('体重 %.1fkg ' % w) if w else ''}"
                   f"({months} 月龄) | 同日重录=替换")
        else:
            records.append(rec)
            records.sort(key=lambda r: r["date"])
            msg = (f"recorded growth {args.date}: "
                   f"{('身高 %.1fcm ' % h) if h else ''}{('体重 %.1fkg ' % w) if w else ''}"
                   f"({months} 月龄) | 共 {len(records)} 条")

    elif args.action == "add-note":
        if (args.date is None) == (args.approx_days is None):
            return 1, "ERROR: give exactly one of --date or --approx-days"
        precision = "day"
        if args.date:
            if DATE_FULL.match(args.date):
                iso = args.date
            elif DATE_SHORT.match(args.date):
                iso = f"{date.today().year}-{args.date}"
            else:
                return 1, (f"ERROR: --date must be YYYY-MM-DD or MM-DD (got {args.date!r});"
                           " fuzzy recollections belong to --approx-days")
        else:
            try:
                back = int(args.approx_days)
                assert back >= 0
            except (ValueError, AssertionError):
                return 1, f"ERROR: --approx-days must be a non-negative integer (got {args.approx_days!r})"
            iso = _days_ago(back)
            precision = "day" if back <= 7 else ("week" if back <= 21 else "month")
        tags = [t.strip() for t in (args.tags or "").split(",") if t.strip()]
        if args.date is None and args.time is not None:
            return 1, "ERROR: --time 与 --approx-days 互斥(模糊回忆不带精确时间,不编造)"
        linked = _validated_issues(child, args.issue)
        if linked is None:
            return 1, f"ERROR: --issue 挂了不存在的问题:{'/'.join(args.issue)}(先 add-issue)"
        rec = {"date": iso, "precision": precision, "tags": tags, "text": args.text}
        if args.title:
            rec["title"] = args.title
        if args.time is not None:
            t = _norm_time(args.time)
            if t is None:
                return 1, f"ERROR: --time 须为 HH:MM(00-23:00-59,现在是 {args.time!r})"
            rec["time"] = t
        if linked:
            rec["issues"] = linked
        child.setdefault("notes", []).append(rec)
        prefix = iso if precision == "day" else f"≈{iso}"
        tagpart = f" [{'/'.join(tags)}]" if tags else ""
        issuepart = f" [→{'/'.join(linked)}]" if linked else ""
        msg = f"recorded note {prefix}{(' ' + rec['time']) if 'time' in rec else ''}({precision}){tagpart}{issuepart}: {args.text[:40]}"

    elif args.action == "mark-revisited":
        s = next((s for s in child.get("strategies", []) if s.get("id") == args.id), None)
        if s is None:
            return 1, f"ERROR: strategy {args.id} not found"
        s["followup"] = args.result
        s["evidence"] = _bump_evidence(s.get("evidence", ""))
        if args.status:
            s["status"] = args.status
        msg = f"revisited {args.id}: {args.result[:40]} (now {s['evidence']}, status {s['status']})"

    elif args.action == "set-status":
        s = next((s for s in child.get("strategies", []) if s.get("id") == args.id), None)
        if s is None:
            return 1, f"ERROR: strategy {args.id} not found"
        s["status"] = args.status
        if args.note:
            s["followup"] = f"{s.get('followup', '')} {args.note}".strip()
        msg = f"strategy {args.id} status -> {args.status}" + (f" ({args.note})" if args.note else "")

    elif args.action == "set-profile":
        if args.verify and args.value is not None:
            return 1, "ERROR: --verify 与 --value 互斥(改值用 --value,对过未变用 --verify)"
        old = _profile_get(child, args.field)
        if args.value is None:
            if not _profile_is_real(old):
                return 1, (f"ERROR: --verify 须字段已有真实值({args.field} 现为空/占位,"
                           "先 --value 填写)")
            _stamp_asof(child, args.field)
            msg = (f"verified {args.field}(现值未变,核实时间 -> "
                   f"{child['profile']['_asOf'][args.field]})")
        else:
            _profile_set(child, args.field, args.value)
            _stamp_asof(child, args.field)
            if _profile_is_real(old) and str(old).strip() == args.value.strip():
                msg = f"verified {args.field}(值未变,按核实处理;不追加 profileHistory)"
            else:
                hist = child.setdefault("profileHistory", [])
                hist.append({"date": date.today().isoformat(), "field": args.field,
                             "from": str(old) if _profile_is_real(old) else "",
                             "to": args.value})
                msg = (f"recorded {args.field} = {args.value[:40]}"
                       f"(旧值留档 profileHistory 共 {len(hist)} 条)")

    elif args.action == "add-reminder":
        due = _norm_reminder_due(args.due)
        items = child.setdefault("reminders", [])
        if any(r.get("due") == due and r.get("topic") == args.topic for r in items):
            return 1, f"ERROR: reminder {due}「{args.topic}」already exists"
        items.append({"due": due, "topic": args.topic,
                      "source": args.source, "status": "pending"})
        msg = f"recorded reminder {due}「{args.topic}」({args.source})"

    elif args.action == "set-reminder-status":
        due = _norm_reminder_due(args.due)
        r = next((r for r in child.get("reminders", [])
                  if r.get("due") == due and r.get("topic") == args.topic), None)
        if r is None:
            return 1, f"ERROR: reminder {due}「{args.topic}」not found"
        r["status"] = args.status
        msg = f"reminder {due}「{args.topic[:30]}」-> {args.status}"

    elif args.action == "set-followup-status":
        due = _norm_short(args.due)
        f = next((f for f in child.get("followups", [])
                  if f.get("due") == due and f.get("topic") == args.topic), None)
        if f is None:
            existing = ";".join(f"{x.get('due')}「{x.get('topic', '')[:20]}」"
                                for x in child.get("followups", [])) or "(无)"
            return 1, (f"ERROR: followup {due} not found"
                       f"(须 due+topic 双精确匹配) | 现有:{existing}")
        f["status"] = args.status
        msg = (f"followup {due}「{args.topic[:30]}」-> {args.status}"
               + ("(留在档案作历史,卡片与热区只显示 pending)" if args.status != "pending" else ""))

    elif args.action == "set-milestone":
        try:
            items = json.loads(args.items)
        except ValueError:
            return 1, "ERROR: --items must be a JSON array of {domain,text,status}"
        if not isinstance(items, list) or not items:
            return 1, "ERROR: --items must be a non-empty JSON array"
        clean = []
        for i, it in enumerate(items):
            if (not isinstance(it, dict) or not str(it.get("domain", "")).strip()
                    or not str(it.get("text", "")).strip()):
                return 1, f"ERROR: items[{i}] needs non-empty domain/text"
            if it.get("status") not in MILESTONE_STATUS:
                return 1, (f"ERROR: items[{i}].status must be one of "
                           f"{'/'.join(('ok', 'watch', 'todo'))} (got {it.get('status')!r})")
            clean.append({"domain": str(it["domain"]), "text": str(it["text"]),
                          "status": it["status"]})
        counts = {s: sum(1 for x in clean if x["status"] == s) for s in sorted(MILESTONE_STATUS)}
        child.setdefault("milestones", {})[str(args.months)] = {
            "source": args.source or "L3 盘点(CDC 检查表口径)",
            "assessed": _today(),
            "items": clean,
        }
        msg = (f"recorded milestone assessment {args.months}m: "
               f"已会 {counts['ok']} / 观察 {counts['watch']} / 未现 {counts['todo']}"
               f"(整组覆盖,重盘会替换该月龄整组)")

    elif args.action == "set-focus":
        old = list(child.get("currentFocus", []))
        new = [f.strip() for f in args.items.split(",") if f.strip()]
        child["currentFocus"] = new
        dropped = [f for f in old if f not in new]
        msg = ("updated currentFocus -> " + ("、".join(new) if new else "(空)")
               + (f" | 划掉:{'/'.join(dropped)}" if dropped else "")
               + " | 整组覆盖,以对话证据为准")

    elif args.action == "add-issue":
        iid = _next_issue_id(child)
        opened = _norm_short(args.opened) or _today()
        issue = {"id": iid, "name": args.name, "status": args.status,
                 "opened": opened, "summary": args.summary}
        brief = {}
        if args.what:
            brief["what"] = args.what
        if args.why:
            brief["why"] = list(args.why)
        if args.how:
            brief["how"] = list(args.how)
        if args.redline:
            brief["redline"] = args.redline
        if args.source:
            brief["sources"] = list(args.source)
        if brief:
            issue["brief"] = brief
        if args.judged:
            issue["judged"] = _norm_short(args.judged)
        if args.pending_care:
            issue["pendingCare"] = args.pending_care
        bad = _brief_format_problems(iid, brief)
        if bad:
            return 1, "ERROR: 拒绝写入(brief 条目格式门禁):\n" + "\n".join(bad)
        child.setdefault("issues", []).append(issue)
        extra = (f", judged {issue['judged']}" if "judged" in issue else "") \
            + (", 就医待办√" if "pendingCare" in issue else "")
        msg = f"recorded issue {iid}「{args.name}」({args.status}, opened {opened}{extra})"

    elif args.action == "set-issue-status":
        it, err = _find_issue(child, args.id)
        if err:
            return 1, err
        it["status"] = args.status
        if args.status == "resolved":
            it["closed"] = _today()
            msg = (f"issue {args.id} -> resolved(closed {it['closed']};"
                   "留档可查,热区/入口卡默认不显示)")
        else:
            it.pop("closed", None)
            msg = f"issue {args.id} -> {args.status}(closed 已清)"

    elif args.action == "set-issue-brief":
        it, err = _find_issue(child, args.id)
        if err:
            return 1, err
        touched = []
        if args.name is not None:
            it["name"] = args.name
            touched.append("name")
        if args.summary is not None:
            it["summary"] = args.summary
            touched.append("summary")
        brief = it.setdefault("brief", {})
        for key, val in (("what", args.what), ("redline", args.redline)):
            if val is not None:
                brief[key] = val
                touched.append(key)
        for key, val in (("why", args.why), ("how", args.how), ("sources", args.source)):
            if val is None:
                continue
            if val == [""]:
                brief.pop(key, None)
            else:
                brief[key] = list(val)
            touched.append(key)
        if not brief:
            it.pop("brief", None)
        if args.pending_care is not None:
            if args.pending_care == "none":
                it.pop("pendingCare", None)
            else:
                it["pendingCare"] = args.pending_care
            touched.append("pendingCare")
        if args.judged is not None:
            it["judged"] = _norm_short(args.judged)
            touched.append("judged")
        if not touched:
            return 1, ("ERROR: 至少传一个 "
                       "--name/--summary/--what/--why/--how/--redline/--pending-care/--judged")
        bad = _brief_format_problems(args.id, it.get("brief") or {})
        if bad:
            return 1, ("ERROR: 拒绝写入(brief 条目格式门禁;"
                       "本次改动已回滚未落盘):\n" + "\n".join(bad))
        msg = (f"updated issue {args.id}: {'/'.join(touched)}"
               "(why/how 整组覆盖,先读全量再写;brief=分享卡唯一素材源)")

    elif args.action == "link-issue":
        it, err = _find_issue(child, args.id)
        if err:
            return 1, err
        if not (args.note or args.strategy or args.followup):
            return 1, "ERROR: 至少给一个 --note/--strategy/--followup"
        targets = []
        for spec in args.note or []:
            n, err = _find_note(child, spec)
            if err:
                return 1, err
            targets.append((n, f"note {spec.split(':', 1)[0]}:{spec.partition(':')[2][:10]}"))
        for sid in args.strategy or []:
            s = next((s for s in child.get("strategies", []) if s.get("id") == sid), None)
            if s is None:
                return 1, f"ERROR: strategy {sid} not found"
            targets.append((s, f"strategy {sid}"))
        for spec in args.followup or []:
            due, _, topic = spec.partition(":")
            f = next((f for f in child.get("followups", [])
                      if f.get("due") == _norm_short(due) and f.get("topic") == topic), None)
            if f is None:
                return 1, f"ERROR: followup {spec!r} not found(须 due+topic 双精确匹配)"
            targets.append((f, f"followup {due}:{topic[:12]}"))
        detail = []
        for rec, label in targets:
            lst = rec.setdefault("issues", [])
            if args.remove:
                if args.id in lst:
                    lst.remove(args.id)
                detail.append(f"-{label}")
            else:
                if args.id not in lst:
                    lst.append(args.id)
                detail.append(f"+{label}")
        msg = f"{'un' if args.remove else ''}linked issue {args.id}: " + " ".join(detail)

    elif args.action == "set-note-time":
        n, err = _find_note(child, args.note)
        if err:
            return 1, err
        t = _norm_time(args.time)
        if t is None:
            return 1, f"ERROR: --time 须为 HH:MM(00-23:00-59,现在是 {args.time!r})"
        n["time"] = t
        msg = f"recorded note time {n.get('date')} {t}:{str(n.get('text', ''))[:30]}"

    elif args.action == "set-note-title":
        n, err = _find_note(child, args.note)
        if err:
            return 1, err
        n["title"] = args.title
        msg = f"recorded note title 「{args.title}」({n.get('date')}:{str(n.get('text', ''))[:24]})"

    elif args.action == "propose-insight":
        # 提议只进台账,档案不动(提议-人审:档案里只有确认过的洞察)
        window = _parse_window(args.window)
        linked = _validated_issues(child, args.issue)
        if linked is None:
            return 1, f"ERROR: --issue 挂了不存在的问题:{'/'.join(args.issue or [])}(先 add-issue)"
        problems, anchors = _insight_problems(args.topic, args.statement, args.anchor, window)
        if problems:
            return 1, "ERROR: 拒绝提议(洞察三硬纪律):\n" + "\n".join(problems)
        used = [e.get("id") for e in _read_log(Path(args.data))]
        iid = _next_insight_id(child, used)
        entry = {"date": date.today().isoformat(), "action": "proposed", "id": iid,
                 "topic": args.topic.strip(), "statement": args.statement.strip(),
                 "anchors": anchors, "window": window, "by": "ai"}
        if linked:
            entry["issues"] = linked
        _append_log(Path(args.data), entry)
        # 只动台账:提前 return,不走公共尾部(那里会写 child.json 并报
        # 「saved child.json」——对提议是假证据,违反证据先于断言)
        return 0, (f"proposed insight {iid}「{args.topic.strip()}」:{args.statement.strip()}"
                   f"(窗 {window[0]}-{window[1]} 月,锚 ×{len(anchors)},依据档=【推断】个案观察)"
                   f" | 待家长确认:confirm-insight --id {iid} / reject-insight --id {iid}"
                   " | 只记台账未入档案(saved insights-log.jsonl)")

    elif args.action == "confirm-insight":
        # 家长确认=门;修订参数给了以确认口径为准
        prop = next((e for e in reversed(_read_log(Path(args.data)))
                     if e.get("action") == "proposed" and e.get("id") == args.id), None)
        if prop is None:
            return 1, f"ERROR: 台账没有 {args.id} 的提议记录(先 propose-insight)"
        if args.id in {x.get("id") for x in child.get("insights", [])}:
            return 1, f"ERROR: {args.id} 已在档案(幂等守卫,不重复确认)"
        topic = args.topic if args.topic is not None else prop["topic"]
        statement = args.statement if args.statement is not None else prop["statement"]
        window = _parse_window(args.window) if args.window else prop["window"]
        anchors_in = args.anchor if args.anchor else prop["anchors"]
        issues_in = args.issue if args.issue else prop.get("issues", [])
        linked = _validated_issues(child, issues_in)
        if linked is None:
            return 1, f"ERROR: --issue 挂了不存在的问题:{'/'.join(issues_in or [])}"
        problems, anchors = _insight_problems(topic, statement, anchors_in, window)
        if problems:
            return 1, "ERROR: 拒绝确认(洞察三硬纪律):\n" + "\n".join(problems)
        rec = {"id": args.id, "topic": str(topic).strip(),
               "statement": str(statement).strip(), "anchors": anchors,
               "window": window, "status": "active", "created": _today()}
        if linked:
            rec["issues"] = linked
        child.setdefault("insights", []).append(rec)
        _append_log(Path(args.data), {"date": date.today().isoformat(),
                                      "action": "confirmed", "id": args.id, "by": "parent"})
        msg = (f"recorded insight {args.id}「{rec['topic']}」:{rec['statement']}"
               f"(窗 {window[0]}-{window[1]} 月) | 过窗热区会提示重验;"
               "台账只计量,被拒提议不进档案")

    elif args.action == "reject-insight":
        prop = next((e for e in reversed(_read_log(Path(args.data)))
                     if e.get("action") == "proposed" and e.get("id") == args.id), None)
        if prop is None:
            return 1, f"ERROR: 台账没有 {args.id} 的提议记录"
        if args.id in {x.get("id") for x in child.get("insights", [])}:
            return 1, f"ERROR: {args.id} 已确认在档,不能 reject(用 review-insight)"
        _append_log(Path(args.data), {"date": date.today().isoformat(),
                                      "action": "rejected", "id": args.id,
                                      "reason": args.reason or ""})
        # 只动台账:提前 return(同 propose,不报 saved child.json 假证据)
        return 0, (f"rejected insight {args.id}(档案未动;台账留痕"
                   f"{',原因:' + args.reason if args.reason else ''})"
                   " | 驳回原因=提炼纪律的校准数据,insight-stats 可查比率")

    elif args.action == "review-insight":
        it = next((x for x in child.get("insights", []) if x.get("id") == args.id), None)
        if it is None:
            known = ";".join(str(x.get("id", "?")) for x in child.get("insights", [])) or "(无)"
            return 1, f"ERROR: insight {args.id} not found(只可重验已确认在档的) | 现有:{known}"
        touched = []
        if args.verdict == "reaffirm":
            if not args.window:
                return 1, "ERROR: reaffirm 须给新 --window 起,止(延窗=重验通过的机械证据,不默认延期)"
            w = _parse_window(args.window)
            problems, _ = _insight_problems(it["topic"], it["statement"], it["anchors"], w)
            if problems:
                return 1, "ERROR: 拒绝延窗:\n" + "\n".join(problems)
            it["window"] = w
            touched.append(f"window→{w[0]}-{w[1]}")
        elif args.verdict == "revise":
            if not (args.statement or args.anchor):
                return 1, "ERROR: revise 须给 --statement 和/或 --anchor"
            stmt = args.statement if args.statement is not None else it["statement"]
            anch = [a.strip() for a in args.anchor if a.strip()] if args.anchor else it["anchors"]
            problems, anchors = _insight_problems(it["topic"], stmt, anch, it["window"])
            if problems:
                return 1, "ERROR: 拒绝修订(洞察三硬纪律):\n" + "\n".join(problems)
            it["statement"] = str(stmt).strip()
            it["anchors"] = anchors
            touched.append("statement/anchors 以重验口径覆盖")
        else:  # drop
            if args.superseded_by:
                if args.superseded_by not in {x.get("id") for x in child.get("insights", [])}:
                    return 1, (f"ERROR: --superseded-by {args.superseded_by} 不存在"
                               "(先确认新洞察,再废弃旧的)")
                it["status"] = "superseded"
                it["supersededBy"] = args.superseded_by
            else:
                it["status"] = "expired"
            touched.append(f"status→{it['status']}")
        _append_log(Path(args.data), {"date": date.today().isoformat(),
                                      "action": "reviewed", "id": args.id,
                                      "verdict": args.verdict, "note": args.note or ""})
        msg = (f"reviewed insight {args.id}({args.verdict}:{' / '.join(touched)})"
               + (f" | {args.note}" if args.note else ""))

    elif args.action == "check":
        problems, ph = _check(child)
        note = f"\n  提示: 还有 {ph} 处模板占位值待替换为真实内容" if ph else ""
        if problems:
            return 1, (f"FAIL: 档案有 {len(problems)} 处问题\n"
                       + "\n".join(f"  - {p}" for p in problems) + note)
        return 0, f"PASS: 档案结构合规(孩子:{child.get('name', '?')})" + note

    else:  # pragma: no cover
        return 1, "ERROR: unknown action"

    _ensure_profile_asof(child)
    _save(path, doc)
    return 0, msg + f" | saved {path.name} (backup: child.json.bak)"


CIRCLED = re.compile(r"[\u2460-\u2473]")   # ①-⑳


def _brief_format_problems(iid, brief):
    """口径卡条目格式门禁(2026-11-10 P4 返工判例):一线一事,禁内联编号糊条。
    why/how/sources 每条=一个动机/动作/来源,what=1-3 句;①②③内联=该拆没拆
    ——详情层 rows 与分享卡 chips 都按「条」取材,一条糊多事渲染必烂。
    双挂点:写入即拒(fail fast)+ check 抓手改档案。判例:conversation.md §2.8。"""
    problems = []
    hit = "含内联编号(①②③类)——一线一事拆成多条,见 conversation.md §2.8 写作判例"
    for field in ("what", "redline"):
        val = brief.get(field)
        if val and CIRCLED.search(str(val)):
            problems.append(f"issue {iid}: brief.{field} {hit}")
    for field in ("why", "how", "sources"):
        for j, item in enumerate(brief.get(field) or []):
            if CIRCLED.search(str(item)):
                problems.append(f"issue {iid}: brief.{field}[{j}] {hit}")
    return problems


def _check(child):
    """Validate one child dict; returns (problems, placeholder_count)."""
    problems = []
    placeholders = [0]

    def is_ph(where, value):
        if str(value) in PLACEHOLDERS:
            placeholders[0] += 1
            return True
        return False

    if not str(child.get("name") or "").strip():
        problems.append("name: 必填(孩子小名)")
    else:
        is_ph("name", child.get("name"))
    if not DATE_FULL.match(str(child.get("birthdate") or "")):
        if not is_ph("birthdate", child.get("birthdate")):
            problems.append("birthdate: 必须是 YYYY-MM-DD 格式(现在是 "
                            f"{child.get('birthdate')!r})")

    def short_date(where, value):
        if not DATE_SHORT.match(str(value or "")):
            if not is_ph(where, value):
                problems.append(f"{where}: 日期须为 MM-DD(现在是 {value!r})")

    if child.get("activeConcerns"):
        problems.append("activeConcerns 已废弃(issues 取代):把在管条目迁到 issues 后清空该键")
    for i, s in enumerate(child.get("strategies", [])):
        short_date(f"strategies[{i}].started", s.get("started"))
        if s.get("status") not in VALID_STATUS and not is_ph(f"strategies[{i}].status", s.get("status")):
            problems.append(f"strategies[{i}].status: 不在枚举内(现在是 {s.get('status')!r},"
                            f"可选 {'/'.join(sorted(VALID_STATUS))})")
        if not re.match(r"^[SM]\d+$", str(s.get("id") or "")):
            problems.append(f"strategies[{i}].id: 须形如 S1/M12(现在是 {s.get('id')!r})")
    ids = [s.get("id") for s in child.get("strategies", []) if s.get("id")]
    dup = {i for i in ids if ids.count(i) > 1}
    if dup:
        problems.append(f"strategies[].id: 重复 {sorted(dup)}")
    for i, s in enumerate(child.get("suspended", [])):
        short_date(f"suspended[{i}].since", s.get("since"))
    for i, e in enumerate(child.get("experiments", [])):
        short_date(f"experiments[{i}].since", e.get("since"))
    for i, f in enumerate(child.get("followups", [])):
        short_date(f"followups[{i}].due", f.get("due"))
        if f.get("status", "pending") not in ("pending", "done", "skipped"):
            problems.append(f"followups[{i}].status: 须为 pending/done/skipped"
                            f"(现在是 {f.get('status')!r})")
    for i, r in enumerate((child.get("growth") or {}).get("records", [])):
        d = r.get("date", "")
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d)):
            problems.append(f"growth.records[{i}].date: 须为 YYYY-MM-DD(现在是 {d!r})")
        for k, lo, hi in (("height", 30, 160), ("weight", 1, 60)):
            v = r.get(k)
            if v is not None and not (isinstance(v, (int, float)) and lo <= v <= hi):
                problems.append(f"growth.records[{i}].{k}: 须为数值且在 {lo}-{hi} 内"
                                f"(现在是 {v!r})")
        if r.get("height") is None and r.get("weight") is None:
            problems.append(f"growth.records[{i}]: 身高体重至少要有一项")
    for i, n in enumerate(child.get("notes", [])):
        nd = str(n.get("date") or "")
        if not (DATE_FULL.match(nd) or DATE_SHORT.match(nd)):
            problems.append(f"notes[{i}].date: 须为 YYYY-MM-DD(新)或 MM-DD(旧,视为当年;"
                            f"现在是 {nd!r})")
        prec = n.get("precision", "day")
        if prec not in NOTE_PRECISION:
            problems.append(f"notes[{i}].precision: 不在枚举 day/week/month(现在是 {prec!r})")
        tags = n.get("tags", [])
        if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
            problems.append(f"notes[{i}].tags: 须为字符串数组(现在是 {tags!r})")
        if n.get("time") is not None and _norm_time(n.get("time")) is None:
            problems.append(f"notes[{i}].time: 须为 HH:MM 00-23:00-59(现在是 {n.get('time')!r})")

    # profile free-text fields: placeholder originals count as "not filled yet"
    prof = child.get("profile", {})
    for f in ("gender", "language", "temperament", "comfortObject", "familyNotes",
              "allergies", "siblings", "healthNotes"):
        is_ph(f"profile.{f}", prof.get(f))
    for f in ("books", "activities"):
        is_ph(f"profile.preferences.{f}", (prof.get("preferences") or {}).get(f))

    # profile snapshot versioning (2026-10-14): _asOf + append-only history
    asof = prof.get("_asOf", {})
    if not isinstance(asof, dict):
        problems.append("profile._asOf: 须为 字段->YYYY-MM-DD 映射")
    else:
        for f, d in asof.items():
            if f not in PROFILE_FIELDS:
                problems.append(f"profile._asOf[{f!r}]: 不是画像字段")
            elif not DATE_FULL.match(str(d)):
                problems.append(f"profile._asOf[{f!r}]: 须为 YYYY-MM-DD(现在是 {d!r})")
    hist = child.get("profileHistory", [])
    if not isinstance(hist, list):
        problems.append("profileHistory: 须为数组(追加式 {date,field,from,to})")
    else:
        for i, h in enumerate(hist):
            if not isinstance(h, dict):
                problems.append(f"profileHistory[{i}]: 须为对象")
                continue
            if h.get("field") not in PROFILE_FIELDS:
                problems.append(f"profileHistory[{i}].field: 不是画像字段(现在是 {h.get('field')!r})")
            if not DATE_FULL.match(str(h.get("date", ""))):
                problems.append(f"profileHistory[{i}].date: 须为 YYYY-MM-DD(现在是 {h.get('date')!r})")
            for k in ("from", "to"):
                if not isinstance(h.get(k), str):
                    problems.append(f"profileHistory[{i}].{k}: 须为字符串")

    for i, d in enumerate(child.get("sleep", {}).get("days", [])):
        for field in ("wakings", "totalHours"):
            if not isinstance(d.get(field), (int, float)):
                problems.append(f"sleep.days[{i}].{field}: 须为数字(现在是 {d.get(field)!r})")

    REMINDER_STATUS = {"pending", "done", "skipped"}
    for i, r in enumerate(child.get("reminders", [])):
        rd = str(r.get("due") or "")
        if not (DATE_SHORT.match(rd) or DATE_FULL.match(rd)):
            problems.append(f"reminders[{i}].due: 须为 MM-DD 或 YYYY-MM-DD"
                            f"(跨年节点,现在是 {r.get('due')!r})")
        if r.get("status") not in REMINDER_STATUS:
            problems.append(f"reminders[{i}].status: 不在枚举 pending/done/skipped"
                            f"(现在是 {r.get('status')!r})")

    for months, pack in (child.get("milestones") or {}).items():
        for j, item in enumerate(pack.get("items", [])):
            if item.get("status") not in MILESTONE_STATUS:
                problems.append(f"milestones.{months}.items[{j}].status: 不在枚举 "
                                f"ok/watch/todo(现在是 {item.get('status')!r})")
        assessed = pack.get("assessed")
        if assessed and not (DATE_FULL.match(str(assessed)) or DATE_SHORT.match(str(assessed))):
            problems.append(f"milestones.{months}.assessed: 须为 YYYY-MM-DD 或 MM-DD"
                            f"(现在是 {assessed!r})")

    # issues(一等实体, docs/specs/issue-tracking-v1.md)
    issue_ids = set()
    for it in child.get("issues", []):
        iid = str(it.get("id", ""))
        if not re.match(r"^P\d+$", iid):
            problems.append(f"issue id 须为 P<N> 格式(现在是 {iid!r})")
        elif iid in issue_ids:
            problems.append(f"issue id 重复:{iid}")
        issue_ids.add(iid)
        if it.get("status") not in ISSUE_STATUS:
            problems.append(f"issue {iid}: status 须为 active/watching/resolved"
                            f"(现在是 {it.get('status')!r})")
        for f in ("opened", "closed", "judged"):
            if it.get(f) and not DATE_SHORT.match(str(it.get(f))):
                problems.append(f"issue {iid}: {f} 须为 MM-DD(现在是 {it.get(f)!r})")
        if it.get("status") == "resolved" and not it.get("closed"):
            problems.append(f"issue {iid}: resolved 须带 closed(用 set-issue-status 关闭)")
        if not str(it.get("summary") or "").strip():
            problems.append(f"issue {iid}: summary 必填(当前状态一句话)")
        problems += _brief_format_problems(iid, it.get("brief") or {})

    # insights(一等实体, 2026-11-11:提议-人审+台账, conversation.md §2.9)
    all_ins = child.get("insights", [])
    insight_ids = {str(x.get("id")) for x in all_ins}
    for it in all_ins:
        iid = str(it.get("id", ""))
        if not re.match(r"^I\d+$", iid):
            problems.append(f"insight id 须为 I<N> 格式(现在是 {iid!r})")
        elif sum(1 for x in all_ins if str(x.get("id")) == iid) > 1:
            problems.append(f"insight id 重复:{iid}")
        if it.get("status") not in INSIGHT_STATUS:
            problems.append(f"insight {iid}: status 须为 active/superseded/expired"
                            f"(现在是 {it.get('status')!r})")
        if not DATE_SHORT.match(str(it.get("created") or "")):
            problems.append(f"insight {iid}: created 须为 MM-DD(现在是 {it.get('created')!r})")
        w = it.get("window")
        if (not isinstance(w, list) or len(w) != 2
                or not all(isinstance(x, int) for x in w)
                or w[0] > w[1] or w[0] < 0 or w[1] > 72):
            problems.append(f"insight {iid}: window 须为 [起月龄,止月龄]"
                            f"(0-72 且起≤止;现在是 {w!r})")
        anc = it.get("anchors")
        if (not isinstance(anc, list) or not anc
                or not all(str(a).strip() for a in anc)):
            problems.append(f"insight {iid}: anchors 须 ≥1 条观察锚(无锚洞察不落档)")
        st = str(it.get("statement") or "")
        if not st.strip():
            problems.append(f"insight {iid}: statement 必填(一句假设级表述)")
        else:
            hit = INSIGHT_BLACKLIST.search(st)
            if hit:
                problems.append(f"insight {iid}: statement 含定性表述「{hit.group(0)}」"
                                "——改写为假设级(「可能与…有关,待观察」)")
        if it.get("status") == "superseded" and str(it.get("supersededBy")) not in insight_ids:
            problems.append(f"insight {iid}: superseded 须带 supersededBy 指向在档洞察")

    for sec, loc in (("notes", lambda r: f"{r.get('date', '')} {str(r.get('text', ''))[:12]}"),
                     ("strategies", lambda r: str(r.get("id", ""))),
                     ("followups", lambda r: f"{r.get('due', '')} {str(r.get('topic', ''))[:12]}"),
                     ("insights", lambda r: str(r.get("id", "")))):
        for r in child.get(sec, []):
            for ref in r.get("issues", []):
                if ref not in issue_ids:
                    problems.append(f"{sec} 记录({loc(r)}…)挂了不存在的问题 {ref}")

    return problems, placeholders[0]


def main():
    code, msg = execute()
    print(msg)
    sys.exit(code)


if __name__ == "__main__":
    main()
