// Anticipatory guidance node table -- mechanical mirror of
// knowledge/anticipatory.md (audited 2026-09-29; vaccine schedule re-audited
// against the 2026 NIP program 2026-10-09; 发育盘点 windows added 2026-10-05).
// HUMAN-READABLE SOURCE: knowledge/anticipatory.md -- keep the two in sync.
// Scope guard: only the reminder nodes audited there live here. Earlier NIP
// doses (<18m) stay in the vaccination booklet by design -- do NOT add
// unaudited medical content to this table.
import { monthsAge } from './util.js'

// 疫苗提醒节点(2026 版免疫程序口径,提前 1 月提示)
const VACCINES = [
  { id: 'v18', name: '18 月龄疫苗', month: 18, note: '百白破第 4 剂 · 麻腮风第 2 剂 · 甲肝' },
  { id: 'v24', name: '2 岁疫苗', month: 24, note: '乙脑减毒第 2 剂' },
  { id: 'v36', name: '3 岁疫苗', month: 36, note: 'A 群 C 群流脑多糖第 1 剂' },
  { id: 'v48', name: '4 岁疫苗', month: 48, note: '脊灰第 4 剂' },
  { id: 'v72', name: '6 岁疫苗', month: 72, note: '百白破第 5 剂 · A+C 流脑第 2 剂' },
]
// 儿保体检:1-3 岁每半年 / 3 岁后每年(1 岁内频次以儿保预约为准)
const CHECKUP_MONTHS = [12, 18, 24, 30, 36, 48, 60, 72]
// 发育盘点检查点窗口(错过不追赶,顺延下一档;可与当次儿保合并)
const DEV_MONTHS = [24, 30, 36, 48, 60]

const addMonths = (date, m) => {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate())
  return new Date(d.getFullYear(), d.getMonth() + m, d.getDate())
}
const ymd = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

const monthRow = (birth, id, kind, name, month, lead, note) => {
  const due = addMonths(birth, month)
  return { id, kind, name, note, due: ymd(due), start: ymd(addMonths(due, -lead)) }
}

// 流感疫苗(年度):9-10 月最佳,整个流行季(9 月-次年 3 月)可补种
function fluRow(today) {
  const y = today.getFullYear(), m = today.getMonth() + 1
  const inSeason = m >= 9 || m <= 3
  const due = inSeason && m <= 3 ? new Date(y, 2, 31) : new Date(y, 9, 31)
  const start = inSeason && m <= 3 ? new Date(y - 1, 8, 1) : new Date(y, 8, 1)
  return { id: 'flu', kind: '季节', name: '流感疫苗(年度)',
    note: '≥6 月龄每年一剂;6 月龄-9 岁以下首种 2 剂间隔 ≥4 周;9-10 月最佳',
    due: ymd(due), start: ymd(start) }
}

// 入园主观节点:档案 profile.childcarePlan({type,age,note} | '未定' | '不送' | 空)
function childcareRows(kid, birth, ageM) {
  const plan = kid?.profile?.childcarePlan
  let target = null, label = '幼儿园'
  if (plan && typeof plan === 'object') {
    const a = parseInt(plan.age, 10)
    if (Number.isFinite(a)) { target = a; label = plan.type || label }
  } else if (typeof plan === 'string') {
    if (plan.includes('不送')) return []
    // set-profile 把 profile 字段一律当字符串写入,childcarePlan 落盘形态
    // 常是「{type: 幼儿园, age: 42, note: …}」dict 字面量——「N 月」文本
    // 匹配不到时再从 age 键机械提取月龄(2026-10-21 实测入园节点因它全缺)
    const m = plan.match(/(\d+)\s*月/) || plan.match(/age["':\s]+(\d+)/i)
    if (m) { target = +m[1]; label = plan.includes('托') ? '托班' : label }
  }
  if (target !== null) {
    return [
      monthRow(birth, 'k-enroll', '报名', `${label}报名了解`, Math.max(1, target - 6), 0,
        '各地报名常提前 3-6 个月;了解本地政策与园所'),
      monthRow(birth, 'k-prep', '准备', '入园适应准备', Math.max(1, target - 2), 1,
        '作息前移 · 自主进食 · 如厕表达 · 分离练习'),
      monthRow(birth, 'k-mat', '材料', '入园材料清单', Math.max(1, target - 1), 0,
        '体检报告 · 疫苗查验证明等(以园所要求为准)'),
      monthRow(birth, 'k-go', '节点', `${label}入园`, target, 0, ''),
    ]
  }
  // 未定/空 + ≥30 月:提醒做决定本身就是价值(立即提,无固定日期)
  const undecided = !plan || plan === '未定'
    || (typeof plan === 'object' && !Number.isFinite(parseInt(plan.age, 10)))
  if (undecided && ageM >= 30)
    return [{ id: 'k-think', kind: '报名', name: '该想想托班/幼儿园的安排了',
      note: '各地报名常提前 3-6 个月,错过等一年', due: '', start: '', status: 'active' }]
  return []
}

// 主入口:全部节点(进行中/接下来/已过),由出生日期+日历机械推导,不造语义
export function anticipatoryNodes(kid, now = new Date()) {
  const birth = kid?.birthdate ? new Date(kid.birthdate) : null
  if (!birth || isNaN(birth)) return []
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const ageM = monthsAge(kid.birthdate, now)
  const rows = []
  const add = (r) => {
    if (!r.status) {
      const due = r.due ? new Date(r.due) : null
      const start = r.start ? new Date(r.start) : null
      r.status = !due ? 'active' : today > due ? 'past' : today >= start ? 'active' : 'upcoming'
    }
    rows.push(r)
  }
  for (const v of VACCINES) add(monthRow(birth, v.id, '疫苗', v.name, v.month, 1, v.note))
  const nextCheck = CHECKUP_MONTHS.find(m => m > ageM)
  if (nextCheck) add(monthRow(birth, 'checkup', '体检', '儿保体检', nextCheck, 0,
    '1-3 岁每半年,3 岁后每年;1 岁内按儿保预约'))
  add(monthRow(birth, 'dental', '筛查', '口腔首检', 12, 0, '第一颗牙萌出 6 个月内,或不晚于 1 岁'))
  add(monthRow(birth, 'vision', '筛查', '视力表筛查', 36, 0, '0-6 岁眼保健随儿保;3 岁起加视力表筛查'))
  const nextDev = DEV_MONTHS.find(m => m > ageM)
  if (nextDev) add(monthRow(birth, 'dev', '盘点', '发育盘点', nextDev, 0,
    '对照 CDC 检查表;可与当次儿保合并;错过顺延下一档'))
  if (ageM >= 6) add(fluRow(today))
  for (const r of childcareRows(kid, birth, ageM)) add(r)
  return rows
}
