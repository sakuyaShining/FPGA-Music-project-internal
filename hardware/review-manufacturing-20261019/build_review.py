"""Build an auditable complete carrier *candidate*, never a fabrication release.

Pin assignments are explicit; native exported netlist is independently compared.
Display connectors are our harness interfaces, NOT vendor module pin numbers.
"""
import csv
import json
import sys
import time
from collections import Counter
from native_review import ROOT, MAIN, PROJECT, ORIGINAL, invoke

CAT={p['lcsc']:dict(p,uuid=p['deviceUuid']) for p in json.loads((MAIN/'hardware/pitch-sliders/selection-20261015/catalog-checked.json').read_text(encoding='utf-8'))}
for file in ['catalog-and-project','extra-catalog','esd-catalog','stock-alternates','connector-alternates',
             'v2-power-catalog','v2-entry-catalog','v2-current-limit-catalog','v2-ilim-catalog']:
    data=json.loads((ROOT/f'evidence/{file}.json').read_text(encoding='utf-8'))['value']
    for rows in data.get('queries',data).values():
        if isinstance(rows,list):
            for p in rows:
                if isinstance(p,dict) and p.get('supplierId'):
                    CAT[p['supplierId']]=dict(p,lcsc=p['supplierId'],mpn=p['manufacturerId'])

PAGES=['01_Nano_headers','02_Shift_and_memory','03_Display_harnesses',
       '04_PCM5122_AUX','05_Power','06_Controls']+[f'{i+7:02}_Scan_lane_{i}' for i in range(6)]+['13_Power_off_isolation','14_Protected_power_entry']
parts=[]
notes={}

def add(page,ref,code,x,y,nets,role='',dnp=False):
    p=CAT[code]
    parts.append(dict(page=page,ref=ref,code=code,mpn=p['mpn'],uuid=p['uuid'],libraryUuid=p['libraryUuid'],
                      footprint=p.get('footprintName'),x=x,y=y,nets={str(k):v for k,v in nets.items()},role=role,dnp=dnp))

def two(page,ref,code,x,y,a,b,role='',dnp=False):
    add(page,ref,code,x,y,{'1':a,'2':b},role,dnp)

def header(page,ref,code,x,y,nets,role):
    add(page,ref,code,x,y,{i+1:n for i,n in enumerate(nets)},role)

def schema():
    # Physical Nano connector numbering: Sipeed 3921 rev1.30, p2. Two 1x20 rows.
    # Unused onboard interfaces are explicitly NC, not rerouted.
    j5=[None,'GND',None,None,'SENSE_4','SENSE_3','I2S_BCK','I2S_DIN',None,'SENSE_5',
        'I2S_LRCK',None,None,None,'GND','3V3_IO',None,None,None,None]
    j6=[None,None,None,None,'TP_INT','BUS_MOSI','SCAN_LATCH','BUS_SCK','BUS_RETURN','I2C_SDA',
        'I2C_SCL','SENSE_0','SENSE_1','SENSE_2','INPUT_LOAD_N','VIS_DC','HARM_CS_N','VIS_CS_N','3V3_IO','GND']
    header(PAGES[0],'J5','C50984',260,700,j5,'Mate to Nano J5; row spacing and mating direction NOT yet dimensioned')
    header(PAGES[0],'J6','C50984',850,700,j6,'Mate to Nano J6; no TF/HDMI/UART pin reuse')
    notes[PAGES[0]]=['Nano J5.1 (+5V) deliberately NC: no USB/external 5V backfeed link.',
      '3V3_IO comes from Nano J5.16 / J6.19. Do NOT join DAC_3V3 to this net.',
      'Only 3921 rev1.30 numbering checked. Confirm actual board revision and pin-1 orientation.',
      'I2S pins 56/54/55 fan out existing outputs; BCK and LRCK remain DAC inputs.',
      'Onboard LED loads on GPIO15..20 remain; measure edge timing on assembled harness.']
    pg=PAGES[1]
    add(pg,'U7','C133541',250,730,{'14':'3V3_IO','7':'GND',**{str(a):f'RC{i}' for i,a in enumerate([1,3,5,9,11,13])},**{str(a):f'INV{i}' for i,a in enumerate([2,4,6,8,10,12])}},'six inverting Schmitt gates')
    add(pg,'U8','C205940',750,730,{'16':'3V3_IO','8':'GND','14':'BUS_MOSI','11':'BUS_SCK','12':'SCAN_LATCH','13':'GND','10':'3V3_IO','9':None,
          '15':'ADDR0','1':'ADDR1','2':'ADDR2','3':'ADDR3','4':'MUX_DISABLE','5':'RC_DRIVE','6':'LCD_RESET_N','7':'TP_RESET_N'},'shared shift register: latch only complete scan/reset word')
    add(pg,'U9','C273656',1250,730,{'16':'3V3_IO','8':'GND','1':'INPUT_LOAD_N','2':'BUS_SCK','15':'GND','10':'GND','9':'KEY_QH','7':None,
          '11':'ENC_A','12':'ENC_B','13':'ENC_PUSH','14':'PRESET0','3':'PRESET1','4':'PRESET2','5':'PRESET3','6':'EDIT'},'parallel input; reload after unrelated SPI traffic')
    add(pg,'U10','C411625',250,330,{'1':'GND','2':'GND','3':'GND','4':'GND','5':'I2C_SDA','6':'I2C_SCL','7':'GND','8':'3V3_IO'},'7-bit address 0x50; WP LOW')
    # Verify library pin names before wiring, against Nexperia function table.
    add(pg,'U11','C503437',750,330,{'1':'KEY_QH','2':'GND','3':'RA_MISO','4':'BUS_RETURN','5':'3V3_IO','6':'HARM_CS_N'},'S=0 RA return; S=1 keys; lifecycle substitution pending')
    for i in range(6):two(pg,f'R{11+i}','C22962',1100+(i%2)*330,360-(i//2)*90,f'INV{i}',f'SENSE_{i}','220R output isolation; stocked replacement for C107696')
    for i in range(5):two(pg,f'C{7+i}','C1591',180+i*300,40,'3V3_IO','GND','100nF adjacent to U7..U11')
    notes[pg]=['U8 output state is not guaranteed at power-up. Firmware must initialize/latch before use.',
      'Q4 HIGH disables all MUXes; drive LOW/discharge, select, settle, then charge/time. Inverted SENSE.',
      'RA8875 return and 165 output are selected by U11. Never wire their push-pull outputs together.',
      'No simultaneous key capture or 595 latch during screen command. Arbitration/timing still to implement.']
    pg=PAGES[2]
    header(pg,'J10','C247920',270,700,['5V_SYS','GND','BUS_SCK','BUS_MOSI','RA_MISO','HARM_CS_N','LCD_RESET_N','I2C_SDA','I2C_SCL','TP_INT','TP_RESET_N','GND'],'OUR 12-way RA8875/CTP harness; supplier pinout NOT implied')
    header(pg,'J11','C247920',900,700,['5V_SYS','GND','BUS_SCK','BUS_MOSI','VIS_CS_N','VIS_DC','LCD_RESET_N',None,None,None,None,'GND'],'OUR 12-way ILI9341 harness for module with onboard regulator; verify MSP2401 revision')
    for i,(n,code) in enumerate([('HARM_CS_N','C98220'),('VIS_CS_N','C98220'),('INPUT_LOAD_N','C98220')]):
        two(pg,f'R{30+i}',code,250+i*450,300,'3V3_IO',n,'idle pull-up')
    for i,n in enumerate(['I2C_SDA','I2C_SCL']):two(pg,f'R{33+i}','C23162',250+i*450,180,'3V3_IO',n,'4.7k initial; DNP if module parallel pull-ups too strong')
    notes[pg]=['J10/J11 are custom cable interfaces. They are NOT native display connectors or FFC footprints.',
      'RA8875 uses SPI command prefixes; VIS_DC belongs only to ILI9341.',
      'ER-TFTM070-5V4 must be ordered 4-wire SPI + capacitive touch; exact revision/configuration pending.',
      'Require all module IO at 3.3V; verify touch pull-ups, INT/reset, MISO behavior and rail sequencing.',
      'Both screen VCCs use 5V_SYS. Small module MUST accept 5V VCC via onboard regulator; ALL IO remain 3.3V.']
    pg=PAGES[3]
    add(pg,'U12','C962071',400,750,{'1':'DAC_3V3','2':'DAC_CAPP','3':'GND','4':'DAC_CAPM','5':'DAC_VNEG','6':'DAC_L_RAW','7':'DAC_R_RAW',
       '8':'DAC_3V3','9':'GND','10':'GND','11':'I2C_SDA','12':'I2C_SCL','13':None,'14':None,'15':None,'16':'GND',
       '17':'GND','18':'DAC_3V3','19':None,'20':'GND','21':'I2S_BCK','22':'I2S_DIN','23':'I2S_LRCK','24':'GND','25':'DAC_XSMT','26':'DAC_LDOO','27':'GND','28':'DAC_3V3'},'I2C mode MODE1=0 MODE2=1 ADR1/2=0 => 0x4C; SCK grounded in 3-wire mode')
    for ref,a,b,x,y in [('C20','DAC_CAPP','DAC_CAPM',1050,820),('C21','DAC_VNEG','GND',1050,700)]:
        two(pg,ref,'C1607',x,y,a,b,'2.2uF charge pump; effective capacitance/bias to confirm')
    two(pg,'C22','C1591',1050,580,'DAC_LDOO','GND','100nF LDOO decoupling; never attach this pin to 3.3V')
    for i in range(3):two(pg,f'C{23+i}','C1591',200+i*420,240,'DAC_3V3','GND','100nF for CPVDD/AVDD/DVDD, place separately at pins')
    two(pg,'C26','C1607',1460,240,'DAC_3V3','GND','2.2uF local bulk')
    two(pg,'R40','C98220',1050,450,'DAC_3V3','DAC_XSMT','10k unmute pull-up; software mute required before manual PLL setup')
    for i,ch in enumerate(['L','R']):
        two(pg,f'R{41+i}','C22775',1050+i*450,340,f'DAC_{ch}_RAW',f'AUX_{ch}','100R series; validate line output load')
        two(pg,f'C{27+i}','C14858',1050+i*450,120,f'AUX_{ch}','GND','100pF RF shunt candidate; not audio low-pass qualification')
    header(pg,'J12','C49257',1650,700,['AUX_L','AUX_R','GND'],'external TRS jack: Tip=L Ring=R Sleeve=GND; NOT headphones/speaker')
    notes[pg]=['TI SLAS763C: VREF mode default => VCOM pin10 GND; unused GPIO internally pulled down, NC.',
      'XSMT pull-up does not replace controlled startup. Keep incoming I2S silent while configuring.',
      '52,734.375Hz / 32fs needs manual BCK PLL, clock-flex, double-speed and readback; NOT bench validated.',
      'J12 feeds an external TRS jack; exact jack footprint and ESD protection not frozen.',
      'MAX98357 onboard speaker is BTL. Neither speaker terminal may connect to AUX or GND.']
    pg=PAGES[4]
    header(pg,'J13','C49257',250,700,['5V_SYS','GND',None],'single regulated 5V supply distribution, connector rating/entry protection pending')
    add(pg,'U13','C51118',800,700,{'1':'5V_SYS','2':'GND','3':'5V_SYS','4':None,'5':'DAC_3V3'},'separate AP2112K 3.3V DAC LDO; not a display regulator')
    two(pg,'C30','C1607',450,390,'5V_SYS','GND','2.2uF ceramic input, effective >=1uF')
    two(pg,'C31','C1607',1050,390,'DAC_3V3','GND','2.2uF ceramic output, effective >=1uF')
    two(pg,'C32','C1592',250,230,'3V3_IO','GND','1uF front-end bulk; local IC 100nF on each scan/core page')
    notes[pg]=['Nano is powered independently through its existing USB connector. J5.1 remains NC.',
      'Use one ground reference; avoid powering Nano and 5V_SYS from incompatible supplies.',
      '3V3_IO powers scan logic; DAC_3V3 is isolated from Nano 3.3V.',
      'Power entry fuse/reverse protection, inrush and USB isolation are NOT yet designed.',
      'AP2112 heat budget at 50mA: (5-3.3)*0.05 = 85mW; actual DAC current/thermal to verify.',
      'Display power/backlight current and switch-on sequence remain fabrication blockers.']
    pg=PAGES[5]
    # Actual ALPS pin names are checked after placement before wiring.
    add(pg,'SW1','C470754',300,700,{'A':'ENC_A','B':'ENC_B','C':'GND','D':'ENC_PUSH','E':'GND','6':None,'7':None},'EC11E15244B2: official ALPS confirms push, 30 detents/15 pulses, 1.5mm travel')
    for i,n in enumerate(['PRESET0','PRESET1','PRESET2','PRESET3','EDIT']):
        add(pg,f'SW{i+2}','C318884',750+(i%3)*350,700-(i//3)*260,{'1':n,'2':n,'3':'GND','4':'GND'},'preset/edit button')
    for i,n in enumerate(['ENC_A','ENC_B','ENC_PUSH','PRESET0','PRESET1','PRESET2','PRESET3','EDIT']):
        code='C4190' if i<2 else ('C23162' if i==2 else 'C98220')
        two(pg,f'R{50+i}',code,230+(i%4)*400,280-(i//4)*120,'3V3_IO',n,'input pull-up; digital debounce required')
    notes[pg]=['Four presets + edit + encoder A/B/push consume all eight 165 inputs.',
      'EC11E15244B2 HAS push (ALPS official page). Old no-push rejection was incorrect; check pad geometry.',
      'Button pin1/2 common and 3/4 common from library; mechanical drawing still to cross-check.']
    muxpins=[9,8,7,6,5,4,3,2,23,22,21,20,19,18,17,16]
    for lane,pg in enumerate(PAGES[6:12]):
        nets={24:'3V3_IO',12:'GND',15:'MUX_DISABLE',10:'ADDR0',11:'ADDR1',14:'ADDR2',13:'ADDR3',1:f'RC{lane}'}
        for addr,pin in enumerate(muxpins):nets[pin]=f'L{lane}_M{addr:02}'
        add(pg,f'U{lane+1}','C179326',260,750,nets,'six parallel 16:1 MUX; address14/15 reference loads')
        two(pg,f'R{lane+1}','C105579',260,300,'RC_DRIVE',f'RC{lane}','47k initial value; no fixed 1nF timing shunt')
        two(pg,f'C{lane+1}','C1591',260,160,'3V3_IO','GND','100nF local MUX decoupling')
        for addr in range(14):
            two(pg,f'R{100+lane*20+addr}','C22548',650+(addr//7)*430,950-(addr%7)*105,
                f'L{lane}_E{addr:02}',f'L{lane}_M{addr:02}','1k per electrode; stocked replacement for C21190')
        for i,(code,addr) in enumerate([('C1634',14),('C14858',15)]):
            two(pg,f'C{100+lane*2+i}',code,700+i*430,160,f'L{lane}_M{addr:02}','GND','10/100pF C0G reference; selection subject to measured capacitance')
        header(pg,f'J{20+lane}','C22465876',1510,750,[f'L{lane}_E{a:02}' for a in range(14)]+['GND','GND'],'1x16 MALE carrier header, female cable required; 14 electrode channels + 2 ground')
        # Four real TI protection devices per lane: full 84-channel protection footprints.
        for group in range(4):
            dn={3:'GND',8:'GND',6:None,7:None,9:None,10:None}
            for ch,pair in enumerate([(1,),(2,),(4,),(5,)]):
                addr=group*4+ch
                n=f'L{lane}_E{addr:02}' if addr<14 else None
                for pin in pair:dn[pin]=n
            add(pg,f'D{1+lane*4+group}','C106794',650+(group%2)*430,-30-(group//2)*230,dn,'TI TPD4E02B04; NOT TECH PUBLIC -TP; physical ESD qualification pending')
        notes[pg]=[f'Lane {lane}: addresses0..13 electrodes, 14=10pF reference, 15=100pF reference.',
           'No 1nF common shunt: old BOM value was unqualified and can swamp the touch delta.',
           '14*6=84 available channels: 80 or83 allocated after 25/26-note endpoint decision.',
           'ESD devices sit connector-side of 1k. Short return to ground; do not claim IEC immunity from schematic.',
           'Electrode shapes, cover film, row spacing and sensor cable capacitance remain to measure.']
    power_v2()
    refs=[p['ref'] for p in parts]
    assert len(refs)==len(set(refs)),[r for r,c in Counter(refs).items() if c>1]
    (ROOT/'design.json').write_text(json.dumps({'pages':PAGES,'parts':parts,'notes':notes},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ROOT/'expected-pin-nets.json').write_text(json.dumps({p['ref']:p['nets'] for p in parts},indent=2)+'\n',encoding='utf-8')
    print('schema:',len(parts),'components',sum(len(p['nets']) for p in parts),'pins')


def power_v2():
    """Power sequencing candidate. References follow independently checked TI pin tables."""
    byref={p['ref']:p for p in parts}
    def nets(ref, changes):byref[ref]['nets'].update({str(k):v for k,v in changes.items()})
    byref['J5']['role']='Nano J5 short harness, NOT stacked; actual revision/pin-1 must be checked'
    byref['J6']['role']='Nano J6 short harness, NOT stacked; no assumed inter-row spacing'
    nets('J10',dict(enumerate(['5V_PERIPH','GND','DISP_SCK','DISP_MOSI','RA_MISO','DISP_HARM_CS_N',
        'DISP_RESET_N','I2C_MOD_SDA','I2C_MOD_SCL','TP_INT_MOD','TP_RESET_MOD_N','GND'],1)))
    nets('J11',dict(enumerate(['5V_PERIPH','GND','DISP_SCK','DISP_MOSI','DISP_VIS_CS_N','DISP_VIS_DC',
        'DISP_RESET_N','VIS_BL_EN',None,None,None,'GND'],1)))
    notes[PAGES[2]]=[
      'Custom 12-way harnesses; MUST translate to supplier connector pin numbering.',
      'MSP2401/2402 5V: regulator bypass J1 OPEN; J11.8 drives module BL pin8 via 3.3V buffer.',
      'ER-TFTM070-5V4: order 4-wire SPI + CTP + 5V + internal backlight PWM. Default board is parallel.',
      'J10.10 is MODULE INT, not host TP_INT. J10.8/9 use isolated peripheral I2C.',
      'All signals are 3.3V. Never join module pull-ups to 5V. Verify exact delivered module revision.']
    nets('U12',{11:'I2C_MOD_SDA',12:'I2C_MOD_SCL'})
    # Remove the unprotected three-pin entry, replaced by the keyed two-pin entry below.
    parts.remove(byref['J13'])
    nets('U13',{1:'5V_PERIPH',3:'5V_PERIPH'})
    nets('C30',{1:'5V_PERIPH'})
    notes[PAGES[4]]=[
      'Nano USB powers 3V3_IO. Separate regulated external 5V powers peripheral domain through page14.',
      'DAC_3V3 and 3V3_PERIPH are separate LDO outputs; neither may join Nano 3V3_IO.',
      'PCM5122 I2S inputs are fail-safe LVCMOS (TI SLAS763C); external I2C uses page13 isolator.',
      'AP2112 thermal estimate at 50mA: 85mW. Measure actual supply current and temperature.',
      'J5.1 remains NC. This is NOT a USB power combiner and NOT an overvoltage protector.']
    pg=PAGES[12]
    add(pg,'U14','C544515',270,760,{1:'3V3_IO',2:'I2C_SCL',3:'I2C_SDA',4:'GND',5:'3V3_PERIPH',
        6:'I2C_MOD_SDA',7:'I2C_MOD_SCL',8:'3V3_PERIPH'},
        'TCA9517: A=host, B=peripheral; EN=B rail, never host rail; verify B-side VOL at actual targets')
    add(pg,'U15','C7668',900,760,{1:'GND',19:'GND',20:'3V3_PERIPH',10:'GND',
        2:'BUS_SCK',18:'DISP_SCK',4:'BUS_MOSI',16:'DISP_MOSI',6:'VIS_CS_N',14:'DISP_VIS_CS_N',
        8:'HARM_CS_N',12:'DISP_HARM_CS_N',11:'VIS_DC',9:'DISP_VIS_DC',
        13:'LCD_RESET_N',7:'DISP_RESET_N',15:'TP_RESET_N',5:'TP_RESET_MOD_N',17:'3V3_IO',3:'VIS_BL_EN'},
        'SN74LVC244A: peripheral-powered, Ioff, both OEs low, eighth channel provides backlight enable')
    add(pg,'U16','C7836',1450,760,{1:None,2:'TP_INT_MOD',3:'GND',4:'TP_INT',5:'3V3_IO'},
        'SN74LVC1G17: host-powered Schmitt input, Ioff; ignore touch INT until module initialized')
    for ref,net,x in [('C33','3V3_IO',250),('C34','3V3_PERIPH',600),('C35','3V3_PERIPH',950),('C36','3V3_IO',1300)]:
        two(pg,ref,'C1591',x,350,net,'GND','100nF at U14 A/B, U15, U16 supply pin')
    for i,n in enumerate(['I2C_MOD_SDA','I2C_MOD_SCL']):
        two(pg,f'R{60+i}','C23162',250+i*440,200,'3V3_PERIPH',n,'B-side 4.7k; recalculate parallel module pull-ups and bus capacitance')
    two(pg,'R62','C98220',1150,200,'3V3_PERIPH','TP_INT_MOD','module INT pull-up; verify module polarity and existing pull-up')
    for i,n in enumerate(['BUS_SCK','BUS_MOSI','VIS_DC']):
        two(pg,f'R{63+i}','C25803',250+i*440,60,n,'GND','100k boot bias while FPGA pins Hi-Z')
    notes[pg]=[
      'No extra FPGA pins. Eight buffered outputs include constant backlight enable.',
      'TCA9517 B-side VOL offset requires target VIL check; never cascade B sides.',
      'U11 host-powered return mux already has Ioff; display MISO must tri-state when deselected.',
      'Power-off leakage and hot-plug behavior are DOCUMENT-REVIEWED, not measured.',
      'BUS_SCK/MOSI still clock scan registers: firmware arbitration and complete-word re-latch remain required.']
    pg=PAGES[13]
    header(pg,'J13','C158012',200,820,['5V_IN','GND'],'JST XH 2.5mm keyed 2P; pin1 +5V, pin2 GND; mating housing/contacts required')
    two(pg,'F1','C210834',650,820,'5V_IN','5V_FUSED','Bourns PTC 1.1A hold at 23C; temperature derating applies')
    add(pg,'Q1','C110499',1100,820,{1:'PWR_GATE',2:'5V_PROTECTED',3:'5V_FUSED'},
        'DMP2035U P-channel reverse polarity: D=input S=output G=100k to GND; not reverse-current isolation')
    two(pg,'R66','C25803',1500,820,'PWR_GATE','GND','100k PMOS gate pull-down')
    add(pg,'U17','C55266',650,500,{1:'5V_PROTECTED',2:'GND',3:'3V3_IO',4:'PWR_FAULT_N',5:'PWR_ILIM',6:'5V_PERIPH'},
        'TPS2553 ACTIVE-HIGH constant-current version; enabled by Nano rail, auto-retry/thermal behavior must be tested')
    two(pg,'R67','C22912',1100,500,'PWR_ILIM','GND','23.7k 1%; TI equations with resistor tolerance: about 1.002..1.184A; not system load budget')
    two(pg,'R68','C25803',1500,500,'3V3_PERIPH','PWR_FAULT_N','100k fault pull-up, test pad only, consumes no FPGA input')
    two(pg,'R69','C25803',200,470,'3V3_IO','GND','EN default low if Nano disconnected; 33uA when host on')
    two(pg,'R70','C98220',1500,330,'5V_PERIPH','GND','10k output bleed; no claim of immediate discharge')
    for ref,net,x in [('C37','5V_PROTECTED',200),('C38','5V_PERIPH',650),('C39','3V3_PERIPH',1100)]:
        two(pg,ref,'C1607',x,170,net,'GND','2.2uF ceramic; local input/output decoupling')
    add(pg,'U18','C51118',1100,330,{1:'5V_PERIPH',2:'GND',3:'5V_PERIPH',4:None,5:'3V3_PERIPH'},
        'AP2112 separate digital peripheral 3.3V regulator, output never join DAC or Nano rail')
    for ref,net,x in [('R71','3V3_PERIPH',650),('R72','DAC_3V3',1100),('R73','3V3_IO',1500)]:
        two(pg,ref,'C22548',x,-20,net,'GND','1k rail bleed, 3.3mA / 10.9mW; bounds residual voltage from Ioff, not a substitute for sequencing tests')
    notes[pg]=[
      'External regulated 5V only. Actual existing PSU UNKNOWN: verify label, polarity, load voltage before hookup.',
      'No OV clamp. Do not connect 9V/12V/PD rail. PTC + PMOS + switch voltage drops require full-load check.',
      'Host absent: peripheral switch disabled; page13 buffers isolate I/O. Either power-on order must be bench tested.',
      'TPS2553 limits inrush/current; display capacitance/current unknown. Confirm successful cold-start at lowest input.',
      'R67=23.7k +/-1%: TI equations give approx 1.002..1.184A limit; not a continuous-load rating.',
      'R71..R73=1k rail bleeds: 200uA assumed total injection gives <=0.202V at +1% R; verify actual leakage.',
      'At 0.8A, PTC Rmax=0.21ohm gives 0.168V drop before MOSFET/switch/wires; adapter headroom still open.',
      'PWR_FAULT_N and all supply rails need PCB test pads. This page is NOT a qualified power supply.']

def pages():
    code="""const p=await eda.dmt_Project.getCurrentProjectInfo();if(p?.friendlyName!==__CLI__.args.name)throw new Error('Wrong project');
const old=await eda.dmt_Schematic.getAllSchematicPagesInfo();const sch=old[0].parentSchematicUuid;const result={};
for(let i=0;i<__CLI__.args.names.length;i++){const name=__CLI__.args.names[i];let id=old[i]?.uuid;if(!id)id=await eda.dmt_Schematic.createSchematicPage(sch);if(!id)throw new Error('No page');await eda.dmt_Schematic.modifySchematicPageName(id,name);await eda.dmt_EditorControl.openDocument(id);
await eda.dmt_Schematic.modifySchematicPageTitleBlock(false);
const wires=await eda.sch_PrimitiveWire.getAllPrimitiveId();if(wires.length)await eda.sch_PrimitiveWire.delete(wires);
const comps=await eda.sch_PrimitiveComponent.getAll();if(comps.length)await eda.sch_PrimitiveComponent.delete(comps.map(c=>c.getState_PrimitiveId()));
const texts=await eda.sch_PrimitiveText.getAllPrimitiveId();if(texts.length)await eda.sch_PrimitiveText.delete(texts);await eda.sch_Document.save();result[name]=id;}return result;"""
    ids=invoke('prepare-review-pages',code,{'name':PROJECT.name,'names':PAGES},120)
    (ROOT/'pages.json').write_text(json.dumps(ids,indent=2)+'\n',encoding='utf-8')
    print('pages:',len(ids))

def place(page):
    ids=json.loads((ROOT/'pages.json').read_text())
    items=[p for p in parts if p['page']==page]
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);const result=[];
const old=await eda.sch_PrimitiveComponent.getAll();
for(const p of __CLI__.args.items){let c=old.find(c=>c.getState_Designator()===p.ref);if(!c){c=await eda.sch_PrimitiveComponent.create({libraryUuid:p.libraryUuid,uuid:p.uuid},p.x,p.y,undefined,0,false,true,true);if(!c)throw new Error('Create '+p.ref);const e=c.toAsync();e.setState_Designator(p.ref);await e.done();}
if(c.getState_SupplierId()!==p.code)throw new Error('Supplier mismatch '+p.ref);
const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());result.push({ref:p.ref,id:c.getState_PrimitiveId(),pins:pins.map(q=>({n:q.getState_PinNumber(),name:q.getState_PinName(),x:q.getState_X(),y:q.getState_Y(),r:q.getState_Rotation()}))});}
if(!await eda.sch_Document.save())throw new Error('Save');return result;"""
    placed=[]
    for i in range(0,len(items),20):
        v=invoke(f'placed-{page}-{i//20}',code,{'page':ids[page],'items':items[i:i+20]})
        placed.extend(v)
    (ROOT/f'evidence/pins-{page}.json').write_text(json.dumps(placed,indent=2)+'\n',encoding='utf-8')
    for p in placed:
        expected=next(q for q in items if q['ref']==p['ref'])['nets']
        actual={x['n'] for x in p['pins']}
        if actual!=set(expected):
            raise RuntimeError(f"Pin mismatch {p['ref']}: {actual} vs {set(expected)}; inspect before wiring")
    print(page,'placed',len(placed),flush=True)

def wire(page):
    ids=json.loads((ROOT/'pages.json').read_text())
    items=[p for p in parts if p['page']==page]
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);if((await eda.sch_PrimitiveWire.getAllPrimitiveId()).length)throw new Error('Already wired');
const components=await eda.sch_PrimitiveComponent.getAll();const result=[];
for(const p of __CLI__.args.items){const c=components.find(c=>c.getState_Designator()===p.ref);if(!c)throw new Error('Missing '+p.ref);const pins=await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId());
for(const q of pins){const n=q.getState_PinNumber();if(!(n in p.nets))throw new Error('Unknown pin '+p.ref+'.'+n);const net=p.nets[n];if(net===null){const e=q.toAsync();e.setState_NoConnected(true);await e.done();continue;}
const x=q.getState_X(),y=q.getState_Y(),r=q.getState_Rotation();const dx=r===0?80:r===180?-80:0,dy=r===90?80:r===270?-80:0;if(!dx&&!dy)throw new Error('Rotation');
if(!await eda.sch_PrimitiveWire.create([x,y,x+dx,y+dy],net))throw new Error('Wire');if(!await eda.sch_PrimitiveComponent.createNetPort('BI',net,x+dx,y+dy,r))throw new Error('Label');result.push([p.ref,n,net]);}}
const allPins=[];for(const c of components)allPins.push(...await eda.sch_PrimitiveComponent.getAllPinsByPrimitiveId(c.getState_PrimitiveId()));
const top=Math.max(...allPins.map(p=>p.getState_Y()))+100,bottom=Math.min(...allPins.map(p=>p.getState_Y()))-130;
await eda.sch_PrimitiveText.create(60,top,__CLI__.args.title+' - REVIEW CANDIDATE / NOT FOR FABRICATION',0,null,null,16,true);
for(let i=0;i<__CLI__.args.notes.length;i++)await eda.sch_PrimitiveText.create(60,bottom-i*22,__CLI__.args.notes[i],0,null,null,10,false);
if(!await eda.sch_Document.save())throw new Error('Save');return {connected:result.length};"""
    result=invoke('wired-'+page,code,{'page':ids[page],'items':items,'title':page,'notes':notes[page]},120)
    print(page,'wired',result,flush=True)

def export():
    ids=json.loads((ROOT/'pages.json').read_text())
    out=PROJECT/'review-exports';out.mkdir(exist_ok=True)
    code="""await eda.dmt_EditorControl.openDocument(__CLI__.args.page);
const n=await eda.sch_ManufactureData.getNetlistFile('dual-screen-review','Protel2');if(!n)throw new Error('No netlist');
const b=await eda.sch_ManufactureData.getBomFile('dual-screen-review','csv');if(!b)throw new Error('No BOM');
const png=await eda.sch_ManufactureData.getPngFile('dual-screen-review',{width:4500});if(!png)throw new Error('No image');
const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.out,png,undefined,true);if(!saved)throw new Error('PNG save');
return {netlist:await n.text(),bomBytes:Array.from(new Uint8Array(await b.arrayBuffer())),image:{name:png.name,size:png.size,saved},drc:await eda.sch_Drc.check(true,false,true)};"""
    v=invoke('native-exports',code,{'page':ids[PAGES[0]],'out':(out/'dual-screen-review.zip').as_posix()},150)
    (ROOT/'native-protel.net').write_text(v['netlist'],encoding='utf-8')
    raw=bytes(v['bomBytes']);encoding='utf-16' if raw[:2] in [b'\xff\xfe',b'\xfe\xff'] else 'utf-8-sig'
    (ROOT/'native-bom.tsv').write_text(raw.decode(encoding),encoding='utf-8')
    (ROOT/'native-drc.json').write_text(json.dumps(v['drc'],ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('export',v['image'],'drc',v['drc'],flush=True)

if __name__=='__main__':
    schema()
    mode=sys.argv[1]
    if mode=='pages':pages()
    elif mode=='place':
        for page in PAGES:place(page)
    elif mode=='wire':
        for page in PAGES:wire(page)
    elif mode=='export':export()
