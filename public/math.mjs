export function allocation(holdings){
 const funded=holdings.filter(h=>Number.isFinite(h.value)&&h.value>0);
 const total=funded.reduce((s,h)=>s+h.value,0);
 const groups={};for(const h of funded)groups[h.type]=(groups[h.type]||0)+h.value;
 const ordered=[...funded].sort((a,b)=>b.value-a.value);
 const hhi=total?funded.reduce((s,h)=>s+(h.value/total)**2,0):0;
 return {total,count:funded.length,groups,largest:ordered[0],effective:hhi?1/hhi:0,topTwo:ordered.slice(0,2).reduce((s,h)=>s+h.value,0)};
}
export function goalPlan(target,savings,years,rate){
 if(![target,savings,years,rate].every(Number.isFinite)||target<=0||target>1e11||savings<0||savings>1e11||!Number.isInteger(years)||years<1||years>50||rate<0||rate>30)throw Error('Enter a positive target, non-negative savings, 1–50 whole years and a return between 0% and 30%. Amounts may be up to ₹10,000 crore.');
 const n=years*12,r=Math.expm1(Math.log1p(rate/100)/12),factor=r===0?n:Math.expm1(n*Math.log1p(r))/r;
 const grown=savings*(1+r)**n,sip=Math.max(0,(target-grown)/factor);
 const points=[];for(let month=0;month<=n;month+=12){const f=r===0?month:Math.expm1(month*Math.log1p(r))/r;points.push({year:month/12,contributed:savings+sip*month,value:savings*(1+r)**month+sip*f});}
 const future=grown+sip*factor,contributed=savings+sip*n;
 return {sip,future,contributed,growth:Math.max(0,future-contributed),points,covered:grown>=target};
}
