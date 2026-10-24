`timescale 1ns/1ps
//------------------------------------------------------------------------------
// tb_area —— 验证 rc_strip_positions 新增的 area（接触面积）输出
//
// 为什么单独写一个 tb，而不是改 tb_positions：
//   tb_positions 用的是交接包里独立模型生成的黄金向量（expected_vectors.hex），
//   向量位宽是 {report_cal, invalid, contact, position} 共 45 位，不含 area。
//   往那里塞 area 就得重生成黄金向量，等于把"独立参考"换成"我自己的模型"。
//   所以这里另起一个：直接驱动 read_delta 流，用本文件内的公式独立算期望值，
//   黄金向量那份回归原样保留、继续跑。
//
// 覆盖：重心与面积的一致性、sum=0、坏节点、校准帧、面积位宽上限。
//------------------------------------------------------------------------------
module tb_area;
    reg clk=0;
    always #5 clk=~clk;

    reg rst_n=0, frame_valid=0, frame_calibration=0, report_ready=0;
    reg [31:0] frame_sequence=0;
    wire [6:0] read_address;
    reg [11:0] read_delta=0;
    reg        read_valid=1;
    wire report_valid, report_calibration;
    wire [3:0] contact, invalid;
    wire [35:0] position;   // 4 strip * 9 bit
    wire [55:0] area;       // 4 strip * (CW+2)=14 bit
    wire [31:0] report_sequence;

    reg [11:0] d   [0:11];  // 4 strip * 3 电极
    reg        bad [0:11];  // 注入读失败

    function [83:0] ident_map;
        input integer ignored;
        integer n;
        begin for(n=0;n<12;n=n+1) ident_map[n*7 +: 7] = n; end
    endfunction

    rc_strip_positions #(.STRIPS(4),.CW(12),.CONFIRM_FRAMES(1),.NODE_MAP(ident_map(0))) dut(
        .clk(clk), .rst_n(rst_n),
        .frame_valid(frame_valid), .frame_ready(),
        .frame_sequence(frame_sequence), .frame_calibration(frame_calibration),
        .read_address(read_address), .read_delta(read_delta), .read_valid(read_valid),
        .threshold_on(14'd60), .threshold_off(14'd30),
        .report_valid(report_valid), .report_ready(report_ready),
        .contact(contact), .invalid(invalid), .position(position), .area(area),
        .report_sequence(report_sequence), .report_calibration(report_calibration));

    // 电极读回：按 read_address 查表。read_address 是寄存器输出，在本拍稳定。
    always @* begin
        read_delta = d[read_address[3:0]];
        read_valid = !bad[read_address[3:0]];
    end

    reg [8:0]  ep [0:3];    // 期望位置（sum=0 / 坏节点 / 校准 时保持不变）
    reg [13:0] ea [0:3];    // 期望面积
    reg [3:0]  ec, ei;
    integer s, errors=0, cal_cur, frames=0;

    // 独立期望模型：与 RTL 同公式，但不共享代码
    task expect_strip;
        input integer idx, a, b, c, badflag;
        integer sum, w;
        begin
            d[idx*3+0] = a[11:0];
            d[idx*3+1] = b[11:0];
            d[idx*3+2] = c[11:0];
            bad[idx*3+1] = badflag[0];
            sum = a + b + c;
            if (cal_cur) begin
                ea[idx] = 0; ec[idx] = 0; ei[idx] = 0;
            end else if (badflag) begin
                ea[idx] = 0; ei[idx] = 1;
                // contact 与 position 在坏帧上保持，故不改 ec/ep
            end else begin
                ea[idx] = sum;
                ec[idx] = (sum >= 60);
                ei[idx] = 0;
                if (sum != 0) begin
                    w = b + 2*c;
                    ep[idx] = (w*128)/sum;
                end
            end
        end
    endtask

    task run_frame;
        begin
            @(negedge clk);
            frame_calibration = cal_cur[0:0];
            frame_valid = 1;
            @(negedge clk);
            frame_valid = 0;
            wait(report_valid);
            #1;
            if (report_sequence !== frame_sequence) begin
                $display("  [FAIL] seq got=%0d want=%0d", report_sequence, frame_sequence); errors=errors+1; end
            if (report_calibration !== cal_cur[0:0]) begin
                $display("  [FAIL] cal got=%b want=%b", report_calibration, cal_cur[0:0]); errors=errors+1; end
            if (contact !== ec) begin
                $display("  [FAIL] f%0d contact got=%b want=%b", frames, contact, ec); errors=errors+1; end
            if (invalid !== ei) begin
                $display("  [FAIL] f%0d invalid got=%b want=%b", frames, invalid, ei); errors=errors+1; end
            for (s=0;s<4;s=s+1) begin
                if (position[s*9 +: 9] !== ep[s]) begin
                    $display("  [FAIL] f%0d strip%0d position got=%0d want=%0d", frames, s, position[s*9 +: 9], ep[s]); errors=errors+1; end
                if (area[s*14 +: 14] !== ea[s]) begin
                    $display("  [FAIL] f%0d strip%0d area got=%0d want=%0d", frames, s, area[s*14 +: 14], ea[s]); errors=errors+1; end
            end
            @(negedge clk);
            report_ready = 1;
            @(negedge clk);
            report_ready = 0;
            frame_sequence = frame_sequence + 1;
            frames = frames + 1;
        end
    endtask

    integer k;
    initial begin
        for (k=0;k<12;k=k+1) begin d[k]=0; bad[k]=0; end
        for (k=0;k<4;k=k+1)  begin ep[k]=0; ea[k]=0; end
        ec=0; ei=0;

        repeat(4) @(negedge clk);
        rst_n=1;
        repeat(2) @(negedge clk);

        // ---- F0 校准帧：接触清零，面积清零，位置保持 ----
        cal_cur=1;
        expect_strip(0,0,0,0,0); expect_strip(1,0,0,0,0);
        expect_strip(2,0,0,0,0); expect_strip(3,0,0,0,0);
        run_frame;

        // ---- F1 基本三态：无触摸 / 左端 / 右端 / 正中 ----
        cal_cur=0;
        expect_strip(0,   0,  0,  0, 0);   // sum=0   -> area 0,   pos 保持 0
        expect_strip(1, 100,  0,  0, 0);   // sum=100 -> area 100, pos 0
        expect_strip(2,   0,  0,100, 0);   // sum=100 -> area 100, pos 256
        expect_strip(3, 100,100,100, 0);   // sum=300 -> area 300, pos 128
        run_frame;

        // ---- F2 非对称重心 / 面积位宽上限 / 坏节点 ----
        cal_cur=0;
        expect_strip(0, 100, 50, 20, 0);   // sum=170   -> area 170,   pos 67
        expect_strip(1,4000,4000,4000,0);  // sum=12000 -> area 12000, pos 128
        expect_strip(2,   5,  5,  5, 0);   // sum=15    -> area 15,    pos 128, contact 掉到 0
        expect_strip(3, 100,100,100, 1);   // 坏节点    -> area 0, invalid 1, contact/pos 保持
        run_frame;

        // ---- F3 再校准：面积必须清零，不能留上一帧的大值 ----
        cal_cur=1;
        expect_strip(0,0,0,0,0); expect_strip(1,0,0,0,0);
        expect_strip(2,0,0,0,0); expect_strip(3,0,0,0,0);
        run_frame;

        // ---- F4 校准帧但电极有读数：面积必须强制为 0 ----
        //   这一帧专治"清零只是碰巧 sum=0"的假通过。真实标定时手指可能正按在
        //   面板上，delta 非零，此时若不清零就会把标定值当成一次重按报上去。
        cal_cur=1;
        expect_strip(0, 200, 200, 200, 0);
        expect_strip(1, 300, 150,  50, 0);
        expect_strip(2,   0,   0, 400, 0);
        expect_strip(3,  10,  20,  30, 0);
        run_frame;

        if (errors!=0) $fatal(1,"area regression: %0d failures",errors);
        $display("PASS area frames=%0d centroid_agrees zero_touch bad_node calibration_zero calibration_with_touch wide_sum",frames);
        $finish;
    end
    initial begin #2000000; $fatal(1,"watchdog"); end
endmodule
