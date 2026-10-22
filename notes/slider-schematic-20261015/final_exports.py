import json
from phase import ROOT,PROJECT,invoke
out=PROJECT/'schematic-draft-exports'
code="""const f=await eda.sch_ManufactureData.getPngFile('prototype-schematic',{width:3000});if(!f)throw new Error('No image');const saved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.image,f,undefined,true);const b=await eda.sch_ManufactureData.getBomFile('prototype-bom','csv');if(!b)throw new Error('No BOM');const bomSaved=await eda.sys_FileSystem.saveFileToFileSystem(__CLI__.args.bom,b,undefined,true);return {image:{name:f.name,size:f.size,saved},bom:{name:b.name,size:b.size,saved:bomSaved},pages:await eda.dmt_Schematic.getAllSchematicPagesInfo()};"""
v=invoke('final-exports',code,{'image':(out/'prototype-schematic.zip').as_posix(),'bom':(out/'prototype-bom.tsv').as_posix()})
print(json.dumps({k:v[k] for k in ['image','bom']},ensure_ascii=True))
