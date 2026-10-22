# 整机候选接口与BOM

状态：**讨论中**，供接合审阅，不用于直接接线、采购或制造放行。

详见[60号整机选型收尾](../../docs/02-技术方案/60-整机选型收尾与真实排针核对-2026-10-15.md)。

- `nano-header-candidate.csv`：17根GPIO的FPGA封装脚与真实Nano J5/J6位置；板版号、LED负载与信号完整性未实测。
- `shift595-candidate.csv`：8个锁存输出的新职责；Q6/Q7仍在既有原型中为NC，尚未实施。
- `waveshare-30896-interface.csv`：具体F款13针接口，5V电源/3.3V逻辑；不通用于其他微雪屏。
- `electrodes-25-slot-example.csv`、`electrodes-26-slot-example.csv`：6路、每路14感测地址的无冲突分配例；八度5节点、3电极/音位、参考值和几何未冻结。
- `system-bom-candidate.csv`：28行范围清单，ESD两个型号互斥，含原型专用项和待明确机械/制造/供电；空白报价不得计成0元。不能直接导入下单。
- `audit.json`：检查范围、已知事实与未完成项。标为true的检查仅覆盖表内静态条件，不代表电气/时序/完整产品已验证。
- `manifest.json`：交付及`notes/hardware-closeout-20261015/`资料、脚本和原生查询的哈希。

用户补充当前原型喇叭4Ω/3W；已有显示模块实物引脚暂不清楚。17脚方案复用LED0～5，保留音频、TF和USB调试；原音乐引擎及小样图纸未修改。
