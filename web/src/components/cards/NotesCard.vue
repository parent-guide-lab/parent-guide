<script setup>
// 与 TimelineCard 同源同序:notes 落档按时间正序,取末尾 N 条倒序=最新在最上。
// 条目排版=IssueDetail 时间轴同款(那次打磨的成果):标题行渐进披露+
// 正文分号切段圆点+段首 ≤8 字标签加粗+标点全角归一——读侧机械转换,原文不动。
import { computed, ref } from 'vue'
import { bodyParas, fullDate, segLabel, zhPunct, linkKnowledge, escHtml, cnpunct } from '../../lib/util.js'
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
// 中改拍板(2026-10-22,demo/ui-card-mid):最新一条升为「头条」签名件——
// 大日期(27 Georgia,与档案卡月龄 hero 同族)+实线分界,历史条目原样走时间线;
// 单条时不做头条(没有历史区,签名件无对照)。卡头「本月 N 条」=MM 机械匹配。
const mm = String(new Date().getMonth() + 1).padStart(2, '0')
const monthCount = computed(() =>
  (props.kid?.notes || []).filter(n => String(n.date || '').slice(0, 2) === mm).length)
const lead = computed(() => list.value.length > 1 ? list.value[0] : null)
const rest = computed(() => lead.value ? list.value.slice(1) : list.value)
// 相对日仅在机械可定时显示(今天/昨天,MM-DD 同年内比对);跨年旧条目留空不猜
const relDay = (n) => {
  const d = n?.date || ''
  const now = new Date()
  const yd = new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)
  const md = (dt) => String(dt.getMonth() + 1).padStart(2, '0') + '-' + String(dt.getDate()).padStart(2, '0')
  if (d === md(now)) return '今天'
  if (d === md(yd)) return '昨天'
  return ''
}
// 头条日期「MM·DD」
const leadMD = (n) => String(n?.date || '').replace('-', '·')
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
  <div class="cband"><h3>成长速记</h3><div v-if="list.length" class="cbsub lead-n"><span>本月 <b>{{ monthCount }}</b> 条</span></div></div>
  <div class="cbody">
    <template v-if="list.length">
      <div v-if="lead" class="lead">
        <div class="lead-date">
          <span class="ld-d">{{ leadMD(lead) }}</span><span v-if="relDay(lead)" class="ld-u">{{ relDay(lead) }}</span>
          <span v-if="lead.time" class="ld-t">{{ lead.time }}</span>
        </div>
        <div v-if="(lead.tags || []).length" class="ev-chips lead-chips">
          <span v-for="t in lead.tags" :key="t" class="chip">{{ cnpunct(t) }}</span>
        </div>
        <div v-if="lead.title" class="lead-title">{{ zhPunct(lead.title) }}</div>
        <div class="lead-body"><p v-for="(seg, j) in bodyParas(lead.text)" :key="j" v-html="bodyHtml(seg)"></p></div>
        <div class="lead-hint">更早的记录在下方时间线</div>
      </div>
      <div class="tl">
        <div v-for="(n, i) in rest" :key="i" class="tl-item">
          <span class="d dline">{{ dispLabel(n) }}</span>
          <div class="ev">
            <div v-if="n.title" class="ev-title" @click="toggle(i)">{{ zhPunct(n.title) }}</div>
            <div v-if="(n.tags || []).length" class="ev-chips">
              <span v-for="t in n.tags" :key="t" class="chip">{{ cnpunct(t) }}</span>
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
    <div v-else class="src">还没有记录过事件——值得记的瞬间（第一次/可爱时刻/生病）回到对话随手说，会积累在这里。</div>
  </div>
</template>

<style scoped>
/* 卡头右侧计数(中改拍板:「本月 N 条」给积累感) */
.cband { display: flex; align-items: baseline; }
/* 卡头单行化(2026-10-23 拍板):跟标题后同排,字号/颜色交全局 .cbsub 体系 */
.cband .lead-n b { font-weight: 600; }
/* 头条签名件(中改拍板):大日期 27 Georgia 与月龄 hero 同族,实线分界 */
.lead { padding-bottom: 12px; margin-bottom: 10px; border-bottom: 1px solid var(--line); }
.lead-date { display: flex; align-items: baseline; gap: 8px; }
.lead-date .ld-d { font-family: Georgia, "Times New Roman", serif; font-size: 27px;
  font-weight: 700; line-height: 1; color: var(--id, var(--ink-blue)); letter-spacing: -.01em; }
.lead-date .ld-u { font-size: 11.5px; color: var(--sub); }
.lead-date .ld-t { margin-left: auto; font-size: 11.5px; color: var(--sub);
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; }
.lead-chips { margin: 4px 0 0; }
.lead-title { font-size: 15px; font-weight: 700; line-height: 1.5; margin-top: 4px; }
.lead-body { font-size: 14px; line-height: 1.6; margin-top: 3px; }
.lead-body p { margin: 0 0 4px; }
.lead-body p:last-child { margin-bottom: 0; }
.lead-hint { font-size: 11.5px; color: var(--sub); margin-top: 6px; }
.lead-hint::before { content: ''; display: inline-block; width: 18px; height: 1px;
  background: var(--id, var(--ink-blue)); vertical-align: 4px; margin-right: 6px; }
/* 日期=Georgia 衬线(2026-10-22 A1 拍板混合语法:时间轴节点日期走图纸衬线
   数字语言,与前瞻卡月分组标题同族;多行日期列仍走 mono) */
.tl-item .d.dline { display: block; margin-right: 0; margin-bottom: 1px;
  font-size: 12.5px; font-family: Georgia, "Times New Roman", serif; }
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
