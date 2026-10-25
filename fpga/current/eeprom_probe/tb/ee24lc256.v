//=============================================================================
// ee24lc256.v -- 24LC256 行为模型（只建模本仓库用得到的部分）
//
// 【为什么自己写】
//   队友说"三次都卡在自写的假芯片上"。假芯片最容易漏掉的一件事是：
//   **主机 ACK 之后，从机立刻把下一字节的 bit7 送到 SDA 上**。
//   真 24LC256 就是这么做的，本模型把这个行为建了出来。
//
// 【建模范围】
//   · 设备地址（7 位 + R/W）、2 字节地址、顺序读、顺序写、ACK/NACK 采样
//   · START / 重复 START / STOP
//   · 32 KB 存储，init_ff 把整片写成 0xFF（真芯片出厂态）
//   · 不建模：tWR（主机本来就要等 10 ms）、页回卷、上升沿斜率
//
// 【索引约定（第一版在这里错过一次）】
//   bit 是"本字节第几个 SCL 脉冲"，不是"已经驱动了几位"。
//   一个字节 = 9 个脉冲：bit 0..7 是数据位，bit 8 是 ACK 槽。
//   · 下降沿：按 bit 驱动（bit<=7 驱动数据位；bit==8 驱动 ACK / 释放）
//   · 上升沿：按 bit 采样（bit<=7 采样数据位；bit==8 采样主机 ACK，然后收字节）
//   第一版在下降沿自增 nb、上升沿用自增后的 nb，于是 bit0 永远落在 nb==8 的
//   ACK 分支里被吃掉，shin 只收到 7 位，设备地址一次都没匹配上。
//
// 【观测口】测试台直接读这些整数：
//   n_ack / n_nack     主机对"读字节"回了多少次 ACK / NACK
//   n_read_bytes       已交付的读字节数
//   n_start / n_stop   见到几次 START / STOP
//   last_nack          最后一个读字节是不是 NACK
//   ptr                从机下一步要送的那个字节的地址
//=============================================================================
`timescale 1ns/1ps
module ee24lc256 #(
    parameter [6:0] DEV = 7'h50
)(
    input  wire scl,
    inout  wire sda
);
    reg [7:0] mem [0:32767];
    reg       drv = 1'b0;                 // 1 = 把 SDA 拉低
    assign    sda = drv ? 1'b0 : 1'bz;

    //---- 状态 ----
    reg        started = 0;               // 已见到 START，处在一次事务里
    reg        sel     = 0;               // 本事务选中了本器件
    integer    bit     = 0;               // 本字节第几个 SCL 脉冲：0..7 数据，8 ACK
    reg [7:0]  shin    = 0;
    reg [7:0]  shout   = 0;
    integer    phase   = 0;               // 0=设备地址 1=高地址 2=低地址 3=数据
    reg        rd      = 0;
    reg        done    = 0;               // 已 NACK：交出总线，等 STOP
    reg [15:0] ptr     = 0;
    reg        ack_nack = 0;              // 最近一次读字节主机回的是不是 NACK

    //---- 观测口 ----
    integer    n_ack        = 0;
    integer    n_nack       = 0;
    integer    n_read_bytes = 0;
    integer    n_start      = 0;
    integer    n_stop       = 0;
    reg        last_nack    = 0;

    reg        scl_p = 1'b1;
    reg        sda_p = 1'b1;

    task init_ff;
        integer i;
        begin
            for (i = 0; i < 32768; i = i + 1) mem[i] = 8'hFF;
        end
    endtask

    task clear_stats;
        begin
            n_ack = 0; n_nack = 0; n_read_bytes = 0;
            n_start = 0; n_stop = 0; last_nack = 0;
            started = 0; sel = 0; done = 0; bit = 0; phase = 0; rd = 0; drv = 0;
            ptr = 0; ack_nack = 0; shin = 0; shout = 0;
        end
    endtask

    //-------------------------------------------------------------------------
    // 一个字节收完：推进 phase / 指针 / 送下一字节。
    // 只在上升沿 bit==8（ACK 采样之后）调用。
    //-------------------------------------------------------------------------
    task byte_end;
        begin
            if (phase == 0) begin
                // 设备地址字节
                if (shin[7:1] == DEV) begin
                    sel = 1'b1;
                    if (shin[0] == 1'b0) begin
                        phase = 1;                        // 写方向：接着收 2 字节地址
                    end else begin
                        rd    = 1'b1;                     // 读方向：立刻开送
                        phase = 3;
                        shout = mem[ptr];
                        drv   = ~mem[ptr][7];
                        n_read_bytes = 0;
                    end
                end else begin
                    sel = 1'b0;                           // 不是本器件，全程不驱动
                end
            end else if (!rd) begin
                case (phase)
                1: begin ptr[15:8] = shin; phase = 2; end
                2: begin ptr[7:0]  = shin; phase = 3; end
                default: begin
                    mem[ptr] = shin;
                    ptr = ptr + 1;
                end
                endcase
            end else if (!ack_nack) begin
                // 主机 ACK ⇒ 继续送下一字节，并且**立刻**把 bit7 推上线
                ptr   = ptr + 1;
                shout = mem[ptr];
                drv   = ~mem[ptr][7];
            end else begin
                // 主机 NACK ⇒ 交出总线，等 STOP。
                // done 置位后本模型不再驱动任何数据位（真片此时进待机）。
                done = 1'b1;
                drv  = 1'b0;
            end
        end
    endtask

    //-------------------------------------------------------------------------
    // 单一 always 块（仿真专用，阻塞赋值）：靠 scl/sda 的前后值分辨边沿。
    // 拆成多个 always 会让 bit/drv 变成多驱动，所以刻意合成一块。
    //-------------------------------------------------------------------------
    always @(scl or sda) begin
        //---- START / 重复 START：SCL 高时 SDA 下降 ----
        if (scl === 1'b1 && sda_p === 1'b1 && sda === 1'b0) begin
            started = 1'b1;
            sel     = 1'b0;
            bit     = 0;
            phase   = 0;
            rd      = 1'b0;
            done    = 1'b0;
            drv     = 1'b0;
            shin    = 8'h00;
            ack_nack = 1'b0;
            n_start = n_start + 1;
            $display("[EE %0t] START", $time);

        //---- STOP：SCL 高时 SDA 上升 ----
        end else if (scl === 1'b1 && sda_p === 1'b0 && sda === 1'b1) begin
            started = 1'b0;
            sel     = 1'b0;
            done    = 1'b0;
            drv     = 1'b0;
            n_stop  = n_stop + 1;
            $display("[EE %0t] STOP  (读字节 %0d，ptr=0x%04h)", $time, n_read_bytes, ptr);

        //---- SCL 上升沿：采样 ----
        end else if (scl === 1'b1 && scl_p === 1'b0) begin
            if (started) begin
                if (bit <= 7) begin
                    // 线上是开漏 + 上拉，取到的就是 0 或 1
                    shin = {shin[6:0], (sda === 1'b1) ? 1'b1 : 1'b0};
                    bit  = bit + 1;                    // 采完这一位，进下一位
                end else begin
                    // ACK 槽：只有读方向才是"主机应答"
                    if (sel && rd) begin
                        ack_nack  = (sda !== 1'b0);
                        last_nack = ack_nack;
                        n_read_bytes = n_read_bytes + 1;
                        if (ack_nack) n_nack = n_nack + 1;
                        else          n_ack  = n_ack  + 1;
                        $display("[EE %0t] 读字节 %0d (addr 0x%04h) = 0x%02h -> 主机%s",
                                 $time, n_read_bytes, ptr, shin, ack_nack ? "NACK" : "ACK");
                    end
                    if (sel) byte_end;
                    bit = 0;
                end
            end

        //---- SCL 下降沿：驱动 ----
        end else if (scl === 1'b0 && scl_p === 1'b1) begin
            if (started && !done) begin
                if (bit <= 7) begin
                    if (sel && rd) begin
                        drv   = ~shout[7];
                        shout = {shout[6:0], 1'b0};
                    end else begin
                        drv = 1'b0;                   // 写方向：数据由主机驱动
                    end
                end else begin
                    // ACK 槽：8 位刚收完，此刻才能判"选没选中本器件"。
                    // 读方向释放让主机来 ACK/NACK；写方向（含地址字节）由本机拉低应答。
                    if (!sel && phase == 0 && shin[7:1] == DEV) sel = 1'b1;
                    drv = (sel && !rd) ? 1'b1 : 1'b0;
                end
            end
        end

        scl_p = scl;
        sda_p = sda;
    end

endmodule
