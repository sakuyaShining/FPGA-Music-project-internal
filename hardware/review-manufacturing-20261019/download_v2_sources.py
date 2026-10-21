import hashlib,json,time
from pathlib import Path
from urllib.request import Request,urlopen
from native_review import ROOT

out=Path('D:/FPGA-Project/codex-deliverables/dual-screen-review-20261020-v2/sources');out.mkdir(parents=True,exist_ok=True)
urls={
 'TI-TPS2553.pdf':'https://www.ti.com/lit/ds/symlink/tps2553.pdf',
 'Bourns-MF-MSMF.pdf':'https://www.bourns.com/docs/Product-Datasheets/mfmsmf.pdf',
 'DIODES-DMP2035U.pdf':'https://www.diodes.com/assets/Datasheets/DMP2035U.pdf',
 'TI-TPS22918.pdf':'https://www.ti.com/lit/ds/symlink/tps22918.pdf',
 'TI-TCA9517.pdf':'https://www.ti.com/lit/ds/symlink/tca9517.pdf',
 'TI-SN74LVC244A.pdf':'https://www.ti.com/lit/ds/symlink/sn74lvc244a.pdf',
 'TI-SN74LVC1G17.pdf':'https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf',
 'MSP2402-schematic.pdf':'https://www.lcdwiki.com/res/MSP2402/MSP2402-2.4-SPI.pdf',
 'MSP2401-mechanical.pdf':'https://www.lcdwiki.com/res/MSP2402/MSP2401_Size.pdf',
 'MSP2402-user-manual.pdf':'https://www.lcdwiki.com/res/MSP2402/2.4inch_SPI_Module_MSP2402_User_Manual_EN.pdf',
 'ER-TFTM070-5V4.pdf':'https://www.buydisplay.com/download/manual/ER-TFTM070-5V4_Datasheet.pdf'
}
rows=[]
for name,url in urls.items():
    target=out/name;row={'file':name,'url':url}
    try:
        if target.exists():raw=target.read_bytes()
        else:
            with urlopen(Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20) as r:raw=r.read()
            assert raw.startswith(b'%PDF'),'Not PDF';target.write_bytes(raw)
        row.update(status='downloaded',sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    except Exception as e:row.update(status='unavailable',error=str(e))
    rows.append(row);print(name,row['status'],flush=True);time.sleep(0.5)
(ROOT/'evidence/v2/source-manifest.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8')
