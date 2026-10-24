<script setup>
// 页面卡(2026-10-24 拍板:卡=小页面,text/list 退役存量兼容)——
// AI 从锁定样式的积木词汇表自由组装,框架管样式、大模型管编排:
//   section 小节标题 / p 段落 / rows 要点行(自动序号) / kv 键值行 /
//   check 勾选组(可交互,同 ListCard local-first) / callout 提示|警示条。
// 未知 kind 一律按 p 渲染(fail-soft:AI 自由发挥不崩卡);
// 全部文本渲染层过 cnpunct(源数据半角不动,8b 口径 finally 齐了)。
import { computed, ref, watch } from 'vue'
import { cnpunct } from '../../lib/util.js'

const props = defineProps({ block: Object, kid: Object })
const emit = defineEmits(['update'])

const title = computed(() => props.block?.props?.title || '页面')
const LIMIT_BLOCKS = 30
const LIMIT_ITEMS = 30

const blocks = computed(() =>
  (Array.isArray(props.block?.props?.blocks) ? props.block.props.blocks : [])
    .slice(0, LIMIT_BLOCKS)
    .map(bl => {
      if (!bl || typeof bl !== 'object') return { kind: 'p', text: String(bl ?? '') }
      const kind = ['section', 'p', 'rows', 'kv', 'check', 'callout'].includes(bl.kind) ? bl.kind : 'p'
      if (kind === 'rows' || kind === 'check') {
        const items = (Array.isArray(bl.items) ? bl.items : [])
          .slice(0, LIMIT_ITEMS)
          .map(it => typeof it === 'string' ? { text: it } : (it && typeof it === 'object' ? it : null))
          .filter(it => it && String(it.text || '').trim())
        return { ...bl, kind, items }
      }
      return { ...bl, kind, text: bl.text ?? '' }
    })
    .filter(bl => bl.kind === 'rows' || bl.kind === 'check'
      ? (bl.items || []).length > 0
      : String(bl.text ?? '').trim() || String(bl.label ?? '').trim()))

// check 组 local-first 交互(ListCard 同款):即时 UI,再经 update 持久化整份 blocks
const localChecks = ref({})
watch(() => props.block?.props?.blocks, v => { localChecks.value = {} })

function toggleCheck(bi, ii) {
  const src = blocks.value[bi]
  const key = `${bi}`
  const items = (localChecks.value[key] || src.items).map((it, idx) =>
    idx === ii ? { ...it, done: !it.done } : it)
  localChecks.value = { ...localChecks.value, [key]: items }
  const next = props.block.props.blocks.map((bl, idx) =>
    idx === bi ? { ...bl, items: items.map(it => ({ text: it.text, done: !!it.done })) } : bl)
  emit('update', { blocks: next })
}
const checkItemsOf = (bi) => localChecks.value[`${bi}`] || blocks.value[bi].items
const punct = (s) => cnpunct(String(s ?? ''))
</script>

<template>
  <div class="cband"><h3>{{ title }}</h3></div>
  <div class="cbody">
    <template v-if="blocks.length">
      <template v-for="(bl, bi) in blocks" :key="bi">
        <div v-if="bl.kind === 'section'" class="pg-sec">{{ punct(bl.text) }}</div>
        <p v-else-if="bl.kind === 'p'" class="pg-p">{{ punct(bl.text) }}</p>
        <div v-else-if="bl.kind === 'rows'" class="pg-rows">
          <div v-for="(it, i) in bl.items" :key="i" class="pg-row">
            <span class="idx num-serif">{{ i + 1 }}</span><span>{{ punct(it.text) }}</span>
          </div>
        </div>
        <div v-else-if="bl.kind === 'kv'" class="pg-kv">
          <b>{{ punct(bl.label) }}</b><span>{{ punct(bl.text) }}</span>
        </div>
        <div v-else-if="bl.kind === 'check'" class="pg-check">
          <label v-for="(it, i) in checkItemsOf(bi)" :key="i" class="pg-li" :class="{ done: it.done }">
            <input type="checkbox" :checked="!!it.done" @change="toggleCheck(bi, i)">
            <span>{{ punct(it.text) }}</span>
          </label>
        </div>
        <div v-else-if="bl.kind === 'callout'" class="pg-callout" :class="bl.tone === 'warn' ? 'warn' : 'hint'">
          {{ punct(bl.text) }}
        </div>
      </template>
    </template>
    <div v-else class="src">空页面——回到对话对 AI 说「把{{ title }}排成…」即可组装内容。</div>
  </div>
</template>

<style scoped>
.pg-sec { font-size: 11.5px; letter-spacing: .08em; color: var(--sub); margin: 12px 0 4px; }
.pg-sec:first-child { margin-top: 2px; }
.pg-p { font-size: 14px; color: var(--ink); line-height: 1.7; margin: 6px 0; }
.pg-p:first-child { margin-top: 0; }
.pg-rows { margin: 4px 0; }
.pg-row { display: flex; gap: 10px; align-items: baseline; font-size: 14px; line-height: 1.6;
  padding: 6px 0; border-bottom: 1px dashed var(--line); }
.pg-row:last-child { border-bottom: none; }
.pg-row .idx { flex: none; min-width: 1.4em; text-align: right; color: var(--ink-blue);
  font-weight: 600; font-size: 14px; }
.pg-kv { display: flex; gap: 12px; font-size: 14px; padding: 6px 0;
  border-bottom: 1px dashed var(--line); }
.pg-kv:last-child { border-bottom: none; }
.pg-kv b { flex: none; min-width: 3.6em; color: var(--ink-blue); font-weight: 600; }
.pg-kv span { flex: 1; min-width: 0; }
.pg-check { margin: 4px 0; }
.pg-li { display: flex; gap: 8px; font-size: 14px; padding: 5px 0; cursor: pointer; align-items: baseline; }
.pg-li input { accent-color: var(--accent); }
.pg-li.done span { color: var(--sub); text-decoration: line-through; }
.pg-callout { font-size: 12.5px; border: 1px solid; border-radius: 8px;
  padding: 8px 12px; margin: 8px 0; line-height: 1.6; }
.pg-callout.hint { color: var(--hint); border-color: var(--hint); background: var(--hint-bg); }
.pg-callout.warn { color: var(--todo); border-color: var(--todo); background: var(--todo-bg); }
</style>
