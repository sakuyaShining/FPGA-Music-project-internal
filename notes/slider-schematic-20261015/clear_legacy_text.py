from phase import invoke
code="""await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const removed=[];for(const t of await eda.sch_PrimitiveText.getAll()){const content=t.getState_Content();if(!content)continue;if(content.includes('SOURCING REVIEW')||content.includes('KEYPARTS')||content.includes('KEY PARTS')){const id=t.getState_PrimitiveId();const ok=await eda.sch_PrimitiveText.delete(id);if(!ok)throw new Error('Legacy text delete failed');removed.push({id,content});}}return {removed,saved:await eda.sch_Document.save()};"""
print(invoke('removed-legacy-review-text',code))
