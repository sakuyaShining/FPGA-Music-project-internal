// Browser prototype of the RTL contract. No serial, audio or device storage.
export function resolve(axes,zones,touches,held,radius,lo=0,hi=479) {
  if(lo>hi || radius<0 || axes.length!==zones.length || axes.length!==held.length)
    throw Error('Invalid geometry');
  if(zones.some(([a,b],i)=>!(a<=axes[i] && axes[i]<b) || (i>0 && zones[i-1][1]>a)))
    throw Error('Zones must be ordered and disjoint');
  if(new Set(touches.map(t=>t.id)).size!==touches.length)throw Error('Duplicate touch ID');
  const result=[...held], selected=[];
  axes.forEach((axis,i)=>{
    let l=null,r=null;
    const better=(a,b)=>b===null || Math.abs(a.x-axis)<Math.abs(b.x-axis) ||
      (Math.abs(a.x-axis)===Math.abs(b.x-axis) && a.id<b.id);
    for(const t of touches){
      if(t.x<zones[i][0] || t.x>=zones[i][1] || Math.abs(t.x-axis)>radius)continue;
      if(t.x<=axis && better(t,l))l=t;
      if(t.x>=axis && better(t,r))r=t;
    }
    let value=null;
    if(l && r)value=Math.floor((l.y+r.y)/2);
    else if(l || r)value=(l || r).y;
    if(value!==null)result[i]=Math.max(lo,Math.min(hi,value));
    selected.push([l?.id??null,r?.id??null]);
  });
  return {result,selected};
}
