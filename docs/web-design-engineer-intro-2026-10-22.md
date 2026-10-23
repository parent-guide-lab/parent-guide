# web-design-engineer skill 引入说明与边界声明

> 2026-10-22 · 分支 `ui-garden` · 触发:用户对卡片内 UI 不满意,引入 [ConardLi/garden-skills](https://github.com/ConardLi/garden-skills) 的 web-design-engineer 作为改版方法论工具(MIT)。
> 性质:维护者工具引入 + 使用边界约定;**未动任何产品 UI 代码**(门禁补丁除外,见 §3)。

## 1. 它是什么

从 Claude Design 系统提示词提炼的设计工程 skill:SKILL.md + 8 份方法论文档(改版协议/失败模式清单/审查指南/五旋钮校准/方向库等)+ 25 套风格配方(Linear/Aesop/MUJI/Tufte/Bloomberg Terminal…)。核心能力:

- **Design Read + 五旋钮**(visual-variance/motion-intensity/information-density/asset-dependence/brand-fidelity):把设计意图变成可讨论的参数
- **改版协议**(`references/redesign-protocol.md`):对已有 UI 先分类 Extension / Preserve / Overhaul,审后改,保护契约不静默改
- **失败模式清单**(`references/failure-patterns.md`):AI 生成界面的俗套检测与修复(cardification/bento 无节奏/形状漂移/运营 UI 营销化…)
- **五维审查**(`references/critique-guide.md`):哲学对齐/视觉层级/工艺质量/功能性/原创性 0-10 打分

## 2. 安装与分发边界

- 安装位置:**用户级** `~/.zcode/skills/web-design-engineer/`(zcode 宿主)
- **不进本仓 `skills/` 分发体系、不进 publish 白名单**:本仓 `skills/` 三个 skill(parent-guide/audit-knowledge/distill)是随仓分发给家长用户的产品组件;web-design-engineer 是**维护者改版工具**,家长用户不需要也不该被路由到它
- 仓库内只保留本说明文档;skill 本体升级跟上游 garden-skills

## 3. 使用边界(硬约束)

本仓视觉方向已于 2026-10-06 用户拍板定稿(graph-paper 生长图纸,三选一 demo 流程)。对本 skill:

**模式锁定 = Preserve / Extension。** 设计系统宣告权在 `design-system.json` + 用户拍板,**禁止**在本仓内做 greenfield 风格宣告、用 25 套配方替换现有体系、或让 AI 重新选色选字体。若要改整体方向 = Overhaul,必须走 demo 先行三选一流程由用户拍板(判例:`demo/ui-2026-10/`)。

**允许使用:**

- Design Read 五旋钮:作为分析语言讨论现有 UI 与改版幅度
- failure-patterns + critique-guide:审查现有卡片/页面,产出 Preserve/Improve/Remove 清单
- 改版协议 Modernization Order:低风险杠杆顺序(先修层级与排版,再加动效,最后重构成块)
- style-recipes:仅作**灵感参照**读,其具体 token(色板/字体/圆角)不得直接落进 web/src

**禁止(机械层已拦的标 ※):**

- 新色彩函数 oklch()/oklab()/color-mix()/color() 落进卡片 style ※(`tests/check-card-style.sh` 规则 4b,2026-10-22 补——该 skill 主推 oklch 派生色,裸函数会绕过 hex/rgba 白名单)
- linear-gradient / 圆角 >12px / 卡头 emoji ※(门禁既有规则)
- 字阶白名单外的字号与 400/500/600/700 外的字重 ※(排版门禁)
- border-left 彩条+浅色底(blocks-spec 2026-10-10「太 AI 了」判例;skill 的 anti-cliché 清单与本条方向一致,互补)
- 引入 Inter/Roboto/system-ui 作 display 字体、替换 Georgia 数字体系(design-system.json 权威)

## 4. 与既有四层规范的关系

| 层 | 文件 | 与新 skill 的关系 |
|---|---|---|
| token 权威 | `design-system.json` | 宣告权所在,新 skill 不可覆盖 |
| 语义规范 | `skills/parent-guide/references/blocks-spec.md`「视觉与内容风格」节 | 卡片生产唯一规范,新 skill 是审查辅助不是替代 |
| 机械门禁 | `tests/check-card-style.sh` | 漂移护栏,oklch 漏点已随本次引入补上 |
| 排版全文 | `docs/typography-spec-2026-10-21.md` | 不变 |

## 5. 累计产出(2026-10-23 更新)

- 分支 `ui-garden`:oklch 门禁补丁 + 本文档 + 规范审核修复(2026-10-23:watch 色补落地/混合语法回写/blocks-spec 补卡内 emoji 禁令与签名件条款等)
- 卡片内 UI 审查与三项拍板落地(emoji 撤/变迁限流/日期混合语法):`demo/ui-card-garden-2026-10-22/` + a31918b
- 中改(结构签名)拍板并落地(速记头条/前瞻下一站):`demo/ui-card-mid-2026-10-22/` + 12b3bd0
- 大改三方向全页面 demo(A 纸间育儿/B 数据墨水/C 深夜诊室),用户看后搁置,A 备查:`demo/ui-overhaul-full-2026-10-22/`
