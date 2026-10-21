<script setup>
// 编辑模式底部面板(2026-10-10 与编辑布局合并;同日改瓦片墙):页面卡片=瓦片
// (整片点击开关显隐+内置卡可 ✕ 删除)+添加卡片+自定义卡对话引导。
//   - 显隐:关=hidden:true 保留几何;开=原位恢复。
//   - 删除=block 移出 page.json,想用随时从「添加卡片」区回来(内置卡数据在
//     child.json,删除零损失);自定义卡带用户内容,删除唯一路径=对话(blocks-spec
//     边界),瓦片上不给 ✕。
import { computed } from 'vue'
import { CARD_META } from './cards/index.js'

const props = defineProps({ page: Object })
const emit = defineEmits(['toggle', 'show', 'remove'])

const blocks = computed(() => (props.page?.blocks || []))
const shown = computed(() => blocks.value.filter(b => !b.hidden))
const hiddenBlocks = computed(() => blocks.value.filter(b => b.hidden))
const allTiles = computed(() => [...shown.value, ...hiddenBlocks.value])

function labelOf(b) {
  const meta = CARD_META[b.type]
  if (b.type === 'text' || b.type === 'list') return b.props?.title || meta?.name || b.type
  const extra = b.props?.tag ? `· ${b.props.tag}` : b.props?.months ? `· ${b.props.months}月` : ''
  return (meta?.name || b.type) + (extra ? ` ${extra}` : '')
}
function descOf(b) {
  const meta = CARD_META[b.type]
  if (meta?.group === 'custom')
    return b.type === 'list' ? `清单 · ${(b.props?.items || []).length} 项` : '便签'
  return meta?.desc || ''
}
const isCustom = (b) => CARD_META[b.type]?.group === 'custom'

// builtin types with no block on the page (shown or hidden) -> can be turned on
const absentTypes = computed(() =>
  Object.entries(CARD_META).filter(([type, m]) =>
    m.group === 'builtin' && !blocks.value.some(b => b.type === type)))
</script>

<template>
  <section class="manage-panel">
    <header>
      <b>卡片管理</b>
      <span class="sub">点卡片切换显示/隐藏 · ✕ 从页面删除 · 拖拽调布局 · 内容回对话</span>
    </header>

    <div class="grp">页面上的卡片</div>
    <div class="tilegrid">
      <div v-for="b in allTiles" :key="b.id" class="tile" :class="{ off: b.hidden }"
           :title="b.hidden ? '点击恢复显示(保留原位置)' : '点击隐藏(保留原位置)'"
           @click="emit('toggle', { id: b.id, on: !!b.hidden })">
        <div class="t-name">{{ labelOf(b) }}</div>
        <div class="t-desc">{{ descOf(b) }}</div>
        <div class="t-foot">
          <span class="t-state">{{ b.hidden ? '已隐藏 · 点击恢复' : '显示中 · 点击隐藏' }}</span>
          <button v-if="!isCustom(b)" class="t-del"
                  title="从页面删除;想用随时在下方「添加卡片」加回"
                  @click.stop="emit('remove', { id: b.id })">✕ 删除</button>
          <span v-else class="t-note">删除回对话</span>
        </div>
      </div>
    </div>

    <template v-if="absentTypes.length">
      <div class="grp">添加卡片</div>
      <div class="tilegrid">
        <button v-for="[type, m] in absentTypes" :key="type" class="pick" @click="emit('show', type)">
          <div class="t-name">{{ m.name }}</div>
          <div class="t-desc">{{ m.desc }}</div>
          <div class="t-foot"><span class="t-add">＋ 添加到页面</span></div>
        </button>
      </div>
    </template>

    <div class="hint-box">
      想加<b>自定义卡</b>(便签/清单)或改卡片内容?<b>回到对话跟 AI 说</b>,比如
      「帮我加一张出门清单卡」「把奶奶须知卡的内容改成…」——AI 会按页面规范直接改配置。
    </div>
  </section>
</template>

<style scoped>
.manage-panel { max-width: 1200px; margin: 10px auto 48px; padding: 18px 22px 20px;
  background: #fff; border: 1.5px solid var(--ink-blue); border-radius: 12px; }
header { display: flex; align-items: baseline; gap: 12px; margin-bottom: 6px;
  padding-bottom: 10px; border-bottom: 1px solid var(--grid-line); }
header b { font-size: 16px; color: var(--ink-blue); letter-spacing: .04em; }
header .sub { font-size: 12.5px; color: var(--sub); }
.grp { font-size: 12.5px; color: var(--sub); letter-spacing: .06em; margin: 14px 0 8px; }
.tilegrid { display: grid; grid-template-columns: repeat(auto-fill, minmax(172px, 1fr)); gap: 10px; }
.tile { border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px 8px;
  cursor: pointer; background: #fff; display: flex; flex-direction: column; gap: 5px;
  min-height: 98px; font: inherit; text-align: left; }
.tile:hover { border-color: var(--ink-blue); }
.tile.off { background: #faf8f4; border-style: dashed; }
.tile.off:hover { border-color: var(--sub); }
.t-name { font-size: 14px; font-weight: 700; color: var(--ink); line-height: 1.4; }
.t-desc { font-size: 11.5px; color: var(--sub); flex: 1; line-height: 1.45; }
.t-foot { display: flex; align-items: center; gap: 8px; font-size: 11.5px;
  border-top: 1px dashed var(--grid-line); padding-top: 6px; }
.t-state { color: var(--ink-blue); }
.tile.off .t-state { color: var(--sub); }
.t-del { margin-left: auto; border: 1px solid transparent; background: none;
  color: var(--sub); font-size: 11.5px; cursor: pointer; padding: 1px 7px; border-radius: 5px; }
.t-del:hover { color: var(--todo); border-color: var(--todo); }
.t-note { margin-left: auto; color: var(--sub); }
.pick { border: 1px dashed var(--ink-blue); border-radius: 10px;
  padding: 10px 12px 8px; cursor: pointer; background: rgba(47,84,112,.03);
  display: flex; flex-direction: column; gap: 5px; min-height: 98px; font: inherit;
  text-align: left; }
.pick:hover { background: var(--accent-soft); }
.t-add { color: var(--ink-blue); font-weight: 600; }
.hint-box { background: var(--accent-soft); border-radius: 10px; padding: 10px 12px;
  font-size: 12.5px; color: var(--hint); margin-top: 14px; line-height: 1.6; }
@media (max-width: 640px) { .tilegrid { grid-template-columns: 1fr 1fr; } }
</style>
