<script setup>
// 与 TimelineCard 同源同序:notes 落档按时间正序,取末尾 N 条倒序=最新在最上。
// 条目排版=IssueDetail 时间轴同款(那次打磨的成果):标题行渐进披露+
// 正文分号切段圆点+段首 ≤8 字标签加粗+标点全角归一——读侧机械转换,原文不动。
import { computed, ref } from 'vue'
import { bodyParas, fullDate, segLabel, zhPunct, linkKnowledge, escHtml } from '../../lib/util.js'
const props = defineProps({ block: Object, kid: Object })
// 正文经 linkKnowledge 转链(知识引用自动可跳);v-html 内容吃不到 scoped
// 样式,seg-lab/.klink 走全局 style.css。
const bodyHtml = (seg) => {
  const lab = segLabel(seg)
  return (lab ? `<b class="seg-lab">${escHtml(lab)}</b>` : '')
    + linkKnowledge(lab ? seg.slice(lab.length) : seg)
}
const list = computed(() =>
  (props.kid?.notes || []).slice(-(props.block?.props?.limit || 5)).reverse())
// autoH 卡(高度自适应)下渐进披露让位:无标题速记正文直接全文,不 clamp 不截段
const noClamp = computed(() => !!props.block?.autoH)
const dispDate = (n) => (n.precision && n.precision !== 'day' ? '≈' : '') + fullDate(n.date)
const dispLabel = (n) => dispDate(n) + (n.time ? ' ' + n.time : '')
// 时间轴渐进披露(NN Group/EHR collapsed-note 模式):标题行扫读+原文展开
const openEv = ref(new Set())
const isOpen = (i) => openEv.value.has(i)
function toggle(i) {
  const s = new Set(openEv.value)
  s.has(i) ? s.delete(i) : s.add(i)
  openEv.value = s
}
</script>

<template>
  <div class="cband"><h3>成长速记</h3></div>
  <div class="cbody">
    <template v-if="list.length">
      <div class="tl">
        <div v-for="(n, i) in list" :key="i" class="tl-item">
          <span class="d dline">{{ dispLabel(n) }}</span>
          <div class="ev">
            <div v-if="n.title" class="ev-title" @click="toggle(i)">{{ zhPunct(n.title) }}</div>
            <div v-if="(n.tags || []).length" class="ev-chips">
              <span v-for="t in n.tags" :key="t" class="chip">{{ t }}</span>
            </div>
            <div v-if="!n.title || isOpen(i)" class="ev-body"
                 :class="{ clamp: !n.title && !isOpen(i) && !noClamp }">
              <p v-for="(seg, j) in bodyParas(n.text).slice(0, !n.title && !isOpen(i) && !noClamp ? 1 : 99)"
                 :key="j" v-html="bodyHtml(seg)">
              </p>
            </div>
            <button v-if="n.title || (!noClamp && (n.text || '').length > 42)" class="ev-toggle"
                    @click="toggle(i)">{{ isOpen(i) ? '收起' : '详情' }}</button>
          </div>
        </div>
      </div>
    </template>
    <div v-else class="src">还没有记录过事件——值得记的瞬间(第一次/可爱时刻/生病)回到对话随手说,会积累在这里。</div>
  </div>
</template>

<style scoped>
.tl-item .d.dline { display: block; margin-right: 0; margin-bottom: 1px;
  font-size: 12.5px; }
.ev { min-width: 0; }
.ev-title { font-size: 14px; font-weight: 600; cursor: pointer; line-height: 1.5; }
.ev-chips { margin: 1px 0 2px; }
.chip { display: inline-block; background: rgba(255,255,255,.75); color: var(--ink-blue);
  border: 1px dashed var(--grid-line); border-radius: 6px; padding: 0 8px;
  font-size: 11.5px; margin-right: 4px; }
.ev-body { font-size: 12.5px; color: var(--sub); margin-top: 2px; line-height: 1.55; }
.ev-body.clamp { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; }
.ev-toggle { border: 0; background: none; color: var(--ink-blue); font-size: 11.5px;
  cursor: pointer; padding: 2px 0; margin-top: 1px; }
.ev-body p { margin: 0 0 4px; padding-left: 13px; position: relative; }
.ev-body p:last-child { margin-bottom: 0; }
.ev-body p::before { content: '•'; position: absolute; left: 1px;
  color: var(--ink-blue); font-size: 11.5px; line-height: 1.9; }
</style>
