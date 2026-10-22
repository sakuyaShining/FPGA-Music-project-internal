// Exact functional definitions from installed vendor simulation library.
module ALU54D (DOUT, CASO, A, B, CASI, ACCLOAD, ASIGN, BSIGN, CLK, CE, RESET);
input [53:0] A, B;
input ASIGN,BSIGN;
input ACCLOAD;
input [54:0] CASI;
input CLK, CE, RESET;
output [53:0] DOUT;
output [54:0] CASO;

parameter AREG = 1'b0; //1'b0:bypass mode; 1'b1: register mode
parameter BREG = 1'b0;
parameter ASIGN_REG = 1'b0;
parameter BSIGN_REG = 1'b0;
parameter ACCLOAD_REG = 1'b0;
parameter OUT_REG = 1'b0;
parameter B_ADD_SUB = 1'b0; //1'b0: add; 1'b1:sub;
parameter C_ADD_SUB = 1'b0;
parameter ALUD_MODE = 0;//0:ACC/0 +/- B +/- A; 1:ACC/0 +/- B + CASI; 2:A +/- B + CASI;
parameter ALU_RESET_MODE = "SYNC";//SYNC, ASYNC

    reg [53:0] ina0_reg_async, ina0_reg_sync, ina0_reg, inb0_reg,ina0_sig,inb0_sig, inb0_reg_async, inb0_reg_sync;
    reg asign0_reg0_async,asign0_reg0_sync,bsign0_reg0_async,bsign0_reg0_sync,asign0_0,bsign0_0,asign0_reg0, bsign0_reg0;
    reg accload_0, accload0_reg;
    reg alu_sel;
    reg alu_sel0, alu_sel0_reg;
    reg [54:0] ina0_ext,inb0_ext,dout_reg_async, dout_reg_sync, dout_reg;
    wire [54:0] acc_load;
    reg [54:0] m_out,dout;
    wire grstn = GSR.GSRO;

    initial
    begin
        dout_reg = 55'b0;
        alu_sel = 1'b1;
        alu_sel0_reg = 1'b0;
    end

    always @(ina0_reg_sync or ina0_reg_async or inb0_reg_sync or inb0_reg_async or asign0_reg0_async or asign0_reg0_sync or bsign0_reg0_async or bsign0_reg0_sync or dout_reg_async or dout_reg_sync)
    begin
        if (ALU_RESET_MODE == "ASYNC")
        begin
            ina0_reg <= ina0_reg_async;
            inb0_reg <= inb0_reg_async;
            asign0_reg0 <= asign0_reg0_async;
            bsign0_reg0 <= bsign0_reg0_async;
            dout_reg <= dout_reg_async;
        end 
        else if (ALU_RESET_MODE == "SYNC")
        begin
            ina0_reg <= ina0_reg_sync;
            inb0_reg <= inb0_reg_sync;
            asign0_reg0 <= asign0_reg0_sync;
            bsign0_reg0 <= bsign0_reg0_sync;
            dout_reg <= dout_reg_sync;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            ina0_reg_async <= 0; 
        end else if (RESET == 1'b1)
        begin
            ina0_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            ina0_reg_async <= A;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            ina0_reg_sync <= 0;
        end else if (RESET == 1'b1)
        begin
            ina0_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            ina0_reg_sync <= A;
        end
    end

    always @(A or ina0_reg)
    begin
        if (AREG == 1'b0)
        begin
            ina0_sig = A;
        end else begin
            ina0_sig = ina0_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            inb0_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            inb0_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            inb0_reg_async <= B;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            inb0_reg_sync <= 0;
        end else if (RESET == 1'b1)
        begin
            inb0_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            inb0_reg_sync <= B;
        end
    end

    always @(B or inb0_reg)
    begin
        if (BREG == 1'b0)
        begin
            inb0_sig = B;
        end else begin
            inb0_sig = inb0_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            asign0_reg0_async <= 0;
        end else if (RESET == 1'b1)
        begin
            asign0_reg0_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            asign0_reg0_async <= ASIGN;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            asign0_reg0_sync <= 0;
        end else if (RESET == 1'b1)
        begin
            asign0_reg0_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            asign0_reg0_sync <= ASIGN;
        end
    end

    always @(ASIGN or asign0_reg0)
    begin
        if (ASIGN_REG == 1'b0)
        begin
            asign0_0 = ASIGN;
        end else
        begin
            asign0_0 = asign0_reg0;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            bsign0_reg0_async <= 0;
        end else if (RESET == 1'b1)
        begin
            bsign0_reg0_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            bsign0_reg0_async <= BSIGN;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            bsign0_reg0_sync <= 0;
        end else if (RESET == 1'b1)
        begin
            bsign0_reg0_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            bsign0_reg0_sync <= BSIGN;
        end
    end

    always @(BSIGN or bsign0_reg0)
    begin
        if (BSIGN_REG == 1'b0)
        begin
            bsign0_0 = BSIGN;
        end else
        begin
            bsign0_0 = bsign0_reg0;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            accload0_reg <= 0; 
        end else if (CE == 1'b1)
        begin
            accload0_reg <= ACCLOAD;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            alu_sel0_reg <= 0;
        end else if (CE == 1'b1)
        begin
            alu_sel0_reg <= alu_sel;
        end
    end
 
    always @(ACCLOAD or accload0_reg or alu_sel or alu_sel0_reg)
    begin
        if (ACCLOAD_REG == 1'b0)
        begin
            accload_0 <= ACCLOAD;
            alu_sel0 <= alu_sel;
        end else
        begin
            accload_0 <= accload0_reg;
            alu_sel0 <= alu_sel0_reg;
        end
    end

    always @(asign0_0 or bsign0_0 or ina0_sig or inb0_sig or alu_sel0)
    begin
        if(alu_sel0 == 1'b1) begin
            if (asign0_0 == 1'b1)
            begin
                ina0_ext[53:0] = ina0_sig[53:0];
                ina0_ext[54] = ina0_sig[53];
            end else
            begin
                ina0_ext[53:0] = ina0_sig[53:0];
                ina0_ext[54] = 1'b0;
            end

            if (bsign0_0 == 1'b1)
            begin
                inb0_ext[53:0] = inb0_sig[53:0];
                inb0_ext[54] = inb0_sig[53];
            end else
            begin
                inb0_ext[53:0] = inb0_sig[53:0];
                inb0_ext[54] = 1'b0;
            end
        end else begin
            ina0_ext[54:0] = 55'b0;
            inb0_ext[54:0] = 55'b0;
        end

    end

    assign acc_load = (accload_0) ? m_out : 0;
    
    always @(acc_load or CASI or ina0_ext or inb0_ext)
    begin
        if(ALUD_MODE == 0)           //ACC/0 +/- B +/- A
        begin
            if(B_ADD_SUB == 1'b0 && C_ADD_SUB == 1'b0)
            begin
                dout = acc_load + inb0_ext + ina0_ext;
            end else if(B_ADD_SUB == 1'b0 && C_ADD_SUB == 1'b1)
            begin
                dout = acc_load + inb0_ext - ina0_ext;
            end else if(B_ADD_SUB == 1'b1 && C_ADD_SUB == 1'b0)
            begin
                dout = acc_load - inb0_ext + ina0_ext;
            end else
            begin
                dout = acc_load - inb0_ext - ina0_ext;
            end
        end else if(ALUD_MODE == 1)  //ACC/0 +/- B + CASI
        begin
            if(B_ADD_SUB == 1'b0)
            begin
                dout = acc_load + inb0_ext + CASI;
            end else
            begin
                dout = acc_load - inb0_ext + CASI;
            end        
        end else if(ALUD_MODE == 2)  //A +/- B + CASI
        begin
            if(B_ADD_SUB == 1'b0)
            begin
                dout = ina0_ext + inb0_ext + CASI;
            end else
            begin
                dout = ina0_ext - inb0_ext + CASI;
            end
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            dout_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            dout_reg_async <= 0;
        end else if (CE == 1'b1)
        begin
            dout_reg_async <= dout;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            dout_reg_sync <= 0;
        end else  if (RESET == 1'b1)
        begin
            dout_reg_sync <= 0;
        end else if (CE == 1'b1)
        begin
            dout_reg_sync <= dout;
        end
    end

    always @(dout_reg or dout)
    begin
        if (OUT_REG == 1'b0)
        begin
            m_out = dout;
        end else
        begin
            m_out = dout_reg;
        end
    end

    assign DOUT = m_out[53:0];
    assign CASO = m_out;

endmodule
module GSR (GSRI);

input GSRI;

wire GSRO;

assign GSRO = GSRI;

endmodule
