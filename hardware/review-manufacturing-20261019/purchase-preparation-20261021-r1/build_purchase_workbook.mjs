import fs from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { Workbook, SpreadsheetFile } from '@oai/artifact-tool';
const root=path.dirname(fileURLToPath(import.meta.url));
const data=JSON.parse(await fs.readFile(path.join(root,'purchase-master.json'),'utf8'));
const out=path.join(root,'outputs','01a158ca-15fe-7ea2-8a60-ba5ae6a61281');
await fs.mkdir(out,{recursive:true});
const wb=Workbook.create();
const main=wb.worksheets.add('采购总表');
const board=wb.worksheets.add('板上物料');
const cable=wb.worksheets.add('小屏接线');
const pending=wb.worksheets.add('待关闭事项');
const ink='#213547',navy='#28445c',amber='#fff1ce',red='#fbe3e1';
function base(s,last,rows){
 s.showGridLines=false;
 s.getRange(`A1:${last}${rows}`).format.font={name:'Microsoft YaHei',size:10,color:ink};
 s.getRange(`A1:${last}${rows}`).format.verticalAlignment='center';
}
function title(s,text){s.getRange('A2').values=[[text]];s.getRange('A2').format.font={name:'Microsoft YaHei',size:16,bold:true,color:ink};}
function headers(s,range,values){s.getRange(range).values=[values];s.getRange(range).format={fill:navy,font:{name:'Microsoft YaHei',size:10,bold:true,color:'#ffffff'},horizontalAlignment:'center',verticalAlignment:'center',rowHeight:30};}
function width(s,col,px){s.getRange(`${col}1:${col}70`).format.columnWidthPx=px;}

const end=6+data.external_items.length;
base(main,'I',end);title(main,'双屏乐器硬件采购准备');main.tabColor=navy;
main.getRange('A3').values=[['一套乐器。217个贴片位号含按键交工厂供料，13个通孔位号手焊；人民币到手价尚未取得。']];
main.getRange('A4').values=[['2026-10-21：覆盖36类板上物料和32项外部范围。当前PCB与大屏尚未放行下单。']];
headers(main,'A6:G6',['编号','项目','型号或加工规格','数量','单位','当前准备状态','下单前条件']);
headers(main,'I6:I6',['资料来源（不等于报价）']);
main.getRange(`A7:G${end}`).values=data.external_items.map(p=>[p.id,p.item,p.spec,p.quantity,p.unit,p.stage,p.action]);
main.getRange(`I7:I${end}`).values=data.external_items.map(p=>[p.url]);
main.getRange(`A7:G${end}`).format.rowHeight=72;
main.getRange(`B7:C${end}`).format.wrapText=true;
main.getRange(`F7:G${end}`).format.wrapText=true;
main.getRange(`D7:D${end}`).format.numberFormat='0';
main.getRange(`F7:F${end}`).conditionalFormats.add('containsText',{text:'暂缓',format:{fill:amber,font:{color:'#855b0b'}}});
main.getRange(`I7:I${end}`).format.font={name:'Microsoft YaHei',size:9,color:'#566879'};
[['A',55],['B',175],['C',330],['D',55],['E',55],['F',200],['G',470],['H',25],['I',760]].forEach(([c,n])=>width(main,c,n));
main.freezePanes.freezeRows(6);main.freezePanes.freezeColumns(2);
main.tables.add(`A6:G${end}`,true,'ExternalScope').showFilterButton=true;

const bstart=8,bend=7+data.board_bom.length;
base(board,'P',bend);title(board,'板上物料与供料分工');
board.getRange('A3:B4').values=[['SMT板数（报价假设）',2],['补焊接口板数',1]];
board.getRange('B3:B4').format.fill=amber;board.getRange('B3:B4').format.font={name:'Microsoft YaHei',size:10,color:'#1e5cad'};
board.getRange('D3:D5').values=[['每板全部位号'],['每板SMT位号'],['每板手焊位号']];
board.getRange('E3').formulas=[[`=SUM(C${bstart}:C${bend})`]];
board.getRange('E4').formulas=[[`=SUMIFS(C${bstart}:C${bend},D${bstart}:D${bend},"工厂SMT供料")`]];
board.getRange('E5').formulas=[['=E3-E4']];
board.getRange('G3').values=[['黄色为可修改的装配数量。第二块SMT板作备份，不自动增加第二套屏幕。']];
board.getRange('G4').values=[['本批用量按实际工厂/手焊分工计算。SMT行散买量为0，避免重复买料。']];
board.getRange('G5').values=[['库存为公开LCSC目录快照，不能证明国内SMT库存。没有填入伪整机总价。']];
headers(board,'A7:M7',['C料号','型号','单板用量','装配分工','本批用量','自购备件','散买MOQ','采购倍数','散买数量','目录库存','散买状态','封装','完整位号']);
headers(board,'O7:P7',['购买来源','核查UTC时间']);
board.getRange(`A${bstart}:M${bend}`).values=data.board_bom.map(p=>[p.code,p.mpn,p.per_board,p.assembly,null,p.repair_spares,p.minimum,p.multiple,null,p.stock,null,p.footprint,p.refs]);
board.getRange(`O${bstart}:P${bend}`).values=data.board_bom.map(p=>[p.url,new Date(p.checked_utc)]);
board.getRange(`P${bstart}:P${bend}`).format.numberFormat='yyyy-mm-dd hh:mm';
for(let i=0;i<data.board_bom.length;i++){
 const r=bstart+i;
 board.getRange(`E${r}`).formulas=[[`=C${r}*IF(D${r}="工厂SMT供料",$B$3,$B$4)`]];
 board.getRange(`I${r}`).formulas=[[`=IF(D${r}="工厂SMT供料",0,CEILING(MAX(E${r}+F${r},G${r}),H${r}))`]];
 board.getRange(`K${r}`).formulas=[[`=IF(I${r}=0,"工厂匹配供料",IF(J${r}>=I${r},"目录数量足够","散买缺货"))`]];
 const n=data.board_bom[i].refs.length;
 board.getRange(`A${r}:M${r}`).format.rowHeight=Math.max(44,Math.ceil(n/85)*16);
}
board.getRange(`B${bstart}:B${bend}`).format.wrapText=true;
board.getRange(`L${bstart}:M${bend}`).format.wrapText=true;
board.getRange(`C${bstart}:C${bend}`).format.numberFormat='0';board.getRange(`E${bstart}:J${bend}`).format.numberFormat='#,##0';
board.getRange(`K${bstart}:K${bend}`).conditionalFormats.add('containsText',{text:'缺货',format:{fill:red,font:{color:'#9b2727',bold:true}}});
[['A',90],['B',250],['C',80],['D',125],['E',85],['F',80],['G',80],['H',80],['I',85],['J',100],['K',165],['L',300],['M',700],['N',25],['O',650],['P',230]].forEach(([c,n])=>width(board,c,n));
board.getRange('A3:A4').format.columnWidthPx=155;
board.freezePanes.freezeRows(7);board.freezePanes.freezeColumns(2);
board.tables.add(`A7:M${bend}`,true,'BoardMaterials').showFilterButton=true;

base(cable,'H',21);title(cable,'MSP2401 小屏转接线');
cable.getRange('A3').values=[['厂家通用资料与当前载板焊盘已核对；成品线仍需确认模块版号、公母、朝向并逐线测通断。']];
cable.getRange('A4').values=[['5V供电时模块J1断开。数字IO为3.3V。下表是错位映射，不能按相同针号直连。']];
headers(cable,'A6:F6',['载板接口','载板脚号','载板网络','模块','模块脚号','模块信号']);
cable.getRange('A7:F14').values=data.small_screen_harness.map(p=>[p.carrier,p.carrier_pin,p.net,p.module,p.module_pin,p.module_label]);
cable.getRange('A7:F14').format.rowHeight=30;
cable.getRange('A16').values=[['模块9 SDO不接；10–14触摸端不使用。载板9–11 NC，12为备用GND。']];
cable.getRange('A18').values=[['资料来源：https://www.lcdwiki.com/2.4inch_SPI_Module_ILI9341_SKU:MSP2402']];
[['A',130],['B',100],['C',240],['D',140],['E',100],['F',140],['G',25],['H',500]].forEach(([c,n])=>width(cable,c,n));

const issues=[
 ['PCB',`${data.hardware_checkpoint.unconnected_errors}项未连通，${data.hardware_checkpoint.pending_nets}网；I²S换层和回流待整理`,'当前局部供电网已闭合；继续联合出线，重建地铜并复跑原生DRC','阻止定制板投产'],
 ['扫描接口','复位字高位、节点映射冲突已有独立候选通过','接入真实产品复位/共享总线控制器，做完整联合回归和PnR','尚未产品集成'],
 ['大屏','确切SPI/5V/CTP出货SKU、针脚和整价未闭合','取得同一出货版本的完整机械/接口图和含触摸整价','阻止大屏最终订货与线束'],
 ['小屏','型号选MSP2401，已完成错位接线表','核实际商品版、公母/视角及含运价；到货后点亮验证','资料推进，实物待验'],
 ['供电','真实双屏启动/稳态电流、压降和热未测','用实际负载替换假设，验证F1/R67与掉电/反灌','阻止电源链冻结'],
 ['传感','覆盖层/电极/寄生/漂移及连续位置未实测','先做少量三电极小样，再确定完整电极几何','阻止电极板最终制造'],
 ['结构','面板与载板、孔位/高度/按钮旋钮未配准','据确切模块和Nano实物完成装配图/纸样','阻止外壳加工与直接叠插'],
 ['供料','C318884散买0但国内页面有贴片库存；已把5按键改交工厂','最终平台匹配217个SMT位号，核按键上料费及连接器机械图','供料路径已选，待匹配报价'],
 ['固件','86号联合结构探针路由失败，没有最终整机码流','保留既定功能完成产品顶层/驱动、约束、联合PnR/STA','阻止整机调试签收'],
 ['功能','完整录放/TF文件/最终混音/保存和实体UI未形成最终闭环','继承已有数字成果，逐项系统验证','目标仍待完成'],
 ['交互','25/26端点、MIDI基准和部分作用范围未冻结','查回用户已有决定；硬件仍保留84容量','不阻断通用电子件准备'],
 ['制造报价','同版Gerber/钻孔/BOM/CPL/DFM和完整人民币报价未完成','先完成设计和真实平台匹配，再交用户下单','制造放行仍为false']
];
base(pending,'D',19);title(pending,'仍需关闭的事项');
headers(pending,'A5:D5',['类别','当前问题','下一步','当前影响']);
pending.getRange('A6:D17').values=issues;pending.getRange('A6:D17').format.rowHeight=70;pending.getRange('B6:D17').format.wrapText=true;
[['A',100],['B',430],['C',500],['D',230]].forEach(([c,n])=>width(pending,c,n));
pending.freezePanes.freezeRows(5);
pending.tables.add('A5:D17',true,'PendingActions').showFilterButton=true;

wb.recalculate();
const summary=await wb.inspect({kind:'table',range:'板上物料!D3:E5',include:'values,formulas',tableMaxRows:3,tableMaxCols:2,maxChars:1500});
const errs=await wb.inspect({kind:'match',searchTerm:'#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!',options:{useRegex:true,maxResults:100},maxChars:2500});
await fs.writeFile(path.join(root,'workbook-checks.json'),JSON.stringify({summary:summary.ndjson,errors:errs.ndjson},null,2));
console.log(summary.ndjson);console.log(errs.ndjson);
// Meaningful boundary check: changing assembly count changes SMT but not hand assembly.
const firstSMT=data.board_bom.findIndex(p=>p.assembly==='工厂SMT供料')+bstart;
const before=board.getRange(`E${firstSMT}`).values[0][0];
board.getRange('B3').values=[[3]];wb.recalculate();
const changed=board.getRange(`E${firstSMT}`).values[0][0];
if(changed*2!==before*3)throw new Error('Assembly count does not recalculate');
board.getRange('B3').values=[[2]];wb.recalculate();
const manualRow=data.board_bom.findIndex(p=>p.assembly==='手焊通孔')+bstart;
const stockBefore=board.getRange(`J${manualRow}`).values[0][0];
board.getRange(`J${manualRow}`).values=[[0]];wb.recalculate();
if(board.getRange(`K${manualRow}`).values[0][0]!=='散买缺货')throw new Error('Missing-stock warning disappeared');
board.getRange(`J${manualRow}`).values=[[stockBefore]];wb.recalculate();
if(board.getRange(`K${manualRow}`).values[0][0]!=='目录数量足够')throw new Error('Stock update failed to recalculate');
for(const [s,range,file] of [[main,'A1:G14','purchase-preview.png'],[main,'A13:G19','connector-scope-preview.png'],[main,'A30:G33','mechanical-scope-preview.png'],[board,'A1:K15','board-preview.png'],[cable,'A1:F18','harness-preview.png'],[pending,'A1:D17','issues-preview.png']]){
 const preview=await wb.render({sheetName:s.name,range,scale:1.25,format:'png'});
 await fs.writeFile(path.join(root,file),new Uint8Array(await preview.arrayBuffer()));
}
const book=await SpreadsheetFile.exportXlsx(wb);const final=path.join(out,'硬件采购准备-r1.xlsx');await book.save(final);
await fs.writeFile(path.join(root,'workbook-output.json'),JSON.stringify({path:final,assembly_count_recalculation_verified:true,sheets:4,manufacturing_release:false},null,2));
console.log('EXPORTED',final);
