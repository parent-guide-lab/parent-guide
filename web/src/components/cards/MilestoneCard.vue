<script setup>
import { computed, inject, ref } from 'vue'
import { monthsAge, nearestMilestone, cnpunct } from '../../lib/util.js'

const props = defineProps({ block: Object, kid: Object })
// 页级长图生成期间强制展开(App 注入;平时为 false,用户折叠状态不受影响)
const capExpand = inject('captureExpand', { value: false })
const capForce = computed(() => !!capExpand.value)
const stLabel = { ok: '已会', watch: '观察', todo: '尚未' }

const pack = computed(() => {
  const m = props.block?.props?.months || nearestMilestone(monthsAge(props.kid?.birthdate))
  return { m, data: props.kid?.milestones?.[m] || null }
})
const counts = computed(() => {
  const items = pack.value.data?.items || []
  const c = { ok: 0, watch: 0, todo: 0 }
  for (const i of items) if (c[i.status] !== undefined) c[i.status]++
  return c
})
const assessed = computed(() => pack.value.data?.assessed || '')
const allDone = computed(() => pack.value.data && counts.value.watch + counts.value.todo === 0)
// 全达标时列表默认折叠(头部数字即结论),有观察/未现项才默认展开
const folded = ref(true)

// 下一档盘点钩子(纯计算,与档案卡同源):档位表里第一个大于当前月龄的档
const STEPS = [18, 24, 30, 36, 48, 60]
const nextStep = computed(() => {
  const age = monthsAge(props.kid?.birthdate)
  if (!age || !props.kid?.birthdate) return null
  const m = STEPS.find(s => s > age)
  if (!m) return null
  const b = new Date(props.kid.birthdate)
  const d = new Date(b.getFullYear(), b.getMonth() + m, b.getDate())
  return { months: m, ym: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }
})
</script>

<template>
  <div class="cband">
    <h3>里程碑 · {{ pack.m }} 月</h3>
    <div v-if="nextStep" class="cbsub">
      <span>下一档 <b>{{ nextStep.months }} 月</b> · {{ nextStep.ym }} 前后</span>
    </div>
  </div>
  <div class="cbody">
    <template v-if="pack.data">
      <div class="mnums num-serif">
        <span class="mn"><i style="color:var(--ok)">{{ counts.ok }}</i><small>已会</small></span>
        <span class="mn"><i style="color:var(--watch)">{{ counts.watch }}</i><small>观察</small></span>
        <span class="mn"><i style="color:var(--todo)">{{ counts.todo }}</i><small>尚未</small></span>
      </div>
      <div v-if="allDone && folded && !capForce" class="alldone">
        全部达标 ✓ {{ assessed ? `基线 ${assessed}` : '' }}
        <button class="tgl" @click="folded = false">展开 {{ counts.ok }} 项 ▸</button>
      </div>
      <template v-else>
        <div v-for="(i, idx) in (pack.data.items || [])" :key="idx" class="mrow">
          <span class="st" :class="i.status">{{ stLabel[i.status] || i.status }}</span>
          <span style="color:var(--sub);flex:none;width:5.5em">{{ cnpunct(i.domain) }}</span>
          <span>{{ cnpunct(i.text) }}</span>
        </div>
        <button v-if="allDone" class="tgl" @click="folded = true">收起 ▴</button>
      </template>
      <div class="src">来源：{{ cnpunct(pack.data.source) }}<template v-if="assessed"> · 盘于 {{ assessed }}</template></div>
    </template>
    <div v-else class="src">还没盘过这个月龄。回到对话说「做个发育盘点」，几分钟判定完会显示在这里。</div>
  </div>
</template>

<style scoped>
.mnums { display: flex; gap: 16px; margin-bottom: 10px; }
.mn { text-align: center; }
.mn i { display: block; font-style: normal; font-size: 27px; font-weight: 700; line-height: 1.15; }
.mn small { font-size: 10.5px; color: var(--sub); letter-spacing: .06em; }
.alldone { font-size: 12.5px; color: var(--ok); margin: 2px 0 4px; }
.tgl { border: 0; background: none; color: var(--ink-blue); font-size: 12.5px;
  cursor: pointer; padding: 2px 0; font: inherit; display: block; }
.tgl:hover { text-decoration: underline; }
/* 窄屏触控目标(规范:命中区 ≥44px) */
@media (max-width: 720px) { .tgl { padding: 10px 0; } }
</style>
