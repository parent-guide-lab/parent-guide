<script setup>
// 页面级导出弹窗(2026-10-22 用户拍板:与卡级同交互——先预览再导出,版本在
// 弹窗中切换):手机版=375px 文件模式板面实时渲染(与窄屏浏览同构,cap-mobile
// 显式套窄屏内边距——媒体查询看视口不看容器),桌面版=当前板面 DOM 克隆钉
// 原宽。预览即所发(导出节点=预览节点),导出=保存图片不弹系统分享。
// PDF/单文件网页入口同弹窗,交回 App 执行。
import { ref, computed, watch, inject, nextTick } from 'vue'
import GridBoard from './GridBoard.vue'
import { exportPng, stampEl } from '../lib/util.js'

const props = defineProps({
  open: Boolean,
  page: { type: Object, default: null },
  kid: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close', 'print', 'report'])

// 与卡级导出同一内容规则:弹窗开着=预览内容全展开(主面板卡同步展开供克隆)
const capExpand = inject('captureExpand', { value: false })

const ver = ref('mobile')      // 'mobile'=375 单列 | 'desktop'=12 列原样
const exporting = ref(false)
const mobEl = ref(null)        // 手机版预览节点(=导出节点)
const deskEl = ref(null)       // 桌面版预览容器(缩放适配)
const deskFit = ref(null)      // 缩放视窗(height=内容高×scale)
const deskInner = ref(null)    // 缩放的克隆挂载点
let deskOff = null             // 桌面版导出源:隐藏全尺寸克隆+角标(预览缩放不影响成图)

const today = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
})()
const dispName = computed(() => props.kid?.name || '页面')

function stripControls(root) {
  root.querySelectorAll('.share-fab, .hmode-fab, .tgl').forEach(el => el.remove())
}

// 桌面版:同一克隆两份用途——①预览=缩放适配容器宽(transform scale,无横向
// 滚动);②导出源=隐藏全尺寸节点(cap-board 藏屏外)+角标,domToPng 成图
// 不受预览缩放影响。弹窗关闭/切回手机版时撤掉隐藏节点。
async function buildDesk() {
  const src = document.querySelector('#grid') || document.querySelector('main.grid')
  if (!src || !deskEl.value) return
  await new Promise(r => requestAnimationFrame(() => r()))   // 折叠展开/自适应卡布局一帧
  const makeClone = () => {
    const c = src.cloneNode(true)
    stripControls(c)
    // 剥 id:克隆保留 #grid 会吃 margin:0 auto(容器窄于板面时整体右偏被
    // 裁)且在文档里产生重复 id
    c.removeAttribute('id')
    c.style.margin = '0'
    c.style.width = Math.round(src.getBoundingClientRect().width) + 'px'
    return c
  }
  // 预览份:缩放适配
  const a = makeClone()
  deskInner.value.replaceChildren(a)
  const w = a.getBoundingClientRect().width
  const s = Math.min(1, deskEl.value.clientWidth / w)
  a.style.transformOrigin = 'top left'   // 默认 center 会向右偏 (1-s)*W/2 被裁
  a.style.transform = `scale(${s})`
  deskFit.value.style.height = Math.ceil(a.offsetHeight * s) + 'px'
  // 导出份:全尺寸隐藏节点
  deskOff?.remove()
  deskOff = document.createElement('div')
  deskOff.className = 'cap-board'
  deskOff.setAttribute('aria-hidden', 'true')
  const b = makeClone()
  deskOff.appendChild(b)
  deskOff.appendChild(stampEl(`${dispName.value} · 截至 ${today}`))
  document.body.appendChild(deskOff)
}

function teardownDesk() {
  deskOff?.remove()
  deskOff = null
}

watch(() => props.open, v => {
  if (v) ver.value = 'mobile'   // 每次打开回到手机版主场景
  else teardownDesk()
  capExpand.value = v
})
watch(ver, v => {
  if (!props.open) return
  if (v === 'desktop') nextTick(buildDesk)
  else teardownDesk()
})

async function doExport() {
  if (exporting.value) return
  if (ver.value === 'mobile') {
    if (!mobEl.value) return
    exporting.value = true
    try {
      await exportPng(mobEl.value, `成长视图-${dispName.value}-手机版-${today}.png`)
    } finally { exporting.value = false }
  } else {
    if (!deskOff) return
    exporting.value = true
    try {
      await exportPng(deskOff, `成长视图-${dispName.value}-桌面版-${today}.png`)
    } finally { exporting.value = false }
  }
}
</script>

<template>
  <Teleport to="body">
    <div v-if="open" class="share-mask" @click.self="emit('close')">
      <div class="share-dialog exp-dialog">
        <div class="share-head">
          <b>导出</b><span class="hint">预览即所发 · 导出即保存图片</span>
          <button class="x" @click="emit('close')">✕</button>
        </div>

        <div class="share-body">
          <aside class="share-side">
            <div class="opt-chips">
              <button class="opt-chip" :class="{ on: ver === 'mobile' }" @click="ver = 'mobile'"
                      title="375px 单列，与手机端渲染同构——发微信">手机版·单列</button>
              <button class="opt-chip" :class="{ on: ver === 'desktop' }" @click="ver = 'desktop'"
                      title="12 列板面原样——存档/打印底稿">桌面版·原样</button>
            </div>
            <p class="foot-hint">两版内容相同（折叠区全展开+截至日期角标），只差版式。</p>

            <div class="side-foot">
              <button class="btn primary" :disabled="exporting" @click="doExport">{{ exporting ? '生成中…' : '导出长图(保存图片)' }}</button>
              <button class="btn sub" @click="emit('print')">PDF（打印/存档）</button>
              <button class="btn sub" @click="emit('report')">单文件网页（转发/存档）</button>
            </div>
          </aside>

          <div class="share-scroll">
            <!-- 手机版:375px 文件模式板面实时渲染(真组件,预览即所发) -->
            <div v-if="ver === 'mobile'" class="exp-live" ref="mobEl">
              <div class="cap-frame cap-mobile">
                <GridBoard :page="page" :kid="kid" :server-mode="false" />
              </div>
              <div class="cap-stamp">{{ dispName }} · 截至 {{ today }}</div>
            </div>
            <!-- 桌面版:克隆缩放适配预览宽(无横向滚动);导出走隐藏全尺寸节点 -->
            <div v-else class="exp-live desk-live" ref="deskEl">
              <div class="desk-fit" ref="deskFit">
                <div class="desk-inner" ref="deskInner"></div>
              </div>
              <div class="cap-stamp">{{ dispName }} · 截至 {{ today }}</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </Teleport>
</template>
