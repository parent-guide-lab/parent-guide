// 计算值全页扫(2026-11-11,tgl 字号失效三连修的制度化闭环)
// 静态门禁(check-card-style)查「代码里写的值」,查不出「实际渲染的值」——
// 声明顺序/特异性/继承链事故只有 computed 才暴露(tgl:写了 12.5px 实渲染 16px)。
// 本扫描遍历真实 DOM,凡计算字号/字重出字阶白名单即违规。
// 消费方:App.vue 探针(#style-sweep hash)+ tests/test-computed-style.sh。
const SIZES = new Set(['10.5px', '11.5px', '12.5px', '14px', '15px', '16px',
  '20px', '22px', '24px', '27px', '54px'])
const SVG_TEXT_SPECIAL = new Set(['6px'])   // 生长曲线刻度(门禁规则 5 同款特例)
const WEIGHTS = new Set(['400', '500', '600', '700'])
const SVG_SHAPE = new Set(['SVG', 'PATH', 'CIRCLE', 'RECT', 'LINE', 'G', 'DEFS', 'USE', 'DEFS'])

export function computedStyleSweep(root = document) {
  const bad = []
  const seen = new Set()
  for (const el of root.querySelectorAll('*')) {
    if (SVG_SHAPE.has(el.tagName)) continue          // 无文本图形不吃字号
    const cs = getComputedStyle(el)
    const size = cs.fontSize, w = cs.fontWeight
    const tag = el.tagName.toLowerCase() + (typeof el.className === 'string' && el.className
      ? '.' + el.className.trim().split(/\s+/).slice(0, 2).join('.') : '')
    const key = tag + '|' + size + '|' + w
    if (seen.has(key)) continue
    seen.add(key)
    const hasText = [...(el.childNodes || [])].some(n => n.nodeType === 3 && n.textContent.trim())
    if (!hasText && el.tagName !== 'text') continue  // 无文本容器不吃字号语义
    if (el.tagName === 'text' && SVG_TEXT_SPECIAL.has(size)) continue
    if (!SIZES.has(size)) bad.push(`字号 ${size} @ ${tag}`)
    if (!WEIGHTS.has(w)) bad.push(`字重 ${w} @ ${tag}`)
  }
  return bad
}
