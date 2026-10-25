const out = {};
const PCB = 'c3fd8656cf425e9f';

try { out.tabId = await eda.dmt_EditorControl.openDocument(PCB); }
catch (e) { out.openErr = e.message; }

await new Promise(r => setTimeout(r, 6000));

try {
	const d = await eda.dmt_SelectControl.getCurrentDocumentInfo();
	out.doc = d ? { documentType: d.documentType, title: d.title || d.name } : null;
} catch (e) { out.docErr = e.message; }

try {
	const t = await eda.dmt_EditorControl.getSplitScreenTree();
	out.tabs = t.tabs.map(x => x.title);
} catch (e) { }

try {
	const nets = await eda.pcb_Net.getAllNetsName();
	out.netCount = nets ? nets.length : null;
	out.sample = nets ? nets.slice(0, 12) : null;
} catch (e) { out.netsErr = e.message; }

const targets = ['ADDR0', 'ADDR1', 'ADDR2', 'ADDR3', 'MUX_DISABLE', 'KEY_QH',
	'PRESET1', 'PRESET2', 'EDIT', 'ENC_A', 'ENC_B', 'ENC_PUSH',
	'BUS_SCK', 'INPUT_LOAD_N', 'RC_DRIVE', '3V3_IO'];

out.lengths = {};
for (const n of targets) {
	try { out.lengths[n] = await eda.pcb_Net.getNetLength(n); }
	catch (e) { out.lengths[n] = 'ERR'; }
}

return out;
