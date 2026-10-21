# parent-guide skill 本体

M4 在此实现(当前为骨架):
- `SKILL.md`(~150 行内:导语判断层 / 分档启动协议 / 压缩路由表 / 红线判例)
- `references/`(templates.md / conversation.md / knowledge-index.md 最小知识核 / blocks-spec.md / cases/)
- `scripts/hot-context.sh`(状态热区,路径参数化)
- `scripts/daily-tips.sh`(daily 档:每日贴士候选信号机械抽取+record 去重记录;编排规则 references/daily.md)
- `scripts/feishu-tip.py`(每日贴士飞书推送:webhook 惰性读取,配置缺失只影响推送不影响生成)
- `scripts/audit-citations.sh`(引用对账:悬空来源/悬空文件/无来源医学断言,机械审计)
- `data-templates/`(child.json 档案模板 + page.json 默认配置)

## 每日贴士(daily 档)

- **手动触发(零配置)**:对话里说「今日贴士」——从回访到期、策略执行、
  发育阶段、当日活动里按克制规则(≤3 条、主推 1)编排当日卡;信号抽取走
  `scripts/daily-tips.sh`,编排规则见 `references/daily.md`。
- **定时(可选,看宿主)**:宿主支持定时任务(如 ZCode 自动化)可每天早上
  自动生成并落去重记录;不支持的宿主每天手动问一句,效果相同。
- **飞书推送(可选)**:群 → 设置 → 群机器人 → 添加「自定义机器人」,把
  webhook 地址整行存入 `~/.config/feishu/webhook_url`;`scripts/feishu-tip.py`
  会把当日卡推成飞书互动卡片。配置是本机文件,仓库不含任何凭证。
- 去重台账在 `data/daily-tips.json`(同 key 7 天不复现);建档收尾会一次性
  告知本功能(认领制,见 conversation.md §0 第 5c 步)。

跨平台子集约束见 docs/specs/product-spec-v1.md §6。
