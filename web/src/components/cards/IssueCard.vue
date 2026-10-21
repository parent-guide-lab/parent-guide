<script setup>
// 问题追踪入口卡:三色计数(里程碑同款大数字)+问题行。
// 骨架字段直读;next/倒计时从该问题 pending followups 机械派生
// (spec issue-tracking-v1 §2.4,不存冗余字段)。已解决默认只计数,
// 点「已解决」在卡内展开历史分组(留档可查),行同样可开病历层。
import { computed, ref } from 'vue'
import { dueKey, dueLabel, fullDate, issueDayNo } from '../../lib/util.js'

const props = defineProps({ block: Object, kid: Object })
const emit = defineEmits(['open-issue'])

const ST_LABEL = { active: '进行中', watching: '观察中', resolved: '已解决' }
const ST_CLASS = { active: 'watch', watching: 'plain', resolved: 'ok' }

const all = computed(() => props.kid?.issues || [])
const list = computed(() => {
  const want = props.block?.props?.status
  return all.value.filter(i => (want ? i.status === want : i.status !== 'resolved'))
})
const counts = computed(() => ({
  live: all.value.filter(i => i.status === 'active' || i.status === 'watching').length,
  care: all.value.filter(i => i.status !== 'resolved' && i.pendingCare).length,
  done: all.value.filter(i => i.status === 'resolved').length,
}))
// 已解决历史分组:仅当主列表没在显示 resolved(config 未指到 resolved/all)
// 时提供,避免同一问题两行;按结案日最新在上。
const doneList = computed(() =>
  all.value.filter(i => i.status === 'resolved')
    .sort((a, b) => dueKey(b.closed || '').localeCompare(dueKey(a.closed || ''))))
const showDone = computed(() =>
  counts.value.done > 0 && !['resolved', 'all'].includes(props.block?.props?.status))
const doneOpen = ref(false)
function nextOf(i) {
  return (props.kid?.followups || [])
    .filter(f => (f.status || 'pending') === 'pending' && (f.issues || []).includes(i.id))
    .sort((a, b) => dueKey(a.due).localeCompare(dueKey(b.due)))[0] || null
}
</script>

<template>
  <div class="cband">
    <h3>问题追踪</h3>
    <div v-if="counts.care" class="cbsub">
      <span class="care-n">{{ counts.care }} 件就医待办</span>
    </div>
  </div>
  <div class="cbody">
    <template v-if="all.length">
      <div class="mnums num-serif">
        <span class="mn"><i style="color:var(--watch)">{{ counts.live }}</i><small>进行中</small></span>
        <span class="mn"><i style="color:var(--todo)">{{ counts.care }}</i><small>待就医</small></span>
        <span class="mn" :class="{ dim: !counts.done, tog: showDone }"
              :title="showDone ? (doneOpen ? '收起已解决分组' : '展开已解决分组') : null"
              @click="showDone && (doneOpen = !doneOpen)">
          <i style="color:var(--ok)">{{ counts.done }}</i>
          <small>已解决<span v-if="showDone" class="arr" :class="{ up: doneOpen }">▾</span></small>
        </span>
      </div>
      <div v-for="i in list" :key="i.id" class="irow" :class="{ wrap: i.pendingCare }" @click="emit('open-issue', i.id)">
        <span class="st" :class="ST_CLASS[i.status] || 'plain'">{{ ST_LABEL[i.status] || i.status }}</span>
        <span class="nm">{{ i.name }}</span>
        <span class="dy">{{ issueDayNo(i) }}</span>
        <span v-if="i.pendingCare" class="nx full care">{{ i.pendingCare }}</span>
        <span v-else-if="nextOf(i)" class="nx">{{ nextOf(i).due }} · {{ dueLabel(nextOf(i).due).label }}</span>
        <span v-else class="nx">{{ (i.summary || '').slice(0, 14) }}</span>
      </div>
      <div v-for="i in doneList" v-show="showDone && doneOpen" :key="i.id" class="irow done"
           @click="emit('open-issue', i.id)">
        <span class="st ok">已解决</span>
        <span class="nm">{{ i.name }}</span>
        <span class="dy">{{ issueDayNo(i) }}</span>
        <span class="nx">结案 {{ fullDate(i.closed) }}</span>
      </div>
      <div v-if="!list.length && !(showDone && doneOpen)" class="src">当前过滤下没有问题。</div>
    </template>
    <template v-else>
      <div class="src">还没有在管问题——聊到持续议题(便秘/发脾气/戒断类)时开题,记录会自动归集到这里。</div>
    </template>
  </div>
</template>

<style scoped>
.mnums { display: flex; gap: 16px; margin-bottom: 10px; }
.mn { text-align: center; }
.mn i { display: block; font-style: normal; font-size: 27px; font-weight: 700; line-height: 1.15; }
.mn small { font-size: 10.5px; color: var(--sub); letter-spacing: .06em; }
.mn.dim i { font-size: 15px; color: var(--sub); line-height: 1.9; }
.mn.dim small { letter-spacing: .04em; }
.mn.tog { cursor: pointer; user-select: none; }
.mn.tog:hover small { color: var(--ink-blue); }
.mn .arr { display: inline-block; margin-left: 2px; font-size: 10.5px;
  color: var(--sub); transition: transform .15s; }
.mn .arr.up { transform: rotate(180deg); }
.care-n { font-size: 11.5px; color: var(--todo); border: 1px solid var(--todo);
  border-radius: 4px; padding: 0 6px; letter-spacing: .04em; font-weight: 600; }
.irow { display: flex; gap: 8px; align-items: baseline; padding: 7px 0;
  border-bottom: 1px dashed var(--line); font-size: 14px; cursor: pointer; }
.irow:last-child { border-bottom: none; }
.irow.wrap { flex-wrap: wrap; }
.irow .nm { font-weight: 600; }
.irow .dy { color: var(--sub); font-size: 12.5px; font-family: Georgia, serif; }
.irow .nx { color: var(--sub); font-size: 12.5px; margin-left: auto; text-align: right;
  min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 45%; }
.irow .nx.full { flex-basis: 100%; max-width: none; white-space: normal;
  text-align: left; overflow: visible; margin-left: 0; }
.irow.done { opacity: .82; }   /* 历史分组:弱一档,与在管行区分 */
.irow .nx .care { color: var(--todo); }
.irow .nx.full.care { color: var(--todo); }
.st { flex: none; font-size: 10.5px; border: 1px solid; border-radius: 4px; padding: 0 6px;
  min-width: 3.2em; text-align: center; font-weight: 600; letter-spacing: .04em; }
.st.watch { background: transparent; color: var(--watch); border-color: var(--watch); }
.st.ok { background: transparent; color: var(--ok); border-color: var(--ok); }
.st.plain { background: transparent; color: var(--sub); border-color: var(--sub); }
</style>
