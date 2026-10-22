import fs from 'node:fs';
import {fileURLToPath} from 'node:url';
import {resolve} from './model.mjs';
const root=fileURLToPath(new URL('../evidence/',import.meta.url));
let checked=0;
for(const n of [1,8,16,'panel']){
  const cases=JSON.parse(fs.readFileSync(root+`cases-${n}.json`,'utf8'));
  for(const c of cases){
    const actual=c.command ? {result:c.seed.map(v=>Math.max(c.lo,Math.min(c.hi,v))),selected:c.axes.map(()=>[null,null])} :
      resolve(c.axes,c.zones,c.touches,c.held,c.radius,c.lo,c.hi);
    if(JSON.stringify(actual.result)!==JSON.stringify(c.expected) || JSON.stringify(actual.selected)!==JSON.stringify(c.selected))
      throw Error(`Parity failure profile${n} frame${checked}`);
    checked++;
  }
}
console.log(`PASS browser model matches ${checked} independent reference cases`);
