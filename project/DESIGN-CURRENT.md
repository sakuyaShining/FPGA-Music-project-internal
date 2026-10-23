# 当前设计与接手导航

唯一已发布入口是仓库`FPGA-Music-project-internal`的实际远程`main`。仓库已由用户公开，名称中的internal不表示私有。待合并PR是候选，不自动成为main。

## 接手顺序

1. [PRODUCT-SPEC.md](PRODUCT-SPEC.md)：产品/制造目的、需求与实现差距、未冻结行为。
2. [SOURCE-MAP.md](SOURCE-MAP.md)：三个current目录、活跃owner源与历史资料的关系。
3. [ENGINEERING.md](ENGINEERING.md)：341项输入清单、依赖、隔离导出与验证入口。
4. [WORK-PLAN.md](WORK-PLAN.md)：音乐回归、硬件制造及后续功能的任务卡与完成条件；[OPEN-RULES.md](OPEN-RULES.md)列出尚需冻结的边界。
5. `decisions.json`、`corrections.json`、`governance.json`、`producers.json`：决定出处、旧说明勘误、审阅期限和活跃源边界。

## 当前已知状态

- `fpga/current/`保存253项候选输入，其中106项构建输入；七项专项、力度表及音高参考通过属于既有工程检查点验证。历史音乐黄金对照在cycle6662失败，后续分层/传感黄金项尚未由该fail-fast流程执行。旧PASS不覆盖当前失败。
- `tdm_ship_owned`默认关闭逐指表达和右手音色接口、保留16路旧pad；`layer_dispatch`仍限制最多两层。完整84节点/J10/编辑/存储/录放载板顶层未接成，未签收完整产品资源和时序。
- `hardware/current/`保存50项原生工程及上下文。e098施工版记录227器件、47项未连通/13网；非制造放行。另存aaa37历史基线不可混用。
- `host/current/`保存38项ca03 11版源码及依赖；100项离线通过不证明当前FPGA实物协议兼容。
- 原owner工作区后续修改不自动进入上述检查点；实时状态须按当前review和只读live检查判断。规格整理阶段未重跑RTL/PnR/板测/CAD；后续独立诊断另有来源与结果，不刷新旧验证日期。

原始验证见[工程检查点审阅](reviews/20261024-engineering-publication/review.json)。本轮规格审阅、直接用户原话及新增观察由`governance.json`指向；旧审阅不可覆盖。

后续隔离诊断已把compat/layers/sensor分别跑完，历史vscale=0配置对照均逐字节匹配旧黄金；当前默认旧判据下的差异和分层断言失败仍保留，详见MUSIC-GOLDEN-DIAGNOSIS.md。用户进一步确认D-019：曲谱与现场同等共享32组，空闲→松键尾音→最早按住音，整音符回收/完整起音；其细化并替代D-018严格FIFO，合同见NOTE-RESOURCE-CONTRACT.md。仍未完成完整曲谱/现场/四层产品接合。

## 防止旧设计回流

用户已取消J11实体音乐可视化屏，保留J10；RA8875仍为候选路线。核心演奏/编辑/保存不应依赖上位机。编辑键后选预设槽、编辑激发方式和音色、保留独立操作键有直接用户出处；这些不批准新GPIO表、16键扩展、功能裁剪或延期。

四层规则中的bank说明、编辑草稿完整性、衰减公式和旧小样采购问题，均以`corrections.json`的勘误及当前RTL为准。原作者材料保留原始字节，不改写历史以掩盖差异。

38/39/49号文档、v1/v2恢复归档、22项工作区保全、结构探针及根目录旧RTL继续用于对应版本的历史复现，不再作为当前工程的默认源码。后续用户决定通过证据及supersedes登记；不能据此自行削减32×16、四槽、逐音滑条、84节点、录放和非易失目标。

获取、pull和校验见[QUICKSTART.md](QUICKSTART.md)，跨会话交回见[MAINTAINING-MAIN.md](MAINTAINING-MAIN.md)。观察新源不会自动续期或签收产品。
