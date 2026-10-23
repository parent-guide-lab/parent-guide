<script setup>
import { computed, onMounted, provide, ref, watch } from 'vue'
import { state, init, currentChild, applyGeometry, applyJsonPage, persistPage } from './lib/store.js'
import GridBoard from './components/GridBoard.vue'
import ShareModal from './components/ShareModal.vue'
import ExportModal from './components/ExportModal.vue'
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

const exportOpen = ref(false)    // 导出弹窗(先预览再导,版本在弹窗中切换)
const shareState = ref(null)     // null | { level: 'card' | 'issue', block, issue }
const issueOpen = ref(null)      // 打开详情覆盖层的 issue id;#issue-P1 hash 可直链
const kbOpen = ref(false)        // 应用内知识库面板(官方库+我的自建)
const kbFile = ref('')           // 打开面板时定位到的文档(顶部知识条跳转用)
// 背景滚动锁(单一来源:任一弹窗开即锁;组件各管会互相覆盖)
watch([() => !!shareState.value, () => !!issueOpen.value, () => kbOpen.value, () => exportOpen.value],
  ([a, b, c, d]) => { document.body.style.overflow = (a || b || c || d) ? 'hidden' : '' },
  { immediate: true })
const print = () => { exportOpen.value = false; window.print() }

// -- 窄屏(≤720px):板面切文件模式渲染 -----------------------------------
// 单列流式与文件模式/手机版长图同一排版模型(blocks-spec「窄屏与移动端」);
// 布局编辑=桌面专属,窄屏进入时强制退出编辑态。
const mqNarrow = window.matchMedia('(max-width: 720px)')
const isNarrow = ref(mqNarrow.matches)
mqNarrow.addEventListener?.('change', e => {
  isNarrow.value = e.matches
  if (e.matches && state.editing) {
    state.editing = false
    document.body.classList.remove('editing')
  }
})
const boardServerMode = computed(() => state.serverMode && !isNarrow.value)

// -- 导出内容规则(2026-10-21 拍板「页面卡片内容都包含」) ------------------
// 长图预览/生成期间强制展开卡内默认折叠区(provide 注入卡组件与分享/导出
// 弹窗读取);结束回落,用户本地折叠状态不受影响。
const captureExpand = ref(false)
provide('captureExpand', captureExpand)
// 打印对齐导出口径(2026-10-23 拍板「5 对齐」):折叠区打印时强制展开——
// beforeprint 置位(事件返回后微任务先于打印渲染 flush,Vue 重渲染来得及),
// afterprint 还原用户原状态;与导出长图共用同一 provide。
let capPrev = false
window.addEventListener('beforeprint', () => {
  capPrev = captureExpand.value
  captureExpand.value = true
})
window.addEventListener('afterprint', () => { captureExpand.value = capPrev })

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
  exportOpen.value = false
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
      <button class="btn" :class="{ active: state.editing }" :disabled="!state.serverMode || isNarrow"
              :title="isNarrow ? '窄屏为只读浏览,布局编辑请在桌面进行'
                : state.editing ? '收起面板并退出拖拽' : '拖拽调布局;底部面板管卡片显隐与添加'"
              @click="toggleEdit">{{ state.editing ? '完成编辑' : '编辑布局' }}</button>
      <button class="btn primary" title="长图(手机版/桌面版)·PDF·单文件网页" @click="exportOpen = true">导出</button>
    </div>

    <TickerBar @open-doc="f => { kbFile = f; kbOpen = true }" />

    <GridBoard :key="state.version + (boardServerMode ? '-srv' : '-file')" :page="state.page" :kid="currentChild()"
               :editing="state.editing" :server-mode="boardServerMode"
               @geometry="applyGeometry" @share-card="b => shareState = { level: 'card', block: b }"
               @props-update="onPropsUpdate" @open-issue="id => issueOpen = id" />

    <CardManager v-if="state.editing" :page="state.page"
                 @toggle="onToggle" @show="onShow" @remove="onRemove" />

    <ShareModal :open="!!shareState" :level="shareState?.level || 'card'"
                :block="shareState?.block" :kid="currentChild()"
                :issue="shareState?.issue"
                @close="shareState = null" />

    <ExportModal :open="exportOpen" :page="state.page" :kid="currentChild()"
                 @close="exportOpen = false" @print="print" @report="exportReport" />

    <IssueDetail :open="!!issueOpen" :kid="currentChild()" :issue-id="issueOpen"
                 @close="issueOpen = null"
                 @share-issue="i => shareState = { level: 'issue', block: null, issue: i }" />

    <KnowledgePage v-if="kbOpen" :file="kbFile" @close="kbOpen = false; kbFile = ''" />
  </template>
</template>
