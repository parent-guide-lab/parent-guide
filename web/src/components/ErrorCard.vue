<script setup>
// Fallback for unknown types (fail-soft). GridBoard passes the whole block,
// so read the type off it; the bare `type` prop is kept for compatibility.
const props = defineProps({ block: Object, type: String })
</script>

<template>
  <div class="card err">
    <div class="cband"><h3>无法渲染的卡片</h3></div>
    <div class="cbody">
      <div>type <code>{{ block?.type || type }}</code> 不在白名单或数据结构不符，已跳过；其余卡片不受影响。</div>
    </div>
  </div>
</template>
