//=============================================================================
// pad_scan.v —— 16 路电容触摸扫描（无 ADC，纯数字 RC 计时）
//
// 依据：docs/02-技术方案/20-pad扫描规格书.md（用户已批准 16 路 + 五声音阶）
//
// 【原理】把电极当电容：
//     IO 推高 64 拍充电 → 切高阻 + 内部下拉（PULL_MODE=DOWN）→
//     数"放电到读 0"的拍数。手指靠近 ⇒ 电容变大 ⇒ 放电变慢 ⇒ 计数变大。
//
// 【与规格书 §2 的两处偏离（已登记任务清单）】
//   1) **16 路并行**：§2 写"每路 3 拍 / 整轮 96 拍 ≈3.6 µs / 每样本 9 轮"，但它同时要求
//      "充电 64 拍" ⇒ 64×16 = 1024 拍/轮，两个说法不能同时成立 。
//      本实现：16 路**同时**充电、**同时**释放、**每路独立计数器** ⇒
//      一轮 = 64 + 放电 ≈ 100~200 拍 ⇒ 每样本 2~5 轮，每路刷新 ≈18 kHz（≫ 人手带宽）
//   2) **基线取标定窗内的最小值**（而非中位数）：手指只让计数变大 ⇒ 最小值就是
//      "未触摸"的电平 ，比中位数更抗"上电时正好被摸" ，且不需要排序器
//
// 【阈值】§2 的 1.15 / 1.08 倍用**移位加**近似（零乘法器）：
//      hi = base + (base>>3) + (base>>5)  = ×1.156
//      lo = base + (base>>4) + (base>>6)  = ×1.078
//   滞回带 [lo, hi] 内不动作 ⇒ 防临界抖动 ；再叠"连续 3 轮同状态"的去抖
//
// 【输出】
//   · state[7:0]  左手音高键位图 → 五声音阶 case 表 → note 事件（力度 v1 固定 12/15）
//   · state[15:8] 右手泛音键位图 → 或进 0x5B HARM_PADS（步③接上）
//   · 事件经 ev_note/ev_on/ev_valid 走 note_map 既有装载路径
//=============================================================================

`timescale 1ns/1ps

module pad_scan #(
    parameter integer NCH     = 16,      // 16 路（bit0-7 左手音高，bit8-15 右手泛音）
    parameter integer CW      = 12,      // 计数位宽（溢出封顶 4095）
    parameter integer CHARGE  = 64,      // 充电拍数（规格书 §2）
    parameter integer CAL_RND = 32,      // 基线标定轮数（规格书 §2）
    parameter integer DEB     = 3        // 去抖轮数（规格书 §2）
)(
    input  wire                clk,
    input  wire                rst_n,
    inout  wire [NCH-1:0]      pad,     // 电极：充/放/读同一根线
    input  wire                note_busy,    // note_map 忙 ⇒ 事件要等它空
    input  wire                oct_up,       // S2：按下 = 整体 +1 个八度（边界限幅）
    output reg  [NCH-1:0]      state,        // 去抖后的触摸位图
    output reg  [6:0]          ev_note,      // 给 note_map 的音符事件
    output reg                 ev_on,
    output reg                 ev_valid,
    output wire [CW-1:0]       dbg_raw0,     // 调试/判据：第 0 路裸计数
    output wire [CW-1:0]       dbg_base0,    // 调试/判据：第 0 路基线
    output wire [1:0]          dbg_phase,    // 调试：0=充电 1=放电 2=锁存
    // (本次)：**通道可选**遥测（上板 bring-up 要逐根量 RC 量程）
 // 理由见 §1：
    //   内部下拉电阻与电极电容都未知 ⇒ 必须先量出"裸计数落在哪"，
    //   否则可能太快（分辨不出）或计数器封顶（永远摸不着）
    input  wire [3:0]          dbg_sel,      // 选哪一路（0..15，越界取 0）
    output wire [CW-1:0]       dbg_raw_sel,  // 该路的裸计数（上一轮锁存值）
    output wire [CW-1:0]       dbg_base_sel  // 该路的基线
);

    localparam S_CHG = 2'd0, S_DIS = 2'd1, S_LAT = 2'd2;

    reg [1:0]        st;
    reg [6:0]        chg_cnt;            // 充电计数器（0..CHARGE-1）
    reg [CW-1:0]     cnt  [0:NCH-1];     // 本轮放电计数
    reg [CW-1:0]     raw  [0:NCH-1];     // 上一轮锁存的裸计数
    reg [CW-1:0]     base [0:NCH-1];     // 基线
    reg [5:0]        cal_rnd;            // 标定轮计数
    reg [5:0]        trk_cnt;            // 跟踪分频（每 64 轮挪 1）
    reg [1:0]        deb_up [0:NCH-1];   // 去抖计数（升）
    reg [1:0]        deb_dn [0:NCH-1];   // 去抖计数（降）
    reg [NCH-1:0]    state_q;            // 打一拍，用于边沿检测
    reg [7:0]        pend_on, pend_off;  // 左手待发事件（每位一个音高键）
    reg [7:0]        edge_on_pulse, edge_off_pulse;  // 扫描块产出的 1 拍边沿脉冲
    reg [7:0]        clr_on, clr_off;    // 发射块自己的清位（单驱动者）

    integer i;
    reg [CW+2:0]     hi, lo;             // 阈值临时量（移位加，不用乘法器）
    reg [2:0]        idx;    // [临时] 三态停用：纯输入状态下不能驱动电极。
    // 恢复：python tools/scripts/pad_mode.py --inout （会写回寄存器使能版）
    // C0 关键修法：三态的【使能必须是寄存器】！
    //    Gowin 的 IOBUF 内置输出使能寄存器；用组合逻辑推断三态时，
    //    布局布线会报 PR0004 "86 unrouted nets" ⇒ 出不了码流
    //    （已排除：组合三态 、+OPEN_DRAIN 、+寄存器表瘦身 ⇒ 只有寄存器使能）
    reg pad_drv_en;
    always @(posedge clk or negedge rst_n)
        if (!rst_n) pad_drv_en <= 1'b0;
        else        pad_drv_en <= (st == S_CHG);
    assign pad = pad_drv_en ? {NCH{1'b1}} : {NCH{1'bz}};

    // 读回线的实际电平（仿真里由测试台的可变电容模型驱动；硬件里由 RC 决定）
    wire [NCH-1:0] pin_val = pad;

    assign dbg_raw0   = raw[0];
    assign dbg_base0  = base[0];
    assign dbg_phase  = st;
    // 通道可选遥测：越界（≥16）取 0，避免综合出越界索引
    assign dbg_raw_sel  = raw[dbg_sel[3:0]];
    assign dbg_base_sel = base[dbg_sel[3:0]];

    //-------------------------------------------------------------------------
    // 扫描 + 判定
    //-------------------------------------------------------------------------
    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st       <= S_CHG;
            chg_cnt  <= 7'd0;
            cal_rnd  <= 6'd0;
            trk_cnt  <= 6'd0;
            state    <= {NCH{1'b0}};
            state_q  <= {NCH{1'b0}};
            // pend_on/pend_off 归【发射块】独占驱动，这里不能碰（否则 EX2000）
            edge_on_pulse  <= 8'd0;          // ★ 本块独占驱动这两个脉冲
            edge_off_pulse <= 8'd0;
            for (i = 0; i < NCH; i = i + 1) begin
                cnt[i]    <= {CW{1'b0}};
                raw[i]    <= {CW{1'b0}};
                base[i]   <= {CW{1'b1}};      // 初值取最大 ⇒ 标定窗内取最小即可
                deb_up[i] <= 2'd0;
                deb_dn[i] <= 2'd0;
            end
        end
        else begin
            case (st)
                //--------------------------------------------- 充电
                S_CHG: begin
                    for (i = 0; i < NCH; i = i + 1) cnt[i] <= {CW{1'b0}};
                    if (chg_cnt == CHARGE[6:0] - 7'd1) begin
                        chg_cnt <= 7'd0;
                        st      <= S_DIS;
                    end
                    else chg_cnt <= chg_cnt + 7'd1;
                end

                //--------------------------------------------- 放电计数
                S_DIS: begin
                    for (i = 0; i < NCH; i = i + 1) begin
                        if (pin_val[i] && cnt[i] != {CW{1'b1}})
                            cnt[i] <= cnt[i] + 1'b1;      // 还在 1 ⇒ 继续数
                    end
                    // 全部落 0（或封顶）⇒ 本轮结束
                    if ((pin_val == {NCH{1'b0}}) || (cnt[0] == {CW{1'b1}}))
                        st <= S_LAT;
                end

                //--------------------------------------------- 锁存 + 基线 + 判定
                S_LAT: begin
                    for (i = 0; i < NCH; i = i + 1) begin
                        raw[i] <= cnt[i];

                        // ---- 基线：标定窗取最小；之后空闲时慢速跟踪 ----
                        if (cal_rnd < CAL_RND[5:0]) begin
                            if (cnt[i] < base[i]) base[i] <= cnt[i];
                        end
                        else if ((trk_cnt == 6'd63) && !state[i]) begin
                            if (cnt[i] > base[i])      base[i] <= base[i] + 1'b1;
                            else if (cnt[i] < base[i]) base[i] <= base[i] - 1'b1;
                        end

                        // ---- 阈值（移位加近似 1.156 / 1.078）----
                        hi = base[i] + (base[i] >> 3) + (base[i] >> 5);
                        lo = base[i] + (base[i] >> 4) + (base[i] >> 6);

                        // ---- 滞回 + 去抖 ----
                        if (cnt[i] > hi) begin                      // 全宽比较：阈值 15 位，切 12 位会在 base>3543 时回绕
                            deb_dn[i] <= 2'd0;
                            if (deb_up[i] == DEB[1:0] - 2'd1) begin
                                deb_up[i] <= DEB[1:0];        // 饱和，等释放条件
                                state[i]  <= 1'b1;
                            end
                            else if (deb_up[i] != DEB[1:0])
                                deb_up[i] <= deb_up[i] + 2'd1;
                        end
                        else if (cnt[i] < lo) begin                      // 同上
                            deb_up[i] <= 2'd0;
                            if (deb_dn[i] == DEB[1:0] - 2'd1) begin
                                deb_dn[i] <= DEB[1:0];
                                state[i]  <= 1'b0;
                            end
                            else if (deb_dn[i] != DEB[1:0])
                                deb_dn[i] <= deb_dn[i] + 2'd1;
                        end
                        else begin
                            deb_up[i] <= 2'd0;             // 落在滞回带内 ⇒ 保持
                            deb_dn[i] <= 2'd0;
                        end
                    end

                    // ---- 轮计数推进 ----
                    if (cal_rnd < CAL_RND[5:0]) cal_rnd <= cal_rnd + 6'd1;
                    else if (trk_cnt == 6'd63)  trk_cnt <= 6'd0;
                    else                        trk_cnt <= trk_cnt + 6'd1;

                    st <= S_CHG;
                end
            endcase

            //-------------------------------------------------------------------------
            // 左手触摸边沿 → 产出 1 拍脉冲（【只写这两个寄存器】，pend_* 由发射块独占）
            //   这里读到的 state 是【上一拍】的值（非阻塞赋值）
            //   修 bug 记录：原来这里直接写 pend_on/pend_off，而发射块也写它们
            //     ⇒ iverilog 允许多驱动（仿真照过），Gowin 报 EX2000 拒绝 。
            //     仿真通过 ≠ 可综合 —— 所以每次改 RTL 都要跑 PnR
            //-------------------------------------------------------------------------
            state_q       <= state[NCH-1:0];
            edge_on_pulse  <= state[7:0]  & ~state_q[7:0];
            edge_off_pulse <= ~state[7:0] & state_q[7:0];
        end
    end

    //-------------------------------------------------------------------------
    // 事件发射器：串行化（note_map 一次只吃一个事件）
    //   优先 note-on（新触摸要立刻响），再 note-off
    //   ev_valid 只保持 1 拍；发出后等 note_map 空了再发下一个
    //-------------------------------------------------------------------------
    // 五声音阶表（写死在 case 里 —— song_seq 的教训：不用 readmemh）
    //   pad0..7 = C4 D4 E4 G4 A4 C5 D5 E5 = MIDI 60 62 64 67 69 72 74 76
    //   必须做成【函数】而不是"先存 idx 再查表"：后者在同一拍里
    //     idx 还是旧值 ⇒ 发出的是上一个键的音（差一个事件 ，实测 pad1 按下发 60）。
    function [6:0] penta_note;
        input [2:0] p;
        begin
            case (p)
                3'd0: penta_note = 7'd60;   // C4
                3'd1: penta_note = 7'd62;   // D4
                3'd2: penta_note = 7'd64;   // E4
                3'd3: penta_note = 7'd67;   // G4
                3'd4: penta_note = 7'd69;   // A4
                3'd5: penta_note = 7'd72;   // C5
                3'd6: penta_note = 7'd74;   // D5
                default: penta_note = 7'd76; // E5
            endcase
        end
    endfunction

    // 八度切换（S2）：整体 +12，上限 108（C8）
    function [6:0] oct_shift;
        input [6:0] n;
        begin
            oct_shift = (oct_up && (n + 7'd12 < 7'd108)) ? (n + 7'd12) : n;
        end
    endfunction

    reg [2:0] pick;
    wire [7:0] pend_eff_on  = pend_on  | edge_on_pulse;
    wire [7:0] pend_eff_off = pend_off | edge_off_pulse;

    always @(*) begin
        pick = 3'd0;
        if      (pend_eff_on[0]) pick = 3'd0;    // 低编号优先（简单、确定）
        else if (pend_eff_on[1]) pick = 3'd1;
        else if (pend_eff_on[2]) pick = 3'd2;
        else if (pend_eff_on[3]) pick = 3'd3;
        else if (pend_eff_on[4]) pick = 3'd4;
        else if (pend_eff_on[5]) pick = 3'd5;
        else if (pend_eff_on[6]) pick = 3'd6;
        else if (pend_eff_on[7]) pick = 3'd7;
    end

    reg [2:0] pick_off;
    always @(*) begin
        pick_off = 3'd0;
        if      (pend_eff_off[0]) pick_off = 3'd0;
        else if (pend_eff_off[1]) pick_off = 3'd1;
        else if (pend_eff_off[2]) pick_off = 3'd2;
        else if (pend_eff_off[3]) pick_off = 3'd3;
        else if (pend_eff_off[4]) pick_off = 3'd4;
        else if (pend_eff_off[5]) pick_off = 3'd5;
        else if (pend_eff_off[6]) pick_off = 3'd6;
        else if (pend_eff_off[7]) pick_off = 3'd7;
    end

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ev_valid   <= 1'b0;
            ev_on      <= 1'b0;
            ev_note    <= 7'd0;
            idx        <= 3'd0;
            pend_on    <= 8'd0;
            pend_off   <= 8'd0;
            clr_on     <= 8'd0;
            clr_off    <= 8'd0;
        end
        else begin
            // ---- 单一驱动者：收边沿 + 应用上一拍定下的清位 ----
            //   edge_on/off_pulse 由【扫描块】独占驱动（这里只读 不能赋值，
            //     否则又是 EX2000 多驱动）
            pend_on  <= pend_eff_on  & ~clr_on;
            pend_off <= pend_eff_off & ~clr_off;
            clr_on   <= 8'd0;                    // 清位脉冲只维持 1 拍
            clr_off  <= 8'd0;

            if (ev_valid) begin
                ev_valid <= 1'b0;                // 只保持 1 拍
            end
            else if (!note_busy && pend_eff_on != 8'd0) begin
                idx      <= pick;
                ev_note  <= oct_shift(penta_note(pick));   // 组合取，不经 idx 寄存器
                ev_on    <= 1'b1;
                ev_valid <= 1'b1;
                clr_on   <= (8'd1 << pick);
            end
            else if (!note_busy && pend_eff_off != 8'd0) begin
                idx      <= pick_off;
                ev_note  <= oct_shift(penta_note(pick_off));
                ev_on    <= 1'b0;
                ev_valid <= 1'b1;
                clr_off  <= (8'd1 << pick_off);
            end
        end
    end

endmodule
