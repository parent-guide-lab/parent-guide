<script setup>
// 前瞻卡(2026-10-13 用户拍板合并:前瞻提醒卡退役,认领的 reminders 并入
// 「记下的」区置顶):记下的(认领制,空则整区不渲染)/进行中(窗口内)/
// 接下来(按月归组)/最近已过。节点部分=出生日期+日历机械推导,与
// knowledge/anticipatory.md 同源(lib/anticipatory-ref.js,两处同步改)。
// 与提醒的自动关联刻意不做(topic 自由文本与节点名的匹配是模糊判断)。
import { computed } from 'vue'
import { dueKey, dueLabel, fullDate } from '../../lib/util.js'
import { anticipatoryNodes } from '../../lib/anticipatory-ref.js'

const props = defineProps({ block: Object, kid: Object })

// 认领的提醒(原前瞻提醒卡全量):家长说「帮我留意」才落档的事项
const claimed = computed(() =>
  (props.kid?.reminders || [])
    .filter(r => (r?.status || 'pending') === 'pending')
    .sort((a, b) => dueKey(a.due).localeCompare(dueKey(b.due))))
const rel = (due) => dueLabel(due).label

const rows = computed(() => anticipatoryNodes(props.kid))
const active = computed(() => rows.value.filter(r => r.status === 'active'))
const groups = computed(() => {
  const byYm = new Map()
  for (const r of rows.value.filter(r => r.status === 'upcoming')) {
    const k = r.due.slice(0, 7)
    if (!byYm.has(k)) byYm.set(k, [])
    byYm.get(k).push(r)
  }
  return [...byYm.entries()].slice(0, 4).map(([ym, rs]) => ({
    ym, names: rs.map(r => r.name).join(' · '),
    notes: rs.map(r => r.note).filter(Boolean).join('；'),
  }))
})
const past = computed(() => rows.value.filter(r => r.status === 'past')
  .sort((a, b) => b.due.localeCompare(a.due)))
const pastText = computed(() => past.value.length
  ? `最近已过:${past.value[0].name}(${past.value[0].due.slice(0, 7)})`
    + (past.value.length > 1 ? ` · 共 ${past.value.length} 项` : '')
  : '')
</script>

<template>
  <div class="cband"><h3>前瞻</h3></div>
  <div class="cbody">
    <template v-if="kid?.birthdate">
      <template v-if="claimed.length">
        <div class="glabel first">记下的</div>
        <div v-for="(r, i) in claimed" :key="'r' + i" class="rrow">
          <span class="due-b" :class="dueLabel(r.due).urgency || 'plain'">
            {{ fullDate(r.due) }}<template v-if="rel(r.due)"> · {{ rel(r.due) }}</template>
          </span>
          <span class="rtopic">{{ r.topic }}</span>
        </div>
      </template>

      <div v-for="r in active" :key="r.id" class="anode">
        <div class="aline">
          <span class="st k">{{ r.kind }}</span>
          <span class="aname">{{ r.name }}</span>
          <span class="adue">{{ r.due ? fullDate(r.due) : '待定' }}</span>
        </div>
        <div v-if="r.note" class="anote">{{ r.note }}</div>
      </div>
      <template v-if="groups.length">
        <div class="glabel" :class="{ first: !claimed.length && !active.length }">接下来</div>
        <div v-for="g in groups" :key="g.ym" class="grow" :title="g.notes">
          <b>{{ g.ym }}</b><span>{{ g.names }}</span>
        </div>
      </template>
      <div v-if="pastText" class="psrc">{{ pastText }}</div>
      <div v-if="!active.length && !groups.length" class="src">
        0-5 岁的前瞻节点都走完了,后续以儿保预约与当地要求为准。
      </div>
    </template>
    <template v-else-if="claimed.length">
      <div class="glabel first">记下的</div>
      <div v-for="(r, i) in claimed" :key="'r' + i" class="rrow">
        <span class="due-b" :class="dueLabel(r.due).urgency || 'plain'">
          {{ fullDate(r.due) }}<template v-if="rel(r.due)"> · {{ rel(r.due) }}</template>
        </span>
        <span class="rtopic">{{ r.topic }}</span>
      </div>
      <div class="src">还没填生日——对话里补上后,这里按月龄铺开疫苗/体检/筛查时间线。</div>
    </template>
    <div v-else class="src">还没填生日——对话里补上后,这里按月龄铺开疫苗/体检/筛查时间线。</div>
  </div>
</template>

<style scoped>
.glabel { font-size: 11.5px; color: var(--sub); letter-spacing: .08em; margin: 10px 0 4px;
  padding-top: 8px; border-top: 1px dashed var(--grid-line); }
.glabel.first { margin-top: 0; padding-top: 0; border-top: none; }
.rrow { display: flex; gap: 10px; align-items: baseline; padding: 5px 0;
  border-bottom: 1px dashed var(--grid-line); font-size: 14px; }
.rrow:last-of-type { border-bottom: none; }
.rtopic { min-width: 0; flex: 1; }
.anode { border: 1px solid var(--ink-blue); border-radius: 6px; padding: 7px 10px;
  margin: 10px 0 8px; }
.aline { display: flex; gap: 8px; align-items: baseline; }
.st.k { color: var(--sub); }
.aname { font-size: 14px; font-weight: 600; }
.adue { margin-left: auto; flex: none; font-size: 11.5px; color: var(--sub);
  font-family: Georgia, serif; font-variant-numeric: tabular-nums; }
.anote { font-size: 12.5px; color: var(--sub); margin-top: 3px; line-height: 1.5; }
.grow { display: flex; gap: 10px; font-size: 12.5px; padding: 5px 0;
  border-bottom: 1px dashed var(--grid-line); align-items: baseline; }
.grow b { flex: none; font-family: Georgia, serif; font-variant-numeric: tabular-nums;
  color: var(--ink-blue); font-weight: 600; font-size: 12.5px; }
.grow span { min-width: 0; line-height: 1.55; }
.psrc { font-size: 11.5px; color: var(--sub); margin-top: 10px; }
</style>
