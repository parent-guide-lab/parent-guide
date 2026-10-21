<script setup>
// 顶部知识轮播条:静态清单(web/src/data/ticker-tips.js,官方库蒸馏)随机出一条,
// 「换一条」按钮随机换(不重复当前条);点击正文在本地服务模式下打开应用内
// 知识库并定位到来源那篇(KnowledgePage 的 file prop)。文件模式纯展示。
// 导出长图/打印/单文件报告的隐藏规则在 style.css(body.capturing/.report)。
import { computed, ref } from 'vue'
import { state } from '../lib/store.js'
import { cnpunct } from '../lib/util.js'
import { TIPS } from '../data/ticker-tips.js'

const emit = defineEmits(['open-doc'])

// 随机抽一条;带 exclude 时保证换一条不出同一条
function randomIdx(exclude = -1) {
  if (TIPS.length <= 1) return 0
  let i = exclude
  while (i === exclude) i = Math.floor(Math.random() * TIPS.length)
  return i
}

const idx = ref(randomIdx())
const tip = computed(() => TIPS[idx.value])
const clickable = computed(() => state.serverMode)

function refresh() { idx.value = randomIdx(idx.value) }
function open() {
  if (clickable.value) emit('open-doc', tip.value.file)
}
</script>

<template>
  <div class="tk-bar">
    <button class="tk-main" :class="{ link: clickable }"
            :title="clickable ? '查看知识库原文' : '连接本地服务后可跳转知识库'"
            @click="open">
      <Transition name="tk-fade" mode="out-in">
        <span class="tk-line" :key="idx">
          <span class="tk-text">{{ cnpunct(tip.t) }}</span>
          <span v-if="tip.src" class="tk-src">依据 · {{ tip.src }}</span>
        </span>
      </Transition>
    </button>
    <button class="tk-refresh" aria-label="换一条" title="换一条" @click="refresh">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
           stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
           aria-hidden="true">
        <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
        <path d="M21 3v5h-5" />
      </svg>
    </button>
  </div>
</template>

<style scoped>
.tk-bar { width: calc(100% - 40px); max-width: 1160px; margin: 14px auto 0;
  padding: 5px 10px 5px 16px;
  display: flex; align-items: center; gap: 10px;
  background: var(--card); border: 1px solid var(--line); border-radius: 10px; }
.tk-main { flex: 1; min-width: 0; border: 0; background: none; padding: 3px 0;
  text-align: left; cursor: default; font: inherit; color: var(--ink); }
.tk-main.link { cursor: pointer; }
.tk-main.link:hover .tk-text { color: var(--accent); }
.tk-line { display: inline; }
.tk-text { font-size: 12.5px; line-height: 1.6; }   /* 用户拍板 2026-10-21 demo 对比 A 档 */
.tk-src { margin-left: 8px; font-size: 11.5px; color: var(--sub); white-space: nowrap; }
.tk-refresh { flex: none; width: 26px; height: 26px; display: inline-flex;
  align-items: center; justify-content: center; border: 1px solid var(--line);
  background: none; color: var(--sub); border-radius: 6px; cursor: pointer; }
.tk-refresh:hover { color: var(--accent); border-color: var(--accent); }
.tk-fade-enter-active, .tk-fade-leave-active { transition: opacity .35s; }
.tk-fade-enter-from, .tk-fade-leave-to { opacity: 0; }
@media (max-width: 720px) {
  .tk-bar { margin-top: 10px; }
  .tk-src { display: none; }   /* 窄屏只留断言本体,来源进知识库面板看 */
}
</style>
