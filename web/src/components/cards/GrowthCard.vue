<script setup>
// Growth chart card: records vs WS/T 423-2022 P3-P97 reference bands.
// Data: knowledge/growth.md (human) == lib/growth-ref.js (machine) -- keep in sync.
// Honest-display rules: no gender -> no band (points only); screening not
// diagnosis (T2 wording on out-of-band, guide to 儿保, never "abnormal").
import { computed, inject, ref } from 'vue'
import { monthsAge } from '../../lib/util.js'
import { GROWTH_REF, refAt } from '../../lib/growth-ref.js'

const props = defineProps({ block: Object, kid: Object })

// 详细记录默认收起:曲线+最新值+趋势是读卡主信息,逐条数据按需展开
// (MilestoneCard 同款 .tgl 语言);页级长图生成期间强制展开(App 注入
// captureExpand,2026-10-21「内容都包含」拍板),平时不受影响。
const listOpen = ref(false)
const capExpand = inject('captureExpand', { value: false })
const capForce = computed(() => !!capExpand.value)

const records = computed(() => {
  const recs = (props.kid?.growth?.records || []).slice()
  // months come from add-growth; compute defensively for hand-added rows
  for (const r of recs) {
    if (r.months == null && props.kid?.birthdate) {
      r.months = monthsAge(props.kid.birthdate, r.date)
    }
  }
  return recs.sort((a, b) => String(a.date).localeCompare(String(b.date)))
})
const latest = computed(() => records.value[records.value.length - 1] || null)

const genderKey = computed(() => {
  const g = String(props.kid?.profile?.gender || '')
  if (g.includes('男')) return 'boys'
  if (g.includes('女')) return 'girls'
  return null
})

// band position of the latest measurement, per metric
function position(metric, v, months) {
  if (!genderKey.value) return null
  const ref = refAt(genderKey.value, metric, months)
  if (!ref) return null
  if (v < ref.p3) return { cls: 'out-low', label: '低于 P3', tip: '建议儿保评估（筛查线，非诊断）' }
  if (v > ref.p97) return { cls: 'out-high', label: '高于 P97', tip: '建议儿保评估（筛查线，非诊断）' }
  const where = v >= (ref.p3 + ref.p50) / 2 ? '区间中上段' : '区间中下段'
  return { cls: 'in', label: `P3-P97 内 · ${where}`, tip: '沿自身通道稳定生长即为正常' }
}
const hPos = computed(() => latest.value?.height ? position('height', latest.value.height, latest.value.months) : null)
const wPos = computed(() => latest.value?.weight ? position('weight', latest.value.weight, latest.value.months) : null)

// 趋势滑档检测(knowledge/growth.md §2「连续跨越两条主要百分位线」的页面侧
// 机械镜像):参考带四分=低于P3/P3-P50/P50-P97/高于P97,相邻两次记录跨
// ≥2 带=偏离自身通道(向上=超速也查),跨 1 带=先复测(家庭测量误差常见)。
// 三线只是标准曲线的子集,该口径偏保守(更难触发,不误报)。
const BAND_NAMES = ['P3 下方', 'P3-P50', 'P50-P97', 'P97 上方']
function bandIdx(metric, v, months) {
  if (!genderKey.value) return null
  const ref = refAt(genderKey.value, metric, months)
  if (!ref) return null
  if (v < ref.p3) return 0
  if (v < ref.p50) return 1
  return v <= ref.p97 ? 2 : 3
}
const trendRows = computed(() => {
  if (!genderKey.value || records.value.length < 2) return []
  const rows = []
  for (const [metric, label] of [['height', '身高'], ['weight', '体重']]) {
    const pts = records.value.filter(r => r[metric] != null)
    if (pts.length < 2) continue
    const a = pts[pts.length - 2], b = pts[pts.length - 1]
    const i0 = bandIdx(metric, a[metric], a.months), i1 = bandIdx(metric, b[metric], b.months)
    if (i0 == null || i1 == null || i0 === i1) continue
    rows.push({ label, cross: Math.abs(i1 - i0), up: i1 > i0,
      from: BAND_NAMES[i0], to: BAND_NAMES[i1] })
  }
  return rows
})
const trendStable = computed(() => genderKey.value && records.value.length >= 2
  && !trendRows.value.length)

// -- SVG chart ---------------------------------------------------------------
// viewBox 300x102; band + P50 + child's polyline + axes. Left 30 / bottom 14
// viewBox units are gutters for tick labels so values read without hover.
const PL = 30, PR = 8, PT = 8, PB = 84  // plot rect inside the viewBox
function chart(metric) {
  const recs = records.value.filter(r => r[metric] != null)
  if (recs.length < 2) return null
  const band = genderKey.value ? GROWTH_REF[genderKey.value][metric] : null
  const months = recs.map(r => r.months)
  const x0 = Math.min(0, ...months), x1 = Math.max(...months) + 2
  const vals = recs.map(r => r[metric])
  let lo = Math.min(...vals), hi = Math.max(...vals)
  if (band) {
    for (const a of band.ages) {
      if (a < x0 || a > x1) continue
      lo = Math.min(lo, band.p3[band.ages.indexOf(a)])
      hi = Math.max(hi, band.p97[band.ages.indexOf(a)])
    }
  }
  const pad = (hi - lo) * 0.08 || 1
  lo -= pad; hi += pad
  const X = (m) => PL + (m - x0) / (x1 - x0) * (300 - PL - PR)
  const Y = (v) => PB - (v - lo) / (hi - lo) * (PB - PT)
  let bandPath = ''
  if (band) {
    const up = [], down = []
    for (const a of band.ages) {
      if (a < x0 || a > x1) continue
      up.push(`${X(a)},${Y(band.p97[band.ages.indexOf(a)])}`)
      down.push(`${X(a)},${Y(band.p3[band.ages.indexOf(a)])}`)
    }
    bandPath = 'M' + up.join(' L') + ' L' + down.reverse().join(' L') + ' Z'
  }
  // polyline points 只认坐标列表,不能带路径命令 L(带了整条线不渲染)
  const line = recs.map(r => `${X(r.months)},${Y(r[metric])}`).join(' ')
  let p50Line = ''
  if (band) {
    const pts = []
    for (const a of band.ages) {
      if (a < x0 || a > x1) continue
      pts.push(`${X(a)},${Y(band.p50[band.ages.indexOf(a)])}`)
    }
    p50Line = pts.join(' ')
  }
  // y 刻度:1/2/5×10^k 步进,目标 ~4 条;x 刻度:每 6 个月
  const step = [1, 2, 5, 10, 20, 50].find(s => (hi - lo) / s <= 4.5) || 50
  const yTicks = []
  for (let v = Math.ceil(lo / step) * step; v <= hi; v += step)
    yTicks.push({ v, y: Y(v), t: step >= 1 ? String(Math.round(v)) : (Math.round(v * 10) / 10).toFixed(1) })
  const xTicks = []
  for (let m = Math.ceil(x0 / 6) * 6; m <= x1; m += 6) xTicks.push({ m, x: X(m) })
  // 节点数值标签:默认点上方,与前一标签横向太挤(<14 单位)时翻到点下方
  const dots = [], labels = []
  let prevX = -99
  for (const r of recs) {
    const x = X(r.months), y = Y(r[metric])
    dots.push({ x, y, v: r[metric], date: r.date,
      out: genderKey.value && (r[metric] < refAt(genderKey.value, metric, r.months)?.p3
        || r[metric] > refAt(genderKey.value, metric, r.months)?.p97) })
    const above = x - prevX >= 14
    if (above) prevX = x
    labels.push({ x, y: above ? y - 5.5 : y + 11, t: String(r[metric]) })
  }
  // 最新月龄处的参考区间数值(图例行直读,出带时对着数字看差多少)
  const last = recs[recs.length - 1]
  const lastRef = band ? refAt(genderKey.value, metric, last.months) : null
  const bandTxt = lastRef
    ? `参考 ${last.months}月：P3 ${lastRef.p3.toFixed(1)} · P50 ${lastRef.p50.toFixed(1)} · P97 ${lastRef.p97.toFixed(1)}`
    : ''
  return { bandPath, line, p50Line, dots, labels, yTicks, xTicks, bandTxt, x0, x1 }
}
const hChart = computed(() => chart('height'))
const wChart = computed(() => chart('weight'))

// 悬停读数:竖向参考线 + 任意月龄的推荐值(参考带连续插值,不只限记录点),
// 2 个月龄内有实测则附带实测值;flip=参考线靠右时浮层右对齐防溢出。
const hoverH = ref(null), hoverW = ref(null)
function chartHover(metric, state, evt) {
  const c = state === 'h' ? hChart.value : wChart.value
  if (!c) return
  const rect = evt.currentTarget.getBoundingClientRect()
  const vx = (evt.clientX - rect.left) * 300 / rect.width
  const month = Math.round(c.x0 + (vx - PL) / (300 - PL - PR) * (c.x1 - c.x0))
  if (month < c.x0 || month > c.x1) return chartLeave(state)
  const x = PL + (month - c.x0) / (c.x1 - c.x0) * (300 - PL - PR)
  const ref = genderKey.value ? refAt(genderKey.value, metric, month) : null
  let best = null
  for (const r of records.value.filter(r => r[metric] != null))
    if (!best || Math.abs(r.months - month) < Math.abs(best.months - month)) best = r
  const rec = best && Math.abs(best.months - month) <= 2
    ? { months: best.months, v: best[metric], date: best.date } : null
  const val = { month, x, ref, rec, flip: x > 205 }
  if (state === 'h') hoverH.value = val; else hoverW.value = val
}
function chartLeave(state) { if (state === 'h') hoverH.value = null; else hoverW.value = null }
const list = computed(() => records.value.slice(-6).reverse())
</script>

<template>
  <div class="cband">
    <h3>生长曲线</h3>
    <div v-if="records.length" class="cbsub">
      <span class="head-stats">
        <span>共 <b>{{ records.length }}</b> 条</span>
        <span v-if="latest">最近 {{ latest.date }}</span>
      </span>
    </div>
  </div>
  <div class="cbody">
  <template v-if="records.length">

    <div v-if="latest && (latest.height || latest.weight)" class="latest">
      <div class="lm">{{ latest.months }} 月龄</div>
      <div v-if="latest.height" class="lv">
        <span class="lk">身高</span><b>{{ latest.height }}</b><span class="lu">cm</span>
        <span v-if="hPos" class="pos" :class="hPos.cls">{{ hPos.label }}</span>
      </div>
      <div v-if="latest.weight" class="lv">
        <span class="lk">体重</span><b>{{ latest.weight }}</b><span class="lu">kg</span>
        <span v-if="wPos" class="pos" :class="wPos.cls">{{ wPos.label }}</span>
      </div>
    </div>

    <div v-if="trendRows.length" class="trend-wrap">
      <div v-for="t in trendRows" :key="t.label" class="trend" :class="t.cross >= 2 ? 'alert' : 'mild'">
        <span class="tw">{{ t.label }}较上次 {{ t.from }} → {{ t.to }}</span>
        <span class="tt">{{ t.cross >= 2
          ? (t.up ? '上跨两条参考线，超速生长也建议评估' : '下跨两条参考线，偏离自身通道')
          : '跨一条参考线——先复测确认，家庭测量误差常见' }}<template v-if="t.cross >= 2">；复测仍如此，带记录看儿保</template></span>
      </div>
    </div>
    <div v-if="trendStable" class="trend calm">两次记录同一参考区间，沿自身通道稳定生长</div>

    <div v-if="hChart" class="chart">
      <div class="ct">身高 cm<span v-if="genderKey" class="cb">{{ hChart.bandTxt }}</span></div>
      <div class="cwrap">
        <svg viewBox="0 0 300 102" @mousemove="chartHover('height', 'h', $event)" @mouseleave="chartLeave('h')">
          <path v-if="hChart.bandPath" :d="hChart.bandPath" class="band" />
          <polyline v-if="hChart.p50Line" :points="hChart.p50Line" class="p50" />
          <line v-for="t in hChart.yTicks" :key="'yg'+t.v" :x1="30" :x2="292" :y1="t.y" :y2="t.y" class="gridline" />
          <polyline :points="hChart.line" class="cline" />
          <circle v-for="(d, i) in hChart.dots" :key="i" :cx="d.x" :cy="d.y" r="2" :class="d.out ? 'cdot out' : 'cdot'" />
          <text v-for="(l, i) in hChart.labels" :key="'hl'+i" :x="l.x" :y="l.y" class="dlabel" text-anchor="middle">{{ l.t }}</text>
          <line v-if="hoverH" :x1="hoverH.x" :x2="hoverH.x" :y1="8" :y2="84" class="hguid" />
          <line :x1="30" :x2="30" :y1="8" :y2="84" class="axis" />
          <line :x1="30" :x2="292" :y1="84" :y2="84" class="axis" />
          <line v-for="t in hChart.xTicks" :key="'xt'+t.m" :x1="t.x" :x2="t.x" :y1="84" :y2="87" class="axis" />
          <text v-for="t in hChart.yTicks" :key="'yt'+t.v" :x="27" :y="t.y + 2" class="tick" text-anchor="end">{{ t.t }}</text>
          <text v-for="t in hChart.xTicks" :key="'xl'+t.m" :x="t.x" :y="95" class="tick" text-anchor="middle">{{ t.m }}</text>
          <text :x="292" :y="95" class="tick" text-anchor="end">月龄</text>
        </svg>
        <div v-if="hoverH" class="tip" :class="{ flip: hoverH.flip }" :style="{ left: (hoverH.x / 300 * 100) + '%' }">
          <b>{{ hoverH.month }} 月龄</b>
          <span v-if="hoverH.ref">推荐 P3 {{ hoverH.ref.p3.toFixed(1) }} · P50 {{ hoverH.ref.p50.toFixed(1) }} · P97 {{ hoverH.ref.p97.toFixed(1) }}</span>
          <span v-if="hoverH.rec">实测 {{ hoverH.rec.v }}（{{ hoverH.rec.months }}月 {{ hoverH.rec.date }}）</span>
        </div>
      </div>
    </div>
    <div v-if="wChart" class="chart">
      <div class="ct">体重 kg<span v-if="genderKey" class="cb">{{ wChart.bandTxt }}</span></div>
      <div class="cwrap">
        <svg viewBox="0 0 300 102" @mousemove="chartHover('weight', 'w', $event)" @mouseleave="chartLeave('w')">
          <path v-if="wChart.bandPath" :d="wChart.bandPath" class="band" />
          <polyline v-if="wChart.p50Line" :points="wChart.p50Line" class="p50" />
          <line v-for="t in wChart.yTicks" :key="'yg'+t.v" :x1="30" :x2="292" :y1="t.y" :y2="t.y" class="gridline" />
          <polyline :points="wChart.line" class="cline" />
          <circle v-for="(d, i) in wChart.dots" :key="i" :cx="d.x" :cy="d.y" r="2" :class="d.out ? 'cdot out' : 'cdot'" />
          <text v-for="(l, i) in wChart.labels" :key="'wl'+i" :x="l.x" :y="l.y" class="dlabel" text-anchor="middle">{{ l.t }}</text>
          <line v-if="hoverW" :x1="hoverW.x" :x2="hoverW.x" :y1="8" :y2="84" class="hguid" />
          <line :x1="30" :x2="30" :y1="8" :y2="84" class="axis" />
          <line :x1="30" :x2="292" :y1="84" :y2="84" class="axis" />
          <line v-for="t in wChart.xTicks" :key="'xt'+t.m" :x1="t.x" :x2="t.x" :y1="84" :y2="87" class="axis" />
          <text v-for="t in wChart.yTicks" :key="'yt'+t.v" :x="27" :y="t.y + 2" class="tick" text-anchor="end">{{ t.t }}</text>
          <text v-for="t in wChart.xTicks" :key="'xl'+t.m" :x="t.x" :y="95" class="tick" text-anchor="middle">{{ t.m }}</text>
          <text :x="292" :y="95" class="tick" text-anchor="end">月龄</text>
        </svg>
        <div v-if="hoverW" class="tip" :class="{ flip: hoverW.flip }" :style="{ left: (hoverW.x / 300 * 100) + '%' }">
          <b>{{ hoverW.month }} 月龄</b>
          <span v-if="hoverW.ref">推荐 P3 {{ hoverW.ref.p3.toFixed(1) }} · P50 {{ hoverW.ref.p50.toFixed(1) }} · P97 {{ hoverW.ref.p97.toFixed(1) }}</span>
          <span v-if="hoverW.rec">实测 {{ hoverW.rec.v }}（{{ hoverW.rec.months }}月 {{ hoverW.rec.date }}）</span>
        </div>
      </div>
    </div>
    <div v-if="!genderKey" class="src">档案未填性别，暂无参考区间对照——回对话补一下性别即可。</div>

    <button class="tgl" @click="listOpen = !listOpen">{{ listOpen ? '收起 ▴' : `详细记录 ${records.length} 条 ▸` }}</button>
    <div v-if="listOpen || capForce" class="rlist">
      <div class="rrow rhead"><span class="rd">日期</span><span class="rm">月龄</span><span class="rv">身高</span><span class="rv">体重</span></div>
      <div v-for="r in list" :key="r.date" class="rrow">
        <span class="rd">{{ r.date }}</span>
        <span class="rm">{{ r.months }}月</span>
        <span class="rv">{{ r.height ? r.height + 'cm' : '—' }}</span>
        <span class="rv">{{ r.weight ? r.weight + 'kg' : '—' }}</span>
      </div>
    </div>
    <div class="src">区间：WS/T 423—2022（<a class="klink" href="site/growth.html" target="_blank">知识库·生长监测</a>） · 筛查参照非诊断，出区间或跨百分位线建议儿保<template v-if="records.length < 2">；再记一笔（下月儿保/在家量）即长出曲线与参考带</template></div>
  </template>
  <div v-else class="src">还没有生长记录——儿保体检本的身高体重抄回来：对话里说「记一下身高体重」，曲线和参考区间就亮了。</div>
  </div>
</template>

<style scoped>
.latest { background: var(--accent-soft); border-radius: 10px; padding: 8px 12px;
  font-size: 12.5px; margin-bottom: 10px; }
.latest .lm { color: var(--sub); font-size: 12.5px; margin-bottom: 3px; }
.latest .lv { display: flex; align-items: baseline; gap: 6px; }
.latest .lk { flex: none; width: 2.6em; color: var(--sub); font-size: 12.5px; }
.latest .lu { flex: none; width: 1.8em; color: var(--sub); font-size: 12.5px; }
.latest .lv b { font-size: 16px; }
.pos { font-size: 11.5px; border-radius: 6px; padding: 1px 8px; }
.pos.in { background: var(--ok-bg); color: var(--ok); }
.pos.out-low { background: var(--todo-bg); color: var(--todo); }
.pos.out-high { background: var(--watch-bg); color: var(--watch); }
.trend-wrap { display: flex; flex-direction: column; gap: 6px; margin-bottom: 10px; }
.trend { border: 1px solid var(--line); border-radius: 6px; padding: 6px 10px;
  font-size: 12.5px; line-height: 1.5; }
.trend.alert { border-color: var(--todo); }
.trend.mild { border-color: var(--watch); }
.trend.calm { border-color: var(--line); color: var(--ok); }
.trend .tw { font-weight: 600; }
.trend .tt { color: var(--sub); margin-left: 6px; }
.chart { margin-bottom: 6px; }
.ct { font-size: 12.5px; color: var(--sub); margin-bottom: 2px; }
.ct .cb { float: right; font-size: 11.5px; }
svg { width: 100%; height: auto; display: block; }
.band { fill: rgba(90,130,180,.10); stroke: none; }
.p50 { fill: none; stroke: var(--sub); stroke-width: 1; stroke-dasharray: 4 3; }
.cline { fill: none; stroke: var(--id, var(--ink-blue)); stroke-width: 2; }
.cdot { fill: #fff; stroke: var(--id, var(--ink-blue)); stroke-width: 1.5; }
.cdot.out { fill: var(--todo); stroke: var(--todo); }
.gridline { stroke: var(--line); stroke-width: .5; opacity: .7; }
.axis { stroke: var(--line); stroke-width: 1; }
.tick { font-size: 6px; fill: var(--sub); }
.dlabel { font-size: 6px; font-weight: 600; fill: var(--ink-blue); }
.rlist { margin-top: 4px; }
.tgl { border: 0; background: none; color: var(--ink-blue); font-size: 12.5px;
  cursor: pointer; padding: 2px 0; display: block; }
.tgl:hover { text-decoration: underline; }
/* 窄屏触控目标(规范:命中区 ≥44px) */
@media (max-width: 720px) { .tgl { padding: 10px 0; } }
.rrow { display: grid; grid-template-columns: 1fr 3.4em 4.4em 4.8em; gap: 0 14px;
  align-items: baseline; font-size: 12.5px; padding: 4px 8px;
  font-variant-numeric: tabular-nums; border-radius: 6px; }
.rrow:not(.rhead):hover { background: var(--accent-soft); }
.rhead { color: var(--sub); font-size: 11.5px; padding-bottom: 3px;
  border-bottom: 1px solid var(--line); }
.rd { color: var(--sub); }
.rm, .rv { text-align: right; }
.cwrap { position: relative; }
.hguid { stroke: var(--accent); stroke-width: .75; stroke-dasharray: 2 2; opacity: .7; }
.tip { position: absolute; top: 4px; transform: translateX(-50%); background: #fff;
  border: 1px solid var(--line); border-radius: 8px; padding: 4px 9px;
  font-size: 11.5px; line-height: 1.55; pointer-events: none; white-space: nowrap;
  box-shadow: 0 2px 8px rgba(90,130,180,.18); z-index: 2;
  display: flex; flex-direction: column; }
.tip.flip { transform: translateX(-100%); }
.tip b { font-size: 12.5px; color: var(--id, var(--ink-blue)); }
.tip span { color: var(--sub); }
</style>
