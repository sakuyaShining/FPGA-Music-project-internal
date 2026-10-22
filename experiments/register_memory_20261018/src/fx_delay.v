//=============================================================================
// fx_delay.v —— 硬件效果器：延迟（delay）+ 合唱（chorus）
//
// 【赛题要求】拓展 E4：「在 FPGA 硬件内部实现混响、延迟、合唱等数字音频效果器」
//
// 【纪律 D2：湿声走并联支路，干声路径最短】
//   本模块【只】产生湿声并做混合；干声那条路在顶层是零延迟组合直通。
//   顶层还有一个总旁路：两个效果都关时，音频【完全绕开本模块】
//   （组合 mux），因此
//       · 干声路径一拍都不多
//       · 旁路时输出与加效果器之前【逐位相同】→ 之前所有回归证据继续有效
//
// 【为什么用一条 8192 样本的线 + 分时读】
//   延迟与合唱各要一个抽头，而 BSRAM 一个端口一次只能读一个地址。
//   好在【每个样本有 512 拍】，于是用一个小状态机把两次读、一次写摊开：
//       st1 读延迟抽头 → st2 读合唱抽头 → st3 写回 + 混合 + 输出
//   → 一块 BSRAM 就够，不需要双口存储器。
//
// 【合唱怎么做】延迟抽头地址被一个三角 LFO 来回推动：
//       cho_delay = CHO_BASE + lfo_off,  lfo_off ∈ [-depth, +depth]
//   → 回声到达时间缓慢起伏 = 合唱/镶边的音高抖动（这正是效果本身的定义）。
//
// 【样本格式】内部 16 位（I2S 本来就只发 16 位）；输入是引擎的 24 位有符号，
//   取高 16 位；输出回到 24 位（高位对齐）。
//=============================================================================

`timescale 1ns/1ps

module fx_delay #(
    parameter integer DW = 16,          // 线缓冲样本位宽
    // AW=12 → 4096 样本 ≈ 78 ms @52734 Hz，占 8 块 BSRAM（18K→9K 每块）。
    //   取 13（8192 项 ≈ 155 ms）要多花 8 块（实测 25/46 = 55%），
    //   而 78 ms 已经覆盖合唱（19 ms）与拍击延迟（≤78 ms）的全部用法，
    //   所以先用 12 把 BSRAM 留给后面的混响。
    parameter integer AW = 11,
    parameter integer CHO_BASE = 1024,  // 合唱基础延迟（样本）≈ 19.4 ms
    // 上电冲刷长度（样本）：复位后先用这么多个样本把线缓冲写一遍 0，
    // 免得引擎复位后的未定态被写进来、再经反馈扩散到整条线（见下方注释）。
    // 顶层用默认 2048（= 整条线）；模块级测试台可设小值以避开自己的激励时刻。
    parameter integer FLUSH_LEN = 2048
)(
    input  wire                clk,
    input  wire                rst_n,
    input  wire                sample_en,
    input  wire signed [23:0]  din,        // 引擎输出

    // ---- 运行时参数（由 reg_bank 给）----
    input  wire                dry_en,
    input  wire                dly_en,
    input  wire                cho_en,
    input  wire                rev_en,     // 混响使能（E4 的第三件）
    input  wire [2:0]          wet_sh,     // 湿声增益 = 1/2^wet_sh
    input  wire [15:0]         dly_len,    // 延迟抽头（样本）
    input  wire [7:0]          fb_q8,      // 反馈（Q8）
    input  wire [15:0]         cho_rate,   // 合唱 LFO 频率字
    input  wire [15:0]         cho_depth,  // 合唱深度（样本）
    input  wire [7:0]          rev_fb_q8,  // 混响反馈（Q8）
    input  wire [2:0]          rev_damp,   // 混响阻尼（右移位数，越大越暗）

    output reg  signed [23:0]  dout,
    output wire signed [15:0]  tap_dbg     // 调试：延迟抽头当前值
);

    //-------------------------------------------------------------------------
    // 线缓冲（一块 BSRAM：1 写 + 1 读，同步读）
    //-------------------------------------------------------------------------
    reg signed [DW-1:0] line [0:(1<<AW)-1];

    // 线缓冲上电为 0。
    //   硬件上 BSRAM 上电本来就是 0（Gowin 支持存储器初值），**综合时不需要也不该写初值**：
    //   GowinSynthesis 的循环上限是 2000 次，而这里是 8192 项 ——
    //   第一次综合直接报 EX3934 "Loop count limit of 2000 exceeded"，
    //   并把整个 fx_delay 当【黑盒】丢掉（资源数字看起来"没变"，最危险的那种失败）。
    //   所以：初值只给【仿真】用（编译时加 -DSIM_INIT），综合路径里没有这个块。
`ifdef SIM_INIT
    integer ii;
    initial begin
        for (ii = 0; ii < (1 << AW); ii = ii + 1)
            line[ii] = {DW{1'b0}};
    end
`endif

    reg [AW-1:0] wptr;                     // 环形写指针
    reg [23:0]   lfo_ph;                   // 合唱 LFO 相位

    //-------------------------------------------------------------------------
    // 上电冲刷（2026-10-02 实测抓到的一个真问题）
    //
    //   现象：直接例化 fx_delay 时线缓冲正常；经 tdm_top 例化时 line[0]=x，
    //         而只要有混响反馈，这个 x 会被**反复写回**，~2048 个样本后
    //         扩散到整条线 ⇒ 顶层输出**永久为 x** 。
    //   来源：复位释放后的第一个样本，引擎输出还没进入定态（仿真里是 x）。
    //   修法：复位后先用 2048 个样本把整条线【确定性地写一遍 0】，
    //         再进入正常处理。这样无论引擎早期输出是什么，线缓冲都是干净的。
    //         硬件上这也是标准做法（避开上电瞬间的未定态/直流冲击），
    //         代价 = 2048 个样本 ≈ 39 ms 的启动静默。
    //-------------------------------------------------------------------------


    wire signed [8:0] lfo_t = lfo_ph[23] ? (9'sd127 - $signed({2'b00, lfo_ph[22:16]}))
                                         : ($signed({2'b00, lfo_ph[22:16]}) - 9'sd128);
    // lfo_off ∈ [-depth, +depth]（有符号，Q0 整数样本）
    //   位宽：24 位乘积右移 7 → 17 位；直接声明成 16 位会被 Gowin 报 EX3791
    wire signed [23:0] lfo_mul = $signed(lfo_t) * $signed({1'b0, cho_depth[15:0]});
    wire signed [16:0] lfo_off = lfo_mul >>> 7;

    // 两个抽头地址（AW 位自然回绕）
    wire [AW-1:0] dl_addr = wptr - dly_len[AW-1:0];
    //   CHO_BASE 是 integer 参数，直接参与加法会让表达式变成 32 位后再被截断
    //     （Gowin 报 EX3791）。先落成 18 位有符号常量，再给和留足 19 位。
    localparam signed [17:0] CHO_BASE_S = CHO_BASE[17:0];
    wire signed [18:0] cho_dly = CHO_BASE_S + $signed({1'b0, lfo_off});
    wire [AW-1:0] ch_addr = wptr - cho_dly[AW-1:0];

    reg signed [DW-1:0] read_data;
    reg [3:0] read_tag;
    reg signed [DW-1:0] dl_saved, ch_saved;
    wire signed [DW-1:0] dl_tap = read_tag==4'd1 ? read_data : dl_saved;
    wire signed [DW-1:0] ch_tap = read_tag==4'd2 ? read_data : ch_saved;
    assign tap_dbg = dl_tap;


    //-------------------------------------------------------------------------
    // 混响（拓展 E4 的第三件）：单线多抽头反馈
    //
    //   为什么不用经典 Schroeder 的 4+2 条独立延迟线：
    //     每条线都要自己的 BSRAM 读写口，4 梳状 + 2 全通 ≈ 12~16 块，
    //     而本项目 BSRAM 已用 17/46。这里改成【共用同一条线缓冲】的
    //     4 个互质抽头 + 阻尼反馈 —— 依然能得到"密集、缓慢衰减的尾巴"，
    //     代价只是每样本多 4 个读周期（每样本有 512 拍，完全够）。
    //
    //   抽头位置取互质（刻意错开），避免回声重叠成梳状尖峰。
    //   阻尼：一阶低通（rev_damp 控制右移位数），模拟空气/墙面吸收高频。
    //-------------------------------------------------------------------------
    localparam integer RT0 =  743,
                       RT1 =  806,
                       RT2 =  870,
                       RT3 =  939,
                       RT4 = 1008,
                       RT5 = 1068,
                       RT6 = 1140,
                       RT7 = 1229;

    // 分时状态机：0 空闲, 1 读延迟抽头, 2 读合唱抽头,
    //             3~10 读 8 个混响抽头, 11 写回 + 混合 + 输出
    reg [3:0] st;

    reg        flush_done;
    reg [AW:0] flush_cnt;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            flush_done <= 1'b0;
            flush_cnt  <= {(AW+1){1'b0}};
        end
        else if (!flush_done && st == 4'd11) begin
            if (flush_cnt == FLUSH_LEN[AW:0] - 1'b1)   // 已写满 FLUSH_LEN 个
                flush_done <= 1'b1;
            else
                flush_cnt <= flush_cnt + 1'b1;
        end
    end
    reg signed [DW-1:0] rt_saved [0:7];
    wire signed [DW-1:0] rt [0:7];
    genvar tap;
    generate for(tap=0;tap<8;tap=tap+1)begin: forward_tap
        assign rt[tap] = read_tag==tap+3 ? read_data : rt_saved[tap];
    end endgenerate
    // One physical synchronous RAM read. Select the offset before subtracting
    // wptr, preserving the old address at this exact edge (including live edits).
    reg [AW-1:0] read_offset;
    always @* begin
        case(st)
            4'd1: read_offset=dly_len[AW-1:0];
            4'd2: read_offset=cho_dly[AW-1:0];
            4'd3: read_offset=RT0[AW-1:0];
            4'd4: read_offset=RT1[AW-1:0];
            4'd5: read_offset=RT2[AW-1:0];
            4'd6: read_offset=RT3[AW-1:0];
            4'd7: read_offset=RT4[AW-1:0];
            4'd8: read_offset=RT5[AW-1:0];
            4'd9: read_offset=RT6[AW-1:0];
            4'd10:read_offset=RT7[AW-1:0];
            default:read_offset=0;
        endcase
    end
    wire [AW-1:0] read_address=wptr-read_offset;
    wire read_enable=rst_n&&!sample_en&&st>=4'd1&&st<=4'd10;
    always @(posedge clk)if(read_enable)read_data<=line[read_address];
    always @(posedge clk or negedge rst_n)begin
        if(!rst_n)begin
            read_tag<=0;dl_saved<=0;ch_saved<=0;
            rt_saved[0]<=0;rt_saved[1]<=0;rt_saved[2]<=0;rt_saved[3]<=0;
            rt_saved[4]<=0;rt_saved[5]<=0;rt_saved[6]<=0;rt_saved[7]<=0;
        end else begin
            read_tag<=read_enable?st:4'd0;
            // Forward the newly read word during its original update cycle;
            // save it on the next edge. No extra cycle reaches any tap/output.
            case(read_tag)
                4'd1:dl_saved<=read_data;4'd2:ch_saved<=read_data;
                4'd3:rt_saved[0]<=read_data;4'd4:rt_saved[1]<=read_data;
                4'd5:rt_saved[2]<=read_data;4'd6:rt_saved[3]<=read_data;
                4'd7:rt_saved[4]<=read_data;4'd8:rt_saved[5]<=read_data;
                4'd9:rt_saved[6]<=read_data;4'd10:rt_saved[7]<=read_data;
            endcase
        end
    end
    reg signed [DW:0]   rev_lp;          // 阻尼低通状态

    // 8 个抽头之和（各自符号扩展到 20 位再相加 → 23 位不溢出）
    integer k;
    reg signed [22:0] rev_acc;
    always @(*) begin
        rev_acc = 23'sd0;
        for (k = 0; k < 8; k = k + 1)
            rev_acc = rev_acc + {{4{rt[k][DW-1]}}, rt[k]};
    end
    wire signed [22:0] rev_sum = rev_acc;

    // 阻尼低通：rev_lp += (rev_sum/8 - rev_lp) >> damp
    wire signed [22:0] rev_q   = rev_sum >>> 3;
    wire signed [22:0] rev_dlt = rev_q - {{6{rev_lp[DW]}}, rev_lp};
    wire signed [22:0] rev_lpn = {{6{rev_lp[DW]}}, rev_lp} + (rev_dlt >>> rev_damp);

    // 反馈量 = 【已 ÷8 的平均值】× rev_fb（Q8）
    //   必须用平均值，不能用抽头之和：
    //      和 × 0.75 里含了 8 个抽头的能量 → 环路增益 = 8×0.75 = 6 > 1
    //      → 第一版实测能量分段一路涨到 2.5e11（自激）。
    //      取平均后环路增益 = rev_fb = 0.75，稳定。
    wire signed [30:0] rev_mul = rev_q * $signed({1'b0, rev_fb_q8});
    wire signed [22:0] rev_fbv = rev_mul >>> 8;

    // 写入值 = 【发送电平 −6 dB 的干声】 + 延迟反馈 + 混响反馈
    //   每一级都显式给足位宽：隐式截断会被 Gowin 报成 EX3791
    //   必须显式按有符号解释 —— 本项目惯犯陷阱（第三次）：
    //      `rev_fbv[16:0]` 是【位选 ⇒ 无符号】，负回授被零扩展成大正数。
    //   而且干声必须先衰减 6 dB（`din[23:9]`）再进线缓冲 —— 这是**关键**：
    //      引擎输出是满量程 16 位，再叠加 0.375/0.75 的回授必然在 `wr_val`
    //      处削顶；**反馈环里的削顶 = 整流**，会把直流灌进线缓冲，
    //      而环路对直流有 1/(1−fb)≈1.6 倍的放大 ⇒ 实测输出直流达**半量程**
    //      （4.2e6/8.4e6）、49% 样本削顶、RMS 虚高。
    //      给一条 −6 dB 发送电平（所有效果器的标准做法）后环内不再削顶。
    wire signed [DW:0]   rev_fbv_w = rev_fbv[DW:0];
    wire signed [DW+8:0] fb_mul = $signed(dl_tap) * $signed({1'b0, fb_q8});   // 25 位
    wire signed [DW:0]   fb_val = fb_mul >>> 8;                               // 17 位
    wire signed [24:0]   wr_sum = ($signed(din) >>> 9) + fb_val
                                + (rev_en ? rev_fbv_w : 17'sd0);              // 25 位
    wire signed [DW-1:0] wr_val = (wr_sum >  25'sd32767) ?  16'sd32767 :
                                  (wr_sum < -25'sd32768) ? -16'sd32768 :
                                                           wr_sum[DW-1:0];


    // 混合：干声（24 位）+ 湿声（三个来源之和，右移 wet_sh）
    wire signed [22:0] rev_wet = rev_en ? (rev_sum >>> 3) : 23'sd0;
    // 三路湿声各可达 +/-8388607，和可达 +/-2.5e7；若直接截成 24 位会回绕成
    // 极性相反的爆音，而后级 mix_sum 的饱和救不了"已经回绕"的值。先加宽求和再饱和。
    wire signed [25:0] wet_raw = (dly_en ? {{10{dl_tap[DW-1]}}, dl_tap} : 26'sd0)
                               + (cho_en ? {{10{ch_tap[DW-1]}}, ch_tap} : 26'sd0)
                               + {{3{rev_wet[22]}}, rev_wet};
    wire signed [23:0] wet_sum = (wet_raw >  26'sd8388607) ?  24'sd8388607 :
                                 (wet_raw < -26'sd8388608) ? -24'sd8388608 :
                                                              wet_raw[23:0];
    // D1 电平对齐（2026-10-03 (本次)修的真实缺陷）
    //   线缓冲是 16 位、干声是 24 位；原来只把抽头【符号扩展】到 24 位（数值不变）
    //   ⇒ 满幅抽头在 24 位域里只有 1/128 = **42 dB 偏低** ⇒ 混响实际听不见
    //   （demo 里"听得见混响"其实是 RV_FB=0.75 时线缓冲饱和削顶把它顶上去的 = 自激失真）
    //   修法：湿声先左移 8 位进入 24 位域 （满幅 32767<<8 = 8388352，恰好不越 24 位上限），
    //         再按 wet_sh 衰减
    wire signed [31:0] wet_al = wet_sum <<< 8;
    wire signed [31:0] wet_at = wet_al >>> wet_sh;
    wire signed [23:0] wet_s  = wet_at[23:0];
    // 干湿相加必须【两个操作数都是有符号】——本项目惯犯陷阱（第四次）：
    //    `(24 位 signed) + (26 位 concat)` 里 concat 是【无符号】
    //    ⇒ 整个加法按无符号做 ⇒ 负数干声被【零扩展】成大正数
    //    ⇒ 输出固定正偏置 ≈ 半量程、49% 样本削顶（实测直流 4.23e6/8.39e6）。
    //    修法：先把符号扩展结果落到 signed wire 上，再做加法。
    wire signed [25:0] wet_s26 = {{2{wet_s[23]}}, wet_s};
    wire signed [25:0] mix_sum = (dry_en ? $signed(din) : 26'sd0) + wet_s26;

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            st     <= 4'd0;
            wptr   <= {AW{1'b0}};
            lfo_ph <= 24'd0;
            rev_lp <= {(DW+1){1'b0}};
            dout   <= 24'sd0;
        end
        else if (sample_en) begin
            st    <= 4'd1;                 // 一个样本开始
        end
        else begin
            //-------------------------------------------------------------
            // The old per-tap RAM reads replicated the line ten times. The
            // tagged read/forward path above retains each old tap update edge.
            // Preserve the existing free-running st override below as well;
            // changing scheduling belongs to a separate behavior decision.
            //-------------------------------------------------------------
            case (st)
                4'd1: begin
                    st     <= 4'd2;
                end
                4'd2: begin
                    st     <= 4'd3;
                end
                4'd3:st<=4'd4;4'd4:st<=4'd5;4'd5:st<=4'd6;4'd6:st<=4'd7;
                4'd7:st<=4'd8;4'd8:st<=4'd9;4'd9:st<=4'd10;4'd10:st<=4'd11;
                4'd11: begin
                    // 冲刷期间写 0，把线缓冲确定性地清干净；之后才写真值
                    line[wptr] <= flush_done ? wr_val : {DW{1'b0}};
                    wptr       <= wptr + 1'b1;
                    lfo_ph     <= lfo_ph + {8'b0, cho_rate};
                    if (rev_en) rev_lp <= rev_lpn[DW:0];
                    // 饱和到 24 位
                    if (mix_sum > 26'sd8388607)       dout <=  24'sd8388607;
                    else if (mix_sum < -26'sd8388608) dout <= -24'sd8388608;
                    else                              dout <= mix_sum[23:0];
                    st <= 4'd0;
                end
                default: st <= 4'd0;
            endcase

            st <= (st >= 4'd11) ? 4'd0 : (st + 4'd1);
        end
    end

endmodule
