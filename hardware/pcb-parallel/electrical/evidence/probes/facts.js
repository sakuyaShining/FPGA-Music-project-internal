const out = {};
const safe = async (k, fn) => {
	try { out[k] = await fn(); }
	catch (e) { out[k] = 'ERR: ' + ((e && e.message) ? e.message : String(e)); }
};

await safe('components', async () => {
	const ids = await eda.pcb_PrimitiveComponent.getAllPrimitiveId();
	return ids ? ids.length : null;
});

await safe('pads', async () => {
	const ids = await eda.pcb_PrimitivePad.getAllPrimitiveId();
	return ids ? ids.length : null;
});

await safe('vias', async () => {
	const ids = await eda.pcb_PrimitiveVia.getAllPrimitiveId();
	return ids ? ids.length : null;
});

await safe('lines', async () => {
	const ids = await eda.pcb_PrimitiveLine.getAllPrimitiveId();
	return ids ? ids.length : null;
});

await safe('pours', async () => {
	const ids = await eda.pcb_PrimitivePour.getAllPrimitiveId();
	return ids ? ids.length : null;
});

await safe('layers', async () => {
	const ls = await eda.pcb_Layer.getAllLayers();
	if (!Array.isArray(ls)) return ls;
	return ls.map(l => ({
		id: l.id !== undefined ? l.id : l.layerId,
		name: l.name,
		type: l.type
	}));
});

await safe('stackup', async () => {
	const s = await eda.pcb_Layer.getCurrentPhysicalStackingConfiguration();
	return s;
});

return out;
