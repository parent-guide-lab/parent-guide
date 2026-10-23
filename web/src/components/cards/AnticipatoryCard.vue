<script setup>
// 前瞻卡(2026-10-21 用户拍板方案 C 时间线合流,demo 留档
// demo/ui-2026-10/anticipatory-sections-2026-10-21.html):认领的提醒与
// 机械推导节点不再分两区,合流成一条按月分组的竖向时间线,「今天」锚线
// 定住当下,来源用徽章区分——「留意」(墨蓝描边)=家长在对话里认领的
// 提醒,其余=节点表(出生日期+日历机械推导,与 knowledge/anticipatory.md
// 同源,lib/anticipatory-ref.js 两处同步改)。与提醒的自动关联刻意不做
// (topic 自由文本与节点名的匹配是模糊判断):同主题条目并排可见即归一。
import { computed } from 'vue'
import { cnpunct } from '../../lib/util.js'
import { anticipatoryNodes } from '../../lib/anticipatory-ref.js'

const props = defineProps({ block: Object, kid: Object })

// 提醒标题/备注拆分:机械规则=第一个冒号(全角/半角)前为标题、其后为
// 备注;无冒号则整句为标题。不猜语义。
function splitTopic(topic) {
  const t = String(topic || '')
  const i = t.search(/[::]/)
  if (i < 0) return { title: t, note: '' }
  return { title: t.slice(0, i), note: t.slice(i + 1).trim() }
}

const now = new Date()
const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`

// 合流条目:pending 提醒(留意)+未过节点(进行中/接下来),统一形状后
// 按日期排序。无 due 的节点(如「该想想托班安排了」)排序时置顶。
const mergedAll = computed(() => {
  const items = []
  for (const r of (props.kid?.reminders || [])
    .filter(r => (r?.status || 'pending') === 'pending')) {
    const s = splitTopic(r.topic)
    items.push({ due: r.due || '', badge: '留意', cls: 'mine',
      name: s.title, note: s.note, odue: r.due < today })
  }
  for (const r of anticipatoryNodes(props.kid)) {
    if (r.status === 'past') continue
    items.push({ due: r.due || '', badge: r.kind, cls: 'k',
      name: r.status === 'active' ? `${r.name}——正在窗口期` : r.name,
      note: r.active ? r.note : '' })
  }
  return items.sort((a, b) => a.due.localeCompare(b.due))
})
// 「下一站」签名件(中改拍板 2026-10-22,demo/ui-card-mid):第一个有 due 且
// 未过的条目升为倒计时头条,并从时间线中移除(不重复);纯机械可算。
// 已过期的(odue)不进头条——它是「过期」状态,时间线里红色日期已表达。
const nextStop = computed(() =>
  mergedAll.value.find(it => it.due && it.due >= today) || null)
const merged = computed(() =>
  nextStop.value ? mergedAll.value.filter(it => it !== nextStop.value) : mergedAll.value)
// 窗口期计数(卡头副行):节点表中 status=active 的机械数量
const activeCount = computed(() =>
  anticipatoryNodes(props.kid).filter(r => r.status === 'active').length)
const daysUntil = (due) => {
  const d = new Date(due + 'T00:00:00')
  const t = new Date(today + 'T00:00:00')
  if (isNaN(d)) return null
  return Math.max(0, Math.round((d - t) / 86400000))
}

// 机械预算:前 5 个月组(当月算第 1 个;demo 拍板形态),更多月份滚动可见
const groups = computed(() => {
  const byYm = new Map()
  for (const it of merged.value) {
    const k = it.due ? it.due.slice(0, 7) : '待定'
    if (!byYm.has(k)) byYm.set(k, [])
    byYm.get(k).push(it)
  }
  return [...byYm.entries()].slice(0, 5)
})

const pastText = computed(() => {
  const past = anticipatoryNodes(props.kid)
    .filter(r => r.status === 'past')
    .sort((a, b) => b.due.localeCompare(a.due))
  return past.length
    ? `最近已过:${past[0].name}(${past[0].due.slice(0, 7)})`
      + (past.length > 1 ? ` · 共 ${past.length} 项` : '')
    : ''
})
</script>

<template>
  <div class="cband"><h3>前瞻</h3><div v-if="activeCount" class="cbsub"><span>在窗口期 {{ activeCount }} 项</span></div></div>
  <div class="cbody">
    <template v-if="groups.length || nextStop">
      <div v-if="nextStop" class="next-sign">
        <div class="ns-label">下一站 · {{ nextStop.badge }}</div>
        <div class="ns-big">
          <span class="n">{{ daysUntil(nextStop.due) }}</span><span class="u">{{ daysUntil(nextStop.due) === 0 ? '今天到期' : '天后' }}</span>
          <span class="due">{{ nextStop.due.slice(5) }}</span>
        </div>
        <div class="ns-what">{{ nextStop.name }}</div>
        <div v-if="nextStop.note" class="ns-note">{{ cnpunct(nextStop.note) }}</div>
      </div>
      <div class="tl">
        <div class="tl-now"><span class="nowline">今天 · {{ today }}</span></div>
        <div v-for="[ym, rs] in groups" :key="ym" class="tl-g">
          <div class="tl-m"><b>{{ ym }}</b></div>
          <template v-for="(r, i) in rs" :key="i">
            <div class="tl-row">
              <span class="st" :class="r.cls">{{ r.badge }}</span>
              <span class="t">{{ r.name }}</span>
              <span class="d" :class="{ od: r.odue }">{{ r.due ? r.due.slice(5) : '' }}</span>
            </div>
            <div v-if="r.note" class="tl-note">{{ cnpunct(r.note) }}</div>
          </template>
        </div>
      </div>
      <div v-if="pastText" class="psrc">{{ pastText }}</div>
      <div v-if="!kid?.birthdate" class="src">还没填生日——对话里补上后,这里按月龄铺开疫苗/体检/筛查时间线。</div>
    </template>
    <div v-else-if="!kid?.birthdate" class="src">还没填生日——对话里补上后,这里按月龄铺开疫苗/体检/筛查时间线。</div>
    <div v-else class="src">0-5 岁的前瞻节点都走完了,后续以儿保预约与当地要求为准。</div>
  </div>
</template>

<style scoped>
/* 「下一站」倒计时签名件(中改拍板):27 Georgia 天数+截止日 mono,实线分界 */
.next-sign { padding-bottom: 12px; margin-bottom: 10px; border-bottom: 1px solid var(--line); }
.ns-label { font-size: 11.5px; color: var(--sub); letter-spacing: .08em; }
.ns-big { display: flex; align-items: baseline; gap: 6px; margin-top: 4px; }
.ns-big .n { font-family: Georgia, "Times New Roman", serif; font-size: 27px;
  font-weight: 700; line-height: 1; color: var(--ink-blue); }
.ns-big .u { font-size: 11.5px; color: var(--sub); }
.ns-big .due { margin-left: auto; font-size: 11.5px; color: var(--sub);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums; }
.ns-what { font-size: 14px; font-weight: 600; line-height: 1.5; margin-top: 4px; }
.ns-note { font-size: 12.5px; color: var(--sub); line-height: 1.55; margin-top: 2px; }
.tl { position: relative; padding-left: 14px; }
.tl::before { content: ""; position: absolute; left: 3.5px; top: 6px; bottom: 6px;
  width: 1px; background: var(--grid-line); }
.tl-now { position: relative; margin: 4px 0 8px; }
.tl-now::before { content: ""; position: absolute; left: -14px; top: 5px; width: 8px; height: 8px;
  border-radius: 50%; background: var(--ink-blue); }
.nowline { display: flex; align-items: center; gap: 8px; font-size: 11.5px; color: var(--ink-blue); }
.nowline::after { content: ""; flex: 1; border-top: 1px dashed var(--grid-line); }
.tl-g > :last-child { border-bottom: none; }
.tl-m { position: relative; margin: 10px 0 2px; }
.tl-m::before { content: ""; position: absolute; left: -14px; top: 5.5px; width: 8px; height: 8px;
  border-radius: 50%; background: #fff; border: 1.5px solid var(--ink-blue); }
.tl-m b { font-family: Georgia, serif; font-variant-numeric: tabular-nums;
  color: var(--ink-blue); font-size: 12.5px; font-weight: 600; }
.tl-row { display: flex; gap: 8px; align-items: baseline; padding: 3px 0;
  font-size: 12.5px; border-bottom: 1px dashed var(--grid-line); }
.tl-row .t { min-width: 0; flex: 1; line-height: 1.5; }
.tl-row .d { flex: none; font-size: 11.5px; color: var(--sub);
  font-family: Georgia, serif; font-variant-numeric: tabular-nums; }
.tl-row .d.od { color: var(--todo); }
.tl-note { font-size: 11.5px; color: var(--sub); line-height: 1.5; padding: 1px 0 4px; }
.st.mine { background: transparent; color: var(--ink-blue); border-color: var(--ink-blue); }
.st.k { color: var(--sub); }
.psrc { font-size: 11.5px; color: var(--sub); margin-top: 10px; }
</style>
