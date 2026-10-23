<script setup>
// Dual-mode board:
//   server mode -> GridStack editor: free drag placement, corner resize,
//                  auto-compact on release (float:false), debounced write-back.
//   file mode   -> CSS grid streaming read-only (x/y/h ignored, order + w).
//
// DOM ownership rule (the v11 lesson, Vue edition): GridStack owns the live
// grid DOM once mounted. Blocks are snapshotted into a shallow ref -- geometry
// write-backs mutate the snapshot fields WITHOUT triggering a re-render, so
// Vue never re-patches nodes GridStack has moved (that fight = "cards jump
// around"). Full rebuild happens only via :key bump (JSON apply / reset).
import { onMounted, onBeforeUnmount, ref, shallowRef, triggerRef, watch, nextTick } from 'vue'
import { GridStack } from 'gridstack'
import { cardFor } from './cards/index.js'
import { clampInt } from '../lib/util.js'

const props = defineProps({
  page: { type: Object, required: true },
  kid: { type: Object, default: () => ({}) },
  editing: Boolean,
  serverMode: Boolean,
})
const emit = defineEmits(['geometry', 'share-card', 'props-update', 'open-issue'])

// B 功能卡身份色(2026-10-23 拍板,两轮演进:demo ui-color → 补拍档案/今日 →
// C1 实色表头 ui-cardhead-tint):type→tone 类,style.css 里 tone 类注入
// --id(卡身签名件用)+实色卡头白字。全部内置卡有实色头(档案=墨蓝本尊色);
// 仅自定义卡(text/list)无映射=白底墨蓝,「无色头」是家长自建卡的信号。
// 纪律:状态徽章与三色大计数不跟身份走。
const TONE = { growth: 'tone-green', issue: 'tone-red', milestone: 'tone-gold',
  anticipatory: 'tone-violet', strategy: 'tone-violet', note: 'tone-teal',
  tracker: 'tone-tea', profile: 'tone-blue', focus: 'tone-violet' }
const cardClass = (b) => ({ 'auto-h': b.autoH, [TONE[b.type]]: !!TONE[b.type] })

// Custom-card content updates (e.g. list checkboxes): patch the snapshot
// element in place (keeps geometry write-back in sync with latest props),
// then bubble up so App persists page.json. No rebuild needed.
function onPropsUpdate(b, nextProps) {
  b.props = { ...(b.props || {}), ...nextProps }
  emit('props-update', { id: b.id, props: b.props })
}

const gridEl = ref(null)
const items = shallowRef([])          // snapshot; field mutations stay silent
let hiddenSnapshot = []               // hidden blocks: not rendered, but geometry
let gs = null                         // write-back must carry them or they get dropped
let saveTimer = null

// -- auto height (autoH) -----------------------------------------------------
// Auto cards size themselves to content: .card.auto-h is height:auto in CSS,
// so ANY internal change (text edit, async chart render, font load) changes
// the card's own height. A ResizeObserver turns that into gs.resizeToContent
// (official API -- measures the card box, converts via the grid's own
// cellHeight math, honors node.minH/maxH) -> 'change' -> the normal debounced
// write-back; autoH/minH ride along inside the block spread, persistence is
// free. At the 20-row ceiling (node.maxH) the card gets .capped -> CSS
// max-height pins it to the container and .cbody goes back to scrolling;
// when content shrinks below the container the card shrinks again, the
// observer fires, and the cap class falls off -- self-closing loop.
const cardEls = new Map()             // id -> .card element (function refs)
let ro = null
const resizeH0 = new Map()            // id -> h at resizestart (user corner-pull)

function setCardEl(id, el) { el ? cardEls.set(id, el) : cardEls.delete(id) }

function setAutoConstraints(b) {
  const el = cardEls.get(b.id)
  const node = el?.closest('.grid-stack-item')?.gridstackNode
  if (!node) return
  if (b.autoH) {
    node.minH = clampInt(b.minH, 1, 20, 3)
    node.maxH = 20
    // measure the .cfit wrapper (content height), NOT the card: the card box
    // stays pinned to the row grid (constant gaps), .cfit is height:auto so
    // it freely expresses what the content needs
    node.resizeToContentParent = '.card'
  } else {
    node.minH = undefined; node.maxH = undefined
    node.resizeToContentParent = undefined
  }
}

function syncAutoHeights() {
  if (!gs) return
  for (const b of items.value) {
    if (!b.autoH) continue
    const el = cardEls.get(b.id)
    const item = el?.closest('.grid-stack-item')
    const node = item?.gridstackNode
    if (!node) continue
    setAutoConstraints(b)
    gs.resizeToContent(item)
    el.classList.toggle('capped', node.h >= 20)   // ceiling: back to container + inner scroll
  }
}

// Manual corner-pull on an auto card = the user takes height control back:
// flip to fixed at the pulled size (width stays whatever they pulled too).
function onResizeStart(ev, el) {
  const n = el?.gridstackNode; if (n) resizeH0.set(n.id, n.h)
}
function onResizeStop(ev, el) {
  const n = el?.gridstackNode; if (!n) return
  const h0 = resizeH0.get(n.id); resizeH0.delete(n.id)
  if (h0 == null || h0 === n.h) return   // pure drag (position) never exits auto
  const b = items.value.find(x => x.id === n.id)
  if (b?.autoH) {
    b.autoH = false
    setAutoConstraints(b)
    const cel = cardEls.get(n.id)
    if (cel) { cel.classList.remove('capped'); const fit = cel.querySelector('.cfit'); if (ro && fit) ro.unobserve(fit) }
    // autoH/class binding needs a render; safe here -- unlike geometry fields,
    // autoH never touches gs-* attributes, so Vue cannot fight GridStack's DOM
    triggerRef(items)
    scheduleSync()
  }
}

// Edit-mode per-card toggle (layout property, editor-owned like drag/resize).
function toggleAutoH(b) {
  b.autoH = !b.autoH
  const el = cardEls.get(b.id)
  const fit = el?.querySelector('.cfit')
  if (b.autoH) {
    if (!b.minH) b.minH = 3
    if (fit && ro) ro.observe(fit)
    triggerRef(items)          // class+label render first: height:auto with the class
    nextTick(syncAutoHeights)  // then measure
  } else {
    if (fit && ro) ro.unobserve(fit)
    el?.classList.remove('capped')
    delete b.minH            // minH is auto-only; don't leave it stranded on fixed cards
    triggerRef(items)
    nextTick(() => setAutoConstraints(b))
  }
  scheduleSync()
}

function snapshot() {
  const L = props.page?.layout || {}
  const cols = L.cols || 12
  const all = props.page?.blocks || []
  items.value = all
    .filter(b => !b.hidden)   // hidden cards keep their block + geometry, just don't render
    .map(b => ({
      ...b,                   // autoH/minH ride along for the geometry write-back
      w: clampInt(b.w, 1, cols, 6), h: clampInt(b.h, 1, 20, 4),
      minH: b.autoH ? clampInt(b.minH, 1, 20, 3) : undefined,
    }))
  hiddenSnapshot = all.filter(b => b.hidden).map(b => ({ ...b }))
}

onMounted(async () => {
  snapshot()
  if (!props.serverMode) return
  await nextTick()
  const L = props.page?.layout || {}
  // GridStack.init auto-registers the Vue-rendered .grid-stack-item children
  // (they already carry gs-x/y/w/h/id attributes). Do NOT makeWidget them
  // again -- double registration duplicates ids (profile -> profile_1) and
  // the two layout entries fight each other (= "cards jump around").
  gs = GridStack.init({
    column: L.cols || 12,
    cellHeight: L.rowHeight || 72,
    margin: L.margin ?? 12,
    float: false,            // release -> vertical compact (grid-layout-plus parity)
    staticGrid: !props.editing,
  }, gridEl.value)
  gs.on('change', scheduleSync)
  gs.on('resizestart', onResizeStart)
  gs.on('resizestop', onResizeStop)
  // saved y values can leave holes; collapse them once on load
  gs.compact()
  ro = new ResizeObserver(syncAutoHeights)
  for (const b of items.value) {
    if (b.autoH) { const fit = cardEls.get(b.id)?.querySelector('.cfit'); if (fit) ro.observe(fit) }
  }
  syncAutoHeights()   // saved h may lag behind content (loaded/edited elsewhere)
})

onBeforeUnmount(() => {
  // 窄屏↔桌面切换会让 App 以新 key 重挂本组件:卸载前冲刷未落盘的几何
  // (拖拽后 300ms 内切窗口,防抖还没跑就拆了 GridStack,结果会丢)
  if (saveTimer) flushSync()
  if (ro) { ro.disconnect(); ro = null }
  if (gs) { gs.destroy(); gs = null }
})

watch(() => props.editing, v => { if (gs) gs.setStatic(!v) })

function scheduleSync() {
  clearTimeout(saveTimer)
  saveTimer = setTimeout(flushSync, 300)  // debounce: no high-frequency writes mid-drag
}

function flushSync() {
  clearTimeout(saveTimer); saveTimer = null
  if (!gs) return
  // save() callback backfills w/h: GridStack omits them from save output
  // when w===minW / h===minH (treated as min-clamped redundancy) and when
  // w===1/h===1 -- writing those back as undefined would DROP the fields
  // from page.json (observed: today card lost h entirely, fell to clamp
  // default 4 on reload and the geometry drifted from the engine's truth)
  // grid.save signature is (saveContent, saveGridOpt, saveCB) -- the cb is
  // the THIRD arg and also runs before grid.save strips el/content
  const geo = new Map((gs.save(false, false, (node, item) => {
    if (item.h == null) item.h = node.h
    if (item.w == null) item.w = node.w
  }) || []).map(i => [i.id, i]))
  // mutate snapshot fields in place: DOM stays GridStack's, files get updated
  for (const b of items.value) {
    const g = geo.get(b.id)
    if (g) { b.x = g.x; b.y = g.y; b.w = g.w; b.h = g.h }
  }
  // emit geometry for VISIBLE blocks, then append the hidden ones untouched:
  // App replaces page.blocks wholesale, dropping them here would delete them
  emit('geometry', [...items.value.map(b => ({ ...b })), ...hiddenSnapshot])
}
</script>

<template>
  <!-- 服务模式:GridStack 编辑器(Geometry by GS, content by Vue) -->
  <main v-if="serverMode" id="grid" ref="gridEl">
    <div v-for="b in items" :key="b.id" class="grid-stack-item"
         :gs-x="b.x" :gs-y="b.y" :gs-w="b.w" :gs-h="b.h" :gs-id="b.id">
      <div class="grid-stack-item-content">
        <div class="card" :class="cardClass(b)" :data-bid="b.id" :ref="el => setCardEl(b.id, el)">
          <div class="cfit">
            <component :is="cardFor(b.type)" :block="b" :kid="kid" @update="p => onPropsUpdate(b, p)" @open-issue="id => emit('open-issue', id)" />
          </div>
          <button class="share-fab" title="分享此卡给家人" @click.stop="emit('share-card', b)"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M4 14v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6"/></svg></button>
          <button v-if="editing" class="hmode-fab" :title="b.autoH ? '高度随内容自适应，点击恢复固定' : '高度固定，点击改为随内容自适应'"
                  @click.stop="toggleAutoH(b)">{{ b.autoH ? '自适应' : '固定' }}</button>
        </div>
      </div>
    </div>
  </main>

  <!-- 文件模式:CSS grid 流式只读 -->
  <main v-else class="grid">
    <section v-for="b in items" :key="b.id" class="card"
             :class="cardClass(b)" :data-bid="b.id"
             :style="{ '--w': clampInt(b.w, 1, 12, 6), '--minh': b.autoH ? (b.minH || 3) : 0 }">
      <div class="cfit">
        <component :is="cardFor(b.type)" :block="b" :kid="kid" @update="p => onPropsUpdate(b, p)" @open-issue="id => emit('open-issue', id)" />
      </div>
      <button class="share-fab" title="分享此卡给家人" @click.stop="emit('share-card', b)"><svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 15V3"/><path d="m7 8 5-5 5 5"/><path d="M4 14v6a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-6"/></svg></button>
    </section>
  </main>
</template>

<style scoped>
.hmode-fab { position: absolute; top: 8px; right: 10px; z-index: 6;
  border: 1px solid var(--line); background: #fff; color: var(--sub);
  border-radius: 6px; cursor: pointer; font-size: 11.5px; font-weight: 500;
  line-height: 1; padding: 5px 8px; font-family: inherit; }
.hmode-fab:hover { border-color: var(--ink-blue); color: var(--ink-blue); }
.share-fab { position: absolute; top: 10px; right: 12px; z-index: 5;
  width: 28px; height: 28px; display: flex; align-items: center; justify-content: center;
  border: 1px solid var(--line); background: #fff; color: var(--sub);
  border-radius: 8px; cursor: pointer; transition: all .15s; padding: 0; font: inherit; }
.share-fab:hover { border-color: var(--ink-blue); color: var(--ink-blue);
  background: var(--accent-soft); }
/* 编辑布局时整卡都是拖拽把手,分享按钮退场防误触。
   注意::global() 必须包裹完整选择器——混合形态 `:global(body.editing) .share-fab`
   会被 Vue scoped 编译成 `body.editing{display:none}`(整页隐藏,编辑模式白屏的根因) */
:global(body.editing .share-fab) { display: none; }
:global(body.capturing .share-fab) { display: none; }   /* WYSIWYG 长图不带走交互钮 */
/* 窄屏触控目标放大(规范:命中区 ≥44px;卡片标题行右让位同步加宽) */
@media (max-width: 720px) {
  .share-fab { width: 40px; height: 40px; top: 12px; right: 12px; }
  :global(.cband h3) { padding-right: 50px; }
}
</style>
