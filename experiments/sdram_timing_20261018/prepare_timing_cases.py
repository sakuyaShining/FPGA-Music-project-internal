from common import *
s=(R/'constraints/sdram_board.sdc').read_text()
stress=s.replace('-max 6.5','-max 10.0').replace('-max 3.0','-max 4.0').replace('-min -2.0','-min -3.0').replace('-setup 0.5','-setup 1.0').replace('-hold 0.2','-hold 0.5')
(R/'reference/stress.sdc').write_text(stress)
missing='\n'.join(line for line in s.splitlines() if not line.startswith(('set_input_delay','set_output_delay','create_generated_clock')) and 'get_clocks' not in line)+'\n'
(R/'reference/missing_io.sdc').write_text(missing)
print('Prepared declared-delay stress and deliberately missing I/O constraint cases')
