//=============================================================================
// pad_pitch.v —— 键位映射与音符事件（与输入源无关）
//
// 依据《音高与八度规格》v2.0：
//   · 通道 0..24  音高：偏移量 = 通道号（0..24），音符号 = 48 + 偏移 + 12×相对档位
//       0..11  下排 C3..B3
//       12..23 上排 C4..B4
//       24     独立高音 C5
//   · 通道 25..29 音域条（不发声，档位由 strip_ctrl 提供）
//   · 通道 30..37 泛音键 → 8 位掩码（不发声）
//
// 关键行为：
//   · **按下时锁存音符号**，松开时用锁存值发 note-off —— 因此中途换挡不会挂音（判据 P6）
//   · 超上限（> 108）**不发声**，且松开时也不补发 note-off（判据 P4）
//   · 扫查式仲裁：每拍处理一个通道，35 拍一轮（27 MHz 下约 1.3 µs），
//     避免优先级饥饿，同时与现有仲裁器的"单事件"接口一致
//   · 换挡本身不产生任何事件（判据 P11）；已在响的音不受换挡影响（判据 P12）
//=============================================================================
module pad_pitch #(
    parameter integer NCH  = 38,   // 与规格一致：0-11 / 12-23 / 24 / 25-29 / 30-37
    parameter integer NPIT = 25,
    parameter integer BASE = 48
)(
    clk, rst_n, touch, pos, vel, ev_on, ev_off, ev_note, ev_vel, harm_mask
);
    // 注意：iverilog 不支持在 ANSI 风格端口里用参数做位宽，故用传统声明
    input  wire           clk;
    input  wire           rst_n;
    input  wire [NCH-1:0] touch;     // 1 = 按下
    input  wire [2:0]     pos;       // 音域档 0..4 → 相对档位 −1..+3
    input  wire [3:0]     vel;
    output reg            ev_on;     // 单拍：note-on
    output reg            ev_off;    // 单拍：note-off
    output reg  [6:0]     ev_note;
    output reg  [3:0]     ev_vel;
    output wire [7:0]     harm_mask; // 泛音键位图（通道 30..37）

    //-------------------------------------------------------------------------
    // 相对档位：pos(0..4) → −1..+3
    //-------------------------------------------------------------------------
    wire signed [10:0] rel  = $signed({8'b0, pos}) - 11'sd1;

    //-------------------------------------------------------------------------
    // 扫查与边沿检测
    //-------------------------------------------------------------------------
    reg  [5:0]     sc;               // 当前扫到的通道
    reg  [NPIT-1:0] seen;            // 每个音高通道【上次被扫到】时的状态
                                     // 注意：不能只存上一拍——扫查 35 拍才回到同一通道，
                                     // 上一拍的快照会漏掉边沿（这正是首版被判据抓到的 bug）

    wire           cur     = touch[sc];
    wire           prev    = seen[sc[4:0]];
    wire           is_pit  = (sc < NPIT);

    // 该通道在"当前档位"下的音符号
    wire signed [10:0] note_of = $signed({3'b0, BASE[7:0]}) + $signed({5'b0, sc}) + (rel * 12);
    wire               in_rng  = (note_of <= 11'sd108) && (note_of >= 11'sd0);

    //-------------------------------------------------------------------------
    // 每通道锁存（防挂音的关键）
    //-------------------------------------------------------------------------
    reg [6:0] lat [0:NPIT-1];
    reg       val [0:NPIT-1];

    integer k;

    // 泛音键 → 掩码（组合直通）
    assign harm_mask = touch[37:30];

    always @(posedge clk or negedge rst_n) begin
        if (!rst_n) begin
            ev_on <= 1'b0; ev_off <= 1'b0; ev_note <= 7'd0; ev_vel <= 4'd0;
            sc <= 6'd0; seen <= {NPIT{1'b0}};
            for (k = 0; k < NPIT; k = k + 1) begin
                lat[k] <= 7'd0;
                val[k] <= 1'b0;
            end
        end else begin
            ev_on  <= 1'b0;
            ev_off <= 1'b0;

            if (is_pit && (cur != prev)) begin
                seen[sc[4:0]] <= cur;
                if (cur) begin
                    // ---- 按下：计算并锁存 ----
                    if (in_rng) begin
                        lat[sc[4:0]] <= note_of[6:0];
                        val[sc[4:0]] <= 1'b1;
                        ev_on    <= 1'b1;
                        ev_note  <= note_of[6:0];
                        ev_vel   <= vel;
                    end else begin
                        // 超出音域上限：不发声，并且记住"这个键没有音"
                        val[sc[4:0]] <= 1'b0;
                    end
                end else begin
                    // ---- 松开：用锁存值发 note-off ----
                    if (val[sc[4:0]]) begin
                        ev_off  <= 1'b1;
                        ev_note <= lat[sc[4:0]];
                    end
                    val[sc[4:0]] <= 1'b0;
                end
            end

            sc <= (sc == NCH[5:0] - 6'd1) ? 6'd0 : (sc + 6'd1);
        end
    end

endmodule
