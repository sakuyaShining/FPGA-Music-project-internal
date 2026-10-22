from pathlib import Path
P=Path(__file__).resolve().parents[2];p=P/'experiments/sdram_stream_board_20261018/reference/board_body.vpart'
s=p.read_text();a=s.index(' task fail;');b=s.index(' task reset_counts;',a)
s=s[:a]+''' // Pure combinational error selection; state/error registers have ONE writer.
 reg [7:0] pending_error;
 reg [31:0] pending_index;
 reg [15:0] pending_observed,pending_expected;
 always @*begin
  pending_error=0;pending_index=0;pending_observed=0;pending_expected=0;
  if(cycles>=WATCHDOG)begin pending_error=4;pending_index=cycles;end
  else if(rv&&rec_ready&&rec_data!==pattern(rec_read,rec_salt))begin
   pending_error=1;pending_index=rec_read;pending_observed=rec_data;pending_expected=pattern(rec_read,rec_salt);
  end else if(pv&&play_data!==pattern(played,play_salt))begin
   pending_error=2;pending_index=played;pending_observed=play_data;pending_expected=pattern(played,play_salt);
  end else if(normal&&(overflow||underflow||miss))begin
   pending_error=3;pending_index=normal_ticks;pending_observed={13'd0,overflow,underflow,miss};
  end else if((state==H_REQ||state==H_WAIT)&&hold_count<32&&((held_rec&&rcd)||(!held_rec&&pcd)))begin
   pending_error=5;pending_index=hold_count;
  end else if((state==H_REQ||state==H_WAIT)&&hold_count<32&&(!mv||{mw,ma,md}!==held_command))begin
   pending_error=6;pending_index=hold_count;pending_observed=md;pending_expected=held_command[15:0];
  end else if(state==OV_DRAIN&&rec_read>PREFIX)begin pending_error=7;pending_index=rec_read;end
  else if(state==MISS&&(pv||!overflow))begin pending_error=8;pending_index=misses;end
  else if((state==H_DONE||state==I_DONE||state==R_DONE)&&(overflow||underflow))begin
   pending_error=9;pending_index=clear_count;pending_observed={14'd0,overflow,underflow};
  end else if(state==I_DONE&&inflight_clears==0)pending_error=10;
  else if(state==FINAL_CHECK)begin
   if(tests!=6'h1f)begin pending_error=11;pending_observed={10'd0,tests};pending_expected=16'h1f;end
   else if(prefix_count!=PREFIX)begin pending_error=12;pending_index=PREFIX;pending_observed=prefix_count[15:0];pending_expected=PREFIX[15:0];end
   else if(clear_count!=6)begin pending_error=13;pending_index=clear_count;pending_observed=clear_count[15:0];pending_expected=6;end
   else if(after_stop==0)begin pending_error=14;pending_expected=1;end
  end
 end
'''+s[b:]
a=s.index('    FINAL_CHECK:begin');b=s.index('    default:;',a)
s=s[:a]+'''    FINAL_CHECK:if(pending_error==0)begin tests[5]<=1;state<=PASS;end
'''+s[b:]
a=s.index('   if(state!=PASS&&state!=FAIL)begin\n    if(cycles>=WATCHDOG)');b=s.index('\n  end\n end\n // Atomic',a)
s=s[:a]+'''   if(state!=PASS&&state!=FAIL&&pending_error!=0)begin
    state<=FAIL;error_code<=pending_error;failure_index<=pending_index;
    observed<=pending_observed;expected<=pending_expected;
   end'''+s[b:]
p.write_text(s)
print('Refactored error selection without changing comparisons or transport RTL')
