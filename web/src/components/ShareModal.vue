<script setup>
// 卡片/问题分享长图:预览即所发,导出即保存图片。
// 卡级(卡片 ⤴)=页面原卡 DOM 克隆双宽(2026-10-22 用户拍板「手机版也显示
// 页面原卡内容」,家人卡重排退役):手机版 375px(微信手机宽)/桌面版原卡
// 页面宽,内容与页面完全一致(capExpand 展开折叠区+截至角标)。
// 问题级(详情层)=375px 家人卡重排保留(问题没有「页面卡」,口径卡是
// 为家人设计的最终形态;调研 docs/sharing-research-2026-10-01.md §3):
// 大字号/去内部黑话/条目勾选/familyNotes 永不出现在此。
import { ref, computed, watch, inject, nextTick } from 'vue'
import { monthsAge, cnpunct, issueDayNo, stampEl, exportPng } from '../lib/util.js'

const props = defineProps({
  open: Boolean,
  level: { type: String, default: 'card' },   // 'card' | 'issue'
  block: { type: Object, default: null },     // card 级的目标卡
  kid: { type: Object, default: () => ({}) },
  issue: { type: Object, default: null },     // issue 级的问题对象(从详情层来)
})
const emit = defineEmits(['close'])

const anonymized = ref(false)   // 以下三项仅问题级家人卡使用
const branded = ref(true)
const selected = ref([])        // issue 级:why/how/sources 条目勾选
const nodeEl = ref(null)        // issue 级家人卡导出节点
const ver = ref('mobile')       // card 级:'mobile'=375px | 'desktop'=原卡宽
const cardEl = ref(null)        // card 级克隆预览容器(导出节点=预览节点)
const exporting = ref(false)
// 页级长图同款内容规则注入(「内容都包含」拍板):卡级预览期间强制展开该卡
// 默认折叠区;问题级家人卡不走此通道
const capExpand = inject('captureExpand', { value: false })

// custom cards carry their own title in props
const TITLES = { 'profile': '孩子档案', 'milestone': '里程碑',
  'anticipatory': '前瞻',
  'note': '成长速记',
  'focus': '今日与回访',
  'issue': '问题追踪', 'growth': '生长记录',
  'text': '便签', 'list': '清单' }
function titleFor(b) {
  if (!b) return ''
  if (b.type === 'text' || b.type === 'list') return b.props?.title || TITLES[b.type]
  return TITLES[b.type] || b.type
}

const todayStr = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// 问题级(issue):从口径卡渲染,why/how 条目可勾选剔除(templates.md 问题分享卡节)
const ISSUE_ST = { active: '进行中', watching: '观察中', resolved: '已解决' }
const issuePack = computed(() => {
  const i = props.issue
  if (!i) return null
  const b = i.brief || {}
  const rows = []
  if (b.what) rows.push({ kind: 'issue-what', text: b.what, label: '情况', fixed: true, group: '现在的情况' })
  const why = (b.why || []).map(w => ({ kind: 'issue-why', text: w, label: `为什么·${w.slice(0, 8)}` }))
  if (why.length) { why[0].group = '为什么这么做'; rows.push(...why) }
  const how = (b.how || []).map(h => ({ kind: 'issue-how', text: h, label: `怎么做·${h.slice(0, 8)}` }))
  if (how.length) { how[0].group = '全家怎么做'; rows.push(...how) }
  if (b.redline) rows.push({ kind: 'issue-red', text: b.redline, label: '就医线', fixed: true })
  const srcs = (b.sources || []).map(x => ({ kind: 'issue-src', text: x, label: `依据·${x.slice(0, 8)}` }))
  if (srcs.length) { srcs[0].group = '依据'; rows.push(...srcs) }
  return { rows, st: ISSUE_ST[i.status] || i.status, dayNoTxt: issueDayNo(i), name: i.name }
})

const sections = computed(() => {
  if (!props.open || props.level !== 'issue') return []
  const pack = issuePack.value
  if (!pack) return []
  const rows = pack.rows.filter((_, i) => selected.value[i] !== false)
  return [{ id: 'issue', type: 'issue', title: pack.name, rows, extra: { st: pack.st } }]
})

const chips = computed(() => {   // 问题级的条目勾选标签
  if (!props.open || props.level !== 'issue') return []
  const pack = issuePack.value
  if (!pack) return []
  return pack.rows
    .map((r, i) => ({ r, i }))
    .filter(({ r }) => !r.fixed)
    .map(({ r, i }) => ({ i, on: selected.value[i] !== false, label: r.label }))
})

const age = computed(() => {
  const m = monthsAge(props.kid?.birthdate)
  return m > 0 ? `${m} 个月` : ''
})
const dispName = computed(() => anonymized.value ? '宝宝' : (props.kid?.name || '宝宝'))
const headTitle = computed(() => {
  // 标题冒号直接写全角(cnpunct 规则同款:CJK 邻接半角转全角;8b)
  if (props.level === 'issue') return `${dispName.value}的${issuePack.value?.name || ''}：全家这样做`
  return titleFor(props.block) || '成长卡片'
})
const headSub = computed(() => {
  if (props.level === 'issue') {
    return [age.value, issuePack.value?.st, issuePack.value?.dayNoTxt, `截至 ${todayStr()}`]
      .filter(Boolean).join(' · ')
  }
  return [dispName.value, age.value, `截至 ${todayStr()}`].filter(Boolean).join(' · ')
})

watch(() => [props.open, props.level, props.block?.id], () => {
  selected.value = []
  ver.value = 'mobile'          // 每次打开默认手机版(微信是分享主场景)
})

// 卡级预览=页面原卡的 DOM 克隆(预览即所发:导出的就是预览里这个节点)。
// capExpand 先展开折叠区再克隆;剔掉交互钮(分享/高度切换/展开收起);
// 手机版钉 347px(=375 视口下真机卡宽,375-页面两侧 14px 边距)并挂
// cap-mobile 套用窄屏内边距——媒体查询看视口不看克隆,不挂则导出图带
// 桌面内边距(2026-10-22 对照实验修);「截至」角标随克隆进预览。
const MOBILE_CARD_W = 347
async function buildCardPreview() {
  const src = props.block
    ? document.querySelector(`.card[data-bid="${CSS.escape(props.block.id)}"]`)
    : null
  if (!src || !cardEl.value) return
  capExpand.value = true
  await nextTick()
  const clone = src.cloneNode(true)
  clone.querySelectorAll('.share-fab, .hmode-fab, .tgl').forEach(el => el.remove())
  clone.classList.toggle('cap-mobile', ver.value === 'mobile')
  clone.style.width = (ver.value === 'mobile' ? MOBILE_CARD_W
    : Math.round(src.getBoundingClientRect().width)) + 'px'
  cardEl.value.replaceChildren(clone, stampEl(`${dispName.value} · 截至 ${todayStr()}`))
}
watch([() => props.open, () => props.block?.id, ver], () => {
  if (props.open && props.level === 'card') nextTick(buildCardPreview)
  else capExpand.value = false
})

function toggleRow(i) { selected.value[i] = selected.value[i] === false ? true : false }

const fileTitle = () => {
  if (props.level === 'issue') return `${issuePack.value?.name || '问题'}-全家这样做`
  return titleFor(props.block) || '卡片'
}
// 单导出钮:导的是当前预览(导出=保存图片,不弹系统分享)
async function doExport() {
  const target = props.level === 'card' ? cardEl.value : nodeEl.value
  if (!target || exporting.value) return
  exporting.value = true
  try {
    const tag = props.level === 'card' ? `${ver.value === 'desktop' ? '桌面版' : '手机版'}-` : ''
    await exportPng(target, `成长分享-${dispName.value}-${fileTitle()}-${tag}${todayStr()}.png`,
      props.level === 'card' ? '#fdfdfb' : '#ffffff')
  } finally { exporting.value = false }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="share-mask" @click.self="emit('close')">
      <div class="share-dialog">
        <div class="share-head">
          <b>分享给家人</b><span class="hint">预览即所发 · 导出即保存图片</span>
          <button class="x" @click="emit('close')">✕</button>
        </div>

        <div class="share-body">
          <aside class="share-side">
            <div v-if="level === 'card'" class="opt-chips">
              <button class="opt-chip" :class="{ on: ver === 'mobile' }" @click="ver = 'mobile'"
                      title="页面原卡缩到微信手机宽——内容与页面完全一致">手机版·微信宽</button>
              <button class="opt-chip" :class="{ on: ver === 'desktop' }" @click="ver = 'desktop'"
                      title="页面原卡按原宽导出——存档/打印底稿用">桌面版·原卡宽</button>
            </div>
            <p v-if="level === 'card'" class="foot-hint">两版内容相同,均与页面这张卡一致(折叠区全展开+截至日期),只差宽度。</p>

            <template v-if="level === 'issue'">
              <div class="opt-chips">
                <label class="opt-chip" :class="{ on: anonymized }">
                  <input type="checkbox" v-model="anonymized">隐去小名</label>
                <label class="opt-chip" :class="{ on: branded }">
                  <input type="checkbox" v-model="branded">署名页脚</label>
              </div>
              <div v-if="chips.length" class="share-chips">
                <span class="chip" :class="{ off: !c.on }" v-for="c in chips" :key="c.i"
                      @click="toggleRow(c.i)">{{ c.on ? '✓ ' : '' }}{{ c.label }}</span>
              </div>
            </template>

            <div class="side-foot">
              <button class="btn primary" :disabled="exporting" @click="doExport">{{ exporting ? '生成中…' : '导出长图(保存图片)' }}</button>
            </div>
          </aside>

          <div class="share-scroll">
          <!-- 卡级:页面原卡克隆(手机版 375px / 桌面版原宽) -->
          <div v-if="level === 'card'" class="cap-preview" ref="cardEl"></div>
          <!-- 问题级:375px 家人卡重排(口径卡是家人版最终形态) -->
          <div v-else class="share-card" ref="nodeEl">
            <div class="sc-head">
              <div class="sc-title">{{ headTitle }}</div>
              <div class="sc-sub">{{ headSub }}</div>
            </div>

            <div v-for="sec in sections" :key="sec.id" class="sc-sec">
              <template v-for="(row, i) in sec.rows" :key="i">
                <div v-if="row.group" class="sc-sec-title">{{ row.group }}</div>
                <div v-else-if="row.kind === 'issue-what'" class="sc-row issue-what">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-why'" class="sc-row issue-why">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-how'" class="sc-row issue-how">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
                <div v-else-if="row.kind === 'issue-red'" class="sc-red">
                  <b>出现这些当天就医：</b>{{ cnpunct(row.text) }}
                </div>
                <div v-else-if="row.kind === 'issue-src'" class="sc-row issue-src">
                  <span class="main">{{ cnpunct(row.text) }}</span>
                </div>
              </template>

              <div v-if="!sec.rows.length" class="sc-empty">暂无内容</div>
            </div>

            <div class="sc-foot">{{ branded ? '由 parent-guide 生成' : '\u00a0' }}</div>
          </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
/* 弹窗基座(share-mask/dialog/head/body/side/opt-chips/chips/side-foot/
   foot-hint/share-scroll)已上收 style.css 全局——ExportModal 共用同一基座;
   这里只留问题级家人卡专属渲染 */
/* A·生长图纸(与页面同系统):坐标纸底+墨蓝+serif 数字+描边小章 */
/* 问题级家人卡:自包含、375px 手机宽、大字号(家人版);坐标纸底 */
.share-card { width: 375px; background-color: #fff;
  background-image:
    linear-gradient(rgba(90,130,180,.06) 1px, transparent 1px),
    linear-gradient(90deg, rgba(90,130,180,.06) 1px, transparent 1px);
  background-size: 14px 14px;
  border: 1px solid var(--grid-line); border-radius: 10px;
  padding: 20px 22px 14px; color: var(--ink); font-size: 15px; line-height: 1.65;
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif; }
.sc-head { border-bottom: 1px solid var(--grid-line); padding-bottom: 10px; margin-bottom: 10px; }
.sc-title { font-size: 20px; font-weight: 700; color: var(--ink-blue); }
.sc-sub { font-size: 12.5px; color: var(--sub); margin-top: 2px; font-variant-numeric: tabular-nums; }
.sc-sec { padding: 4px 0; }
.sc-sec-title { font-size: 12.5px; font-weight: 600; color: var(--sub);
  letter-spacing: .2em; margin: 10px 0 2px; }
.sc-row { padding: 9px 0; border-bottom: 1px dashed var(--grid-line); }
.sc-row:last-child { border-bottom: none; }
.sc-row .main { display: block; }
.sc-red { background: var(--todo-bg); border: 1px solid var(--todo); border-radius: 8px;
  padding: 10px 12px; margin: 10px 0; font-size: 14px; }
.sc-red b { color: var(--todo); }
.sc-empty { color: var(--sub); font-size: 14px; padding: 8px 0; }
.issue-src .main { font-size: 12.5px; color: var(--sub); }
.sc-foot { text-align: center; color: var(--sub); font-size: 11.5px; margin-top: 14px; }

/* 卡级预览容器:页面原卡克隆钉宽放入,截至角标随克隆常驻(预览即所发) */
.cap-preview { position: relative; }
</style>
