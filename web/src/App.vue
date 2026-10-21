<script setup>
import { onMounted, ref, watch } from 'vue'
import { domToPng } from 'modern-screenshot'
import { state, init, currentChild, applyGeometry, applyJsonPage, persistPage } from './lib/store.js'
import GridBoard from './components/GridBoard.vue'
import ShareModal from './components/ShareModal.vue'
import CardManager from './components/CardManager.vue'
import IssueDetail from './components/IssueDetail.vue'
import KnowledgePage from './components/KnowledgePage.vue'
import TickerBar from './components/TickerBar.vue'
import { CARD_META } from './components/cards/index.js'

onMounted(async () => {
  await init()
  const h = window.location.hash
  if (/^#issue-P\d+$/.test(h)) issueOpen.value = h.slice(7)
  if (/^#share-P\d+$/.test(h)) {           // 调试后门:详情+分享弹窗直链
    issueOpen.value = h.slice(8)
    const iss = (currentChild()?.issues || []).find(i => i.id === h.slice(8))
    if (iss) shareState.value = { level: 'issue', block: null, issue: iss }
  }
})

const exportOpen = ref(false)    // 导出下拉菜单
const exporting = ref(false)     // 板面长图生成中
const shareState = ref(null)     // null | { level: 'card' | 'issue', block, issue }
const issueOpen = ref(null)      // 打开详情覆盖层的 issue id;#issue-P1 hash 可直链
const kbOpen = ref(false)        // 应用内知识库面板(官方库+我的自建)
const kbFile = ref('')           // 打开面板时定位到的文档(顶部知识条跳转用)
// 背景滚动锁(单一来源:任一弹窗开即锁;组件各管会互相覆盖)
watch([() => !!shareState.value, () => !!issueOpen.value, () => kbOpen.value], ([a, b, c]) => {
  document.body.style.overflow = (a || b || c) ? 'hidden' : ''
}, { immediate: true })
const print = () => { exportOpen.value = false; window.print() }

// 页面级长图 = 所见即所得(用户拍板 2026-10-10:家人版卡片排版显示不好,
// 页面怎么显示就怎么导出):直接截板面,不走 ShareModal 重排;卡级/问题级
// 家人卡(一条口径给长辈)仍是重排版,入口在卡片 ⤴ 与问题详情层。
async function shareBoard() {
  const board = document.querySelector('#grid') || document.querySelector('main.grid')
  if (!board || exporting.value) return
  exporting.value = true
  document.body.classList.add('capturing')   // 长图不带走卡上的分享交互钮
  try {
    const url = await domToPng(board, { scale: 2, backgroundColor: '#fdfdfb' })
    const blob = await (await fetch(url)).blob()
    const d = new Date()
    const ts = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
    const name = `成长视图-${currentChild().name || '页面'}-${ts}.png`
    const file = new File([blob], name, { type: 'image/png' })
    if (navigator.canShare && navigator.canShare({ files: [file] })) {
      try { await navigator.share({ files: [file], title: name }); return }
      catch (e) { if (e?.name === 'AbortError') return }
    }
    const a = document.createElement('a')
    a.href = URL.createObjectURL(blob)
    a.download = name
    a.click()
    URL.revokeObjectURL(a.href)
  } finally {
    document.body.classList.remove('capturing')
    exporting.value = false; exportOpen.value = false
  }
}
function pickExport(fn) {
  exportOpen.value = false
  if (fn === 'image') shareBoard()
  else if (fn === 'report') exportReport()
}

function toggleEdit() {
  if (!state.serverMode) {
    alert('布局编辑需要本地服务:在仓库根目录运行 python3 server.py --open')
    return
  }
  state.editing = !state.editing
  document.body.classList.toggle('editing', state.editing)
}

// -- card visibility management ------------------------------------------------
function nextId(page) {
  const nums = (page?.blocks || [])
    .map(b => String(b.id || '').match(/^b(\d+)$/)).filter(Boolean).map(m => +m[1])
  return 'b' + ((nums.length ? Math.max(...nums) : 0) + 1)
}

// switch an existing block on/off; off keeps the block (hidden:true) so the
// geometry and any custom content survive a re-enable
function onToggle({ id, on }) {
  const block = state.page?.blocks?.find(x => x.id === id)
  if (!block) return
  block.hidden = !on
  if (on) delete block.hidden
  applyJsonPage(state.page)   // rebuild: GridBoard snapshot filters hidden
}

// turn on a builtin type that has no block yet -> add one with default geometry
function onShow(type) {
  const meta = CARD_META[type]
  if (!meta) return
  const cols = state.page?.layout?.cols || 12
  const blocks = state.page?.blocks || []
  const maxY = Math.max(0, ...blocks.map(b => (b.y || 0) + (b.h || 4)))
  const block = { id: nextId(state.page), type, x: 0, y: maxY,
                  w: Math.min(meta.w || 6, cols), h: meta.h || 4 }
  applyJsonPage({ ...state.page, blocks: [...blocks, block] })
}

// remove a block from the page entirely (builtin only in UI; data lives in
// child.json so nothing is lost -- re-addable from the panel's add section)
function onRemove({ id }) {
  const blocks = state.page?.blocks || []
  applyJsonPage({ ...state.page, blocks: blocks.filter(b => b.id !== id) })
}

// from GridBoard (list checkbox): snapshot already patched in place, so only
// mirror into page.json + persist -- no rebuild (keeps the flicker out)
function onPropsUpdate({ id, props }) {
  const block = state.page?.blocks?.find(x => x.id === id)
  if (block) { block.props = props; persistPage() }
}

// Export a standalone single-file report: clone the document, swap the two
// embedded-JSON tags with current page/data, drop the live app DOM (the inline
// bundle re-mounts on open and falls back to the embedded values in file mode).
function exportReport() {
  const safe = o => JSON.stringify(o, null, 2).replace(/<\//g, '<\\/')
  const doc = document.documentElement.cloneNode(true)
  const pg = doc.querySelector('#pg-embedded-page')
  const dt = doc.querySelector('#pg-embedded-data')
  if (pg) pg.textContent = safe(state.page)
  if (dt) dt.textContent = safe(state.data)
  const app = doc.querySelector('#app')
  if (app) app.innerHTML = ''
  const body = doc.querySelector('body')
  if (body) { body.classList.remove('editing'); body.classList.add('report') }
  const blob = new Blob(['<!DOCTYPE html>\n' + doc.outerHTML], { type: 'text/html' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = `成长视图-${currentChild().name || 'report'}.html`
  a.click()
  URL.revokeObjectURL(a.href)
}
</script>

<template>
  <template v-if="state.ready">
    <div class="toolbar">
      <span class="brand">🧸 成长视图<small>parent-guide</small></span>
      <span class="mode-badge" :class="{ on: state.serverMode }" :title="state.serverMode
        ? '已连接本地后端(server.py):拖拽/拉伸/编辑直接写回 data/page.json'
        : '未检测到本地服务;想体验布局编辑,运行 python3 server.py --open'">
        {{ state.serverMode ? '🔌 本地服务 · 编辑即保存' : '📄 文件模式 · 只读' }}
      </span>
      <button v-if="state.serverMode" class="btn" title="官方循证知识 + 我的自建(knowledge/user/,仅本机)" @click="kbOpen = true">📖 知识库</button>
      <button class="btn" :class="{ active: state.editing }" :disabled="!state.serverMode"
              :title="state.editing ? '收起面板并退出拖拽' : '拖拽调布局;底部面板管卡片显隐与添加'"
              @click="toggleEdit">{{ state.editing ? '完成编辑' : '编辑布局' }}</button>
      <div class="export-wrap">
        <button class="btn primary" @click="exportOpen = !exportOpen">导出</button>
        <div v-if="exportOpen" class="export-menu">
          <button :disabled="exporting" @click="pickExport('image')">{{ exporting ? '生成中…' : '长图(微信分享)' }}</button>
          <button @click="print()">PDF(打印/存档)</button>
          <button @click="pickExport('report')">单文件网页(转发/存档)</button>
        </div>
      </div>
    </div>

    <div v-if="exportOpen" class="menu-mask" @click="exportOpen = false"></div>

    <TickerBar @open-doc="f => { kbFile = f; kbOpen = true }" />

    <GridBoard :key="state.version" :page="state.page" :kid="currentChild()"
               :editing="state.editing" :server-mode="state.serverMode"
               @geometry="applyGeometry" @share-card="b => shareState = { level: 'card', block: b }"
               @props-update="onPropsUpdate" @open-issue="id => issueOpen = id" />

    <CardManager v-if="state.editing" :page="state.page"
                 @toggle="onToggle" @show="onShow" @remove="onRemove" />

    <ShareModal :open="!!shareState" :level="shareState?.level || 'card'"
                :block="shareState?.block" :kid="currentChild()"
                :issue="shareState?.issue"
                @close="shareState = null" />

    <IssueDetail :open="!!issueOpen" :kid="currentChild()" :issue-id="issueOpen"
                 @close="issueOpen = null"
                 @share-issue="i => shareState = { level: 'issue', block: null, issue: i }" />

    <KnowledgePage v-if="kbOpen" :file="kbFile" @close="kbOpen = false; kbFile = ''" />
  </template>
</template>
