const out = {};
const safe = async (k, fn) => {
	try { out[k] = await fn(); }
	catch (e) { out[k] = 'ERR: ' + ((e && e.message) ? e.message : String(e)); }
};

await safe('ruleConfigName', () => eda.pcb_Drc.getCurrentRuleConfigurationName());
await safe('defaultRuleConfigName', () => eda.pcb_Drc.getDefaultRuleConfigurationName());
await safe('ruleConfig', async () => {
	const c = await eda.pcb_Drc.getCurrentRuleConfiguration();
	return c;
});
await safe('netClasses', async () => {
	const c = await eda.pcb_Drc.getAllNetClasses();
	return Array.isArray(c) ? c.map(x => x.name) : c;
});

return out;
