//=============================================================================
// note_map.v —— 音符映射：把【音符事件】展开成【时隙装载序列】
//
// 【它解决的问题】
//   tdm_engine 只认"往第 k 个时隙写 inc/amp/gate/epar"这一层。
//   但乐器收到的是"按下 MIDI 60，力度 100"。
//   本模块就是这两者之间的那一层 —— 也是"从引擎到乐器"的最后一块 FPGA 逻辑。
//
// 【时隙怎么分给音符】
//   固定分组：音符组 g 占时隙 [g*P, g*P+P-1]（P = 每组泛音数）。
//   NG 个组 × P 个泛音 = NG*P = NSLOT 个时隙。
//   选固定分组而不是动态池的理由：确定、可验证、时隙归属无歧义
//   —— 这正好满足赛题"频谱可观测对应数量独立谱峰"的现场验证要求。
//
// 【音符 --> 频率】
//   128 项 ROM（note_inc.hex）：MIDI 音符号 → 24 位相位增量。
//   用 ROM 而不是现场算 2^((n-69)/12)：精确、无近似、只占 3 Kbit。
//
// 【泛音比 --> 每个泛音的 inc】
//   preset_part.hex 给每个泛音一个 Q8 定点频率比：
//       inc_partial = (inc_note * ratio_q8) >> 8
//   谐波（比 = 整数）用 Q8 表示是精确的（1.0=256、2.0=512…）；
//   非谐（钟 2.76、马林巴 4.0）也能表，精度 1/256 足够。
//   为什么这里必须用乘法：泛音比是"每音色一份"、音符是"每次演奏一个"，
//     乘积无法预先查表（128 音 × 16 泛音 × 4 音色 = 8192 项）。
//     一个共享乘法器在装载时算，一个音符只需 P 次。
//
// 【门控语义】
//   音符开 → 该组 P 个时隙写 gate=1；音符关 → 写 gate=0。
//   因为走的是 tdm_engine 的 load_* 通路，自动获得【样本边界对齐】语义
//   （2026-10-01 加入）—— 同一次音符事件对所有泛音原子生效。
//
// 【复音管理】
//   音符开：优先找已在奏同一音符号的组（重触发）→ 再找空闲组 → 都没有就抢占
//           （round-robin 指针指向的组，最老的那个）。
//   音符关：找在奏该音符号的组，写 gate=0（进入释放段，不是硬停）。
//=============================================================================

`timescale 1ns/1ps

module note_map_reference #(
    parameter NG      = 32,             // 音符组数（= 最大复音数）
    parameter P       = 16,             // 每组的泛音数
    parameter PHASE_W = 24,
    parameter AMP_W   = 8,
    parameter NB      = 7,              // 音符号位宽（0..127）
    parameter NPRE    = 4,              // 音色预设数
    // 滑音（portamento）：默认关。关时每次 note_on 都写 gq=0（清残余），
    //   与"没有这个功能"的旧行为等价。
    parameter GLIDE_EN = 1'b0,
    parameter SPEC_STAGED = 0,
    parameter OWNED_EVENTS = 0,
    parameter OWNER_W = 13
)(
    input  wire                clk,
    input  wire                rst_n,

    //---- 音符事件（一个脉冲一个事件）----
    input  wire                ev_valid,
    input  wire                ev_on,        // 1 = 音符开, 0 = 音符关
    input  wire [NB-1:0]       ev_note,
    input  wire [AMP_W-1:0]    ev_vel,       // 力度（0..255）

    // Dedicated instance identity; legacy events remain in their own domain.
    input wire ev_owned,
    input wire [OWNER_W-1:0] ev_instance,
    output wire result_valid,result_owned,result_on,result_success,
    output wire [OWNER_W-1:0] result_instance,
    output wire [$clog2(NG)-1:0] result_group,

    //---- 音色选择 ----
    input wire [1:0] preset, own_preset,
    input wire cfg_valid,cfg_commit,
    input wire [1:0] cfg_slot,
    input wire [3:0] cfg_part,
    input wire [47:0] cfg_word,
    output wire cfg_ready,cfg_applied,cfg_error,

    //---- 力度->谱形（D-19/D-20；默认 0/0 ⇒ 恒等，既有音频逐位不变）----
    input  wire signed [9:0]   tilt_vbias,   // 预留（将来的全局倾斜基准）
    input  wire [7:0]          tilt_vgain,   // 非零 = 打开"力度->音色"
    input  wire [8:0]          vel_vscale,   // 力度灵敏度（Q0.8，256 = 表一等一）

    //---- 独立亮度轴 0x5C TILT（32 号 D-13 / I-13）----
    //   0x00 = 最暗 … 0x70 = 恒等（中点）… 0xFF = 最亮
    input  wire [7:0]          tilt,         // 谱形倾斜（低↔高连续轴）

    //---- 塑谱（步③，19 号 §3/§4 + 修正案 A1）----
    //   谱 RAM 16×8：上位机经 0x58/0x59 写入（地址由 tdm_top 侧的指针给出）
    input  wire                spec_commit,
    input  wire                spec_we,      // 写使能（1 拍）
    input  wire [3:0]          spec_addr,    // 0..15
    input  wire [7:0]          spec_wdata,
    input  wire                spec_replace, // 1=替换(只用谱) / 0=叠加(预设+谱) —— 默认 0=安全
                                             //   注意：19 号 §3 的位定义文字写"[0]0=替换/1=叠加"，
                                             //     与它自己给的默认值 0x02"（叠加+自动刷新）"矛盾 。
                                             //     本实现按【默认值+注释】取：bit0 1=替换、0=叠加
                                             //     ⇒ 默认 0x02 = 叠加 上电有声 （已登记任务清单）
    input  wire [15:0]         pad_mask,     // 右手电极 OR 0x5B（bit k ↔ 泛音 k+1）
    //   刷新在响声部（D6 + A1）：脉冲触发，区间 [rf_lo, rf_hi) 内**只刷在响的组**
    input  wire                refresh_valid,
    input  wire [NB-1:0]       rf_lo,
    input  wire [NB:0]         rf_hi,        // 32 ⇒ 需要 NB+1 位

    //---- 到 tdm_engine 的装载口 ----
    output reg                 load_en,
    output reg  [$clog2(NG*P)-1:0] load_slot,
    output reg  [PHASE_W-1:0]  load_inc,
    output reg  [AMP_W-1:0]    load_amp,
    output reg                 load_gate,
    output reg  [7:0]          load_start_tag, // changes only on note-on
    output reg  [22:0]         load_epar,

    //---- 到 tdm_engine 的【滑音初值】----
    //   Q2.16 有符号音高比偏移，随 16 个时隙的装载一起写入待生效区，
    //   与 inc/amp/gate/epar 在同一个消费拍生效（避免混代样本）
    output reg  signed [17:0]  load_gq,

    //---- 状态 ----
    output wire                busy,
    //   事件接收确认（阶段 2，2026-10-06）：消费掉一个事件的那一拍输出单拍脉冲。
    //   上游待处理队列必须用它做 out_ready，**不能**用 `~busy` 这种电平：
    //     busy 是状态输出，事件被接收后要**下一拍**才拉高；在那之前 ~busy 仍为 1，
    //     队列会在那几个连续空闲拍里连续出队，而本模块在忙期间只接收第一个
    //     ⇒ 其余静默消失（实测：发 28 条只到 4 条）。
    output wire                ev_ack,
    output wire [NG-1:0]       active,     // 哪些组在奏（调试/LED 用）
    // Allocation notification for contact-to-voice binding. Refresh is excluded.
    output wire               voice_valid,
    output wire               voice_on,
    output wire [$clog2(NG)-1:0] voice_group,
    output wire [NB-1:0]       voice_note
);

    localparam SW = $clog2(NG*P);
    localparam [NB-1:0] FREE = {NB{1'b1}};      // 127 = 空闲标记

    //-------------------------------------------------------------------------
    // 表：音符 → inc ；音色 → 每个泛音的 (ratio_q8, amp, epar)
    //-------------------------------------------------------------------------
    reg [PHASE_W-1:0] note_rom [0:127];
    reg [47:0]        part_rom [0:NPRE*P-1];
    // 滑音用倒数表：recip[n] = round(2^32 / inc[n])
    //   目的是把"除法"换成"乘一次" —— note_on 时算 1 次，无需除法器
    //   位宽 20：$readmemh 每行 5 个十六进制字符 → 必须正好 20 位，
    //   否则 Gowin 报 EX2526（entry size 与 memory width 不符）
    reg [19:0]        recip_rom [0:127];

    //-------------------------------------------------------------------------
    // 亮度轴权重表（0x5C TILT，32 号 D-13 / I-13）
    //
    //   16 档 × 16 条泛音，每项 9 位（256 = 1.0 倍）。表在
    //     src/gowin/tdm_synth/tilt_wtab.hex，由 tools/scripts/gen_tilt_wtab.py 生成。
    //   **恒等点在档位 7**（= 寄存器 0x70）：w(7,k) ≡ 256 ∀k
    //     ⇒ 上电 0x5C=0 是"最暗"而不是"恒等"，所以 reg_bank 必须把
    //       默认值写成 0x70；否则既有全部音频证据会被这一维改掉。
    //   （表项位宽必须与 hex 的 3 个十六进制位一致 = 12，理由见 vel_shape.v
    //     里那条 EX2526 教训：位宽不符仿真看不出来，板上 ROM 装不进去。）
    //
    //   ★ 数组必须开 [0:255]，不能开 [0:15]（2026-10-06 实测踩到）：
    //     hex 是"一行 16 个词、共 16 行"= 256 个词。声明 [0:15] 时 iverilog 报
    //       WARNING: $readmemh(tilt_wtab.hex): Too many words in the file
    //                 for the requested range [0:15]
    //     然后**静默地**把前 48 项装进去、其余留 X（实测 tilt_rom[7] = 0 0 0 … x x x x）。
    //     后果不是报错，而是"亮度轴看起来能跑、其实恒等点被夹到下限"——
    //     正是本项目反复栽的那类"仿真绿、功能假"的坑。
    //     现在按【文件词数】开数组、用 {档位, 泛音号} 做索引，逐词对齐，
    //     并让测试台在开跑前打印 tilt_rom[112..127] 自检（缺表/错装一眼可见）。
    //-------------------------------------------------------------------------
    reg [11:0]        tilt_rom [0:255];
    initial $readmemh("tilt_wtab.hex", tilt_rom);

    //-------------------------------------------------------------------------
    // 塑谱谱 RAM（步③）：16 个泛音的幅度，运行时由上位机/右手电极驱动
    //   初始化：上电为 0（= 不加任何塑形）⇒ 与"没有这个功能"逐位等价
    //     （所以 R0 黄金参考、既有全部证据都不受影响）
    //-------------------------------------------------------------------------
    reg [7:0] spec_ram [0:P-1];
    // 初值只给【仿真】用（编译时加 -DSIM_INIT）—— 与 fx_delay 的线缓冲同一套做法
    //    原因：综合工具对"存储器 initial 块"的处理很脆（本项目踩过 EX3934 循环上限 ，
    //    fx_delay 因此被当成黑盒丢掉）。而**硬件上 RAM 上电本来就是 0**
    //    （BSRAM 与分布式 LUTRAM 的初值都来自码流，默认 0）
    //    ⇒ 综合路径里不放 initial 块，仿真路径用 -DSIM_INIT 补 0
`ifdef SIM_INIT
    integer si;
    initial for (si = 0; si < P; si = si + 1) spec_ram[si] = 8'd0;
`endif

    generate if (SPEC_STAGED) begin : staged_spectrum
        reg [7:0] pending [0:P-1];
        integer sp;
        always @(posedge clk or negedge rst_n) begin
            if (!rst_n) begin
                for (sp = 0; sp < P; sp = sp + 1) begin pending[sp] <= 0; spec_ram[sp] <= 0; end
            end else begin
                if (spec_we) pending[spec_addr] <= spec_wdata;
                if (spec_commit)
                    for (sp = 0; sp < P; sp = sp + 1)
                        spec_ram[sp] <= (spec_we && spec_addr == sp) ? spec_wdata : pending[sp];
            end
        end
    end else begin : legacy_spectrum
        always @(posedge clk) if (spec_we) spec_ram[spec_addr] <= spec_wdata;
    end endgenerate

    //-------------------------------------------------------------------------
    // 组表：每个组正在奏哪个音符号（FREE = 空闲）
    //-------------------------------------------------------------------------
    reg [NB-1:0]  gtab [0:NG-1];
    reg [AMP_W-1:0] group_velocity [0:NG-1];
    reg [7:0] group_start_tag [0:NG-1];
    reg [NG-1:0] group_owned;
    reg [OWNER_W-1:0] group_instance[0:NG-1];
    reg [$clog2(NG)-1:0] owner_index;
    reg [1:0] preset_hold;
    reg custom_hold,bank_hold;
    wire [3:0] cfg_enabled,cfg_banks;
    wire [47:0] custom_entry;
    reg owned_hold;
    reg [OWNER_W-1:0] instance_hold;
    reg [NG-1:0]  gact;                 // 该组是否正在发声（gate=1）
    reg [NG-1:0]  gact_q;               // 打一拍，供装载序列使用

    integer gi;
    integer reset_group;
    initial begin
        $readmemh("note_inc.hex", note_rom);
        $readmemh("preset_part.hex", part_rom);
        $readmemh("recip_inc.hex", recip_rom);
        for (gi = 0; gi < NG; gi = gi + 1) begin
            gtab[gi] = FREE;
            gact[gi] = 1'b0;
            group_velocity[gi] = 0;
            group_start_tag[gi] = 0;
            group_instance[gi] = 0;
        end
        gact_q = {NG{1'b0}};
        group_owned=0;
    end

    assign active = gact & gact_q;

    //-------------------------------------------------------------------------
    // 状态编码（提前声明：下面的组合/时序块要用到）
    //-------------------------------------------------------------------------
    localparam ST_IDLE  = 3'd0,
               ST_ALLOC = 3'd1,   // ★流水级1：抓事件 + 组分配搜索（结果寄存）
               ST_GLIDE = 3'd2,   // ★流水级2：读旧音高 ROM + 组表写入（结果寄存）
               ST_GQ    = 3'd3,   // ★流水级3：减法 + 倒数表乘法（结果寄存）
               ST_LOAD  = 3'd4,   // 每拍一个时隙
               ST_RFCH  = 3'd5;   // ★步③：刷新序列 —— 在 [rf_lo,rf_hi) 里找在响的组

    //-------------------------------------------------------------------------
    // 流水寄存器与状态（Verilog 要求"先声明后使用"——滑音组合段要用到它们，
    //   所以必须在这里声明，不能放到下面的状态机旁边。本项目(本次)踩这个坑。）
    //-------------------------------------------------------------------------
    reg [2:0]  st;
    reg [NB-1:0]    n_hold;             // 事件音符快照（跨流水级保持）
    reg [NB-1:0]    gsel_r;             // 流水级1：选中组
    reg             match_r;            // 流水级1：是否命中"同音在奏"
    reg             free_r;             // 流水级1：该组【原来是】空闲的
                                        //   必须单独记：g_note_r 在音符开时被覆盖成新音，
                                        //     用它判"有没有旧音高"是错的（会把空闲组判成可滑音）
    reg [NB-1:0]    g_note_r;           // 流水级2：本组要装载的音符号
    reg [PHASE_W-1:0] inc_old_r;        // 流水级2：旧音高（滑音起点）
    reg [PHASE_W-1:0] inc_new_r;        // 流水级2：新音高
    reg          on_cur;
    assign voice_valid = (st == ST_GLIDE) && (on_cur || match_r);
    assign voice_on = on_cur;
    assign voice_group = gsel_r[$clog2(NG)-1:0];
    assign voice_note = (OWNED_EVENTS&&owned_hold&&!on_cur)?gtab[gsel_r]:n_hold;
    assign result_valid=(st==ST_GLIDE);
    assign result_owned=owned_hold;
    assign result_instance=instance_hold;
    assign result_on=on_cur;
    assign result_success=on_cur||match_r;
    assign result_group=gsel_r[$clog2(NG)-1:0];
    reg [AMP_W-1:0] vel_cur;
    reg [$clog2(P)-1:0] k;
    wire [3:0] table_next_k=(st==ST_LOAD)?k[3:0]+4'd1:k[3:0];
    assign cfg_ready=(st==ST_IDLE);
    instrument_table table_store(.clk(clk),.rst_n(rst_n),
        .valid(cfg_valid&&cfg_ready),.commit(cfg_commit),.slot(cfg_slot),.part(cfg_part),.word(cfg_word),
        .applied(cfg_applied),.error(cfg_error),.enabled(cfg_enabled),.banks(cfg_banks),
        .read_addr({preset_hold,bank_hold,table_next_k}),.read_word(custom_entry));
    // 步③ 刷新序列状态
    reg             rf_pend;             // 收到刷新请求（脉冲）后挂起
    reg             rf_mode;             // 正在刷新
    reg [NB:0]      rf_grp;              // 当前扫描到的组（NB+1 位：能表示 32 = 越界）
    reg [NB-1:0]    rf_lo_r;
    reg [NB:0]      rf_hi_r;

    //-------------------------------------------------------------------------
    // 组选择（组合逻辑，一拍出结果）—— 【流水级 1 的输入】
    //   优先级：已在奏同一音符的组 > 空闲组 > round-robin 抢占
    //
    //   2026-10-02 流水化（步②）：
    //     原来这条搜索直接吃 ev_note，结果组合地喂给 gtab→note_rom→减法→45 位乘法，
    //     成了 PnR 实测最差路径（41.941 ns / slack +0.391 ns）的**头部**——
    //     单这一段"32 声部优先搜索 + 轮询"就独占 15.4 ns（5.3→20.7 ns）。
    //     现在它改由【事件快照 n_hold】驱动，结果在 ST_ALLOC 末尾寄存成 gsel_r/
    //     match_r ⇒ 后续所有逻辑从寄存器出发，长链被切断。
    //-------------------------------------------------------------------------
    integer n;
    reg [NB-1:0] gsel_cur;
    reg          found_match, found_free;
    reg          found_open;             // 找到了"可回收"的组（见下）

    always @(*) begin
        gsel_cur    = {NB{1'b0}};
        found_match = 1'b0;
        found_free  = 1'b0;
        found_open  = 1'b0;
        // 先找"正在奏同一音符"的组
        for (n = 0; n < NG; n = n + 1) begin
            if (!found_match && gact[n] &&
                (OWNED_EVENTS ? (!owned_hold&&!group_owned[n]&&gtab[n]==n_hold) : (gtab[n]==n_hold))) begin
                gsel_cur    = n[NB-1:0];
                found_match = 1'b1;
            end
        end
        // Occupancy is authoritative: MIDI 127 has the same bits as FREE.
        if (!found_match) begin
            for (n = 0; n < NG; n = n + 1) begin
                if (!found_free && !gact[n]) begin
                    gsel_cur   = n[NB-1:0];
                    found_free = 1'b1;
                end
            end
        end
        // 第三档：【可回收】的组 —— 设计意图是"已收到 note-off、但释放尾音可能还在响"。
        //
        //   ★★★ 2026-10-07 实测结论：**这一档目前不可达（死代码）**。
        //     原因是我在**同一次修复**里还加了 `gtab[gsel_r] <= FREE`（见下面 ST_GLIDE
        //     的 note-off 分支），两者叠加后产生一条不变量：
        //           gact[n] == 0   ⇒   gtab[n] == FREE
        //     （note-off 同时清 gact、写 gtab=FREE；上电时也是 FREE）
        //     而本搜索的**第二档 FREE 在前、且遍历所有组** ⇒ FREE 档必然先命中
        //     ⇒ 第三档永远选不到。
        //
        //     这不是"推理"：`src/sim/tb_inv.v` 遍历了"逐个按下/松开 + 占满 32 组再全放"
        //     的序列，全程 `gact==0 且 gtab!=FREE` 的组数**恒为 0**（RESULT inv=PASS）
        //     ⇒ 第三档从未被填充过。
        //
        //     为什么保留而不删：
        //       · 删它属于**代码整理**，应另开一次改动并复跑 `19 alloc`/`28 legato`；
        //       · 更要紧的是它**曾经**有实现对象（旧实现 note-off 不写 FREE 时），
        //         留着代码 + 这条注释，能让后来人看懂"为什么要写 FREE"这件事的来龙去脉。
        //     若将来有人让"松手后延迟回 FREE"（例如等释放尾音真正结束），
        //     这一档就会**重新变成可达**，那时它正是需要的。
        if (!found_match && !found_free) begin
            for (n = 0; n < NG; n = n + 1) begin
                if (!found_open && !gact[n]) begin
                    gsel_cur   = n[NB-1:0];
                    found_open = 1'b1;
                end
            end
        end
    end

    wire owner_hit=OWNED_EVENTS&&owned_hold&&gact[owner_index]&&group_owned[owner_index]&&group_instance[owner_index]==instance_hold;
    wire allocation_commit=(st==ST_ALLOC)&&(!OWNED_EVENTS||!owned_hold||owner_hit||owner_index==NG-1);

    // round-robin 抢占指针（在 ST_ALLOC 那一拍推进，与搜索同拍）
    reg [NB-1:0] rr;
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n)                       rr <= {NB{1'b0}};
        else if (allocation_commit && on_cur && !found_match && !found_free && !owner_hit)
            rr <= (rr == NG - 1) ? {NB{1'b0}} : (rr + 1'b1);
    end

    wire [NB-1:0] gsel = (found_match || found_free || found_open) ? gsel_cur : rr;

    //-------------------------------------------------------------------------
    // 滑音初值（2026-10-01 新增）
    //
    //   gq0 = (inc_old - inc_new) / inc_new     ← 有符号 Q2.16 音高比偏移
    //   之后由 pitch_mod 指数衰减到 0 → 音高从旧音滑到新音。
    //
    //   不用除法器：inc_new 只可能是 128 个音之一，把它的倒数预先做成表
    //     （recip_inc.hex），note_on 时乘一次即可。
    //   三种情况【不滑】：
    //       · GLIDE_EN=0（功能关）
    //       · 该组之前是空闲的（没有"旧音高"可滑）
    //       · 同音重触发（found_match）—— 那是重击同一个音，不是滑音
    //   音域上限：±2 个八度（超出则从边界开始滑）。再大既无音乐意义，
    //     又会让频率跑到 0 附近（相位倒转）。
    //   2026-10-02 流水化（步②）：这里原来串着
    //     "搜索→gtab 读→note_rom 读→减法→45 位乘法→钳位"一整条长链，
    //     现在每一段的输入都来自寄存器（gsel_r / g_note_r / inc_old_r / inc_new_r），
    //     减法与乘法落在 ST_GQ 同一拍内 ⇒ 45 位乘法不再是长链的尾巴。
    //-------------------------------------------------------------------------
    wire                    glide_ok = GLIDE_EN && !match_r && !free_r;
    wire signed [PHASE_W:0] dinc     = $signed({1'b0, inc_old_r}) - $signed({1'b0, inc_new_r});
    wire signed [45:0]      gq_mul   = dinc * $signed({1'b0, recip_rom[n_hold]});
    wire signed [29:0]      gq_raw   = gq_mul >>> 16;
    wire signed [17:0]      gq_cal   = !glide_ok               ? 18'sd0      :
                                       (gq_raw >  30'sd131071) ? 18'sd131071 :
                                       (gq_raw < -30'sd114688) ? -18'sd114688 :
                                                                 gq_raw[17:0];


    //-------------------------------------------------------------------------
    // 装载序列状态机（步② 流水化后 5 态）
    //   IDLE → ALLOC（组分配搜索，结果寄存）→ GLIDE（组表写 + 旧/新音高读，寄存）
    //        → GQ（滑音初值：减法 + 倒数表乘法，寄存）→ LOAD（16 拍写 16 时隙）→ IDLE
    //   · 音符开：走全部 5 态 ≈ 20 拍 ≈ 0.74 µs @27 MHz
    //   · 音符关：跳过 GQ（不需要滑音初值）≈ 19 拍；若没找到在奏的组则直接回 IDLE
    //   · **装载口时序（load_en/load_slot/load_inc/amp/gate/epar/gq）与流水化前逐拍等价**
    //     ⇒ tdm_engine 的待生效装载区/周期奇偶语义完全不受影响（21 号 §2 三不变量）
    //   （st / n_hold / gsel_r / match_r / g_note_r / inc_old_r / inc_new_r /
    //     on_cur / vel_cur / k 已在文件上方声明 —— 滑音组合段要用它们）
    //-------------------------------------------------------------------------

    assign busy = (st != ST_IDLE);

    //   接收确认：正好在"ST_IDLE 且 ev_valid"那一拍为 1 —— 事件被真正抓进快照的那一拍。
    //   用组合而不是打一拍：打一拍会让确认晚于接收，队列就又会在两者之间多出
    //   一次"以为对方空闲"的出队机会（同一个坑的另一副面孔）。
    assign ev_ack = (st == ST_IDLE) && ev_valid && !cfg_valid;

    // 当前泛音的预设项
    wire [47:0] pentry = (owned_hold&&!rf_mode) ? (custom_hold ? custom_entry : part_rom[{preset_hold,k}]) : part_rom[{preset,k}];
    wire [15:0] ratio_q8 = pentry[47:32];
    wire [AMP_W-1:0] p_amp = pentry[31:24];
    // pentry 给 epar 留了 24 位，而 epar 实际 23 位。直接写 pentry[23:0]
    //   会触发 EX3791（24 位截到 23 位）。取低 23 位等价（bit23 恒 0），
    //   但显式写出来，避免"靠隐式截断"这种隐患。
    wire [22:0] p_epar   = pentry[22:0];

    // 乘法（共享，每音符 P 次）—— 输入来自寄存器（g_note_r / k）
    // 位宽说明：note_rom 24 位 x ratio_q8 16 位 = 40 位，声明 [PHASE_W+16-1:0]
    //   即 [39:0]，宽度本来就是够的（不要把它误读成 39 位而再去加宽）。
    wire [PHASE_W+16-1:0] inc_mul = note_rom[g_note_r] * ratio_q8;
    // 显式切片：inc_mul>>8 是 32 位，直接赋 24 位会触发 EX3791
    wire [PHASE_W-1:0]    inc_cal = inc_mul[PHASE_W+7:8];

    //-------------------------------------------------------------------------
    // 塑谱：本泛音的有效幅度（步③，19 号 §4）
    //   spec_eff = max(谱 RAM 值, 电极掩码?255:0)
    //     —— §4 的"物理电极扫描 + 0x5B 按位或"在这里等价成"摸到就是满幅"
    //   amp_src  = 替换模式 ? spec_eff : min(255, 预设底谱 + spec_eff)
    //   默认 SPEC_MODE=0x02 ⇒ 叠加 ⇒ 谱为 0 时 amp_src == 预设底谱
    //     ⇒ **与未加塑谱时逐位相同** （既有证据不受影响）
    //-------------------------------------------------------------------------
    wire [7:0] spec_eff   = pad_mask[k] ? 8'd255 : spec_ram[k];
    wire [8:0] amp_add9   = {1'b0, p_amp} + {1'b0, spec_eff};
    wire [7:0] amp_add    = (amp_add9 > 9'd255) ? 8'd255 : amp_add9[7:0];
    wire [7:0] amp_src = (owned_hold&&!rf_mode&&custom_hold) ? p_amp : (spec_replace ? spec_eff : amp_add);   // 1=替换 / 0=叠加（默认叠加 ⇒ 安全）

    //-------------------------------------------------------------------------
    // 独立亮度轴（0x5C TILT，32 号 D-13 / I-13）
    //
    //   为什么放在这里（谱合成之后、力度之前）：
    //     · 亮度是"音色"的一维，必须作用在**该泛音的幅度**上；
    //       放在力度乘法之后会变成"改音量"，那是被否决的做法（D-13 否决项）。
    //     · 放在预设谱合成之后 ⇒ 对 4 个预设都生效，不必给每个预设单独做表。
    //   为什么是"基音退、高次进"：
    //     单纯把高次放大 = 整体变响；把基音同时压低 ⇒ 谱心上升而总能量大致不变，
    //     这才是耳朵认的"变亮"。tilt_wtab 的表极值就是 w(0)=256、w(15)=511。
    //   刷新语义（D-14）：本值只在下一次装载时被读走 ⇒ 生效要经 0x63 刷新。
    //     所以亮度是【手势级】控制（几十个周期的延迟），不做音频级摆动。
    //     这是引擎机制的真实上限，不是实现疏忽。
    //-------------------------------------------------------------------------
    wire [3:0]        tilt_idx = tilt[7:4];                      // 8 位 → 16 档（0x70 → 7 = 恒等）
    //   索引 = {档位, 泛音号}：与 hex 的"一行一档、行内 16 条泛音"逐词对齐。
    wire [7:0]        tilt_wi  = {tilt_idx, k[3:0]};
    wire [8:0]        tilt_w9  = tilt_rom[tilt_wi][8:0];
    //   下限保护：最暗档也不许把基音打到零（否则"最暗"= 没声）。
    //   注：当前 tilt_wtab 对**每一档**都保证 w(0) = 256（基音不动），所以
    //   这个 64 的下限在现有表下永远不会触发 —— 留着是给"将来换表"兜底，
    //   不是当前行为的组成部分（写清楚，免得后人以为它在起作用）。
    wire [8:0]        tilt_w   = (tilt_w9 < 9'd64) ? 9'd64 : tilt_w9;
    //   位宽必须 17：amp_src 8 位 × tilt_w 9 位 = 17 位（最大 255×511 = 130305）。
    //   写成 [2*AMP_W-1:0]（16 位）会截掉最高位 —— 正是本项目栽过的那类
    //   "上下文决定宽度"的坑，所以这里显式给足。
    //   饱和用的是">>8 之后再比 255"，不是"看原积的最高位"：
    //     后者会把 255×256 = 65280（正好等于 255.0 倍，不该饱和）误判为溢出。
    wire [AMP_W+8:0]   tilt_mul = amp_src * tilt_w;
    wire [AMP_W+1:0]   tilt_sh  = tilt_mul[AMP_W+8:8];
    wire [AMP_W-1:0]  amp_tilt  = (tilt_sh > {2'b00, {AMP_W{1'b1}}})
                                  ? {AMP_W{1'b1}} : tilt_sh[AMP_W-1:0];

    //   力度->谱形：插在"预设/谱合成 + 亮度轴"与"力度音量乘法"之间。
    //   默认状态（0x5C=0x70 恒等、0x6E=0 关）⇒ amp_tilt == amp_src 且
    //     amp_shaped == amp_tilt ⇒ **与未加本功能时逐位相同**，既有证据不受影响。
    //   （注意：0x5C 的恒等点是 0x70 而不是 0 —— reg_bank 的初值必须给 0x70。）
    wire [AMP_W-1:0]      amp_shaped;
    vel_shape #(.AW(AMP_W)) u_vshape (
        .vel(vel_cur[AMP_W-1:AMP_W-4]), .part(k[3:0]), .base(amp_tilt),
        .tilt_bias(tilt_vbias), .tilt_gain(tilt_vgain), .vscale(vel_vscale),
        .amp(amp_shaped)
    );
    wire [2*AMP_W-1:0]    amp_mul = amp_shaped * vel_cur;
    wire [AMP_W-1:0]      amp_cal = amp_mul[AMP_W+7:8];

    //-------------------------------------------------------------------------
    // 奈奎斯特防护（步② 与流水化同批）
    //   inc 是"每样本相位增量"的 24 位小数：inc = f/fs × 2^24。
    //   inc ≥ 2^23 ⇔ f ≥ fs/2 = 26.37 kHz ⇒ 该泛音必然折叠成假频
    //   （基音高于 ~1648 Hz 时第 16 泛音就越界）。
    //   处理：把该泛音的幅度置 0，而不是让它折回来当噪声。
    //   注：不做"改频率"，因为折叠后的频率并不等于原频率的镜像不是音乐上要的东西。
    //-------------------------------------------------------------------------
    // Test the full Q8 product BEFORE narrowing; no wrapped partials.
    wire nyq_kill = |inc_mul[PHASE_W+15:PHASE_W+7];

    // 时隙号必须在【足够宽的上下文】里算。
    //   Verilog 的 * 是"上下文决定宽度"的：g(7 位) * P(16) 若在 7 位上下文里
    //   求值会溢出（32*16=512 需要 10 位）。osc_core 的 `prod4 <= (a*b) >>> 16`
    //   就栽在同一件事上。这里显式加宽，不依赖上下文推断。
    wire [2*NB-1:0] slot_wide = gsel_r * P;
    wire [SW-1:0]   slot_calc = slot_wide[SW-1:0] + k;

    // 音符关时不改【音色形态】：用 amp_src（谱形幅度，未经力度）
    //   谱为 0 时 amp_src == p_amp ⇒ 与未加塑谱时逐位相同
    wire [AMP_W-1:0] amp_use = on_cur ? (nyq_kill ? {AMP_W{1'b0}} : amp_cal)
                                      : (nyq_kill ? {AMP_W{1'b0}} : amp_src);

    localparam [$clog2(P)-1:0] K0 = {($clog2(P)){1'b0}};

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            gact <= {NG{1'b0}};
            group_owned<=0;owned_hold<=0;instance_hold<=0;owner_index<=0;preset_hold<=0;custom_hold<=0;bank_hold<=0;
            for (reset_group = 0; reset_group < NG; reset_group = reset_group + 1) begin
                gtab[reset_group] <= FREE;
                group_velocity[reset_group] <= 0;
                group_start_tag[reset_group] <= 0;
                group_instance[reset_group]<=0;
            end
            st        <= ST_IDLE;
            load_en   <= 1'b0;
            load_slot <= {SW{1'b0}};
            load_inc  <= {PHASE_W{1'b0}};
            load_amp  <= {AMP_W{1'b0}};
            load_gate <= 1'b0;
            load_start_tag <= 8'd0;
            load_epar <= 23'd0;
            k         <= K0;
            n_hold    <= {NB{1'b0}};
            gsel_r    <= {NB{1'b0}};
            match_r   <= 1'b0;
            free_r    <= 1'b1;
            g_note_r  <= FREE;
            inc_old_r <= {PHASE_W{1'b0}};
            inc_new_r <= {PHASE_W{1'b0}};
            on_cur    <= 1'b0;
            vel_cur   <= {AMP_W{1'b0}};
            gact_q    <= {NG{1'b0}};
            load_gq   <= 18'sd0;
            rf_pend   <= 1'b0;
            rf_mode   <= 1'b0;
            rf_grp    <= {(NB+1){1'b0}};
            rf_lo_r   <= {NB{1'b0}};
            rf_hi_r   <= {(NB+1){1'b0}};
        end
        else begin
            gact_q <= gact;
            // 刷新请求：锁存成挂起标志（这样在忙时到达的请求也不会丢）
            if (refresh_valid) rf_pend <= 1'b1;
            case (st)
                ST_IDLE: begin
                    load_en <= 1'b0;
                    if (ev_valid && !cfg_valid) begin
                        // 只抓事件快照；分配搜索放到 ST_ALLOC 那一拍做
                        n_hold <= ev_note;
                        preset_hold<=own_preset;
                        custom_hold<=cfg_enabled[own_preset];bank_hold<=cfg_banks[own_preset];
                        owner_index<=0;
                        owned_hold<=OWNED_EVENTS && ev_owned;
                        instance_hold<=(OWNED_EVENTS && ev_owned)?ev_instance:{OWNER_W{1'b0}};
                        on_cur <= ev_on;
                        vel_cur <= ev_vel;
                        st     <= ST_ALLOC;
                    end
                    else if (rf_pend) begin
                        // 步③：开始刷新序列（区间 [rf_lo, rf_hi)，只刷在响的组）
                        //   音符事件优先于刷新（演奏要紧）
                        rf_lo_r <= rf_lo;
                        rf_hi_r <= rf_hi;
                        rf_grp  <= {1'b0, rf_lo};
                        rf_mode <= 1'b1;
                        rf_pend <= 1'b0;
                        st      <= ST_RFCH;
                    end
                end

                //--------------------------------------------------------- 刷新扫描
                ST_RFCH: begin
                    if (rf_grp >= rf_hi_r) begin
                        rf_mode <= 1'b0;
                        st      <= ST_IDLE;
                    end
                    else if (gact[rf_grp[NB-1:0]] && !group_owned[rf_grp[NB-1:0]]) begin
                        // 命中在响的组：按【当前】音高与【当前】谱形重装它的 16 个时隙
                        gsel_r   <= rf_grp[NB-1:0];
                        g_note_r <= gtab[rf_grp[NB-1:0]];
                        vel_cur  <= group_velocity[rf_grp[NB-1:0]];
                        on_cur   <= 1'b1;          // load_gate = 1（它本来就在响 ✓）
                        free_r   <= 1'b0;
                        match_r  <= 1'b1;          // 不参与滑音判定（刷新不改音高）
                        k        <= K0;
                        rf_grp   <= rf_grp + 1'b1;
                        st       <= ST_LOAD;
                    end
                    else rf_grp <= rf_grp + 1'b1;
                end

                ST_ALLOC: begin
                    // 本拍完成搜索（组合），末尾寄存 ⇒ 长链在此切断
                    if(OWNED_EVENTS&&owned_hold)begin
                        if(owner_hit)begin
                            gsel_r<=owner_index;match_r<=1;free_r<=0;st<=ST_GLIDE;
                        end else if(owner_index==NG-1)begin
                            gsel_r<=gsel;match_r<=0;free_r<=!gact[gsel];st<=ST_GLIDE;
                        end else owner_index<=owner_index+1'b1;
                    end else begin
                        gsel_r<=gsel;match_r<=found_match;free_r<=!gact[gsel];st<=ST_GLIDE;
                    end
                end

                ST_GLIDE: begin
                    // 组表更新 + 旧/新音高读取（结果全部寄存）
                    if (on_cur) begin
                        gtab[gsel_r] <= n_hold;
                        group_owned[gsel_r]<=owned_hold;
                        group_instance[gsel_r]<=instance_hold;
                        group_velocity[gsel_r] <= vel_cur;
                        group_start_tag[gsel_r] <= group_start_tag[gsel_r] + 1'b1;
                        gact[gsel_r] <= 1'b1;
                        g_note_r     <= n_hold;             // 装载新音
                    end
                    else if (match_r) begin
                        gact[gsel_r] <= 1'b0;
                        group_owned[gsel_r]<=0;
                        //   ★ 关键修复（2026-10-06）：note-off 时把 gtab 写回 FREE。
                        //   旧实现只清 gact —— 于是 32 组被用过之后，空闲搜索
                        //   （条件是 gtab==FREE）**永远不再命中**，之后每个 note-on
                        //   都走 round-robin 抢占，会把正在按住的音抢掉。
                        //   释放尾音由包络自己的 release 段负责，不需要"占着组号"。
                        //   实测缺陷（修前）：按住 40、依次按放 32 个音，新音把 40 的组抢走；
                        //     修后：新音落在已松手的组上，按住的音安然无恙。
                        gtab[gsel_r] <= FREE;
                        g_note_r     <= gtab[gsel_r];       // 释放正在响的那个音
                    end
                    // 滑音起点 = 该组【写入前】的内容（组合读到旧值）
                    inc_old_r <= note_rom[gtab[gsel_r]];
                    inc_new_r <= note_rom[n_hold];
                    k         <= K0;
                    st        <= on_cur ? ST_GQ : (match_r ? ST_LOAD : ST_IDLE);
                end

                ST_GQ: begin
                    // 滑音初值一次算好；之后在整个 LOAD 期间保持稳定
                    // （tdm_engine 在每个 load_en 都写 pgq_mem[load_slot] <= load_gq）
                    load_gq <= gq_cal;
                    st      <= ST_LOAD;
                end

                ST_LOAD: begin
                    load_en   <= 1'b1;
                    load_slot <= slot_calc;
                    load_inc  <= inc_cal;
                    load_amp  <= amp_use;
                    load_gate <= on_cur;
                    load_start_tag <= group_start_tag[gsel_r];
                    load_epar <= p_epar;
                    if (rf_mode) load_gq <= 18'sd0;   // ★ 刷新时不把旧滑音初值灌回去 ✗
                    if (k == P - 1) begin
                        st <= rf_mode ? ST_RFCH : ST_IDLE;   // 刷新完继续扫下一个在响的组
                    end
                    else begin
                        k <= k + 1'b1;
                    end
                end
            endcase
        end
    end

endmodule
