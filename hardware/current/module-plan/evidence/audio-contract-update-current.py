from pathlib import Path
import datetime, hashlib, json

B = Path(r'D:\FPGA-Project\codex-deliverables\dual-screen-review-20261020-v2')
E = B / 'module-plan-current-evidence'
def read(p): return json.loads(p.read_text(encoding='utf-8-sig'))
def save(p, d): p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
now = datetime.datetime.now().astimezone().isoformat()

# Only audit existing CAD files; no editor, native file or producer writes.
pres = read(E / 'sensor-front-native-preservation-and-snapshot-current.json')
expected = {r['file']: r['after'] for r in pres['protected_native_files']}
for r in pres['candidate_files']: expected[r['native']] = r['sha256']
native_checks = [{'file': p, 'expected': h, 'actual': sha(Path(p))} for p, h in expected.items()]
assert all(r['expected'] == r['actual'] for r in native_checks), 'Native state changed; inspect before publication'
audio = read(E / 'audio-010313400000-pin-coverage-current.json')
source = read(E / 'audio-registered-source-current.json')
source_checks = [{'file': p, 'sha256': sha(Path(p)), 'expected': r['sha256']} for p, r in source['read_sources'].items()]
assert all(r['sha256'] == r['expected'] for r in source_checks), 'Registered audio sources changed'
mapping = read(B / 'purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json')
assert len(mapping['records']) == 227 and all(r['function_retained'] for r in mapping['records'])
assert not mapping['module_mapping_complete'] and mapping['module_fully_verified_covered'] == 0

files = [
 'audio-010313400000-pin-coverage-current.json',
 'audio-010313400000-original17-map-current.json',
 'audio-010313400000-wiring-current.md',
 'audio-registered-source-current.json',
 'audio-playback-sourcing-current.json',
 'Spotpear-audio-DAC-amp-review-current.png',
 'Spotpear-audio-header-review-current.png',
 'Spotpear-audio-routing-review-current.png',
 'Spotpear-PCM5122-mode-straps-detail-current.png',
 'XHX-3525BOX-4ohm3W-datasheet.pdf',
 'XHX-3525BOX-spec-page2-current.png',
 'XHX-3525BOX-response-page5-current.png',
 'audio-contract-update-current.py'
]
event = {
 'at': now, 'state': 'AUDIO_PIN_AND_SUBFUNCTION_CONTRACT_SAVED_NOT_PURCHASE_RELEASE',
 'SKU': '010313400000', 'listed_CNY': 55,
 'contract': str(E / files[0]), 'readable_wiring': str(E / files[2]),
 'original_audio_items': 17, 'schematic_subfunctions_confirmed': 11,
 'pending_original_references': ['R41', 'R42', 'C27', 'C28', 'J12', 'R72'],
 'all227functions_retained': True, 'fully_accepted_module_coverage': 0,
 'DAC_7bit_address': '0x4D', 'TPA_7bit_address': '0x60',
 'firmware_finding': 'F07: registered producer clock1.6875MHz/52.734375kHz,16bit duplicatedslots; full PCM PLL/format/TPA initialization and independent stereo product acceptance pending',
 'playback_sourcing': str(E / 'audio-playback-sourcing-current.json'),
 'excluded': ['FIT0502 actual out of stock', '3525BOX low-cost speaker F0=1.5kHz, not selected as sole music playback'],
 'candidate_only': ['DFR0119-O 8.50CNY in stock, still needs compatible speakers/level/harness', 'R12U complete stereo analogue-input candidate, domestic quote/delivery pending'],
 'native_file_hashes_verified': len(native_checks), 'native_files_changed_this_turn': False,
 'RTL_build_flash_changed': False, 'messages_orders_payments': False,
 'whole_plan_ready': False, 'physical_tests': 'UNMEASURED'
}
checkpoint = {'at': now, 'event': event, 'native_file_checks': native_checks, 'registered_audio_source_checks': source_checks}
save(E / 'audio-contract-checkpoint-current.json', checkpoint)
files += ['audio-contract-checkpoint-current.json']
ev = read(B / '模块方案-当前证据.json')
ev['updated_at'] = now
ev['audio_candidate'].update(pin_contract=files[0], readable_wiring=files[2], DAC_7bit_address='0x4D', headphone_amp_7bit_address='0x60', original_items_reviewed=17, schematic_subfunctions_confirmed=11, pending_original_references=event['pending_original_references'], initialization_and_shipping_and_full_coverage_unaccepted=True)
ev['audio_current_stage'] = event
ev['audio_playback_sourcing'] = 'module-plan-current-evidence/audio-playback-sourcing-current.json'
if 'F07' not in ev['firmware_contract_findings']['ids']: ev['firmware_contract_findings']['ids'].append('F07')
ev['firmware_contract_findings']['audio_source'] = str(E / 'audio-registered-source-current.json')
for name in files: ev['evidence_sha256']['module-plan-current-evidence/' + name] = sha(E / name)
ev['evidence_sha256']['purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json'] = sha(B / 'purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json')
save(B / '模块方案-当前证据.json', ev)

next_action = 'Main path remains complete module/simple hybrid procurement <=700CNY. Read audio-010313400000-wiring-current.md and audio-playback-sourcing-current.json: exact55CNYDAC pins/0x4D+0x60 and17item mapping saved;11schematic subfunctions only,6uncovered andF07 init/format pending. Next close preweld84front-end/control/power-isolation quote and assembly, complete stereo playback/line cable and final screen landed quote, total accessories and producer compatibility. ExistingSensor14Bank91TopCu/36GNDvias remains21nets56items open; whole14electrode group order required before native continuation. Do not replay terminal apply/routing jobs or restart original complexPCB solver.'
for name in ['PCB-CURRENT-CAPACITY-RECOVERY-20261024.json', 'PCB-ACTIVE-WORK.json', '实体交付当前入口.json']:
 d = read(B / name)
 d['updated_at'] = now
 d['audio_current_stage'] = event
 d['next_action'] = next_action
 d['latest_followup'] = str(B / '模块方案-当前证据.json')
 rf = d.setdefault('read_first', [])
 for p in [E / 'audio-010313400000-wiring-current.md', E / 'audio-playback-sourcing-current.json']:
  if str(p) not in rf: rf.append(str(p))
 save(B / name, d)

md = B / '模块方案-当前工作单.md'
text = md.read_text(encoding='utf-8-sig')
marker = '\n## 当前音频接口与可买发声链核对'
text = text.split(marker)[0] + marker + '\n\n'
text += '55元斑梨SKU010313400000的逐针接线、I2C地址和原17件音频电路映射已保存到 `module-plan-current-evidence/audio-010313400000-wiring-current.md`。MODE2经R21拉高，MODE1/ADR2接地、ADR1拉高，DAC7位地址为0x4D，耳放0x60。早期低分辨率误将GPIO6的NC看成MODE2，已用原PDF高倍图纠正；不存在已证实的模式接法缺陷。\n\n'
text += '本轮仅确认11项原理图子功能覆盖，R41/R42/C27/C28输出滤波、J12接线与真实播放负载、R72关断泄放仍未覆盖验收。原227功能全部保留，完整模块已验收覆盖数仍为0。音频板的DAC稳压器不能代替整机3V3_PERIPH；P1.1/17独立3V3标签与VCC未示相连，保持不接；I2C仍需要原功能的断电隔离。\n\n'
text += '只读登记producer实际27MHz/DIV_BCK16/每帧32位，推得BCK1.6875MHz与LRCK52.734375kHz，两16位槽当前复制相同样本。增加F07：软件模式、接地SCK的PCM5122需要明确BCK参考PLL/分频与样本格式；耳放默认通道未启用，需0x60寄存器初始化。条件LTJ16格式寄存器为页0寄存器40=0x30，尚未批准为完整启动表。当前没有修改RTL、构建、烧录或向其他聊天发消息，不能声称该音频板接线后即可直接运行。\n\n'
text += 'DFRobot DFR0119-O实际页面8.50元/有货，贴片已装、排针/导线需自行焊，作为立体声功放候选；尚缺扬声器、输入电平、全部配线/电源。FIT0502实际页面缺货，不能沿用索引现货。云汉3525BOX-4Ω3W-2P1.25实际2.4444元/4只库存，但原厂标F0=1500Hz±20%、有效F0至20kHz，不选作乐器唯一发声器。成品Edifier R12U官方确认USB供电、模拟AUX立体声与音量旋钮，可减少组装；国内唯一卖家/含运价/到货仍未核实，不列为已定采购。证据见 `module-plan-current-evidence/audio-playback-sourcing-current.json`。\n\n'
text += '全部已知价格只是分项：DAC55元；DAC+DFR功放63.50元，均未含扬声器/配线/供电/运费/其余子系统。完整700元预算仍未闭合。现有小板和原951及14页本轮哈希核验未变。下一步优先完整84前端/控制保护预焊实现与费用、屏报价及整机驱动契约，不重开复杂主板或重放终态布线。\n'
md.write_text(text, encoding='utf-8')
save(E / 'audio-current-stage-file-map.json', {'at': now, 'evidence_files': files, 'mapping_source': str(B / 'purchase-preparation-20261021-r1/227件功能分块与混合方案映射-current.json')})
print(json.dumps({'saved': True, 'native_hashes': len(native_checks), 'audio_sources_unchanged': len(source_checks), 'functions_retained': 227, 'evidence_files': len(files)}, ensure_ascii=False))
