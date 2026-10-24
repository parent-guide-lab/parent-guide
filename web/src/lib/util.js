// Shared pure helpers (ported from demo render.html)
// (导出公共件是浏览器侧 DOM 操作,非纯函数——文件同时服务两种模式,保持单点)

import { domToPng } from 'modern-screenshot'

export function monthsAge(birthdate, on) {
  const b = new Date(birthdate), n = on ? new Date(on) : new Date()
  if (isNaN(b)) return 0
  return Math.max(0, (n.getFullYear() - b.getFullYear()) * 12 + n.getMonth() - b.getMonth())
}

export function nearestMilestone(m) {
  const steps = [18, 24, 30, 36, 48, 60]
  return steps.find(s => s >= m) || 60
}

export function clampInt(v, lo, hi, dflt) {
  const n = parseInt(v, 10)
  return Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : dflt
}

// MM-DD(按当年推断)或 YYYY-MM-DD -> 本地零点 Date;解析失败 null。
function parseDay(d) {
  if (!d) return null
  const full = String(d).match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  const short = String(d).match(/^(\d{1,2})-(\d{1,2})$/)
  if (full) return new Date(+full[1], +full[2] - 1, +full[3])
  if (short) return new Date(new Date().getFullYear(), +short[1] - 1, +short[2])
  return null
}

// Whole days since a MM-DD (treated as this year) or YYYY-MM-DD date.
// Negative (cross-year artifacts) clamps to null -> caller hides the badge.
export function daysSince(d) {
  const b = parseDay(d)
  if (!b || isNaN(b)) return null
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((today - b) / 86400000)
  return diff >= 0 ? diff : null
}

// 问题历时文案(卡行/病历层头/分享卡共用):在管=开题至今天;resolved=
// 开题至结案日——冻结,不再随时间增长。解析失败/倒挂回退「自 opened」。
export function issueDayNo(issue) {
  if (!issue) return ''
  let d = null
  if (issue.status === 'resolved' && issue.closed) {
    const a = parseDay(issue.opened), b = parseDay(issue.closed)
    if (a && b && !isNaN(a) && !isNaN(b)) {
      const diff = Math.round((b - a) / 86400000)
      if (diff >= 0) d = diff
    }
  } else {
    d = daysSince(issue.opened)
  }
  return d !== null ? `第 ${d + 1} 天` : `自 ${issue.opened}`
}

// MM-DD 或 YYYY-MM-DD -> { label, urgency } for due dates (cards, today-local).
// urgency: 'overdue' | 'today' | 'soon' (<=7d) | 'later'; null date -> neutral.
export function dueLabel(due) {
  if (!due) return { label: '', urgency: '' }
  const now = new Date()
  let d = null
  if (/^\d{4}-\d{2}-\d{2}$/.test(due)) d = new Date(due)
  else if (/^\d{1,2}-\d{1,2}$/.test(due)) {
    const [m, day] = due.split('-').map(Number)
    d = new Date(now.getFullYear(), m - 1, day)
  }
  if (!d || isNaN(d)) return { label: due, urgency: '' }
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  const diff = Math.round((d - today) / 86400000)
  if (diff < 0) return { label: diff === -1 ? '昨天到期' : `已到期 ${-diff} 天`, urgency: 'overdue' }
  if (diff === 0) return { label: '今天到期', urgency: 'today' }
  if (diff === 1) return { label: '明天', urgency: 'soon' }
  if (diff <= 7) return { label: `${diff} 天后`, urgency: 'soon' }
  return { label: `${diff} 天后`, urgency: 'later' }
}

// 完整日期显示(YYYY-MM-DD,用户拍板 2026-10-09 全局统一):MM-DD 补当年,
// ISO 原样;其他原样返回。与 IssueDetail/卡片/分享卡共用。逐段补零
// ("6-7"→"06-07",整串 padStart 会补出 "006-7")。
export function fullDate(d) {
  const s2 = String(d || '')
  let m = s2.match(/^(\d{4})-(\d{1,2})-(\d{1,2})$/)
  if (m) return `${m[1]}-${m[2].padStart(2, '0')}-${m[3].padStart(2, '0')}`
  m = s2.match(/^(\d{1,2})-(\d{1,2})$/)
  if (m) return `${new Date().getFullYear()}-${m[1].padStart(2, '0')}-${m[2].padStart(2, '0')}`
  return s2
}

// 排序键:due 字段现在 MM-DD(近程)与 YYYY-MM-DD(跨年节点,如 2027 入园)混存,
// 字符串 localeCompare 会排错;统一归一成可比较的完整日期串。
export function dueKey(d) {
  return fullDate(d)
}

// 中文语境标点归一(读侧机械转换,档案原文不动——中文文案排版指北口径):
// 排版规范 8b(2026-10-21 拍板):CJK 邻接的半角标点转全角,其余保持半角——
// 英文语境 "(AAP, 2019)" / "d=0.39" / "10-17" 原样,中文句读全角。CJK 判定含
// 汉字+中文标点+全角区,行内代码(`…`)整段跳过。
// 与 knowledge_render.cnpunct 同规则双实现(server 侧 md 渲染用 Python 版)。
// 旧 zhPunct(全量转 ,:;() 不转 ?!)2026-10-24 退役:与 8b 双规则并存时详情/速记
// 层留下「测试;问?叹!」半转残留(e2e 对抗档抓到),全项目归一为 cnpunct 单规则。
const _CN = '[\\u4e00-\\u9fff\\u3000-\\u303f\\uff00-\\uffef]'
const _PUNCT_FULL = { ',': '，', ':': '：', ';': '；', '!': '！', '?': '？', '(': '（', ')': '）' }
// 语法保护段:行内代码与 md 链接整体跳过(链接 ) 后跟中文若转全角会打断解析)
const _SYNTAX_SPAN = /(`[^`]*`|\[[^\]]*\]\([^)]*\))/g
export function cnpunct(s) {
  return String(s ?? '').split(_SYNTAX_SPAN).map((seg, i) => {
    if (i % 2 === 1) return seg
    // 三遍规则迭代到不动点:前一遍转出的全角字会制造新的 CJK 邻接对
    // (判例 `(停会员业务);A3`——`)` 转全角后 `）;` 才成立,单趟扫不到)
    for (let k = 0; k < 4; k++) {
      const next = seg
        .replace(new RegExp('(' + _CN + ')([,;:!?()])', 'g'), (m, c, p) => c + _PUNCT_FULL[p])
        .replace(new RegExp('([,;:!?()])(' + _CN + ')', 'g'), (m, p, c) => _PUNCT_FULL[p] + c)
        .replace(new RegExp('\\)(?=' + _CN + ')', 'g'), '）')
      if (next === seg) break
      seg = next
    }
    return seg
  }).join('')
}

// 详情正文分段:标点归一后按中文分号切段(NN Group 分段/列点证据);
// 段首「标签：」(<=8 字)由渲染层加粗——纯机械,不做语义判断。
// 内核=cnpunct(8b 单规则);半→全为等长替换,seg.slice(lab.length) 不受影响。
export function bodyParas(text) {
  return cnpunct(text).split('；').map(t => t.trim()).filter(Boolean)
}
export function segLabel(seg) {
  const m = cnpunct(seg).match(/^([^：]{1,8})：/)
  return m ? m[1] + '：' : ''
}

// ── 知识引用自动链接 ─────────────────────────────────────────────
// 官方库 17 文件 → 知识子站同名页(tantrum-cdc→tantrum 是唯一非同名映射);
// 白名单与 tests/check-knowledge.sh 的清单同步维护,未知 .md 保持纯文本
// (fail-soft:自建层 knowledge/user/ 或笔误不产生死链)。
const KB_PAGES = new Set(['milestones', 'sleep', 'nutrition', 'emotion', 'activities',
  'anticipatory', 'weaning', 'toilet', 'growth', 'child-mind', 'eczema', 'newborn',
  'screen', 'toys', 'fears', 'books'])
const KB_REMAP = { 'tantrum-cdc': 'tantrum' }
export function escHtml(s) {
  return String(s ?? '').replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;')
}
const KB_LINK_RE = /([a-z-]+\.md)( ?§\d+)?/g
// 对已生成的 HTML 转链(不转义):知识库面板里 server 渲染的自建文档走这里,
// 纯文本先 escHtml 再进来。白名单与 tests/check-knowledge.sh 清单同步维护。
export function linkifyHtml(html) {
  return String(html ?? '').replace(KB_LINK_RE, (m, file, sec) => {
    const base = file.slice(0, -3)
    const page = KB_REMAP[base] || (KB_PAGES.has(base) ? base : null)
    return page
      ? `<a class="klink" href="site/${page}.html" target="_blank" rel="noopener">${file}${sec || ''}</a>`
      : m
  })
}
// 渲染层统一转链:后续数据文本里新增的知识引用(含 §节号)零改动自动生效。
export function linkKnowledge(text) {
  return linkifyHtml(escHtml(text))
}

// -- 长图导出公共件(App 页级双版 / ShareModal 卡级双版共用) ----------------
// 截至日期角标:时点快照必带(2026-10-01 分享调研 §3 判例)。挂到截取节点
// 内(目标需 position:relative),截完由调用方 remove。
export function stampEl(text) {
  const el = document.createElement('div')
  el.className = 'cap-stamp'
  el.textContent = text
  return el
}
// 生成 PNG 并保存为文件。导出=保存图片(2026-10-22 用户拍板):不唤起
// navigator.share 系统分享面板——要转发由用户从保存的文件自行发起
export async function exportPng(node, fname, bg = '#fdfdfb') {
  const url = await domToPng(node, { scale: 2, backgroundColor: bg })
  const blob = await (await fetch(url)).blob()
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = fname
  a.click()
  URL.revokeObjectURL(a.href)
}
