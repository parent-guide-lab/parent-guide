<script setup>
// 在跑计划卡(2026-10-23,必要性验证 docs/plan-card-demand-scan-2026-10-23.md §4:
// 真实档案孤儿计划 S1+家人分享缺口)。轻解:读 child.strategies 现有数据,零新校验
// (生产者 add-strategy/set-status 既有)。在跑=active/partial/effective(与 focus 卡
// 卡头计数同口径),按「试行中最显眼」排序;收尾(ineffective/suspended/absorbed)
// 默认折叠计数(issue 卡「已解决」同款交互,capExpand 强制展开)。挂问题的计划
// 行内带 P 号可点开病历(与档案卡当前关注 chips 同语言)。
import { computed, inject, ref } from 'vue'
import { fullDate, cnpunct } from '../../lib/util.js'

const props = defineProps({ block: Object, kid: Object })
const emit = defineEmits(['open-issue'])

// 页级长图生成期间强制展开收尾分组(与里程碑/问题卡同口径)
const capExpand = inject('captureExpand', { value: false })
const capForce = computed(() => !!capExpand.value)

// 状态→[徽章文本, 描边色 class];st 全局样式,sub 色组件内补
const ST = {
  active: ['试行中', 'watch'], partial: ['部分有效', 'watch'],
  effective: ['已成日常', 'ok'], ineffective: ['效果不佳', 'todo'],
  suspended: ['已挂起', 'sub'], absorbed: ['已并入', 'sub'],
}
const RUNNING = ['active', 'partial', 'effective']
const RUN_ORDER = { active: 0, partial: 1, effective: 2 }   // 试行中最显眼

const all = computed(() => props.kid?.strategies || [])
const running = computed(() =>
  all.value.filter(s => RUNNING.includes(s?.status))
    .sort((a, b) => (RUN_ORDER[a.status] ?? 9) - (RUN_ORDER[b.status] ?? 9)))
const closed = computed(() =>
  all.value.filter(s => !RUNNING.includes(s?.status)))
const closedOpen = ref(false)
const closedShown = computed(() =>
  (capForce.value || closedOpen.value) ? closed.value : [])

const stOf = (s) => ST[s?.status] || [s?.status || '未知', 'sub']
// started 存 MM-DD,展示补年(与 issue 时间线同口径的读侧归一)
const startedLabel = (s) => {
  const d = String(s?.started || '')
  return /^\d{2}-\d{2}$/.test(d) ? `${new Date().getFullYear()}-${d}` : fullDate(d)
}
</script>

<template>
  <div class="cband">
    <h3>在跑计划</h3>
    <div v-if="running.length" class="cbsub">
      <span class="head-stats"><span><b>{{ running.length }}</b> 个在跑</span></span>
    </div>
  </div>
  <div class="cbody">
    <template v-if="all.length">
      <div v-for="s in running" :key="s.id" class="srow">
        <div class="shd">
          <span class="st" :class="stOf(s)[1]">{{ stOf(s)[0] }}</span>
          <span class="nm">{{ cnpunct(s.name) }}</span>
          <span class="sd">{{ startedLabel(s) }} 起</span>
        </div>
        <div v-if="s.applied" class="sap">{{ cnpunct(s.applied) }}</div>
        <div v-if="(s.issues || []).length || s.evidence" class="smeta">
          <template v-if="(s.issues || []).length">挂
            <a v-for="pid in s.issues" :key="pid" class="plink"
               title="点击查看病历详情" @click="emit('open-issue', pid)">{{ pid }}</a>
          </template>
          <span v-if="s.evidence" :class="{ lead: (s.issues || []).length }">{{ cnpunct(s.evidence) }}</span>
        </div>
      </div>

      <button v-if="closed.length && !closedOpen && !capForce" class="tgl"
              @click="closedOpen = true">已收尾 {{ closed.length }} 个 ▸</button>
      <button v-else-if="closed.length && closedOpen && !capForce" class="tgl"
              @click="closedOpen = false">收起收尾 ▴</button>
      <div v-for="s in closedShown" :key="'c' + s.id" class="srow dim">
        <div class="shd">
          <span class="st" :class="stOf(s)[1]">{{ stOf(s)[0] }}</span>
          <span class="nm">{{ cnpunct(s.name) }}</span>
          <span class="sd">{{ startedLabel(s) }} 起</span>
        </div>
        <div v-if="s.applied" class="sap">{{ cnpunct(s.applied) }}</div>
      </div>
    </template>
    <div v-else class="src">还没有计划——聊到想养成的习惯或想启动的事（如厕/启蒙/作息调整）时说「帮我定个计划」，这里会列出来，回访到期今日卡见。</div>
  </div>
</template>

<style scoped>
.srow { padding: 7px 0; border-bottom: 1px dashed var(--line); }
.srow:last-child { border-bottom: none; }
.srow.dim { opacity: .82; }   /* 收尾历史:弱一档,与在管区分(issue 卡同语言) */
.shd { display: flex; gap: 8px; align-items: baseline; }
.nm { font-weight: 600; font-size: 14px; min-width: 0; }
.sd { margin-left: auto; flex: none; font-size: 11.5px; color: var(--sub);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums; }
.sap { font-size: 12.5px; color: var(--sub); line-height: 1.55; margin-top: 3px;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.smeta { font-size: 11.5px; color: var(--sub); margin-top: 3px; }
.smeta .lead { margin-left: 8px; }
.plink { color: var(--id, var(--ink-blue)); cursor: pointer; font-weight: 600;
  font-family: Georgia, serif; margin: 0 2px; }
.plink:hover { text-decoration: underline; }
.tgl { border: 0; background: none; color: var(--ink-blue); font-size: 12.5px;
  cursor: pointer; padding: 6px 0 0; display: block; font: inherit; }
.tgl:hover { text-decoration: underline; }
/* 窄屏触控(规范:命中区 ≥44px) */
@media (max-width: 720px) { .tgl { padding: 10px 0; } }
</style>
