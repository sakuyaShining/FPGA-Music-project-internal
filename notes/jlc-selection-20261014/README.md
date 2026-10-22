# 嘉立创选型调研证据

此目录从2026-10-14开始建立，后续纯滑条选型继续复用。不是可提交制造的PCB目录。

- `reference/easyeda-api-SKILL.md`：GitHub获取的官方1.1.52技能文本，与已安装文件SHA256相同。
- `easyeda-api-official.zip`：官方下载备用入口提供的旧1.0.3包；不作为当前安装版本，SHA256 `cf2a25de2400678a16d390a2e83f038da190d77b6682b70c72e0bc5e89de1418`。
- `reference/official-zip-SKILL.md`：旧ZIP的技能文本，用于区分版本。
- `reference/lcsc-sourcing-SKILL.md`：社区选型技能来源文本。
- `reference/lceda-cli-for-ai.md`：官方AI CLI指南本地参考，源URL `https://prodocs.lceda.cn/storage/texts/api/guide/cli-for-ai.md`。
- `query_lcsc_checked.py`：只读目录检索和精确型号身份过滤，须Python≥3.10及已安装lcsc skill。
- `evidence/AD7147-community-identity-check.json`：真实查询返回电容，被身份过滤器拒绝；保留失败结果，不把搜索成功当成选型成功。

已安装官方skill：`C:/Users/Sakuya/.codex/skills/easyeda-api`，1.1.52；社区skill：`C:/Users/Sakuya/.codex/skills/lcsc`。客户端未安装/未连接，不宣称已完成EDA原理图/PCB/DRC。国内报价未取得。

当前设计入口：`docs/02-技术方案/46-嘉立创AI选型与PCB制造工作流-2026-10-15.md`及`47-纯滑条音高演奏三方案与制造边界-2026-10-15.md`。
