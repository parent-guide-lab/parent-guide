<script setup>
// 今日与回访卡(2026-10-13 用户拍板合并:待回访卡退役,全量回访并入本卡):
// 「今天」区=就医待办+≤48h 窗口回访(过期未做也算,-7..+2 天,全机械可算);
// 「接下来的回访」区=窗口外全部 pending 回访(原 FollowupCard 排版平移:
// 日期徽章+主题词粗体+细节分段圆点,行点击开病历);在跑计数入卡头副行,
// 原 rollup「下一节点」由在途区第一行取代。点击行=开对应病历(有挂靠时)。
import { computed } from 'vue'
import { bodyParas, dueKey, dueLabel, fullDate, segLabel, linkKnowledge, escHtml, cnpunct } from '../../lib/util.js'

const props = defineProps({ block: Object, kid: Object })
const emit = defineEmits(['open-issue'])

// 回访细节正文知识引用自动转链(与 NotesCard/IssueDetail 同一 util);
// v-html 吃不到 scoped 样式,seg-lab/.klink 在全局 style.css。
const bodyHtml = (seg) => {
  const lab = segLabel(seg)
  return (lab ? `<b class="seg-lab">${escHtml(lab)}</b>` : '')
    + linkKnowledge(lab ? seg.slice(lab.length) : seg)
}

// 就医待办(常驻,优先级最高):在管问题里所有 pendingCare
const careRows = computed(() =>
  (props.kid?.issues || [])
    .filter(i => i.status !== 'resolved' && i.pendingCare)
    .map(i => ({ issue: i, text: i.pendingCare })))

function dueDiff(due) {
  const d = new Date(fullDate(due))
  if (isNaN(d)) return null
  const today = new Date(); today.setHours(0, 0, 0, 0)
  return Math.round((d - today) / 86400000)
}
// ≤48h 窗口内的回访(过期未做也算今天的事):due 距今天 -7..+2 天
const dueRows = computed(() =>
  (props.kid?.followups || [])
    .filter(f => (f.status || 'pending') === 'pending')
    .map(f => ({ ...f, diff: dueDiff(f.due) }))
    .filter(f => f.diff !== null && f.diff <= 2 && f.diff >= -7)
    .sort((a, b) => a.diff - b.diff))

// 窗口外的在途回访(原待回访卡全量余量),按 due 升序
const upcoming = computed(() =>
  (props.kid?.followups || [])
    .filter(f => (f.status || 'pending') === 'pending')
    .map(f => ({ ...f, diff: dueDiff(f.due) }))
    .filter(f => f.diff !== null && f.diff > 2)
    .sort((a, b) => a.diff - b.diff))

const running = computed(() =>
  (props.kid?.strategies || []).filter(s => ['active', 'effective', 'partial'].includes(s?.status)))

// 「主题:细节」拆两级(冒号前是家长扫读用的主题词);细节段=时间轴同款圆点
function splitTopic(t) {
  const m = String(t || '').split(/[:：]/)
  return m.length > 1 ? { lead: m[0], rest: m.slice(1).join(':').trim() } : { lead: t, rest: '' }
}
const restParas = (t) => bodyParas(t)
const dueBadge = (f) => {
  const { label, urgency } = dueLabel(f.due)
  return { text: label || fullDate(f.due), cls: urgency || 'plain' }
}
const issueOf = (row) =>
  (row.issues || []).length
    ? (props.kid?.issues || []).find(i => i.id === row.issues[0] && i.status !== 'resolved') : null
const openRow = (row) => { const i = issueOf(row); if (i) emit('open-issue', i.id) }
</script>

<template>
  <div class="cband">
    <h3>今日与回访</h3>
    <div v-if="running.length" class="cbsub"><span>在跑 {{ running.length }} 个计划</span></div>
  </div>
  <div class="cbody">
    <template v-if="careRows.length || dueRows.length">
      <div v-for="r in careRows" :key="r.issue.id" class="act care lnk"
           :title="`点击查看${cnpunct(r.issue.name)}病历`"
           @click="emit('open-issue', r.issue.id)">
        <span class="alab">就医待办</span>
        <span class="atxt">{{ cnpunct(r.text) }}</span>
        <span class="adr">{{ r.issue.id }}</span>
      </div>
      <div v-for="f in dueRows" :key="f.due + f.topic" class="act next"
           :class="{ lnk: issueOf(f) }" :title="issueOf(f) ? '点击查看病历' : ''"
           @click="openRow(f)">
        <span class="alab">{{ f.diff < 0 ? `过期 ${-f.diff} 天` : f.diff === 0 ? '今天到期' : f.diff === 1 ? '明天' : `${f.diff} 天后` }}</span>
        <span class="atxt">{{ cnpunct(f.topic) }}</span>
        <span class="adr">{{ issueOf(f) ? issueOf(f).id + ' · ' : '' }}{{ fullDate(f.due) }}</span>
      </div>
    </template>
    <div v-else class="calm">今天没有到期事项 ✓</div>

    <template v-if="upcoming.length">
      <div class="glabel">接下来的回访</div>
      <div v-for="f in upcoming" :key="f.due + f.topic" class="frow"
           :class="{ lnk: issueOf(f) }" :title="issueOf(f) ? '点击查看病历' : ''"
           @click="openRow(f)">
        <span class="due-b" :class="dueBadge(f).cls">{{ dueBadge(f).text }}</span>
        <span class="dorig">{{ fullDate(f.due) }}</span>
        <div class="topic">
          <b>{{ cnpunct(splitTopic(f.topic).lead) }}</b>
          <div v-if="splitTopic(f.topic).rest" class="ev-body">
            <p v-for="(seg, j) in restParas(splitTopic(f.topic).rest)" :key="j" v-html="bodyHtml(seg)">
            </p>
          </div>
        </div>
      </div>
    </template>
    <div v-if="!careRows.length && !dueRows.length && !upcoming.length" class="src">
      回访会随计划自动排期——聊到想改的习惯时说「帮我记一下」，到期这里见。
    </div>
  </div>
</template>

<style scoped>
.act { display: flex; gap: 10px; align-items: baseline; padding: 8px 12px;
  border: 1px solid var(--line); border-radius: 6px; margin-bottom: 8px;
  font-size: 14px; line-height: 1.55; }
.act.lnk { cursor: pointer; }
.act.lnk:hover { border-color: var(--ink-blue); background: var(--accent-soft); }
.act.care { border-color: var(--todo); }
.act.next { border-color: var(--ink-blue); }
.act .alab { flex: none; font-size: 11.5px; border: 1px solid; border-radius: 4px;
  padding: 0 6px; font-weight: 600; letter-spacing: .04em; }
.act.care .alab { color: var(--todo); border-color: var(--todo); }
.act.next .alab { color: var(--ink-blue); border-color: var(--ink-blue); }
.act .atxt { min-width: 0; }
.act .adr { margin-left: auto; flex: none; font-size: 11.5px; color: var(--sub);
  font-family: Georgia, serif; font-variant-numeric: tabular-nums; }
.calm { font-size: 12.5px; color: var(--ok); padding: 6px 2px; }
.glabel { font-size: 11.5px; color: var(--sub); letter-spacing: .08em; margin: 10px 0 4px;
  padding-top: 8px; border-top: 1px dashed var(--grid-line); }
.frow { display: flex; gap: 10px; align-items: flex-start; padding: 6px 2px;
  border-bottom: 1px dashed var(--grid-line); font-size: 14px; }
.frow:last-child { border-bottom: none; }
.frow.lnk { cursor: pointer; }
.frow.lnk:hover { background: var(--accent-soft); }
.frow .dorig { flex: none; font-size: 11.5px; color: var(--sub);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-variant-numeric: tabular-nums; margin-top: 2px; }
.frow .topic { flex: 1; min-width: 0; }
.frow .topic b { font-weight: 600; }
.ev-body { font-size: 12.5px; color: var(--sub); margin-top: 2px; line-height: 1.55; }
.ev-body p { margin: 0 0 4px; padding-left: 13px; position: relative; }
.ev-body p:last-child { margin-bottom: 0; }
.ev-body p::before { content: '•'; position: absolute; left: 1px;
  color: var(--ink-blue); font-size: 11.5px; line-height: 1.9; }
.src { font-size: 11.5px; color: var(--sub); margin-top: 10px; }
</style>
