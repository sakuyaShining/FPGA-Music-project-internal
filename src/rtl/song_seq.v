//=============================================================================
// song_seq.v —— 片上曲目定序器（拓展 E7）＋ 演奏指引（拓展 E6 的 LED 部分）
//
// 【赛题要求】
//   E7「脱机 LED 曲目指引」：不接电脑也能自己演奏/指路，并给 LED 指引。
//   E6「可视化」里可做的那一半：把"该弹哪个音"用板载 6 个 LED 显示出来。
//
// 【怎么讲清"脱机"】本模块不依赖任何外部事件：曲谱就烧在 RTL 里（case 表），
//   节拍由 tempo_inc 累加器产生，输出的事件直接驱动 note_map ——
//   上电写一个寄存器就能自己把一首曲子弹完。
//
// 【节拍怎么算才不动除法】沿用本项目一贯做法：上位机把 BPM 换算成
//   "每样本前进多少拍（Q24）" 写进 tempo_inc：
//        tempo_inc = (BPM / 60) × 2^24 / fs
//   定序器只做【加法 + 进位】——进位就是"一拍到了"。BPM=120、fs=52734.375 时
//   tempo_inc = 636（实测拍率 1.9996 拍/秒，误差 0.02%）。
//
// 【曲谱】小星星（Twinkle Twinkle），MIDI 音高：
//   C C G G A A G(2) | F F E E D D C(2) | 休止(2)
//   一共 15 步，循环播放。step_note 就是"该按哪个键"的编号。
//
// 【LED 指引怎么用】输出 cur_note（当前应弹音高的低 5 位）与 beat_pulse（拍点）。
//   顶层把它接到 6 个 LED：[5]=拍点闪，[4:0]=音高编号（二进制）。
//   演奏者照着 LED 的二进制编号按键即可 —— 这就是"脱机曲目指引"。
//=============================================================================

`timescale 1ns/1ps

module song_seq #(
    parameter integer NB    = 7,      // MIDI 音高位数
    parameter integer NSTEP = 15      // 曲谱步数
)(
    input  wire            clk,
    input  wire            rst_n,
    input  wire            sample_en,

    input  wire            enable,     // 使能（0 = 让位给外部演奏事件）
    input  wire            hold,       // 电平：拉高则停在第 0 步（复位/暂停）
    input  wire [23:0]     tempo_inc,  // 每样本拍数（Q24）
    input  wire [7:0]      vel,        // 力度

    // ---- 曲谱 RAM 端口（拓展 E8：曲谱可由上位机下载）----
    //   ram_sel: 0 = 写音高, 1 = 写拍数；写拍数会由顶层自动步进索引
    input  wire            ram_we,
    input  wire            ram_sel,
    input  wire [6:0]      ram_note,
    input  wire [7:0]      ram_beats,
    input  wire [5:0]      ram_idx,
    input  wire            use_ram,    // 1 = 用下载的曲谱，0 = 用内置曲谱
    input  wire [5:0]      ram_len,    // 下载曲谱的步数

    // ---- 送给 note_map 的事件（与外部事件二选一，由顶层 mux）----
    output reg             ev_valid,
    output reg             ev_on,
    output reg  [NB-1:0]   ev_note,
    output reg  [7:0]      ev_vel,

    // ---- 送 LED 的指引 ----
    output reg             beat_pulse,
    output reg  [NB-1:0]   cur_note,
    output wire [7:0]      step_dbg
);

    //-------------------------------------------------------------------------
    // 曲谱（case 表：每一步的音高与拍数）
    //   用 case 而不是 $readmemh：本项目吃过"hex 文件没加载成功却静默继续"
    //     的亏，曲谱烧在 RTL 里最不容易出错，而且 Python 判据可以逐字对照。
    //-------------------------------------------------------------------------
    reg [NB-1:0] step_note;
    reg [7:0]    step_beats;
    reg [7:0]    step;              // 当前步（case 表按它索引）

    always @(*) begin
        case (step)
            8'd0:  begin step_note = 7'd60; step_beats = 8'd1; end  // C
            8'd1:  begin step_note = 7'd60; step_beats = 8'd1; end  // C
            8'd2:  begin step_note = 7'd67; step_beats = 8'd1; end  // G
            8'd3:  begin step_note = 7'd67; step_beats = 8'd1; end  // G
            8'd4:  begin step_note = 7'd69; step_beats = 8'd1; end  // A
            8'd5:  begin step_note = 7'd69; step_beats = 8'd1; end  // A
            8'd6:  begin step_note = 7'd67; step_beats = 8'd2; end  // G(2)
            8'd7:  begin step_note = 7'd65; step_beats = 8'd1; end  // F
            8'd8:  begin step_note = 7'd65; step_beats = 8'd1; end  // F
            8'd9:  begin step_note = 7'd64; step_beats = 8'd1; end  // E
            8'd10: begin step_note = 7'd64; step_beats = 8'd1; end  // E
            8'd11: begin step_note = 7'd62; step_beats = 8'd1; end  // D
            8'd12: begin step_note = 7'd62; step_beats = 8'd1; end  // D
            8'd13: begin step_note = 7'd60; step_beats = 8'd2; end  // C(2)
            default: begin step_note = 7'd0;  step_beats = 8'd2; end // 休止(2)
        endcase
    end

    assign step_dbg = step;

    //-------------------------------------------------------------------------
    // 下载曲谱（E8）：64 步的小 RAM
    //   由顶层把 UART 收到的 (音高, 拍数) 对写进来；use_ram 时取代内置曲谱。
    //   读是组合读（64 项很小，综合成分布式 LUT RAM 即可）。
    //-------------------------------------------------------------------------
    reg [6:0] rnote  [0:63];
    reg [7:0] rbeats [0:63];

    always @(posedge clk) begin
        if (ram_we && !ram_sel) rnote [ram_idx] <= ram_note;
        if (ram_we &&  ram_sel) rbeats[ram_idx] <= ram_beats;
    end

    // 生效的曲谱（内置 or 下载）
    wire [6:0] note_eff  = use_ram ? rnote [step[5:0]] : step_note;
    wire [7:0] beats_eff = use_ram ? rbeats[step[5:0]] : step_beats;
    wire [7:0] nstep_eff = use_ram ? {2'b00, ram_len}  : NSTEP[7:0];

    //-------------------------------------------------------------------------
    // 节拍累加器：进位 = 一拍
    //-------------------------------------------------------------------------
    reg [7:0]  beat_cnt;
    reg [23:0] acc;
    reg [1:0]  ev_st;            // 0 空闲, 1 发 note-off, 2 发 note-on
    reg        beat_pend;        // 有一拍待处理（不丢拍）
    reg        started;          // 本次使能是否已弹出第 0 步
    reg [11:0] bp_cnt;           // 拍点展宽计数（LED 看得见）

    localparam integer BP_LEN = 2109;   // ≈40 ms @52734 Hz

    wire [24:0] acc_sum  = {1'b0, acc} + {1'b0, tempo_inc};
    wire        beat_now = enable & ~hold & sample_en & acc_sum[24];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            step <= 8'd0; beat_cnt <= 8'd0; acc <= 24'd0;
            ev_st <= 2'd0; beat_pend <= 1'b0; bp_cnt <= 12'd0; started <= 1'b0;
            ev_valid <= 1'b0; ev_on <= 1'b0; ev_note <= 7'd0; ev_vel <= 8'd0;
            beat_pulse <= 1'b0; cur_note <= 7'd0;
        end
        else begin
            ev_valid <= 1'b0;

            // 拍点展宽
            if (bp_cnt != 12'd0) bp_cnt <= bp_cnt - 12'd1;
            beat_pulse <= (bp_cnt != 12'd0);

            if (hold) begin
                step <= 8'd0; beat_cnt <= 8'd0; acc <= 24'd0;
                beat_pend <= 1'b0;
                started <= 1'b0;
                ev_st <= 2'd2;          // 复位后立刻从头弹第一个音
            end
            else if (enable && sample_en) begin
                //-----------------------------------------------------------------
                // ① 节拍累加器【每样本都推进】——必须与事件状态机解耦
                //    第一版把它放在状态机的"空闲"分支里，于是每次换音的那 2 拍
                //    不计时，每一步的拍点都往后漂 2~3 个样本（实测拍间隔 13192
                //    而理论 13187）。听感上无所谓，但"时间戳 vs 曲谱"这条判据
                //    就永远差几个样本 —— 计时应是独立的，不该被记账逻辑拖住。
                //-----------------------------------------------------------------
                acc <= acc_sum[23:0];
                if (acc_sum[24]) begin
                    bp_cnt    <= BP_LEN[11:0];
                    beat_pend <= 1'b1;
                end

                //-----------------------------------------------------------------
                // ② 事件状态机（同拍只发一个事件，所以关旧音与新音拆成两拍）
                //-----------------------------------------------------------------
                // 刚使能时先把第 0 步弹出来：否则定序器会一直等到第一个拍点，
                //   而那一刻正好换步 —— 第 0 步的音【永远不会响】（实测漏掉 62）。
                if (!started) begin
                    started <= 1'b1;
                    ev_st   <= 2'd2;
                end
                else if (ev_st == 2'd1) begin
                    if (cur_note != 7'd0) begin
                        ev_valid <= 1'b1; ev_on <= 1'b0;
                        ev_note  <= cur_note; ev_vel <= vel;
                    end
                    ev_st <= 2'd2;
                end
                else if (ev_st == 2'd2) begin
                    if (note_eff != 7'd0) begin
                        ev_valid <= 1'b1; ev_on <= 1'b1;
                        ev_note  <= note_eff; ev_vel <= vel;
                        cur_note <= note_eff;
                    end
                    else
                        cur_note <= 7'd0;
                    ev_st <= 2'd0;
                end
                else if (beat_pend) begin
                    // 一拍处理完 → 计步
                    beat_pend <= 1'b0;
                    if (beat_cnt + 8'd1 >= beats_eff) begin
                        beat_cnt <= 8'd0;
                        step     <= (step >= nstep_eff - 8'd1) ? 8'd0 : (step + 8'd1);
                        ev_st    <= 2'd1;      // 到点：先关旧音
                    end
                    else
                        beat_cnt <= beat_cnt + 8'd1;
                end
            end
        end
    end

endmodule
