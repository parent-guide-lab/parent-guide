# parent-guide 产品规格 v2

> 日期:2026-10-14 | 状态:现状收敛稿
> 本文档是产品当前形态的唯一执行口径;与 HANDOFF 追加节/git 提交信息冲突时以本文为准。
> v1(docs/specs/product-spec-v1.md)已归档,仅存 M0-M7 启动期范围;本文收敛其后的全部演进
> (问题追踪/知识质量线/前瞻指导/卡片体系重构/画像版本化/应用内知识库/分发定位修正)。

## 1. 产品定位

开源的循证育儿顾问:一个跑在用户自配 AI 助手里的 skill 家族 + 中文循证知识库 + 本地页面。
零云端、零账号、零遥测,孩子数据只存在用户本地 `data/` 目录。适用 0-5 岁(学龄仅睡眠口径
与就医红线)。继承自 v1 的定位不变;变化在分发与形态收敛(见 §3、§5-§8)。

## 2. 产品组成(五层资产)

| 层 | 内容 | 载体 |
|----|------|------|
| skill 家族 | parent-guide(家长问答)/ audit-knowledge(知识审计)/ distill(蒸馏入库) | `skills/` |
| 知识库 | 官方闭集 20 专题+速查(五域分组)/用户自建层 `knowledge/user/` | `knowledge/` + `site-src/quickref.md` |
| 本地页面 | Vue3 单文件产物 + 零依赖 Python 服务(REST 读写/静态托管/知识 API) | `web/` + `server.py` |
| 静态站点 | 知识库可浏览页面,与本地 `/site` 同源 | `site/`(构建产物) |
| 分发面 | 源码仓(org 公开)+ 官网独立仓(landing+知识子站) | 见 §3 |

## 3. 分发定位(2026-10-14 拍板)

- **GitHub 开源**:`parent-guide-lab/parent-guide`(org 公开仓,README 为入口);
- **使用场景**:Claude Code / zcode / dsh 等支持 Agent Skills 的宿主(README 宿主表为权威口径);
- **待出**:各宿主的安装与上手指引(README 路线图末条);
- **废止**:早期「群文件 zip 交付 / OpenClaw 承接国内普通家长」叙事,不再作为漏斗假设;
- 官网 `parent-guide-site`(独立公开仓)= landing + 知识子站 19 页镜像,与源码仓命运解耦。

## 4. 数据契约(单一规则:用户本地 `data/child.json`)

结构(`check` 子命令为形状权威,写入一律走 `update-child.py`):

| 区 | 内容 | 备注 |
|----|------|------|
| `profile` | 13 白名单字段:gender/caregivers/language/temperament/comfortObject/familyNotes/childcarePlan/allergies/siblings/healthNotes/preferences.books/preferences.activities/sleep.note | `_asOf[field]`=核实时间;`profileHistory[]`=set-profile 改值自动留档;超 183 天未核实热区机械提示 |
| `currentFocus` | 当前关注(整组覆盖) | 热区第一行 |
| `notes` | 事件速记(tags 多标签/可选 title 与 time) | 最高频写入区,时间轴数据源 |
| `issues` | 问题一等实体(P<N>:status active/watching/resolved,brief{what,why,how,redline,sources},pendingCare) | 时间线=notes/strategies/followups 按 `issues` 外键聚合,不设独立 events 数组 |
| `insights` | 孩子特点洞察一等实体(I<N>:status active/superseded/expired,statement 假设级[定性词黑名单机械拒],anchors ≥1 观察锚,window 月龄窗[发育性过期]) | 依据档恒【推断】;**提议-人审**:propose→家长确认才落档;过窗热区提示重验(2026-11-11,conversation.md §2.9);台账 `data/insights-log.jsonl` 只计量非知识源 |
| `strategies` | L2 计划(六状态) | 可挂 issues |
| `followups` | 回访(due/topic/status pending/done/skipped) | 可挂 issues |
| `reminders` | 认领的前瞻提醒(YYYY-MM-DD 跨年保年份) | |
| `milestones` | L3 盘点(按月龄档,assessed) | |
| `growth` | 身高体重记录(records[]) | 对照 WS/T 423-2022,读侧判带 |
| `sleep` | sleep.note 概况字段 | 不逐日记录(2026-10-01 拍板) |

写入纪律:三步门(读热区→Run 脚本→引脚本输出为证);`activeConcerns`/`severity` 类结构化
已废弃——**结构化只给机械操作,语义归一留读侧**(全项目铁律)。写入动作全集 24 个
(add-note/set-profile[--verify]/set-milestone/add-issue/set-issue-brief/link-issue/
add-strategy/add-followup/add-growth/add-reminder/set-focus/mark-revisited/
set-note-time/set-note-title/set-status/set-issue-status/set-reminder-status/
set-followup-status/propose-insight/confirm-insight/reject-insight/review-insight/
insight-stats/check/init,以 `update-child.py --help` 为准)。

## 5. skill 协议体系(parent-guide)

- **分档启动**:L1 紧急(≤150 字动作卡)/ E 评估(口径判定→孩子的逻辑→三选菜单)/
  L2 计划(含孩子的逻辑节)/ L3 发育观察 / guide 日常;通用育儿知识问句也走本口径。
- **依据随行**:断言双轴=T 级(T1 就医红线/T2 建议评估/T3 居家)+依据四档
  (【机构】【研究】【综述】【推断】,推断必带区分信号);原始出处优先,库内文件不作引用终点。
- **调研七步**(缺口/质疑调研必走):问题定形→层级检索→≥2 独立来源→停止三条件→
  矛盾并陈→外推降档→链接探活;分层沉淀:锚点→用户自建层→官方晋升(人审)。
- **孩子的逻辑**:行为问题出假设菜单(可能性排序+区分信号),需求语言禁临床词,只假设不断言。
- **画像保鲜**:语义相关即触发核实;`--verify` 对过即刷 `_asOf`;静默≠过期。
- **写入/分享**:写入三步门;家人分享卡去黑话、纯文本、必带截至日期。
- 红线判例带日期累积于 SKILL.md,dogfooding 真实失败是判例唯一来源。

## 6. 页面体系(七卡终态,blocks-spec.md 为 AI 修改契约)

- **内置功能卡 7 型**:profile(档案)/ focus(今日与回访)/ issue(问题,病历级详情层)/
  milestone(里程碑)/ growth(生长曲线+滑档预警)/ anticipatory(前瞻:记下的+节点表)/
  note(成长速记);**自定义卡 2 型**:text/list(唯一创建路径=对话,AI 按 blocks-spec 改 page.json)。
- **退役卡型**(已删组件,RETIRED_TYPES 静默剔除老布局):strategy-effect/timeline/
  sleep-week/followup/reminder——合并入 issue/focus/anticipatory,职责不丢。
- 页面只做视图:内容生产全归对话;编辑入口两件(卡片管理/编辑布局),JSON 直改与整页重置
  无 UI 通道;导出=长图(所见即所得)/PDF/单文件网页。
- **知识库独立页**:官方库(页内直读,五域分组+速查置顶)/我的自建(server 三层白名单,
  自建私密永不出本地);引用自动转链至 site 同名页。

## 7. 知识体系

- 官方闭集=knowledge/ 根目录 20 篇:健康与身体(4)/喂养与睡眠(2)/习惯与界限(4)/
  情绪与行为(5)/发育与玩耍(4)/参考(1)+速查置顶(site-src/quickref.md,与
  knowledge-index §2 同源双侧同步);新专题入库四件套+定组必填(组闭集在 check-knowledge)。
- 用户自建层 knowledge/user/:三要素头标「自建」,publish 永不分发。
- 质量线:BACKLOG 缺口记录(人审队列)/ 引用对账(audit-citations,--anchor 锚点校验)/
  审计 SOP+LOG(轮转深审)/ 蒸馏 SOP(结构性安全:先决定什么不装)。
- 全量表分工:growth-ref.js(0-78 月内置曲线)与 growth.md(关键节点)防双表漂移,
  check-growth-ref 机械锁定。

## 8. 质量门与验收

- **八项门禁**(commit 前全绿):check-knowledge / check-bundle / check-card-style /
  check-growth-ref / test-hot-context / test-update-child / test_server / test-audit-citations。
- **publish.sh 七步**:对账→staging swap→跑测试→泄漏 guard→commit→镜像 site 仓→
  (--push)推两公开仓;日常一条命令 `bash scripts/publish.sh --push`。
- **验收方法**:15 题验收集+压力测试集(spec 级,回归用);新功能=虚构档案沙箱+裸跑
  subagent 行为级验收;UI 改动=demo 对比页先行、用户拍板后落地。

## 9. 合规红线(继承 v1,不变)

- 不架公共在线服务/API/公共 demo(生成式 AI 备案边界;server 仅本地 127.0.0.1)。
- 用户真实数据绝不入仓库(.gitignore + publish 泄漏 guard 双保险)。
- README 重要声明:育儿参考非医疗建议;CDC 内容公有领域中文化、不暗示背书;AIGC 声明。
- 许可证:代码 MIT,knowledge/ 内容 CC BY 4.0。

## 10. 非目标(当前明确不做)

1. 多孩档案(单 child.json 单孩;README 已如实说明,二胎家庭为已知边界)。
2. 主动推送/提醒服务(本地优先哲学,回访靠对话与页面消费)。
3. 疫苗记录(对分析无增益,2026-10-13 拍板);用药剂量预置库(以「用药剂量应答纪律」
   零数字方案替代)。
4. Phase B(MCP server)与 Phase C(独立应用)。
5. 付费/订阅体系(语料已全量开源,open core 三层变现设计废止,2026-10-14)。
6. insights 卡片化(InsightCard/分享过滤/热区条数上限/daily-tips 消费):洞察回路
   2026-11-11 v1 走对话与热区消费,卡片化等真实洞察量起量再做;**web 端当前不渲染
   insights 属设计而非遗漏**,卡片化时必须带分享过滤(conversation.md §2.9 第 7 条)。
