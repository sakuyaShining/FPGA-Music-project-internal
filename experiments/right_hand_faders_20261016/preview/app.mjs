import {resolve} from './model.mjs';
const canvas=document.querySelector('#surface'),ctx=canvas.getContext('2d');
const axes=Array.from({length:8},(_,i)=>i*100+50),zones=axes.map((_,i)=>[i*100,(i+1)*100]);
const lo=52,hi=420,points=new Map(),drag=new Map(),colors=['#d77c3b','#7659b2','#2e8c95','#c34f6a','#668f30'];
const touchIDs=new Map();
let held=axes.map(()=>hi),selection=axes.map(()=>[null,null]),radius=50,trace=[];
let touchFramePending=false;
function scheduleTouchCommit(){
  if(touchFramePending)return;
  touchFramePending=true;
  requestAnimationFrame(()=>{touchFramePending=false;commit()});
}
function commit(){
  const touches=[...points.values()].map(({id,x,y})=>({id,x,y}));
  const next=resolve(axes,zones,touches,held,radius,lo,hi);held=next.result;selection=next.selected;
  trace.push({touches,held:[...held],selected:selection.map(s=>[...s]),radius});
  if(trace.length>2000)trace.shift();
  draw();
}
function draw(){
  ctx.clearRect(0,0,800,480);ctx.font='14px Microsoft YaHei';ctx.textAlign='center';
  axes.forEach((x,i)=>{
    ctx.fillStyle=i%2?'#f7f8f2':'#fffdf8';ctx.fillRect(i*100,0,100,480);
    ctx.fillStyle='#e5eee7';ctx.fillRect(Math.max(i*100,x-radius),lo,Math.min((i+1)*100,x+radius)-Math.max(i*100,x-radius),hi-lo);
    ctx.strokeStyle='#d2d8cd';ctx.beginPath();ctx.moveTo(i*100,0);ctx.lineTo(i*100,480);ctx.stroke();
    ctx.fillStyle='#34483d';ctx.fillText(`第 ${i+1} 组`,x,28);
    ctx.strokeStyle='#c6d1c6';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(x,lo);ctx.lineTo(x,hi);ctx.stroke();
    ctx.strokeStyle='#43846b';ctx.lineWidth=5;ctx.beginPath();ctx.moveTo(x,hi);ctx.lineTo(x,held[i]);ctx.stroke();
    const ids=[...new Set(selection[i].filter(id=>id!==null))];
    ctx.setLineDash([4,4]);ctx.lineWidth=1.5;
    for(const id of ids){const p=points.get(id);if(!p)continue;ctx.strokeStyle=colors[id%colors.length];ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.lineTo(x,held[i]);ctx.stroke();}
    ctx.setLineDash([]);ctx.fillStyle=ids.length?'#285e4c':'#768779';ctx.fillRect(x-15,held[i]-5,30,10);
    ctx.fillStyle='#294c3c';ctx.fillText(`${Math.round((hi-held[i])/(hi-lo)*100)}%`,x,450);
    ctx.fillStyle='#7b8479';ctx.font='11px Microsoft YaHei';ctx.fillText(ids.length===2?'两侧取中':ids.length===1?'触点控制':'位置保持',x,470);ctx.font='14px Microsoft YaHei';
  });
  for(const p of points.values()){
    ctx.fillStyle=colors[p.id%colors.length]+'33';ctx.beginPath();ctx.arc(p.x,p.y,15,0,2*Math.PI);ctx.fill();
    ctx.strokeStyle=colors[p.id%colors.length];ctx.lineWidth=2;ctx.stroke();ctx.fillStyle=colors[p.id%colors.length];ctx.fillText(String(p.id+1),p.x,p.y+5);
    if(p.pinned){ctx.beginPath();ctx.moveTo(p.x-4,p.y-21);ctx.lineTo(p.x+4,p.y-21);ctx.stroke();}
  }
  document.querySelector('#status').textContent=`有效触点 ${points.size}/5 · ${points.size?'松开后保留每根推子的最后位置':'当前没有触点，位置保持'} · 分区边界固定`;
}
function position(event){const r=canvas.getBoundingClientRect();return{x:Math.max(0,Math.min(799,Math.round((event.clientX-r.left)*800/r.width))),y:Math.max(0,Math.min(479,Math.round((event.clientY-r.top)*480/r.height)))}}
function nearest(p){return [...points.values()].filter(t=>t.pinned&&Math.hypot(t.x-p.x,t.y-p.y)<20).sort((a,b)=>Math.hypot(a.x-p.x,a.y-p.y)-Math.hypot(b.x-p.x,b.y-p.y))[0]}
canvas.addEventListener('pointerdown',e=>{
  if(e.pointerType==='touch')return;
  if(e.button!==0)return;e.preventDefault();const p=position(e),existing=nearest(p);
  let id=existing?.id;
  if(id===undefined){id=[0,1,2,3,4].find(i=>!points.has(i));if(id===undefined)return;points.set(id,{id,...p,pinned:e.shiftKey});}
  else Object.assign(points.get(id),p);
  drag.set(e.pointerId,id);canvas.setPointerCapture(e.pointerId);commit();
});
canvas.addEventListener('pointermove',e=>{if(e.pointerType==='touch')return;const id=drag.get(e.pointerId);if(id===undefined||!points.has(id))return;Object.assign(points.get(id),position(e));commit()});
function finish(e){if(e.pointerType==='touch')return;const id=drag.get(e.pointerId);drag.delete(e.pointerId);if(id!==undefined&&!points.get(id)?.pinned)points.delete(id);commit()}
canvas.addEventListener('pointerup',finish);canvas.addEventListener('pointercancel',finish);
canvas.addEventListener('lostpointercapture',e=>{if(drag.has(e.pointerId))finish(e)});
canvas.addEventListener('contextmenu',e=>{e.preventDefault();const p=nearest(position(e));if(p)points.delete(p.id);commit()});
// A native touch event contains the complete contact report. Apply it once,
// rather than processing per-pointer releases into a spurious intermediate value.
function touchReport(e){
  e.preventDefault();
  const report=[...e.touches],live=new Set(report.map(t=>t.identifier));
  for(const [source,id] of touchIDs)if(!live.has(source)){points.delete(id);touchIDs.delete(source)}
  for(const t of report){
    let id=touchIDs.get(t.identifier);
    if(id===undefined){id=[0,1,2,3,4].find(i=>!points.has(i));if(id===undefined)continue;touchIDs.set(t.identifier,id)}
    points.set(id,{id,...position(t),pinned:false});
  }
  scheduleTouchCommit();
}
for(const name of ['touchstart','touchmove','touchend','touchcancel'])canvas.addEventListener(name,touchReport,{passive:false});
function example(pts){drag.clear();touchIDs.clear();points.clear();for(const p of pts)points.set(p.id,{...p,pinned:true});commit()}
document.querySelector('#near').onclick=()=>example([{id:0,x:220,y:110},{id:1,x:245,y:330}]);
document.querySelector('#middle').onclick=()=>example([{id:0,x:230,y:120},{id:1,x:270,y:360}]);
document.querySelector('#zones').onclick=()=>{radius=150;document.querySelector('#radius').value=150;document.querySelector('#radiusText').textContent='150 px（仍限本区）';example([{id:0,x:299,y:100}])};
document.querySelector('#release').onclick=()=>{drag.clear();touchIDs.clear();points.clear();commit()};
document.querySelector('#reset').onclick=()=>{drag.clear();touchIDs.clear();points.clear();held=axes.map(()=>hi);commit()};
document.querySelector('#radius').oninput=e=>{radius=Number(e.target.value);document.querySelector('#radiusText').textContent=radius+' px';commit()};
document.querySelector('#export').onclick=()=>{const url=URL.createObjectURL(new Blob([JSON.stringify({axes,zones,lo,hi,frames:trace},null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='right-hand-fader-trace.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)};
commit();
// Local prototype inspection only; no device connection or audio generation.
window.faderPreview={get state(){return{held:[...held],selection:selection.map(s=>[...s]),touches:[...points.values()],radius}},example};
