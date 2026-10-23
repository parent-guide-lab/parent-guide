// Card registry: type whitelist, split into two groups.
//   BUILTIN (功能卡): data-bound cards reading child.json -- product-managed,
//            each pairs with skill write-actions; empty state = guide back to chat.
//   CUSTOM  (自定义卡): self-contained cards whose content lives in page.json
//            blocks (props only, never child.json -- that's the script contract).
// Adding a builtin block = adding one component here + blocks-spec.md entry.
import ProfileCard from './ProfileCard.vue'
import MilestoneCard from './MilestoneCard.vue'
import GrowthCard from './GrowthCard.vue'
import NotesCard from './NotesCard.vue'
import FocusCard from './FocusCard.vue'
import IssueCard from './IssueCard.vue'
import AnticipatoryCard from './AnticipatoryCard.vue'
import StrategyCard from './StrategyCard.vue'
import TextCard from './TextCard.vue'
import ListCard from './ListCard.vue'
import TrackerCard from './TrackerCard.vue'
import ErrorCard from '../ErrorCard.vue'

export const REGISTRY = {
  'profile': ProfileCard,
  'milestone': MilestoneCard,
  'growth': GrowthCard,
  'note': NotesCard,
  'focus': FocusCard,
  'issue': IssueCard,
  'anticipatory': AnticipatoryCard,
  'strategy': StrategyCard,
  'text': TextCard,
  'list': ListCard,
  'tracker': TrackerCard,
}

// Single source of truth for the add-panel, spec docs and validation.
// w/h = sensible defaults when instantiated from the panel.
// 2026-10-10 退役:strategy-effect(被问题追踪取代)/timeline(与速记同源重复)/
// sleep-week(睡眠不单独记,无数据生产者)——老页面残留 block 由 store.stripRetired 剔除。
// 2026-10-13 退役:followup(与「今日与回访」卡重合,全量回访并入 focus 卡双区)、
// reminder(与「前瞻」卡合并:认领 reminders 并入「记下的」区;add-reminder
// 写入链与 hot-context 对话侧不变,只是页面不再有独立卡)。
export const CARD_META = {
  'profile':        { group: 'builtin', name: '孩子档案',   desc: '小名/月龄/画像/当前重点一览', w: 6, h: 8 },
  'focus':          { group: 'builtin', name: '今日与回访', desc: '就医待办+到期回访+在途回访+在跑计划', w: 5, h: 6 },
  'issue':          { group: 'builtin', name: '问题追踪',   desc: '在管问题三色计数+病历详情(持续议题)', w: 6, h: 6 },
  'milestone':      { group: 'builtin', name: '里程碑',     desc: '发育盘点结果(按月龄档)', w: 6, h: 6 },
  'growth':         { group: 'builtin', name: '生长曲线',   desc: '身高体重记录对照参考区间', w: 6, h: 6 },
  'anticipatory':   { group: 'builtin', name: '前瞻',       desc: '记下的提醒+疫苗/体检/筛查/入园月龄时间线', w: 6, h: 5 },
  'strategy':       { group: 'builtin', name: '在跑计划',   desc: '习惯养成/启蒙路线状态追踪(试行中/已成日常/效果不佳)', w: 6, h: 6 },
  'note':           { group: 'builtin', name: '成长速记',   desc: '最近的事件笔记', w: 6, h: 5 },
  'text':           { group: 'custom', name: '文本卡',     desc: '标题+自由文本(奶奶须知/黑名单)', w: 4, h: 4 },
  'list':           { group: 'custom', name: '清单卡',     desc: '可勾选清单(出门清单/待办)', w: 4, h: 5 },
  'tracker':        { group: 'custom', name: '记录卡',     desc: '分组台账:状态+计数(绘本管理/用药记录/奖励表)', w: 6, h: 5 },
}

export function cardFor(type) {
  return REGISTRY[type] || ErrorCard
}
export function isCustom(type) {
  return CARD_META[type]?.group === 'custom'
}
