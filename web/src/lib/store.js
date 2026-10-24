// App state: dual-mode load waterfall + persistence.
//   server mode: GET/POST /api/page + /api/data (local server.py)
//   file mode:   localStorage memory + embedded defaults from index.html
import { reactive } from 'vue'
import { cnpunct } from './util.js'

export const state = reactive({
  page: null, data: null,
  serverMode: false, editing: false, ready: false,
  version: 0, // bump to force GridBoard full rebuild (JSON apply / reset)
})

async function tryFetch(url) {
  try {
    const r = await fetch(url)
    if (!r.ok) throw new Error(r.status)
    return await r.json()
  } catch { return null }
}

function readEmbedded(id) {
  const el = document.getElementById(id)
  try { return JSON.parse(el ? el.textContent : 'null') } catch { return null }
}

function stripBootstrapped(obj) {
  if (obj && typeof obj === 'object') delete obj.bootstrapped
  return obj
}

// 2026-10-10 产品级退役卡型:老 page.json 里残留的 block 加载时静默剔除
// (不渲染错误占位卡);服务模式在 init 尾部写回一次,完成存量清理。
// 2026-10-13 增:followup(与「今日与回访」卡重合)、reminder(并入「前瞻」卡
// 「记下的」区;add-reminder 写入链与对话侧不变)。
const RETIRED_TYPES = ['strategy-effect', 'timeline', 'sleep-week', 'followup', 'reminder']
let retiredStripped = false
function stripRetired(page) {
  if (!page || !Array.isArray(page.blocks)
      || !page.blocks.some(b => RETIRED_TYPES.includes(b?.type))) return page
  retiredStripped = true
  return { ...page, blocks: page.blocks.filter(b => !RETIRED_TYPES.includes(b?.type)) }
}

export async function init() {
  const apiPage = await tryFetch('/api/page')   // file:// fails here -> file mode
  if (apiPage && Array.isArray(apiPage.blocks)) {
    const apiData = await tryFetch('/api/data')
    if (apiData) {
      state.serverMode = true
      state.page = stripRetired(stripBootstrapped(apiPage))
      state.data = stripBootstrapped(apiData)
    }
  }
  if (!state.serverMode) {
    let stored = null
    try { stored = JSON.parse(localStorage.getItem('pg-page') || 'null') } catch {}
    state.page = stripRetired((stored && Array.isArray(stored.blocks) && stored) ||
                 readEmbedded('pg-embedded-page'))
    state.data = readEmbedded('pg-embedded-data')
  }
  if (state.serverMode && retiredStripped) persistPage()   // 存量清理写回
  document.title = cnpunct(state.page?.title) || '成长视图'
  state.ready = true
}

export function currentChild() {
  const d = state.data || {}
  const key = state.page?.child && d[state.page.child] ? state.page.child
    : Object.keys(d).find(k => !k.startsWith('_'))
  return (key && d[key]) || {}
}

export function persistPage() {
  if (state.serverMode) {
    fetch('/api/page', { method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(state.page) }).catch(() => {})
    return
  }
  try { localStorage.setItem('pg-page', JSON.stringify(state.page)) } catch {}
}

// GridStack geometry -> page.blocks (called debounced from GridBoard)
export function applyGeometry(blocks) {
  if (!state.page) return
  state.page.blocks = blocks
  persistPage()
}

export function applyJsonPage(next) {
  state.page = stripRetired(next)
  persistPage()
  state.version++   // full board rebuild
}
