<script setup>
// 家人分享长图:预览即所发。
// 家人版 ≠ 档案版(调研 docs/sharing-research-2026-10-01.md §3):
//   大字号/去内部黑话(id、英文状态)/必带截至日期/familyNotes 永不出现在此。
// 条目级分享 = 卡片分享时按条勾选(主场景:给长辈的「一条口径」)。
// 页面级整页分享 2026-10-10 改为板面所见即所得直出(App.shareBoard 截 #grid),
// 本组件只服务卡级(卡片 ⤴)与问题级(详情层)两类家人卡。
import { ref, computed, watch } from 'vue'
import { domToPng } from 'modern-screenshot'
import { monthsAge, nearestMilestone, dueKey, cnpunct, fullDate, issueDayNo } from '../lib/util.js'
import { anticipatoryNodes } from '../lib/anticipatory-ref.js'

const props = defineProps({
  open: Boolean,
  level: { type: String, default: 'card' },   // 'card' | 'issue'
  block: { type: Object, default: null },     // card 级的目标卡
  kid: { type: Object, default: () => ({}) },
  issue: { type: Object, default: null },     // issue 级的问题对象(从详情层来)
})
const emit = defineEmits(['close'])

const anonymized = ref(false)
const branded = ref(true)
const exporting = ref(false)
const selected = ref([])       // card/issue 级:条目勾选
const nodeEl = ref(null)

// 状态转人话(家人版不出现 S1/effective 这类内部口径)
const MS = { ok: '已会', watch: '观察中', todo: '还没会' }
const TITLES = { 'profile': '孩子档案', 'milestone': '里程碑',
  'anticipatory': '前瞻',
  'note': '成长速记',
  'focus': '今日与回访',
  'issue': '问题追踪', 'growth': '生长记录',
  'text': '便签', 'list': '清单' }

// custom cards carry their own title in props
function titleFor(b) {
  if (!b) return ''
  if (b.type === 'text' || b.type === 'list') return b.props?.title || TITLES[b.type]
  return TITLES[b.type] || b.type
}

const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 每种卡 → 通用行模型(kind 决定渲染分支);一律返回 { rows, ...附加信息 }
// 问题级(issue):从口径卡渲染,why/how 条目可勾选剔除(templates.md 问题分享卡节)
const ISSUE_ST = { active: '进行中', watching: '观察中', resolved: '已解决' }

const issuePack = computed(() => {
  const i = props.issue
  if (!i) return null
  const b = i.brief || {}
  const rows = []
  if (b.what) rows.push({ kind: 'issue-what', text: b.what, label: '情况', fixed: true, group: '现在的情况' })
  const why = (b.why || []).map(w => ({ kind: 'issue-why', text: w, label: `为什么·${w.slice(0, 8)}` }))
  if (why.length) { why[0].group = '为什么这么做'; rows.push(...why) }
  const how = (b.how || []).map(h => ({ kind: 'issue-how', text: h, label: `怎么做·${h.slice(0, 8)}` }))
  if (how.length) { how[0].group = '全家怎么做'; rows.push(...how) }
  if (b.redline) rows.push({ kind: 'issue-red', text: b.redline, label: '就医线', fixed: true })
  const srcs = (b.sources || []).map(x => ({ kind: 'issue-src', text: x, label: `依据·${x.slice(0, 8)}` }))
  if (srcs.length) { srcs[0].group = '依据'; rows.push(...srcs) }
  return { rows, st: ISSUE_ST[i.status] || i.status, dayNoTxt: issueDayNo(i), name: i.name }
})

function rowsFor(b) {
  const kid = props.kid || {}
  const t = b?.type
  if (t === 'issue') {
    // 卡/页级的问题卡分享:一问题一行(名+状态+当前摘要),就医线跟着所属问题走;
    // 完整口径卡(情况→为什么→怎么做)在问题详情层的「分享问题卡」里
    const want = b?.props?.status
    const rows = []
    for (const i of (kid.issues || [])) {
      if (!(want ? i.status === want : i.status !== 'resolved')) continue
      rows.push({ kind: 'issue-row', label: i.name, name: i.name,
        st: ISSUE_ST[i.status] || i.status, stRaw: i.status,
        dayNoTxt: issueDayNo(i),
        care: i.pendingCare || '', summary: i.summary || '' })
      if (i.brief?.redline)
        rows.push({ kind: 'issue-red', label: `${i.name}·就医线`, text: i.brief.redline, fixed: true })
    }
    return { rows }
  }
  if (t === 'growth') {
    const rows = (kid.growth?.records || []).slice(-6).map(r => ({
      kind: 'growth', label: r.date, date: r.date, height: r.height, weight: r.weight }))
    return { rows }
  }
  if (t === 'milestone') {
    const m = b?.props?.months || nearestMilestone(monthsAge(kid.birthdate))
    const data = kid.milestones?.[m]
    const rows = (data?.items || [])
      .map(i => ({ kind: 'milestone', label: i.domain, st: MS[i.status] || i.status,
        stRaw: i.status, domain: i.domain, text: i.text }))
    return { m, source: data?.source, rows }
  }
  if (t === 'note') {
    // 与 NotesCard 同源同序(最新在前):页面看到什么,长图就发什么
    const rows = (kid.notes || []).slice(-(b?.props?.limit || 5)).reverse()
      .map(n => ({ kind: 'note', label: (n.precision && n.precision !== 'day' ? '≈' : '') + n.date,
        approx: n.precision && n.precision !== 'day', date: n.date, tags: n.tags || [], text: n.text }))
    return { rows }
  }
  if (t === 'profile') return { rows: [{ kind: 'profile', label: '档案' }] }
  if (t === 'focus') {
    // 今日与回访:就医待办+窗口回访(-7..+2 天)+在途回访全量(与卡同口径,
    // 2026-10-13 合并待回访卡;kind 'followup' 行渲染器沿用)
    const rows = []
    for (const i of (kid.issues || []))
      if (i.status !== 'resolved' && i.pendingCare)
        rows.push({ kind: 'care', label: `就医待办·${i.name}`, text: i.pendingCare })
    const dDiff = (due) => {
      const d = new Date(fullDate(due))
      if (isNaN(d)) return null
      const today = new Date(); today.setHours(0, 0, 0, 0)
      return Math.round((d - today) / 86400000)
    }
    const pend = (kid.followups || [])
      .filter(f => (f.status || 'pending') === 'pending')
      .sort((a, c) => dueKey(a.due).localeCompare(dueKey(c.due)))
    for (const f of pend) {
      const diff = dDiff(f.due)
      if (diff !== null && diff <= 2 && diff >= -7)
        rows.push({ kind: 'followup', label: f.due, due: f.due, topic: f.topic })
    }
    for (const f of pend) {
      const diff = dDiff(f.due)
      if (diff !== null && diff > 2)
        rows.push({ kind: 'followup', label: f.due, due: f.due, topic: f.topic })
    }
    return { rows }
  }
  if (t === 'anticipatory') {
    // 与卡同口径:记下的(认领提醒)+进行中+接下来(已过不进长图);节点注
    // 一起带走,家人看得懂
    const rows = (kid.reminders || [])
      .filter(r => (r?.status || 'pending') === 'pending')
      .sort((a, c) => dueKey(a.due).localeCompare(dueKey(c.due)))
      .map(r => ({ kind: 'followup', label: r.due, due: r.due, topic: r.topic }))
    for (const r of anticipatoryNodes(kid).filter(r => r.status !== 'past'))
      rows.push({ kind: 'followup', label: r.due ? r.due.slice(0, 7) : '待定',
        due: r.due || '', topic: r.name + (r.note ? ' · ' + r.note : '') })
    return { rows }
  }
  if (t === 'text') {
    const text = (b?.props?.text || '').trim()
    return { rows: text ? [{ kind: 'textline', label: '内容', text }] : [] }
  }
  if (t === 'list') {
    const rows = (b?.props?.items || [])
      .map((it, i) => ({ kind: 'listitem', label: it.text, text: it.text, done: !!it.done, i }))
    return { rows }
  }
  return { rows: [] }
}

const sections = computed(() => {
  if (!props.open) return []
  if (props.level === 'issue') {
    const pack = issuePack.value
    if (!pack) return []
    const rows = pack.rows.filter((_, i) => selected.value[i] !== false)
    return [{ id: 'issue', type: 'issue', title: pack.name, rows, extra: { st: pack.st } }]
  }
  if (!props.block) return []
  const r = rowsFor(props.block)
  const rows = r.rows.filter((_, i) => selected.value[i] !== false)
  return [{ id: props.block.id, type: props.block.type, title: titleFor(props.block), rows, extra: r }]
})

const chips = computed(() => {   // card/issue 级的条目勾选标签
  if (props.level === 'issue') {
    const pack = issuePack.value
    if (!pack) return []
    return pack.rows
      .map((r, i) => ({ r, i }))
      .filter(({ r }) => !r.fixed)
      .map(({ r, i }) => ({ i, on: selected.value[i] !== false, label: r.label }))
  }
  if (props.level !== 'card' || !props.block) return []
  return rowsFor(props.block).rows.map((row, i) => ({ i, on: selected.value[i] !== false, label: row.label }))
})

const age = computed(() => {
  const m = monthsAge(props.kid?.birthdate)
  return m > 0 ? `${m} 个月` : ''
})
const dispName = computed(() => anonymized.value ? '宝宝' : (props.kid?.name || '宝宝'))
const headTitle = computed(() => {
  if (props.level === 'issue') return `${dispName.value}的${issuePack.value?.name || ''}:全家这样做`
  return titleFor(props.block) || '成长卡片'
})
const headSub = computed(() => {
  if (props.level === 'issue') {
    return [age.value, issuePack.value?.st, issuePack.value?.dayNoTxt, `截至 ${todayStr()}`]
      .filter(Boolean).join(' · ')
  }
  return [dispName.value, age.value, `截至 ${todayStr()}`].filter(Boolean).join(' · ')
})

watch(() => [props.open, props.level, props.block?.id], () => {
  selected.value = []
})

function toggleRow(i) { selected.value[i] = selected.value[i] === false ? true : false }

const fileTitle = () => {
  if (props.level === 'issue') return `${issuePack.value?.name || '问题'}-全家这样做`
  return titleFor(props.block) || '卡片'
}
async function save() {
  if (!nodeEl.value || exporting.value) return
  exporting.value = true
  try {
    const url = await domToPng(nodeEl.value, { scale: 2, backgroundColor: '#ffffff' })
    const blob = await (await fetch(url)).blob()
    const name = `成长分享-${dispName.value}-${fileTitle()}-${todayStr()}.png`
    const file = new File([blob], name, { type: 'image/png' })
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], title: name }); return }
      catch (e) { if (e?.name === 'AbortError') return }
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name
    a.click()
    URL.revokeObjectURL(a.href)
  } finally { exporting.value = false }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="share-mask" @click.self="emit('close')">
      <div class="share-dialog">
        <div class="share-head">
          <b>分享给家人</b><span class="hint">预览即所发 · 长图发微信</span>
          <button class="x" @click="emit('close')">✕</button>
        </div>

        <div class="share-body">
          <aside class="share-side">
            <div class="opt-chips">
              <label class="opt-chip" :class="{ on: anonymized }">
                <input type="checkbox" v-model="anonymized">隐去小名</label>
              <label class="opt-chip" :class="{ on: branded }">
                <input type="checkbox" v-model="branded">署名页脚</label>
            </div>

            <div v-if="chips.length" class="share-chips">
              <span class="chip" :class="{ off: !c.on }" v-for="c in chips" :key="c.i"
                    @click="toggleRow(c.i)">{{ c.on ? '✓ ' : '' }}{{ c.label }}</span>
            </div>

            <div class="side-foot">
              <button class="btn primary" :disabled="exporting" @click="save">{{ exporting ? '生成中…' : '保存长图' }}</button>
            </div>
          </aside>

          <div class="share-scroll">
          <div class="share-card" ref="nodeEl">
            <div class="sc-head">
              <div class="sc-title">{{ headTitle }}</div>
              <div class="sc-sub">{{ headSub }}</div>
            </div>

            <div v-for="sec in sections" :key="sec.id" class="sc-sec">

              <template v-for="(row, i) in sec.rows" :key="i">
                <div v-if="row.group" class="sc-sec-title">{{ row.group }}</div>
                <div v-if="row.kind === 'issue-what'" class="sc-row issue-what">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-why'" class="sc-row issue-why">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-how'" class="sc-row issue-how">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-red'" class="sc-red">
                  <b>出现这些当天就医：</b>{{ cnpunct(row.text) }}
                </div>
                <div v-else-if="row.kind === 'issue-row'" class="sc-row issuerow">
                  <div class="r1">
                    <b>{{ row.name }}</b>
                    <span class="pill" :class="row.stRaw === 'active' ? 'watch'
                      : row.stRaw === 'resolved' ? 'ok' : 'plain'">{{ row.st }}</span>
                    <span class="since" style="margin:0 0 0 auto">{{ row.dayNoTxt }}</span>
                  </div>
                  <div v-if="row.care" class="careline">就医待办：{{ cnpunct(row.care) }}</div>
                  <div v-if="row.summary" class="main">{{ cnpunct(row.summary) }}</div>
                </div>
                <div v-else-if="row.kind === 'growth'" class="sc-row growthrow">
                  <span class="date">{{ fullDate(row.date) }}</span>
                  <span class="main">身高 {{ row.height ?? '—' }} cm · 体重 {{ row.weight ?? '—' }} kg</span>
                </div>
                <div v-else-if="row.kind === 'issue-src'" class="sc-row issue-src">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'milestone'" class="sc-row milestone">
                  <span class="pill" :class="row.stRaw">{{ row.st }}</span>
                  <span class="domain">{{ row.domain }}</span>
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'care'" class="sc-red">
                  <b>就医待办：</b>{{ cnpunct(row.text) }}
                </div>
                <div v-else-if="row.kind === 'followup'" class="sc-row followup">
                  <span class="due">{{ fullDate(row.due) }}</span><span class="main">{{ cnpunct(row.topic) }}</span>
                </div>
                <div v-else-if="row.kind === 'note'" class="sc-row note">
                  <span class="date">{{ row.approx ? '≈' : '' }}{{ fullDate(row.date) }}</span>
                  <span v-for="t in row.tags" :key="t" class="ntag">{{ t }}</span>
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'profile'" class="sc-row profile">
                  <div class="kv"><b>孩子</b><span>{{ dispName }}{{ age ? `(${age})` : '' }}</span></div>
                  <div class="kv" v-if="(kid.currentFocus || []).length"><b>当前关注</b>
                    <span class="focus">{{ kid.currentFocus.join('、') }}</span></div>
                </div>
                <div v-else-if="row.kind === 'focus'" class="sc-row focusrow">
                  <span class="ftag">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'textline'" class="sc-row textline">
                  <span class="main" style="white-space:pre-wrap">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'listitem'" class="sc-row listrow" :class="{ done: row.done }">
                  <span class="box">{{ row.done ? '☑' : '☐' }}</span>
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
              </template>

              <div v-if="!sec.rows.length" class="sc-empty">暂无内容</div>
              <div v-if="sec.extra?.source" class="sc-src">来源：{{ sec.extra.source }}</div>
              <div v-if="sec.extra?.note" class="sc-src">{{ sec.extra.note }}</div>
            </div>

            <div class="sc-foot">{{ branded ? '由 parent-guide 生成' : '\u00a0' }}</div>
          </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* A·生长图纸(与页面同系统):坐标纸底+墨蓝+serif 数字+描边小章 */
.share-mask { position: fixed; inset: 0; background: rgba(30,58,82,.58); z-index: 50;
  display: flex; align-items: center; justify-content: center; padding: 20px; }
.share-dialog { background: #fdfdfb; border-radius: 12px; width: min(920px, 100%);
  max-height: 92vh; display: flex; flex-direction: column; overflow: hidden;
  box-shadow: 0 12px 40px rgba(30,58,82,.22); }
.share-head { display: flex; align-items: center; gap: 10px; padding: 12px 16px;
  background: #fff; border-bottom: 1px solid var(--grid-line); }
.share-head b { font-size: 15px; color: var(--ink); }
.share-head .hint { font-size: 12.5px; color: var(--sub); }
.share-head .x { margin-left: auto; border: 0; background: none; font-size: 15px;
  cursor: pointer; color: var(--sub); padding: 4px 8px; }
.share-body { display: grid; grid-template-columns: 264px minmax(0, 1fr);
  min-height: 0; flex: 1; }
@media (max-width: 760px) { .share-body { grid-template-columns: 1fr; }
  .share-side { border-right: 0; border-bottom: 1px solid var(--grid-line); } }
.share-side { border-right: 1px solid var(--grid-line); background: #fff;
  padding: 14px 16px; display: flex; flex-direction: column; gap: 12px; overflow: auto; }
.opt-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.opt-chip { position: relative; display: inline-flex; align-items: center;
  border: 1px solid var(--grid-line); border-radius: 6px; padding: 4px 12px 4px 10px;
  font-size: 12.5px; cursor: pointer; user-select: none; color: var(--sub); }
.opt-chip input { position: absolute; opacity: 0; pointer-events: none; }
.opt-chip.on { border-color: var(--ink-blue); background: var(--accent-soft);
  color: var(--ink-blue); }
.opt-chip.on::before { content: '✓'; font-size: 12.5px; margin-right: 5px; }
.share-chips { display: flex; flex-wrap: wrap; gap: 6px; }
.share-chips .chip { background: #fff; color: var(--ink-blue); border: 1px solid var(--grid-line);
  border-radius: 6px;
  padding: 2px 10px; font-size: 12.5px; cursor: pointer; user-select: none; max-width: 100%;
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.share-chips .chip.off { background: #f0f3f6; color: var(--sub); border-color: transparent; text-decoration: line-through; }
.side-foot { margin-top: auto; padding-top: 10px; }
.side-foot .btn { width: 100%; border: 0; background: var(--ink-blue); color: #fff;
  border-radius: 8px; padding: 9px 16px; font-size: 12.5px; cursor: pointer; }
.side-foot .btn:disabled { opacity: .5; }
.share-scroll { overflow: auto; padding: 16px;
  display: flex; justify-content: center;
  align-items: flex-start; }   /* 不 stretch:卡片高度=内容高,网格背景才铺全 */

/* ↓ 导出节点:自包含、375px 手机宽、大字号(家人版);坐标纸底 */
.share-card { width: 375px; background-color: #fff;
  background-image:
    linear-gradient(rgba(90,130,180,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(90,130,180,.06) 1px, transparent 1px);
  background-size: 14px 14px;
  border: 1px solid var(--grid-line); border-radius: 10px;
  padding: 20px 22px 14px; color: var(--ink); font-size: 15px; line-height: 1.65;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.sc-head { border-bottom: 1px solid var(--grid-line); padding-bottom: 10px; margin-bottom: 10px; }
.sc-title { font-size: 20px; font-weight: 700; color: var(--ink-blue); }
.sc-sub { font-size: 12.5px; color: var(--sub); margin-top: 2px; font-variant-numeric: tabular-nums; }
.sc-sec { padding: 4px 0; }
.sc-sec-title { font-size: 12.5px; font-weight: 600; color: var(--sub);
  letter-spacing: .2em; margin: 10px 0 2px; }
.sc-row { padding: 9px 0; border-bottom: 1px dashed var(--grid-line); }
.sc-row:last-child { border-bottom: none; }
.sc-row .r1 { display: flex; align-items: center; gap: 8px; }
.sc-row .r1 b { font-size: 16px; }
.pill { flex: none; font-size: 12.5px; border-radius: 5px; padding: 1px 8px; }
.pill.ok { background: var(--ok-bg); color: var(--ok); }
.pill.watch { background: var(--watch-bg); color: var(--watch); }
.pill.plain { background: #f0f3f6; color: var(--sub); }
.issuerow .careline { font-size: 12.5px; color: var(--todo); margin: 2px 0 3px; }
.growthrow { display: flex; gap: 10px; align-items: baseline; }
.growthrow .date { flex: none; color: var(--sub); font-family: Georgia, serif;
  font-variant-numeric: tabular-nums; }
.pill.todo { background: var(--todo-bg); color: var(--todo); }
.since { font-size: 12.5px; color: var(--sub); margin: 1px 0 3px; font-variant-numeric: tabular-nums; }
.main { display: block; }
.fu { font-size: 12.5px; color: var(--sub); margin-top: 3px; }
.milestone { display: flex; gap: 8px; align-items: baseline; font-size: 15px; }
.milestone .pill { min-width: 3.4em; text-align: center; }
.milestone .domain { flex: none; width: 5em; color: var(--sub); font-size: 14px; }
.followup { display: flex; gap: 10px; align-items: baseline; }
.followup .due { flex: none; background: var(--accent-soft); color: var(--ink-blue);
  border-radius: 5px; padding: 1px 8px; font-size: 12.5px;
  font-family: Georgia, serif; font-weight: 700; }
.note .date { flex: none; color: var(--sub); margin-right: 6px; font-size: 14px;
  font-family: Georgia, serif; }
.note .ntag { display: inline-block; background: #fff; color: var(--ink-blue);
  border: 1px solid var(--grid-line); border-radius: 5px; padding: 0 6px; font-size: 11.5px; margin-right: 4px; }
.profile .kv { display: flex; gap: 10px; padding: 3px 0; font-size: 15px; }
.profile .kv b { flex: none; color: var(--sub); font-weight: 500; min-width: 4.5em; }
.focusrow .ftag { display: inline-block; background: #fff; color: var(--ink-blue);
  border: 1px solid var(--grid-line); border-radius: 6px; padding: 3px 12px; font-size: 15px; margin: 0 6px 6px 0; }
.sc-red { background: var(--todo-bg); border: 1px solid var(--todo); border-radius: 8px;
  padding: 10px 12px; margin: 10px 0; font-size: 14px; }
.sc-red b { color: var(--todo); }
.textline .main { font-size: 15px; }
.listrow { display: flex; gap: 8px; align-items: baseline; }
.listrow .box { flex: none; color: var(--ink-blue); }
.listrow.done .main { color: var(--sub); text-decoration: line-through; }
.sc-empty { color: var(--sub); font-size: 14px; padding: 8px 0; }
.sc-src { font-size: 11.5px; color: var(--sub); margin-top: 6px; }
.issue-src .main { font-size: 12.5px; color: var(--sub); }
.sc-foot { text-align: center; color: var(--sub); font-size: 11.5px; margin-top: 14px; }
</style>
