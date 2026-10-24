<script setup>
// 应用内知识库·独立页面:顶部只分「官方库 | 我的自建」,左侧目录栏,右侧正文。
// 官方文档由 server 渲染(knowledge/ 闭集+site-src 速查),自建来自 knowledge/user/
// (仅本机,永不发布);两区正文同走 .kb-doc 全局样式,引用经 linkifyHtml 转链。
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { linkifyHtml } from '../lib/util.js'

const emit = defineEmits(['close'])

// 可选初始文档(顶部知识轮播条跳转用):在官方清单里则直接定位打开
const props = defineProps({ file: { type: String, default: '' } })

const tab = ref('official') // 'official' | 'user'
const official = ref([])
const user = ref([])
const loading = ref(true)
const listError = ref('')
const sel = ref({ official: '', user: '' }) // 每区记住最近打开的一篇
const doc = ref(null) // { file, title, meta, html }
const docLoading = ref(false)
const docError = ref('')

async function loadList() {
  loading.value = true
  listError.value = ''
  try {
    const r = await fetch('/api/knowledge')
    if (!r.ok) throw new Error(`HTTP ${r.status}`)
    const d = await r.json()
    official.value = d.official || []
    user.value = d.user || []
    if (official.value.length) {
      const target = props.file && official.value.some(o => o.file === props.file)
        ? props.file : official.value[0].file
      await pick(target)
    }
  } catch (e) {
    listError.value = `知识库加载失败（${e.message}）——确认本地服务已在运行`
  } finally {
    loading.value = false
  }
}

async function openDoc(file) {
  docLoading.value = true
  docError.value = ''
  try {
    const r = await fetch(`/api/knowledge/read?file=${encodeURIComponent(file)}`)
    const d = await r.json()
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`)
    // server 出的是转义后的 HTML,这里只补知识引用转链(同白名单,不自建死链)
    doc.value = { ...d, html: linkifyHtml(d.html) }
  } catch (e) {
    docError.value = `打开失败：${e.message}`
  } finally {
    docLoading.value = false
  }
}

async function pick(file) {
  sel.value[tab.value] = file
  await openDoc(file)
}

async function switchTab(t) {
  tab.value = t
  if (sel.value[t]) return openDoc(sel.value[t])
  doc.value = null // 自建区空态:内容区出引导,目录区出提示
}

const docMeta = computed(() => {
  if (!doc.value) return {}
  if (doc.value.file.startsWith('user/')) return { isUser: true }
  const t = official.value.find(o => o.file === doc.value.file)
  return { src: t?.src, group: t?.group }
})

// 左栏分组:速查置顶(无组头),其余按 knowledge.json 带出的组连续分段
const sidebar = computed(() => {
  const pinned = official.value.filter(t => t.slug === 'quick-ref')
  const groups = []
  for (const t of official.value) {
    if (t.slug === 'quick-ref') continue
    const g = t.group || '其他'
    if (!groups.length || groups[groups.length - 1].name !== g) groups.push({ name: g, items: [] })
    groups[groups.length - 1].items.push(t)
  }
  return { pinned, groups }
})

function onKey(e) { if (e.key === 'Escape') emit('close') }
onMounted(async () => {
  window.addEventListener('keydown', onKey)
  await loadList()
})
onUnmounted(() => window.removeEventListener('keydown', onKey))
</script>

<template>
  <Teleport to="body">
    <div class="kbp">
      <header class="kbp-top">
        <button class="kbp-back" @click="emit('close')">← 成长视图</button>
        <span class="kbp-title">知识库</span>
        <div class="kbp-tabs">
          <button :class="{ on: tab === 'official' }" @click="switchTab('official')">官方库</button>
          <button :class="{ on: tab === 'user' }" @click="switchTab('user')">我的自建</button>
        </div>
      </header>

      <div class="kbp-body">
        <aside class="kbp-side">
          <div v-if="loading" class="kbp-hint">加载中…</div>
          <div v-else-if="listError" class="kbp-hint err">{{ listError }}</div>
          <template v-else-if="tab === 'official'">
            <button v-for="t in sidebar.pinned" :key="t.slug" class="kbp-item pin"
                    :class="{ on: sel.official === t.file }" @click="pick(t.file)">{{ t.title }}</button>
            <template v-for="g in sidebar.groups" :key="g.name">
              <div class="kbp-group">{{ g.name }}</div>
              <button v-for="t in g.items" :key="t.slug" class="kbp-item ind"
                      :class="{ on: sel.official === t.file }" @click="pick(t.file)">{{ t.title }}</button>
            </template>
          </template>
          <template v-else>
            <div v-if="!user.length" class="kbp-hint">还没有自建文件</div>
            <button v-for="u in user" :key="u.file" class="kbp-item"
                    :class="{ on: sel.user === u.file }" @click="pick(u.file)">
              {{ u.title }}
              <span class="sub">{{ u.meta?.date }}<template v-if="u.meta?.type"> · {{ u.meta.type }}</template></span>
            </button>
          </template>
        </aside>

        <main class="kbp-main">
          <div v-if="docLoading" class="kbp-hint">加载中…</div>
          <div v-else-if="docError" class="kbp-hint err">{{ docError }}</div>
          <div v-else-if="doc" class="kbp-docwrap">
            <div class="kbp-dochead">
              <h1>{{ doc.title }}</h1>
              <div class="kbp-docmeta">
                <template v-if="docMeta.isUser">
                  <span v-if="doc.meta?.date">{{ doc.meta.date }}</span>
                  <span v-if="doc.meta?.type" class="kbp-badge">{{ doc.meta.type }}</span>
                  <span v-if="doc.meta?.check" class="kbp-badge">核对={{ doc.meta.check }}</span>
                  <span v-if="doc.meta?.source">来源：{{ doc.meta.source }}</span>
                  <span class="kbp-badge local">家庭自建 · 仅本地</span>
                </template>
                <template v-else-if="docMeta.src">
                  <span v-if="docMeta.group && docMeta.group !== '速查'" class="kbp-badge">{{ docMeta.group }}</span>
                  {{ docMeta.src }}
                </template>
              </div>
            </div>
            <!-- eslint-disable-next-line vue/no-v-html —— server 渲染的白名单 markdown -->
            <div class="kb-doc" v-html="doc.html"></div>
          </div>
          <div v-else-if="tab === 'user' && !user.length" class="kbp-empty">
            还没有自建知识。对话里调研沉淀或蒸馏出的专题会写进 knowledge/user/，出现在左侧目录——
            只保存在你自己的电脑上，公开分享的只有官方库。
          </div>
        </main>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.kbp { position: fixed; inset: 0; z-index: 40; display: flex; flex-direction: column;
  background-color: var(--bg);
  background-image: linear-gradient(var(--grid) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 22px 22px; }

/* 顶栏:返回 + 标题 + 官方/自建切换(类型清单不在顶栏) */
.kbp-top { display: flex; align-items: center; gap: 14px; padding: 10px 20px;
  background: var(--card); border-bottom: 1px solid var(--line); }
.kbp-back { border: 1px solid var(--line); background: #fff; color: var(--ink-blue);
  border-radius: 8px; padding: 5px 12px; font-size: 12.5px; cursor: pointer; }
.kbp-back:hover { border-color: var(--accent); }
.kbp-title { font-size: 16px; font-weight: 700; color: var(--ink-blue); margin-right: auto; }
.kbp-tabs { display: flex; border: 1px solid var(--line); border-radius: 8px;
  overflow: hidden; background: #fff; }
.kbp-tabs button { border: 0; background: none; padding: 6px 18px; font-size: 12.5px;
  color: var(--sub); cursor: pointer; }
.kbp-tabs button + button { border-left: 1px solid var(--line); }
.kbp-tabs button.on { background: var(--accent-soft); color: var(--ink-blue); font-weight: 600; }

/* 左目录 + 右正文 */
.kbp-body { flex: 1; display: flex; min-height: 0; }
.kbp-side { width: 232px; flex: none; overflow: auto; background: var(--card);
  border-right: 1px solid var(--line); padding: 8px 0; }
.kbp-item { display: block; width: 100%; text-align: left; padding: 9px 16px;
  font: inherit; font-size: 12.5px; line-height: 1.45; color: var(--ink); background: none;
  border: 0; border-left: 2px solid transparent; cursor: pointer; }
.kbp-item.ind { padding-left: 30px; }
.kbp-item:hover { background: var(--accent-soft); }
.kbp-item.on { background: var(--accent-soft); color: var(--ink-blue); font-weight: 600;
  border-left-color: var(--ink-blue); }
.kbp-item .sub { display: block; font-size: 10.5px; color: var(--sub); font-weight: 400; margin-top: 1px; }
.kbp-item.pin { color: var(--ink-blue); font-weight: 600; }
.kbp-group { font-size: 12.5px; font-weight: 700; letter-spacing: .08em; color: var(--ink-blue);
  padding: 14px 16px 5px; user-select: none; }
.kbp-group:first-child { padding-top: 4px; }
.kbp-main { flex: 1; overflow: auto; padding: 26px 34px 48px; }
.kbp-main > div { max-width: 800px; margin: 0 auto; }
.kbp-hint { padding: 32px 0; text-align: center; color: var(--sub); font-size: 14px; }
.kbp-hint.err { color: var(--hint); }
.kbp-dochead { border-bottom: 1px solid var(--line); padding-bottom: 12px; margin-bottom: 8px; }
.kbp-dochead h1 { font-size: 22px; color: var(--ink-blue); }
.kbp-docmeta { display: flex; gap: 8px; flex-wrap: wrap; align-items: center;
  font-size: 12.5px; color: var(--sub); margin-top: 6px; }
.kbp-badge { border: 1px solid var(--line); border-radius: 5px; padding: 1px 8px;
  font-size: 11.5px; background: var(--accent-soft); color: var(--ink-blue); }
.kbp-badge.local { color: var(--hint); border-color: #e3d5c0; background: #faf5ec; }
.kbp-empty { border: 1px dashed var(--grid-line); border-radius: 10px; background: var(--card);
  padding: 18px 20px; font-size: 14px; color: var(--sub); line-height: 1.7; margin-top: 24px; }

/* 窄屏:目录折叠为顶部横向滚动行 */
@media (max-width: 760px) {
  .kbp-body { flex-direction: column; }
  .kbp-side { width: 100%; max-height: 132px; border-right: 0; border-bottom: 1px solid var(--line);
    display: flex; gap: 4px; padding: 8px 10px; }
  .kbp-item { flex: none; width: auto; border: 1px solid var(--line); border-radius: 8px;
    padding: 6px 12px; }
  .kbp-item.ind { padding-left: 12px; }
  .kbp-item.on { border-color: var(--ink-blue); }
  .kbp-item .sub { display: none; }
  .kbp-main { padding: 18px 16px 40px; }
}
</style>
