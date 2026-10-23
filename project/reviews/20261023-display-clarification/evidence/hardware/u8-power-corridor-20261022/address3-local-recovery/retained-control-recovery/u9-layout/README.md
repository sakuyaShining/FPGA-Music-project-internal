
## 2026-10-23T13:18:14.782062+08:00：固定布局试算终态，转联合邻近控制区域

原生源仍40c8175b…，54项/14网、227件602孔；PRESET0/PRESET3及已恢复供电保持，不是本轮新增成果。ENC_A三层与四铜层图搜索均得到约319.73mm绕行，未导入，均终态；四铜层选项没有实际使用Inner15，也没有证明更好的路线。禁止重复这些作业。

已完成 control-joint-layout-screen.json 的新布局初筛：U9=74/42mm90°、C9=72/36.25mm0°；C8=58.75/52mm180°、R63=66/52.75mm90°、R64=62.25/52.75mm90°、TP13=67.5/52、TP14=60.75/53.25、TP15=68.5/69。初始C8/U8包络、C9/RC_DRIVE、TP13及下拉电阻/5V铜冲突已通过候选位置调整消除，未动实物源。最新初筛的包络/焊盘冲突及范围外铜冲突为零；仍有36条按新器件分别统计的控制/供电/地铜冲突须恢复。这个数字不是剩余飞线，也不代表布通。

下一步唯一入口 construction-state.json.next_action：先准备C8/R63/R64及3个独立测试PAD的完整联合恢复批次，保持当前U9/C9/P0/P3，解除未来U9位置占用；新TP14/R64位置涉及BUS_SCK线f3a6405ac4b283d9和孔1a1cee6c2ae8b608，须联合恢复时钟。完整路线、实际新参考地、去耦回路、原生courtyard均尚未通过，不能直接导入八器件候选。TP13/14/15是独立PAD，验证器必须精确核对声明的PAD变换，不能忽略非铜差异。保护47供电脚、共享母线及RC/传感/音频，禁止为了开路删除共享电源主干。

所有任务终态，无路由进程；当前自有CAD会话路径/PCB UUID/哈希已复核。原生恢复包及aaa37回退包未改。浏览器读取官方屏目录尝试因本地运行时资源路径缺失失败，没有创建页面、没有核实新报价。硬件选型未定、所有实物UNMEASURED；继续自动唤醒。

# U9/C9 区域施工唯一入口

更新 2026-10-23T12:40:06.993712+08:00。原aaa62f2/37项6网基线及完整恢复包不变。**当前是区域施工副本，尚未晋升，不可投板。**

工程：C:\Users\Sakuya\Documents\LCEDA-Pro\projects\FPGA-Music-U9ControlWork-20261023
PCB SHA256：40c8175b3ae31124bf9f915025de8c0ae9ffef524acbb04ba40d1e11df0eb9a2
会话：779175c3-353c-48b8-b5df-826ebf4e3b9f；项目UUID：6b570f10a9004c2a7374c39b14185fbbe64449a767876fe377667e630fc1e3c7。先查真实session/process及文件哈希，所有本批作业已终态，无后台路由。

四层重铺、保存关闭重开严格DRC：0间距/0物理/0网表，54项未连通/14网，227件602孔。PRESET0整网真实闭合：U9.14、R53.2、SW2.1/2处于同一实铜岛并退出原生错误表。施工58→54；仍有本次拆线的9个控制网未恢复，不能宣称本施工版已优于原37版整板。

PRESET0新增19条6mil线、4信号孔及1地孔。完整目标铜岛方法可结束在所属岛的焊盘/铜端点/过孔，修复了固定单焊盘目标导致的无效搜索。首次实际重铺发现一个既有Ground孔3d54fb770b69bfa2的Ground16接触0.1484766mm²，导致Top/Bottom换层所需合格回流距离2.203mm，不通过。已将两段新PRESET0 Inner16线共同折点移动+0.05/-0.10mm；重新四层重铺及保存重开后，Ground16实际接触0.1669281mm²，Ground15/2约0.16756mm²，实际回流恢复0.809514mm。未降低0.15偏好或1.5mm回流门，也未添加备选的额外地孔。失败包control-next-return-loss-native.zip保留，备选return-repair.json已禁止导入。

最终428项当前几何/实际铺铜参考比较无新增退化；所有声明新增线全宽最近参考缺口0，新增孔四层铜/孔焊盘间距及实际参考/回流检查通过。完整实际铜对账、899节点、52外部接口焊盘及非铜属性保持。继承参考缺口及低活动复位Ground2约6.110mm例外仍开放；RC_DRIVE旧地孔Ground16接触0.1474mm²偏好缺口如实保留。以上不代表整板SI/PI或实物功能通过。

U9=91/19mm180°，C9=99.25/16mm0°，R30=68.4/65.6mm90°。其他非铜属性严格一致；旧C9=97.75位置被器件包络检查否决，不可回退。3V3_IO全部47供电脚、地、PRESET3、HARM片选及触控复位保持闭合。产品RTL/原理图/BOM未改，旧CPL这三行无效。

Resume this same native U9ControlWork project, current40c8175b/54 connection errors/14nets/602vias. PRESET0 whole net now restored and accepted; never rerun it. No active routing/native jobs. Next restore ENC_A using actual current copper and whole connected target-island goals, then remaining9 controls before promotion over aaa37. Router control-recovery.py route ENC_A --three-layers uses current source/review guard and writes a new control-next-plan; geometric_pass remains false until coupled four-layer/holes/pads/reference/returns preflight. Reviewer control-branches-review.py next now retains every accepted_control_plans batch, including PRESET0, and checks their actual full-width references, continuity and returns in later changes. PRESET2 fixed-target and392/445mm whole-island detours are terminal NOT imported; do not tune fixed-layout search again. Its next attempt must jointly change actual adjacent DISP_MOSI/PDN corridor while restoring those networks and real reference Ground. Then BUS_MOSI/R64/TP14 and ADDR0/1/2/MUX_DISABLE. Preserve oldaaa37/b766 recoveries, exact R30/U9/C9 poses, RC/audio,47IO supply pads,52 externalpads and899nodes. All physical testsUNMEASURED; no fab release.

仍需恢复9控制：BUS_SCK, INPUT_LOAD_N, KEY_QH, ENC_A, ENC_B, ENC_PUSH, PRESET1, PRESET2, EDIT。PRESET1远端仍两岛，其余已恢复远端支路但U9主链接未全部闭合。原5个BUS_MOSI/ADDR0/1/2/MUX_DISABLE目标仍开放。PRESET2固定焊盘两/三层失败及392/445mm全板绕行候选均终态不导入，不能反复试相同布局。

恢复包construction-native-NOT-FOR-FAB.zip含本版19原生文件及本说明；manifest核验全部文件SHA/CRC。control-branches-source-native.zip保留b766/58阶段，control-source-native.zip保留adb/67阶段，pdn-source-native.zip保留PDN阶段，原aaa37包../native-touch-reset-WORK-IN-PROGRESS.zip保持f28dab61不变。当前证据control-PRESET0-native-review.json、construction-state/capture/drc及control-PRESET0-plan.json；旧regional/three-component报告为历史，当前精确非铜核验以本版review为准。

保留屏正确V4接口图原始URL已定位，但完整原厂文档访问仍403，索引中的旧FT5206标注与目录FT5316须区分；不能用索引基础价当配置整价/交期或锁定供货。最终硬件选型尚未完成，没有可下单制造包，实物测试始终UNMEASURED，不下单付款外发。PCB完整定稿与最终硬件选型均落定后才关闭自动唤醒。
