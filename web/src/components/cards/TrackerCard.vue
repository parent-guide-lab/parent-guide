<script setup>
// tracker 台账卡(M1,2026-10-22 验收集背书 docs/custom-card-acceptance-2026-10-22.md):
// 自定义卡第三型——分组台账(绘本管理/用药记录/奖励表)。props 自含,对话生产;
// 构件只有两个:head(机械计数——AI 只声明统计口径,数值渲染器从 items 现算,
// 加条目不漏改)+ list(按 group 首现顺序分组的行式列表)。
// 样式全锁图纸语言:mnums 大数字(里程碑/问题卡同族)/st 描边徽章(全局)/
// Georgia 组标题(前瞻卡月分组同族)/虚线行分隔。
import { computed } from 'vue'
import { cnpunct } from '../../lib/util.js'
const props = defineProps({ block: Object, kid: Object })
const punct = (s) => cnpunct(String(s ?? ''))

const p = computed(() => props.block?.props || {})
const title = computed(() => p.value.title || '记录')
// 容错渲染(fail-soft):坏条目剔除而非整卡崩,结构性损坏由 server POST 拦在前
const items = computed(() =>
  (Array.isArray(p.value.items) ? p.value.items : [])
    .filter(it => it && typeof it === 'object' && String(it.text || '').trim()))

// head 机械计数(设计铁律「结构化只给机械操作」的卡内版):声明口径,现算数值
const head = computed(() => {
  const h = Array.isArray(p.value.head) ? p.value.head.slice(0, 4) : []
  return h
    .map(x => {
      if (!x || !String(x.label || '').trim()) return null
      let n = null
      if (x.count === 'items') n = items.value.length
      else if (x.count === 'group' && String(x.eq || '').trim())
        n = items.value.filter(i => i.group === x.eq).length
      return n === null ? null : { label: x.label, tone: x.tone || 'ink-blue', n }
    })
    .filter(Boolean)
})

// 分组:按 group 首次出现顺序;无 group 的条目平铺在最前(无组标题)
const groups = computed(() => {
  const out = []
  const idx = new Map()
  for (const it of items.value) {
    const g = typeof it.group === 'string' ? it.group : ''
    if (!idx.has(g)) { idx.set(g, out.length); out.push({ label: g, items: [] }) }
    out[idx.get(g)].items.push(it)
  }
  return out
})
const toneOf = (it) =>
  ['ok', 'watch', 'todo', 'sub'].includes(it.tone) ? it.tone : 'sub'
</script>

<template>
  <div class="cband"><h3>{{ punct(title) }}</h3></div>
  <div class="cbody">
    <template v-if="items.length">
      <div v-if="head.length" class="mnums num-serif">
        <span v-for="(h, i) in head" :key="i" class="mn">
          <i :style="{ color: `var(--${h.tone})` }">{{ h.n }}</i><small>{{ punct(h.label) }}</small>
        </span>
      </div>
      <div v-for="(g, gi) in groups" :key="gi" class="tgrp">
        <div v-if="g.label" class="tgrp-t">{{ punct(g.label) }} · {{ g.items.length }}</div>
        <div v-for="(it, ii) in g.items" :key="ii" class="trow">
          <span v-if="it.badge" class="st" :class="toneOf(it)">{{ punct(it.badge) }}</span>
          <span class="t">{{ punct(it.text) }}</span>
          <span v-if="it.meta" class="meta">{{ punct(it.meta) }}</span>
        </div>
      </div>
    </template>
    <div v-else class="src">还没有条目——回到对话对 AI 说「{{ punct(title) }}加上…」即可记录。</div>
  </div>
</template>

<style scoped>
.mnums { display: flex; gap: 16px; margin-bottom: 10px; }
.mn { text-align: center; }
.mn i { display: block; font-style: normal; font-size: 27px; font-weight: 700; line-height: 1.15; }
.mn small { font-size: 10.5px; color: var(--sub); letter-spacing: .06em; }
.tgrp { margin-top: 10px; }
.tgrp-t { font-family: Georgia, "Times New Roman", serif; font-variant-numeric: tabular-nums;
  color: var(--id, var(--ink-blue)); font-size: 12.5px; font-weight: 600; margin-bottom: 2px;
  }
.trow { display: flex; gap: 8px; align-items: baseline; padding: 6px 0;
  border-bottom: 1px dashed var(--line); font-size: 14px; }
.trow:last-child { border-bottom: none; }
.trow .t { flex: 1; min-width: 0; line-height: 1.5; }
.trow .meta { flex: none; font-size: 11.5px; color: var(--sub); text-align: right;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums; }
.st.sub { background: transparent; color: var(--sub); border-color: var(--sub); }
/* 窄屏触控:行式只读无交互钮,行距即命中区,无需加垫 */
</style>
