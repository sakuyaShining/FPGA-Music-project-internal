import json
from phase import ROOT,invoke

def main():
    code="""await eda.dmt_EditorControl.openDocument('ba336973a1f81bda');const f=await eda.sch_ManufactureData.getNetlistFile('slider-prototype','Protel2');if(!f)throw new Error('No netlist');return {name:f.name,size:f.size,text:await f.text()};"""
    v=invoke('native-protel-netlist',code)
    (ROOT/'native-protel.net').write_text(v['text'],encoding='utf-8')
    print('netlist',v['name'],v['size'])
    v=invoke('native-schematic-drc',"return await eda.sch_Drc.check(true,false,true);")
    print('DRC',json.dumps(v,ensure_ascii=True)[:5500])

if __name__=='__main__':main()
