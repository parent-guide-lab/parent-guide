<script setup>
import { computed } from 'vue'
import { monthsAge, fullDate } from '../../lib/util.js'
const props = defineProps({ block: Object, kid: Object })
const emit = defineEmits(['open-issue'])
const age = computed(() => props.kid?.birthdate ? monthsAge(props.kid.birthdate) : null)
const initial = computed(() => (props.kid?.name || '宝').slice(0, 1))

// 下一档盘点钩子(纯计算):CDC 检查点档位表里第一个大于当前月龄的档
const STEPS = [18, 24, 30, 36, 48, 60]
const nextStep = computed(() => {
  if (age.value === null || !props.kid?.birthdate) return null
  const m = STEPS.find(s => s > age.value)
  if (!m) return null
  const b = new Date(props.kid.birthdate)
  const d = new Date(b.getFullYear(), b.getMonth() + m, b.getDate())
  return { months: m, ym: `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}` }
})

// 关注 chips 挂 P 号:与在管问题按名称精确匹配(机械),命中可点开病历
const issueByName = computed(() => {
  const map = {}
  for (const i of (props.kid?.issues || [])) if (i.status !== 'resolved') map[i.name] = i
  return map
})

// 画像字段:模板占位原文=未填,跳过不渲染(与 check 的占位感知同口径)
const P = new Set(['语言发展一句话', '气质特点一句话', '安抚物(如有)',
  '家庭管教口径、长辈观点等背景', '过敏史(食物/药物/湿疹;没有写无)',
  '兄弟姐妹(没有写无)',
  '长期健康背景(湿疹体质/哮喘/反复中耳炎/手术史;没有写无)',
  '绘本偏好', '活动偏好', '主要照顾人与分工'])
const clean = (v) => (v && !P.has(String(v).trim())) ? String(v).trim() : ''
const prof = computed(() => props.kid?.profile || {})
const caregivers = computed(() => clean(prof.value.caregivers))
const siblings = computed(() => clean(prof.value.siblings))
const temperament = computed(() => clean(prof.value.temperament))
const language = computed(() => clean(prof.value.language))
const comfort = computed(() => clean(prof.value.comfortObject))
const familyNotes = computed(() => clean(prof.value.familyNotes))
const allergies = computed(() => clean(prof.value.allergies))
const healthNotes = computed(() => clean(prof.value.healthNotes))
const books = computed(() => clean(prof.value.preferences?.books))
const activities = computed(() => clean(prof.value.preferences?.activities))
const hasPref = computed(() => !!(books.value || activities.value || comfort.value))

// 画像快照的核实时间(_asOf 由 update-child.py 维护):孩子画像区取已展示字段的
// 最晚核实日,超 6 月(183 天)未核对给提示——机械信号,清提示的路径仍是
// 「对话中对过现值」(set-profile --verify / 改值),页面不提供编辑入口
const FIELD_LABELS = { temperament: '气质', language: '语言', comfortObject: '安抚物',
  caregivers: '照料', familyNotes: '家庭口径', allergies: '过敏',
  healthNotes: '健康', siblings: '兄弟姐妹',
  'preferences.books': '绘本偏好', 'preferences.activities': '活动偏好',
  'sleep.note': '睡眠', gender: '性别', childcarePlan: '托育安排' }
const asofMap = computed(() => prof.value._asOf || {})
const shownFields = computed(() => {
  const pairs = [['temperament', temperament.value], ['language', language.value],
    ['comfortObject', comfort.value], ['allergies', allergies.value],
    ['healthNotes', healthNotes.value], ['familyNotes', familyNotes.value]]
  return pairs.filter(([, v]) => v).map(([f]) => f)
})
const secAsOf = computed(() => {
  const ds = shownFields.value.map(f => asofMap.value[f]).filter(Boolean).sort()
  return ds[ds.length - 1] || ''
})
const staleFields = computed(() => {
  const out = []
  for (const f of shownFields.value) {
    const d = asofMap.value[f]
    if (!d) continue
    const days = (Date.now() - new Date(d).getTime()) / 86400000
    if (days > 183) out.push({ label: FIELD_LABELS[f] || f, months: Math.max(1, Math.round(days / 30.44)) })
  }
  return out
})
const staleHint = computed(() => {
  if (!staleFields.value.length) return ''
  const worst = Math.max(...staleFields.value.map(s => s.months))
  return `${staleFields.value.map(s => s.label).join('/')}超 ${worst} 个月未核对`
})

// 画像变迁(2026-10-14):set-profile 改值自动留档 profileHistory,最新在上
const hist = computed(() => (props.kid?.profileHistory || []).slice().reverse())
</script>

<template>
  <div class="cband"><h3>档案</h3></div>
  <div class="cbody pf-body">
    <div class="phead">
      <div>
        <div class="pname">{{ kid.name || '未填写' }}</div>
        <div class="big"><span class="num-serif num-hero" v-if="age !== null">{{ age }}</span><span v-if="age !== null" class="num-unit">个月</span></div>
        <div v-if="nextStep" class="nextstep">下一档 <b>{{ nextStep.months }} 月</b> · {{ nextStep.ym }} 前后做发育盘点对照</div>
        <div class="meta">
          <template v-if="kid.birthdate">{{ fullDate(kid.birthdate) }} 出生</template>
          <template v-else>生日未填写</template>
          <template v-if="siblings"> · {{ siblings }}</template>
          <template v-if="caregivers"> · {{ caregivers }}</template>
        </div>
      </div>
      <span class="seal">{{ initial }}</span>
    </div>

    <div v-if="(kid.currentFocus || []).length" class="psec">
      <div class="plabel">当前关注</div>
      <div><span v-for="f in kid.currentFocus" :key="f" class="chip"
        :class="{ lnk: issueByName[f] }" :title="issueByName[f] ? '点击查看病历详情' : ''"
        @click="issueByName[f] && emit('open-issue', issueByName[f].id)">{{ f }}<template v-if="issueByName[f]"><b class="p">{{ issueByName[f].id }}</b></template></span></div>
    </div>

    <div v-if="hasPref || temperament || language || allergies" class="psec">
      <div class="plabel">孩子画像<template v-if="secAsOf"><span class="asof">截至 {{ secAsOf }}</span><span v-if="staleHint" class="asof stale">{{ staleHint }}</span></template></div>
      <div v-if="temperament" class="kv"><b>气质</b><span>{{ temperament }}</span></div>
      <div v-if="language" class="kv"><b>语言</b><span>{{ language }}</span></div>
      <div v-if="hasPref" class="kv"><b>偏好</b><span>
        <span v-if="comfort" class="chip">🧸 {{ comfort }}</span>
        <span v-if="activities" class="chip">🏃 {{ activities }}</span>
        <span v-if="books" class="chip">📖 {{ books }}</span>
      </span></div>
      <div v-if="allergies" class="kv"><b>过敏</b><span>{{ allergies }}</span></div>
      <div v-if="healthNotes" class="kv"><b>健康</b><span>{{ healthNotes }}</span></div>
      <div v-if="familyNotes" class="kv"><b>家庭口径</b><span class="muted">{{ familyNotes }}</span></div>
    </div>

    <div v-if="hist.length" class="psec">
      <div class="plabel">画像变迁</div>
      <div v-for="(h, i) in hist" :key="i" class="phist">
        <div class="phd">{{ h.date }} · {{ FIELD_LABELS[h.field] || h.field }}</div>
        <div class="pvals"><span class="pv old">{{ h.from || '(未填)' }}</span><span class="parr">→</span><span class="pv">{{ h.to }}</span></div>
      </div>
    </div>

    <div v-if="!hasPref && !temperament && !language && !allergies" class="src">
      画像(气质/语言/偏好)还没填——聊到这些话题时 AI 会顺带记录,这里会慢慢丰满。
    </div>
  </div>
</template>

<style scoped>
/* 卡头=标准 cband(2026-10-11 用户:规范不该有特例);phead 顶部加呼吸感 */
.pf-body { padding-top: 14px; }
.phead { display: flex; align-items: flex-start; gap: 12px; padding-bottom: 12px;
  border-bottom: 1px solid var(--grid-line); }
.pname { font-size: 22px; font-weight: 700; line-height: 1.25; }
.nextstep { font-size: 11.5px; color: var(--sub); margin: 5px 0 2px; }
.nextstep b { color: var(--ink-blue); font-weight: 600; }
.meta { font-size: 12.5px; color: var(--sub); margin-top: 2px; }
.seal { flex: none; margin-left: auto; width: 46px; height: 46px; border-radius: 8px;
  border: 1.5px solid var(--grid-line); background: rgba(255,255,255,.8);
  display: flex; align-items: center; justify-content: center;
  font-size: 20px; font-weight: 700; color: var(--ink-blue); }
.psec { margin-top: 12px; }
.plabel { display: flex; align-items: baseline; gap: 8px; font-size: 11.5px;
  color: var(--sub); margin-bottom: 5px; letter-spacing: .08em; }
.plabel .asof { margin-left: auto; letter-spacing: 0; font-size: 11.5px;
  font-variant-numeric: tabular-nums; }
.plabel .asof.stale { color: var(--watch); }
.phist { padding: 6px 0; border-bottom: 1px dashed var(--grid-line); }
.phist:last-child { border-bottom: none; }
.phd { font-size: 11.5px; color: var(--sub); margin-bottom: 3px;
  font-variant-numeric: tabular-nums; }
.pvals { display: flex; gap: 6px; align-items: flex-start; font-size: 12.5px;
  line-height: 1.5; }
.pv { flex: 1; min-width: 0; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical; overflow: hidden; }
.pv.old { color: var(--sub); }
.parr { flex: none; color: var(--ink-blue); }
.chip.lnk { border-style: solid; border-color: var(--ink-blue); cursor: pointer; }
.chip.lnk:hover { background: var(--accent-soft); }
.chip .p { font-size: 10.5px; font-weight: 700; margin-left: 4px;
  font-family: Georgia, serif; }
.kv { display: flex; gap: 10px; font-size: 12.5px; padding: 6px 0;
  border-bottom: 1px dashed var(--grid-line); align-items: baseline; }
.kv:last-child { border-bottom: none; }
.kv b { flex: none; width: 4em; color: var(--sub); font-weight: 500; font-size: 12.5px; }
.kv span { flex: 1; min-width: 0; line-height: 1.55; }
.kv .muted { color: var(--sub); }
</style>
