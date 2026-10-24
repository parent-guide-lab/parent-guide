<script setup>
import { computed } from 'vue'
import { cnpunct } from '../../lib/util.js'
const props = defineProps({ block: Object, kid: Object })
const title = computed(() => props.block?.props?.title || '便签')
const text = computed(() => (props.block?.props?.text || '').trim())
// 存量渲染兼容(text 已退役):标点归一同现役口径
const punct = (s) => cnpunct(String(s ?? ''))
</script>

<template>
  <div class="cband"><h3>{{ punct(title) }}</h3></div>
  <div class="cbody">
    <p v-if="text" class="text-body">{{ punct(text) }}</p>
    <div v-else class="src">内容为空——回到对话对 AI 说「把{{ punct(title) }}的内容写成…」即可填入。</div>
  </div>
</template>

<style scoped>
.text-body { white-space: pre-wrap; font-size: 14px; color: var(--ink); margin: 0;
  line-height: 1.7; max-height: 420px; overflow-y: auto; }
</style>
