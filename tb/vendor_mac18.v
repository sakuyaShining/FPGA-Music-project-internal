// Exact MULTALU18X18 definition from installed vendor simulation library.
module MULTALU18X18 (DOUT, CASO, A, B, C, D, CASI, ACCLOAD, ASIGN, BSIGN, DSIGN, CLK, CE, RESET);
input [17:0] A, B;
input CLK,CE,RESET;
input ASIGN, BSIGN;
input ACCLOAD,DSIGN;
input [53:0] C,D;
input [54:0] CASI;
output [53:0] DOUT;
output [54:0] CASO;

parameter AREG = 1'b0;// 1'b0: bypass mode; 1'b1: registered mode
parameter BREG = 1'b0;
parameter CREG = 1'b0;
parameter DREG = 1'b0;
parameter DSIGN_REG = 1'b0;
parameter ASIGN_REG = 1'b0;
parameter BSIGN_REG = 1'b0;
parameter ACCLOAD_REG0 = 1'b0;
parameter ACCLOAD_REG1 = 1'b0;
parameter MULT_RESET_MODE = "SYNC"; // SYNC, ASYNC
parameter PIPE_REG = 1'b0;
parameter OUT_REG = 1'b0;
parameter B_ADD_SUB = 1'b0; //1'b0: "+"; 1'b1: "-";
parameter C_ADD_SUB = 1'b0;
parameter MULTALU18X18_MODE = 0; //0:ACC/0 +/- 18x18 +/- C; 1:ACC/0 +/- 18x18 + CASI; 2: 18x18 +/- D + CASI;


    reg [17:0] ina0_reg_async,ina0_reg_sync,ina0_reg,inb0_reg,ina1,inb1,inb0_reg_async,inb0_reg_sync;
    reg [35:0] ina,inb;
    reg asign0_reg_async,asign0_reg_sync,bsign0_reg_async,bsign0_reg_sync,asign_0,bsign_0,asign0_reg, bsign0_reg,absign_reg_async, absign_reg,absign_reg_sync, absign;
    reg dsign_reg_async,dsign_reg_sync,dsign_0,dsign_reg;
    reg accload_0, accload0_reg, accload1_reg,accload_1;
    reg alu_sel;
    reg alu_sel0, alu_sel0_reg, alu_sel1_reg,alu_sel1;
    reg [53:0] ind_0, ind_reg, ind_reg_async, ind_reg_sync;
    reg [53:0] inc_reg_async,inc_reg_sync,inc_reg,inc;
    reg [35:0] out0_async, out0_sync, out0,out1;
    wire [35:0] mult_out;
    reg [54:0] ppout1_ext,acc_reg_async, acc_reg_sync, acc_reg;
    wire [54:0] acc_load,ind_ext,inc_ext;
    reg [54:0] acc_out,dout;
    wire grstn = GSR.GSRO;

    initial 
    begin
        acc_reg = 55'b0;
        alu_sel = 1'b1;
        alu_sel0_reg = 1'b0;
        alu_sel1_reg = 1'b0;
    end

    always @(ina0_reg_sync or ina0_reg_async or inb0_reg_sync or inb0_reg_async or inc_reg_async or inc_reg_sync or asign0_reg_async or asign0_reg_sync or bsign0_reg_async or bsign0_reg_sync or absign_reg_async or absign_reg_sync or dsign_reg_async or dsign_reg_sync or ind_reg_async or ind_reg_sync or acc_reg_async or acc_reg_sync or out0_async or out0_sync)
    begin
        if (MULT_RESET_MODE == "ASYNC")
        begin
            ina0_reg <= ina0_reg_async;
            inb0_reg <= inb0_reg_async;
            inc_reg <= inc_reg_async;
            asign0_reg <= asign0_reg_async;
            bsign0_reg <= bsign0_reg_async;
            absign_reg <= absign_reg_async;
            dsign_reg <= dsign_reg_async;
            ind_reg <= ind_reg_async;
            out0 <= out0_async;
            acc_reg <= acc_reg_async;
        end
        else if (MULT_RESET_MODE == "SYNC")
        begin
            ina0_reg <= ina0_reg_sync;
            inb0_reg <= inb0_reg_sync;
            inc_reg <= inc_reg_sync;
            asign0_reg <= asign0_reg_sync;
            bsign0_reg <= bsign0_reg_sync;
            absign_reg <= absign_reg_sync;
            dsign_reg <= dsign_reg_sync;
            ind_reg <= ind_reg_sync;
            out0 <= out0_sync;
            acc_reg <= acc_reg_sync;
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
            ina1 = A;
        end else begin
            ina1 = ina0_reg;
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
            inb1 = B;
        end else 
        begin
            inb1 = inb0_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            inc_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            inc_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            inc_reg_async <= C;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            inc_reg_sync <= 0; 
        end else if (RESET == 1'b1)
        begin
            inc_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            inc_reg_sync <= C;
        end
    end

    always @(C or inc_reg)
    begin
        if (CREG == 1'b0)
        begin
            inc = C;
        end else begin
            inc = inc_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            asign0_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            asign0_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            asign0_reg_async <= ASIGN;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            asign0_reg_sync <= 0;  
        end else if (RESET == 1'b1)
        begin
            asign0_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            asign0_reg_sync <= ASIGN;
        end
    end

    always @(ASIGN or asign0_reg)
    begin
        if (ASIGN_REG == 1'b0)
        begin
            asign_0 = ASIGN;
        end else
        begin
            asign_0 = asign0_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            bsign0_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            bsign0_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            bsign0_reg_async <= BSIGN;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            bsign0_reg_sync <= 0;  
        end else if (RESET == 1'b1)
        begin
            bsign0_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            bsign0_reg_sync <= BSIGN;
        end
    end

    always @(BSIGN or bsign0_reg)
    begin
        if (BSIGN_REG == 1'b0)
        begin
            bsign_0 = BSIGN;
        end else
        begin
            bsign_0 = bsign0_reg;
        end
    end

    assign absign_0 = asign_0 || bsign_0;

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            dsign_reg_async <= 0;  
        end else if (RESET == 1'b1)
        begin
            dsign_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            dsign_reg_async <= DSIGN;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            dsign_reg_sync <= 0;  
        end else if (RESET == 1'b1)
        begin
            dsign_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            dsign_reg_sync <= DSIGN;
        end
    end

    always @(DSIGN or dsign_reg)
    begin
        if (DSIGN_REG == 1'b0)
        begin
            dsign_0 = DSIGN;
        end else
        begin
            dsign_0 = dsign_reg;
        end
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            ind_reg_async <= 0;
        end
        else if (CE == 1'b1)
        begin
            ind_reg_async <= D;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            ind_reg_sync <= 0; 
        end else if (RESET == 1'b1)
        begin
            ind_reg_sync <= 0;
        end
        else if (CE == 1'b1)
        begin
            ind_reg_sync <= D;
        end
    end

    always @(D or ind_reg)
    begin
        if (DREG == 1'b0)
        begin
            ind_0 = D;
        end else
        begin
            ind_0 = ind_reg;
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

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            alu_sel1_reg <= 0;
        end else if (CE == 1'b1)
        begin
            alu_sel1_reg <= alu_sel0;
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
 
    always @(ACCLOAD or accload0_reg or alu_sel or alu_sel0_reg)
    begin
        if (ACCLOAD_REG0 == 1'b0)
        begin
            accload_0 <= ACCLOAD;
            alu_sel0 <= alu_sel;
        end else
        begin
            accload_0 <= accload0_reg;
            alu_sel0 <= alu_sel0_reg;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            accload1_reg <= 0;
        end else if (CE == 1'b1)
        begin
            accload1_reg <= accload_0;
        end
    end
 
    always @(accload_0 or accload1_reg or alu_sel0 or alu_sel1_reg)
    begin
        if (ACCLOAD_REG1 == 1'b0)
        begin
            accload_1 <= accload_0;
            alu_sel1 <= alu_sel0;
        end else 
        begin
            accload_1 <= accload1_reg;
            alu_sel1 <= alu_sel1_reg;
        end
    end
 
    always @(ina1 or asign_0)
    begin
        if (asign_0 == 1'b1)
        begin
            ina[17:0] = ina1;
            ina[35:18] = {ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17],ina1[17]};
        end else
        begin
            ina[17:0] =  ina1;
            ina[35:18] = 0;
        end
    end

    always @(inb1 or bsign_0)
    begin
        if (bsign_0 == 1'b1)
        begin
            inb[17:0] = inb1;
            inb[35:18] = {inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17],inb1[17]};
        end else
        begin
            inb[17:0] = inb1;
            inb[35:18] = 0;
        end
    end

    assign mult_out = (!ina || !inb)? 0 : ina * inb ;

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            out0_async <= 0;
            absign_reg_async <= 0;  
        end else if (RESET == 1'b1)
        begin
            out0_async <= 0;
            absign_reg_async <= 0;  
        end
        else if (CE == 1'b1)
        begin
            out0_async <= mult_out;
            absign_reg_async <= absign_0;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            out0_sync <= 0;
            absign_reg_sync <= 0;  
        end else if (RESET == 1'b1)
        begin
            out0_sync <= 0;
            absign_reg_sync <= 0;  
        end
        else if (CE == 1'b1)
        begin
            out0_sync <= mult_out;
            absign_reg_sync <= absign_0;  
        end
    end
    
    always @(mult_out or out0 or absign_0 or absign_reg)
    begin
        if (PIPE_REG == 1'b0)
        begin
            out1 = mult_out;
            absign = absign_0;
        end else
        begin
            out1 = out0;
            absign = absign_reg;
        end
    end

    always @(out1 or absign or alu_sel1)
    begin
        if(alu_sel1)
        begin
            if (absign == 1'b1)
            begin
                ppout1_ext[35:0] = out1[35:0];
                ppout1_ext[54:36] = {out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35],out1[35]};
            end else
            begin
                ppout1_ext[35:0] =  out1[35:0];
                ppout1_ext[54:36] = 19'b0;
            end
        end else begin
            ppout1_ext[54:0] = 55'b0;
        end
    end

    assign acc_load = (accload_1) ? dout : 0;
    assign ind_ext = (alu_sel1) ? {dsign_0 & ind_0[53], ind_0[53:0]} : 0;
    assign inc_ext = (alu_sel1) ? {1'b0,inc[53:0]} : 0;
    
    always @(acc_load or CASI or ppout1_ext or ind_ext or inc_ext)
    begin
        if(MULTALU18X18_MODE == 0)           //ACC/0 +/- 18x18 +/- C
        begin
            if(B_ADD_SUB == 1'b0 && C_ADD_SUB == 1'b0)
            begin
                acc_out = acc_load + ppout1_ext + inc_ext;
            end else if(B_ADD_SUB == 1'b0 && C_ADD_SUB == 1'b1)
            begin
                acc_out = acc_load + ppout1_ext - inc_ext;
            end else if(B_ADD_SUB == 1'b1 && C_ADD_SUB == 1'b0)
            begin
                acc_out = acc_load - ppout1_ext + inc_ext;
            end else
            begin
                acc_out = acc_load - ppout1_ext - inc_ext;
            end
        end else if(MULTALU18X18_MODE == 1)  //ACC/0 +/- 18x18 + CASI
        begin
            if(B_ADD_SUB == 1'b0) 
            begin
                acc_out = acc_load + ppout1_ext + CASI;
            end else
            begin
                acc_out = acc_load - ppout1_ext + CASI;                
            end        
        end else if(MULTALU18X18_MODE == 2)  //18x18 +/- D + CASI
        begin
            if(B_ADD_SUB == 1'b0) 
            begin
                acc_out = ppout1_ext + ind_ext + CASI;
            end else
            begin
                acc_out = ppout1_ext - ind_ext + CASI;                
            end
        end 
    end

    always @(posedge CLK or posedge RESET or negedge grstn)
    begin
        if (!grstn) begin
            acc_reg_async <= 0;
        end else if (RESET == 1'b1)
        begin
            acc_reg_async <= 0;
        end else if (CE == 1'b1)
        begin
            acc_reg_async <= acc_out;
        end
    end

    always @(posedge CLK or negedge grstn)
    begin
        if (!grstn) begin
            acc_reg_sync <= 0;
        end else  if (RESET == 1'b1)
        begin
            acc_reg_sync <= 0;
        end else if (CE == 1'b1)
        begin
            acc_reg_sync <= acc_out;
        end
    end

    always @(acc_reg or acc_out)
    begin
        if (OUT_REG == 1'b0)
        begin
            dout = acc_out;
        end else
        begin
            dout = acc_reg;
        end
    end

    assign DOUT = dout;
    assign CASO = {dout[53] & absign,dout[53:0]};

endmodule
