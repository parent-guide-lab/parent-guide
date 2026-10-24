<script setup>
// Checkbox toggles are local-first (instant UI, no parent re-render needed --
// GridBoard snapshots are deliberately non-reactive for GridStack compat),
// then persisted upward via 'update' -> GridBoard 'props-update' -> App.
import { computed, ref, watch } from 'vue'
import { cnpunct } from '../../lib/util.js'
const props = defineProps({ block: Object, kid: Object })
// 存量渲染兼容(list 已退役):标点归一同现役口径
const punct = (s) => cnpunct(String(s ?? ''))
const emit = defineEmits(['update'])
const title = computed(() => props.block?.props?.title || '清单')
const items = ref([...(props.block?.props?.items || [])])

watch(() => props.block?.props?.items, v => { items.value = [...(v || [])] })

function toggle(i) {
  items.value = items.value.map((it, idx) => idx === i ? { ...it, done: !it.done } : it)
  emit('update', { items: items.value.map(it => ({ text: it.text, done: !!it.done })) })
}
const doneCount = computed(() => items.value.filter(i => i.done).length)
const pct = computed(() => items.value.length
  ? Math.round(doneCount.value / items.value.length * 100) : 0)
const allDone = computed(() => items.value.length > 0 && doneCount.value === items.value.length)
</script>

<template>
  <div class="cband">
    <h3>{{ punct(title) }}</h3>
    <div v-if="items.length" class="cbsub">
      <span class="head-stats"><span :class="allDone ? 'ok' : ''"><b>{{ doneCount }}</b>/{{ items.length }}</span></span>
    </div>
  </div>
  <div class="cbody">
    <template v-if="items.length">
      <div class="track" :title="`${doneCount}/${items.length}`">
        <div class="fill" :class="{ done: allDone }" :style="{ width: pct + '%' }"></div>
      </div>
      <label v-for="(it, i) in items" :key="i" class="li" :class="{ done: it.done }">
        <input type="checkbox" :checked="it.done" @change="toggle(i)">
        <span>{{ punct(it.text) }}</span>
      </label>
    </template>
    <div v-else class="src">清单为空——回到对话对 AI 说「{{ punct(title) }}加上…」即可补充条目。</div>
  </div>
</template>

<style scoped>
.track { background: var(--line); border-radius: 4px; height: 6px; overflow: hidden; margin-bottom: 10px; }
.fill { height: 100%; border-radius: 4px;
  background: var(--ink-blue); opacity: .82;
  transition: width .25s; }
.fill.done { background: var(--ok); opacity: 1; }
.li { display: flex; gap: 8px; font-size: 14px; padding: 4px 0; cursor: pointer; align-items: baseline; }
.li input { accent-color: var(--accent); }
.li.done span { color: var(--sub); text-decoration: line-through; }
</style>
