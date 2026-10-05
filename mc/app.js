/* Market Council - mission control screens. Reads the same repository files as the base app; places no orders. */
(function(){
"use strict";
var MC=window.MC; if(!MC)return;
var S=MC.S,$=MC.$,esc=MC.esc,num=MC.num;
var X={},st={rng:"1W",pview:null,xdim:"sector",open:null,opt:"wide",cm:"held",runs:null,runsAt:0};
var EXTRA={quant:"state/quant.json",navh:"state/nav_history.json",series:"state/series.json",profiles:"state/profiles.json"};
var GH="https://api.github.com/repos/benipkun/market-council-state";
var MINUS=String.fromCharCode(8722),DASH=String.fromCharCode(8212),MID=String.fromCharCode(183),ARROW=String.fromCharCode(8594),
LARR=String.fromCharCode(8592),NL=String.fromCharCode(10),SIGMA=String.fromCharCode(963);
var SECT={"Technology":"#4aa3ff","Industrials":"#e8a33d","Health Care":"#b792ff","Consumer Discretionary":"#ff8fd0","Financials":"#5ad1e6",
"Communication Services":"#ff9966","Broad market":"#c8d1e0","Defensive sectors":"#9db4d6","Bonds":"#8f9bff","Gold":"#d9c36a","Cash":"#7a879c","Unclassified":"#5f6b80"};
var SHORT={"Consumer Discretionary":"CONSUMER DISC.","Communication Services":"COMMUNICATION","Defensive sectors":"DEFENSIVE"};
var NB='<span class="stg nb">NOT BUILT YET</span>';
function col(s){return SECT[s]||SECT.Unclassified;}
function A(t){return (X.quant&&X.quant.assets&&X.quant.assets[t])||{};}
function p1(v,d){var n=num(v);return n==null?DASH:(100*n).toFixed(d==null?1:d)+"%";}
function sp(v,d){var n=num(v);if(n==null)return '<span class="fl">'+DASH+'</span>';var c=n>0?"up":(n<0?"dn":"fl");
return '<span class="'+c+'">'+(n>0?"+":(n<0?MINUS:""))+Math.abs(100*n).toFixed(d==null?1:d)+'%</span>';}
function sm(v){var n=num(v);if(n==null)return DASH;return '<span class="'+(n>0?"up":(n<0?"dn":"fl"))+'">'+MC.money(n,true)+'</span>';}
function f2(v,d){var n=num(v);return n==null?DASH:(n<0?MINUS:"")+Math.abs(n).toFixed(d==null?2:d);}
function pts(v){var n=num(v);return n==null?DASH:(n>0?"+":(n<0?MINUS:""))+Math.abs(100*n).toFixed(1)+" points";}
function sd(s){if(!s)return DASH;var d=new Date(String(s).length===10?s+"T12:00:00Z":s);return isNaN(d)?String(s):d.toLocaleDateString("en-GB",{day:"numeric",month:"short"});}
function wkH(iso){var t=new Date(iso).getTime();if(!isFinite(t))return 1e9;var n=Date.now(),h=0;
for(var x=t;x<n&&h<3000;x+=3600000){var d=new Date(x).getUTCDay();if(d!==0&&d!==6)h++;}return h;}
function tag(iso,lim){if(!iso)return '<span class="stg stale">NO DATA YET</span>';
return wkH(iso)<=lim?'<span class="stg live">LIVE</span>':'<span class="stg stale">STALE '+MID+' '+esc(MC.when(iso))+'</span>';}
function upd(iso){return iso?"updated "+esc(MC.when(iso))+" ("+esc(MC.ago(iso))+")":"no update time recorded";}
function nb(n,what){return '<div class="nbx">'+NB+' '+esc(what)+' <span class="fl">Upgrade item '+n+'.</span></div>';}
function blk(label,tg,body,src){return '<div class="blk"><div class="bh"><span class="lbl">// '+label+'</span>'+(tg||"")+'</div>'+body+(src?'<div class="src">'+src+'</div>':"")+'</div>';}
function head(label,title,right){return '<div class="ph"><div><div class="lbl">// '+label+'</div><div class="pt1" role="heading" aria-level="1">'+title+'</div></div>'+(right||"")+'</div>';}
function seg(act,cur,opts){return '<div class="rng">'+opts.map(function(o){return '<button data-mc="'+act+'" data-v="'+o[0]+'" aria-pressed="'+(o[0]===cur)+'">'+o[1]+'</button>';}).join("")+'</div>';}
function rho(a,b){var c=X.quant&&X.quant.corr;if(!c)return null;var i=c.tickers.indexOf(a),j=c.tickers.indexOf(b);return i<0||j<0?null:c.m[i][j];}
function pos(){var tr=S.treasury||{},nav=num(tr.nav)||0;return MC.positions().map(function(p){var mv=num(p.market_value)||0,cb=num(p.cost_basis);
return {t:p.ticker,mv:mv,cost:cb,w:nav?mv/nav:0,pl:cb?mv/cb-1:null,sec:A(p.ticker).sector||"Unclassified",px:num(p.last_price)};});}
function qAge(){return X.quant&&X.quant.as_of;}
function psrc(){var p=X.quant&&X.quant.price_sources,k=p?Object.keys(p).filter(function(n){return n!=="none";}):[];return k.length?esc(k.join(" and ")):"public";}
/* later phases plug in here: an add-on file registers slot renderers, tools, checklist tests and extra data files */
var SL={},TOOLS={},DONE={};
function slot(name,arg,fallback){var f=SL[name];if(f){try{var h=f(arg);if(h)return h;}catch(e){if(window.console)console.error(e);}}return fallback||"";}

/* ---------- top strip ---------- */
function sources(){
var di=((S.status&&S.status.data_issues)||[]).map(String),bt=S.status&&S.status.books_ran_at,dg=S.digest&&S.digest.as_of,out=[];
function issue(n){return di.filter(function(x){return x.toLowerCase().indexOf(n.toLowerCase())===0;})[0];}
[["Twelve Data","live quotes and exchange rates"],["Alpha Vantage","backup quotes, news, insider trades (25 calls a day)"],["MNB","official forint rate for tax"]].forEach(function(c){
var is=issue(c[0]);out.push({n:c[0],use:c[1],ok:!is&&!!bt,at:bt,note:is?is.slice(is.indexOf(":")+1).trim():"no problem reported at the last bookkeeping run",fix:c[0]==="MNB"?"net":"conn"});});
var tech=(S.digest&&S.digest.technicals)||{},fmp=Object.keys(tech).some(function(k){return String(tech[k].fair_value_method||"").indexOf("FMP")>=0;});
out.push({n:"FMP",use:"company statements and fair values (large companies only on your plan)",ok:fmp&&wkH(dg)<=30,at:dg,note:fmp?"used in the latest pipeline run":"not used in the latest pipeline run",fix:"conn"});
out.push({n:"News search",use:"headlines for every watched company",ok:!!dg&&wkH(dg)<=9,at:dg,note:"read by the pipeline's News Reader",fix:""});
((X.quant&&X.quant.sources)||[]).forEach(function(s){out.push({n:s.name,use:s.use,ok:s.status==="live",at:qAge(),
note:s.status==="live"?(s.of?s.ok+" of "+s.of+" symbols":"reachable"):(s.status==="not set"?"optional backup, not set up":(s.detail||s.status)),fix:"eng",opt:s.status==="not set"});});
return out;}
function renderStrip(){
var el=$("strip");if(!el)return;var q=X.quant,s=q&&q.stress,src=sources().filter(function(x){return !x.opt;}),live=src.filter(function(x){return x.ok;}).length;
el.innerHTML=(s?'<button class="stg lvl" data-tab="system" style="background:none">DOOMSDAY LEVEL: '+esc(String(s.level).toUpperCase())+'</button>'+tag(q.as_of,14)
:'<span class="stg stale">DOOMSDAY LEVEL: NO DATA YET</span>')+
'<button class="stg '+(live===src.length?"live":"stale")+'" data-tab="system" style="background:none">SOURCES '+live+'/'+src.length+' LIVE</button>';}

/* ---------- today: decisions first ---------- */
function renderTodayTop(){var el=$("td-dec");if(!el)return;
el.innerHTML=slot("td-dec",null,blk("DECISIONS WAITING FOR YOU",NB,'<div class="nbx">Order tickets that need your yes or no will sit here, above everything else. Nothing is waiting because this part is not built yet. <span class="fl">Upgrade items 13 and 18.</span></div>'));}

/* ---------- portfolio ---------- */
function t2(l,v,c,cls){return '<div class="t2'+(cls?" "+cls:"")+'"><div class="lbl">'+l+'</div><div class="v">'+v+'</div><div class="c">'+c+'</div></div>';}
function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
function mapSvg(P,cashW){
var W=320,H=400,cx=160,cy=200,nodes=P.map(function(p){return {t:p.t,w:p.w,pl:p.pl,sec:p.sec};});
nodes.push({t:"CASH",w:cashW,pl:null,sec:"Cash",cash:true});
var hubs=[],hi={};nodes.forEach(function(n){if(hi[n.sec]==null){hi[n.sec]=hubs.length;hubs.push({s:n.sec,w:0,n:[]});}var h=hubs[hi[n.sec]];h.w+=n.w;h.n.push(n);});
hubs.sort(function(a,b){return b.w-a.w;});
function F(v){return v.toFixed(1);}
var g1="",g2="",g3="",g4="",occ=[[cx-30,cy-30,cx+30,cy+30]];
function box(x,y,chars,size){occ.push([x-chars*size*0.31,y-size,x+chars*size*0.31,y+3]);}
hubs.forEach(function(h,i){var ang=(-90+i*360/hubs.length)*Math.PI/180;h.a=ang;h.x=cx+62*Math.cos(ang);h.y=cy+72*Math.sin(ang);
h.n.forEach(function(n,j){var a2=ang+(j-(h.n.length-1)/2)*Math.min(0.55,2.2/hubs.length);n.r=10+26*Math.sqrt(Math.max(0,n.w));
n.x=clamp(cx+118*Math.cos(a2),n.r+5,W-n.r-5);n.y=clamp(cy+152*Math.sin(a2),n.r+30,H-n.r-30);occ.push([n.x-n.r,n.y-n.r,n.x+n.r,n.y+n.r]);});
g1+='<line x1="'+cx+'" y1="'+cy+'" x2="'+F(h.x)+'" y2="'+F(h.y)+'" stroke="'+col(h.s)+'" stroke-width="1.5" opacity=".85"/>';
h.n.forEach(function(n){g1+='<line x1="'+F(h.x)+'" y1="'+F(h.y)+'" x2="'+F(n.x)+'" y2="'+F(n.y)+'" stroke="'+col(h.s)+'" stroke-width="1" opacity=".65"/>';});
var c=Math.cos(ang),side=Math.abs(c)>0.5,txt=(SHORT[h.s]||h.s.toUpperCase())+(side?"":" "+p1(h.w,0)),lx=side?h.x+(c>0?2:-2):h.x+11,ly=side?h.y-11:h.y+3.5;
if(side)box(lx,ly,txt.length,8.5);else occ.push([lx,ly-9,lx+txt.length*5.6,ly+3]);
g3+='<rect x="'+F(h.x-5)+'" y="'+F(h.y-5)+'" width="10" height="10" fill="'+col(h.s)+'" transform="rotate(45 '+F(h.x)+' '+F(h.y)+')"/>'+
'<text class="hl" x="'+F(lx)+'" y="'+F(ly)+'" text-anchor="'+(side?"middle":"start")+'" font-size="8.5" font-weight="700" style="fill:var(--dim)">'+esc(txt)+'</text>';});
nodes.forEach(function(n){var up=n.pl!=null&&n.pl>0,dn=n.pl!=null&&n.pl<0,fill=up?"var(--ups)":(dn?"var(--dns)":"var(--sf2)"),stroke=up?"var(--up)":(dn?"var(--dn)":"var(--dim)"),
pl=n.pl==null?"":(n.pl>0?"+":(n.pl<0?MINUS:""))+Math.abs(100*n.pl).toFixed(1)+"%",out=n.y<cy-24?-1:1,mid=Math.abs(n.y-cy)<=24,wt=p1(n.w),tx="",
lab=n.t+", "+wt+" of the portfolio"+(n.pl==null?"":", "+(n.pl<0?"down ":"up ")+Math.abs(100*n.pl).toFixed(1)+"% since purchase");
function T(y,size,weight,fillc,s,halo,chars){if(halo)box(n.x,y,chars,size);return '<text'+(halo?' class="hl"':"")+' x="'+F(n.x)+'" y="'+F(y)+'" text-anchor="middle" font-size="'+size+'" font-weight="'+weight+'"'+(fillc?' style="fill:'+fillc+'"':"")+'>'+s+'</text>';}
if(n.r>=27){tx=T(n.y-(pl?7:1),12,800,"",esc(n.t))+(pl?T(n.y+6,10,700,stroke,pl):"")+T(n.y+(pl?19:13),9.5,400,"var(--dim)",wt);}
else if(n.r>=20){tx=T(n.y+(pl?-1:4),11,800,"",esc(n.t))+(pl?T(n.y+10,9.5,700,stroke,pl):"")+T(out<0&&!mid?n.y-n.r-6:n.y+n.r+13,9.5,400,"var(--dim)",wt,true,wt.length);}
else{var y1=mid?n.y-n.r-6:(out<0?n.y-n.r-18:n.y+n.r+13);
tx=T(y1,10.5,800,"",esc(n.t)+(pl?' <tspan style="fill:'+stroke+'">'+pl+'</tspan>':""),true,n.t.length+pl.length+1)+T(mid?n.y+n.r+13:y1+12,9.5,400,"var(--dim)",wt,true,wt.length);}
g3+='<g class="nd" '+(n.cash?"":'data-mc="pos" data-t="'+esc(n.t)+'" tabindex="0" role="button" ')+'aria-label="'+esc(lab)+'"><circle cx="'+F(n.x)+'" cy="'+F(n.y)+'" r="'+F(n.r)+'" fill="'+fill+'" stroke="'+stroke+'" stroke-width="2"/>'+tx+'</g>';});
function link(a,b){var mx=(a.x+b.x)/2,my=(a.y+b.y)/2,dx=b.x-a.x,dy=b.y-a.y,len=Math.sqrt(dx*dx+dy*dy)||1,d=Math.abs((cx-a.x)*dy-(cy-a.y)*dx)/len,q=null;
if(d<=46){var px=-dy/len,py=dx/len;[1,-1].forEach(function(sg){var qx=mx+sg*px*72,qy=my+sg*py*72,m=1e9;
nodes.forEach(function(n){if(n!==a&&n!==b){var dd=Math.sqrt((n.x-qx)*(n.x-qx)+(n.y-qy)*(n.y-qy))-n.r;if(dd<m)m=dd;}});if(!q||m>q.m)q={m:m,x:qx,y:qy};});}
function at(t){var u=1-t;return q?[u*u*a.x+2*t*u*q.x+t*t*b.x,u*u*a.y+2*t*u*q.y+t*t*b.y]:[a.x+t*dx,a.y+t*dy];}
var pick=null;[0.5,0.36,0.64,0.27,0.73,0.2,0.8].some(function(t){var p=at(t),bx=[p[0]-15,p[1]-8,p[0]+15,p[1]+6];if(!pick)pick=p;
var hit=occ.some(function(o){return bx[0]<o[2]&&bx[2]>o[0]&&bx[1]<o[3]&&bx[3]>o[1];});if(!hit){pick=p;occ.push(bx);}return !hit;});
return {d:"M"+F(a.x)+" "+F(a.y)+(q?"Q"+F(q.x)+" "+F(q.y)+" ":"L")+F(b.x)+" "+F(b.y),lx:pick[0],ly:pick[1]};}
var real=nodes.filter(function(n){return !n.cash;}),pairs=[];
real.forEach(function(a,i){real.slice(i+1).forEach(function(b){var r=rho(a.t,b.t);if(r!=null)pairs.push({a:a,b:b,r:r});});});
var many=pairs.length>6;if(many)pairs=pairs.filter(function(p){return Math.abs(p.r)>=0.4;});
pairs.forEach(function(p){var L=link(p.a,p.b);
g2+='<path d="'+L.d+'" fill="none" stroke="#e6edf7" stroke-opacity=".5" stroke-width="'+F(1+6*Math.abs(p.r))+'"'+(p.r<0?' stroke-dasharray="5 4"':"")+' stroke-linecap="round"/>'+
'<path d="'+L.d+'" fill="none" stroke="transparent" stroke-width="24" class="nd" data-mc="corr" data-a="'+esc(p.a.t)+'" data-b="'+esc(p.b.t)+'"/>';
if(!many)g4+='<text class="hl" x="'+F(L.lx)+'" y="'+F(L.ly+3.5)+'" text-anchor="middle" font-size="10" font-weight="700" pointer-events="none">'+f2(p.r)+'</text>';});
return '<svg viewBox="0 0 '+W+' '+H+'" role="group" aria-label="Portfolio map: positions grouped by sector, sized by weight, with correlation lines">'+g1+g2+
'<circle cx="'+cx+'" cy="'+cy+'" r="29" fill="var(--bg)" stroke="var(--tx)" stroke-width="1.5"/><text x="'+cx+'" y="'+(cy+3)+'" text-anchor="middle" font-size="8.5" font-weight="800">PORTFOLIO</text>'+g3+g4+'</svg>';}
function donut(rows){var C=2*Math.PI*44,acc=0,segs="";rows.forEach(function(r){var len=Math.max(0,r[1]*C-2);
segs+='<circle cx="60" cy="60" r="44" fill="none" stroke="'+col(r[0])+'" stroke-width="15" stroke-dasharray="'+len.toFixed(2)+" "+(C-len).toFixed(2)+'" stroke-dashoffset="'+(-acc).toFixed(2)+'" transform="rotate(-90 60 60)"><title>'+esc(r[0])+" "+p1(r[1])+'</title></circle>';acc+=r[1]*C;});
return '<div style="display:flex;gap:14px;align-items:center"><svg viewBox="0 0 120 120" style="width:118px;flex:none" role="img" aria-label="Allocation by sector and asset class">'+segs+
'<text x="60" y="57" text-anchor="middle" font-size="16" font-weight="800" style="fill:var(--tx);font-family:var(--mono)">'+rows.length+'</text><text x="60" y="71" text-anchor="middle" font-size="7.5" style="fill:var(--dim);font-family:var(--mono)" letter-spacing=".8">GROUPS</text></svg>'+
'<div style="flex:1;min-width:0">'+rows.map(function(r){return '<div class="kv2"><span style="color:var(--tx)"><i class="sw" style="background:'+col(r[0])+'"></i>'+esc(r[0])+'</span><b>'+p1(r[1])+'</b></div>';}).join("")+'</div></div>';}
function bars(dim,P){var q=X.quant,ex=q&&q.portfolio&&q.portfolio.exposure,rows=(ex&&ex[dim])||P.map(function(p){return [p.t,p.w];}),lim=q&&q.profile&&q.profile.limits,
cap={stock:lim?lim.stock_cap:null,sector:0.4,theme:0.3,country:0.85}[dim];
return rows.map(function(r){var nm=r[0],c=dim==="sector"||dim==="class"?col(nm):(dim==="stock"?col(nm==="Cash"?"Cash":A(nm).sector):"var(--s1)"),over=cap&&nm!=="Cash"&&r[1]>cap;
return '<div class="xb"><span class="nm">'+esc(nm)+'</span><span class="tr"><i style="width:'+clamp(100*r[1],0.8,100).toFixed(1)+'%;background:'+c+'"></i>'+(cap?'<u style="left:'+(100*cap).toFixed(1)+'%"></u>':"")+'</span><span class="pv">'+p1(r[1])+(over?' <b title="over the limit">!</b>':"")+'</span></div>';}).join("")+
(cap?'<div class="src">The white line marks '+p1(cap,0)+": "+(dim==="stock"?"the most your risk profile allows in one company":"the health check's warning line for one "+dim)+'. ! means over it.</div>':"");}
function listRows(P){return P.map(function(p){var a=A(p.t),hp=(X.quant&&X.quant.health&&X.quant.health.positions||[]).filter(function(x){return x.t===p.t;})[0]||{};
return '<button class="lrow" data-mc="pos" data-t="'+esc(p.t)+'"><span class="a"><i class="sw" style="background:'+col(p.sec)+'"></i>'+esc(p.t)+'</span><span class="a r">'+p1(p.w)+'</span>'+
'<span class="b">'+esc(a.name||p.sec)+" "+MID+" "+esc(p.sec)+'</span><span class="b r">'+sp(p.pl)+' since purchase</span>'+
'<span class="b">volatility '+p1(a.vol_1y,0)+" "+MID+" share of risk "+p1(hp.risk_share,0)+'</span><span class="b r">'+(MC.pfVisible()?MC.money(p.mv):"")+'</span></button>';}).join("");}
function renderMap(){
var el=$("v-map");if(!el)return;var tr=S.treasury;if(!tr){el.innerHTML='<div class="msg">No portfolio data loaded yet. Tap refresh.</div>';return;}
var q=X.quant,pf=(q&&q.portfolio)||{},vis=MC.pfVisible(),P=pos(),nav=num(tr.nav)||0,cash=num(tr.cash)||0,cost=0,mv=0;
P.forEach(function(p){cost+=p.cost||0;mv+=p.mv;});
var vc=pf.value_change||{},r=vc[st.rng],d1=vc["1D"],hid='<span class="fl">HIDDEN</span>',lim=q&&q.profile&&q.profile.limits,days=(X.navh&&X.navh.days)||[],c0=null;
if(r)days.forEach(function(d){if(d.date===r.from)c0=num(d.cash);});
var slow=(navigator.deviceMemory&&navigator.deviceMemory<=2)||(navigator.hardwareConcurrency&&navigator.hardwareConcurrency<=2)||P.length>24,view=st.pview||(slow?"list":"map");
var tiles='<div class="tl2">'+
t2("Value",vis?esc(MC.money(nav)):hid,r?st.rng+": "+sp(r.pct)+(vis?" "+sm(r.usd):"")+" since "+sd(r.from):"no history for this period yet")+
t2("Day change",d1?sp(d1.pct,2):DASH,d1?(vis?sm(d1.usd)+" ":"")+"vs "+sd(d1.from)+" close":"needs two days of records")+
t2("Total gain / loss",cost?sp(mv/cost-1):DASH,vis&&cost?sm(mv-cost)+" on "+esc(MC.money(cost))+" paid":"against what you paid")+
t2("Cash",vis?esc(MC.money(cash)):p1(nav?cash/nav:0),p1(nav?cash/nav:0)+" of value"+(vis&&c0!=null?" "+MID+" "+st.rng+": "+esc(MC.money(cash-c0,true)):""))+
t2("Volatility",pf.vol_1y!=null?p1(pf.vol_1y,0):DASH,pf.vol_1y!=null?"a year "+MID+" your target "+(lim?p1(lim.target_vol,0):DASH):"needs the calculation engine","wide")+'</div>';
var mapB=view==="map"?'<div class="map">'+mapSvg(P,nav?cash/nav:0)+'</div><div id="map-info" class="src">Tap a position for its panel, or a line for the correlation behind it.</div>'+
'<div class="leg"><span>Circle size = weight</span><span><i style="background:var(--ups);border:1px solid var(--up)"></i>+ gain since purchase</span><span><i style="background:var(--dns);border:1px solid var(--dn)"></i>'+MINUS+' loss</span><span>Line thickness = correlation (number on the line)</span></div>'
:'<div>'+listRows(P)+'</div>'+(slow&&!st.pview?'<div class="gap"><button class="btn sm" data-mc="pv" data-v="map">Load the map</button></div>':"");
var secRows=(pf.exposure&&pf.exposure.sector)||[];
el.innerHTML=head("PORTFOLIO CORE","Portfolio",tag(tr.as_of,9))+
'<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:8px"><span class="lbl">Period</span>'+seg("rng",st.rng,[["1D","1D"],["1W","1W"],["1M","1M"],["YTD","YTD"],["ALL","ALL"]])+'</div>'+tiles+
(vis?"":'<div class="src" style="margin:8px 0">Amounts are hidden on this device because this page is public; percentages still show. <button class="link" id="pf-show">Show amounts here</button></div>')+
'<div class="src" style="margin:6px 0 12px">Value and cash: latest treasury snapshot, '+upd(tr.as_of)+". Changes leave out deposits and withdrawals; records began "+sd(days.length?days[0].date:null)+". Volatility: "+(q?(q.window_days+" daily returns, "+upd(q.as_of)):"not calculated yet")+'.</div>'+
'<div class="g3"><div>'+blk("PORTFOLIO MAP",seg("pv",view,[["map","MAP"],["list","LIST"]]),mapB,"Weights and gains: treasury snapshot. Correlations: "+(q&&q.corr?q.corr.window_days+" trading days to "+sd(q.corr.through)+", "+psrc()+" prices":"not calculated yet")+".")+'</div><div>'+
blk("ALLOCATION",tag(tr.as_of,9),secRows.length?donut(secRows):'<div class="nbx">Needs the calculation engine.</div>',"By sector and asset class; cash counts as its own group.")+
blk("EXPOSURE",tag(tr.as_of,9),seg("xd",st.xdim,[["stock","STOCK"],["sector","SECTOR"],["country","COUNTRY"],["currency","CURRENCY"],["theme","THEME"]])+'<div class="gap">'+bars(st.xdim,P)+'</div>',"Share of total value. Sector, country, currency and theme labels come from a hand-kept reference list.")+
'</div></div><div class="row"><button class="btn sm" data-tab="risk">Health check and diversification '+ARROW+'</button><button class="btn sm" data-tab="portfolio">Books, goal and tax '+ARROW+'</button></div>';}

/* ---------- risk desk ---------- */
function heat(tk){var h='<table class="mt hm"><tr><th></th>'+tk.map(function(t){return '<th>'+esc(t)+'</th>';}).join("")+'</tr>';
tk.forEach(function(a){h+='<tr><td><b>'+esc(a)+'</b></td>'+tk.map(function(b){var r=rho(a,b);return '<td style="background:rgba(74,163,255,'+(r==null?0:Math.min(0.75,Math.abs(r)*0.75)).toFixed(2)+')">'+(a===b?"1":f2(r))+'</td>';}).join("")+'</tr>';});return h+'</table>';}
function optTable(o){if(!o)return '<div class="nbx">Needs at least two holdings with price history.</div>';var M=[["current","NOW"],["minvar","MIN VARIANCE"],["hrp","RISK PARITY (HRP)"],["tangency","MAX SHARPE"],["mincvar","MIN CVaR"],["target","YOUR TARGET"]];
var h='<table class="mt"><tr><th>Weight</th>'+M.map(function(m){return '<th>'+m[1]+'</th>';}).join("")+'</tr>';
o.tickers.forEach(function(t,i){if(M.every(function(m){return !(o.methods[m[0]].w[i]>0.0005);}))return;
h+='<tr><td><b>'+esc(t)+'</b></td>'+M.map(function(m){var w=o.methods[m[0]].w[i];return '<td>'+(w>0.0005?p1(w,0):'<span class="fl">'+MID+'</span>')+'</td>';}).join("")+'</tr>';});
[["vol","Volatility a year",function(v){return p1(v,1);}],["ret","Return a year (estimate)",function(v){return p1(v,1);}],["sharpe","Sharpe (estimate)",function(v){return f2(v);}],
["cvar","Bad-day loss (CVaR 95%)",function(v){return sp(v,1);}],["mdd","Worst fall in the window",function(v){return sp(v,0);}]].forEach(function(row){
h+='<tr><td>'+row[1]+'</td>'+M.map(function(m){return '<td>'+row[2](o.methods[m[0]][row[0]])+'</td>';}).join("")+'</tr>';});return '<div class="ox">'+h+'</table></div>';}
function renderRisk(){
var el=$("v-risk");if(!el)return;var q=X.quant;if(!q){el.innerHTML=head("RISK DESK","Health check",'<span class="stg stale">NO DATA YET</span>')+'<div class="msg">The calculation engine has not produced its first results yet.</div>';return;}
var H=q.health||{findings:[],positions:[]},pr=q.profile||{},lim=pr.limits||{},held=pos().map(function(p){return p.t;}),tg=tag(q.as_of,14);
var fnd=H.findings.map(function(f){return '<div class="fd"><div class="ft"><span class="sev '+esc(f.level)+'">'+esc(f.level.toUpperCase())+'</span>'+esc(f.title)+'</div><div class="fx2">'+esc(f.detail)+'</div><div class="src" style="margin-top:3px">How: '+esc(f.method)+'</div></div>';}).join("")||'<div class="msg">No findings.</div>';
var prow='<div class="ox"><table class="mt"><tr><th>Position</th><th>Weight</th><th>Share of risk</th><th>Volatility</th><th>Beta</th><th>From 12-month high</th><th>Since purchase</th></tr>'+
H.positions.map(function(p){return '<tr><td><b>'+esc(p.t)+'</b></td><td>'+p1(p.w)+'</td><td>'+p1(p.risk_share,0)+'</td><td>'+p1(p.vol_1y,0)+'</td><td>'+f2(p.beta_1y)+'</td><td>'+sp(p.from_high_1y,0)+'</td><td>'+sp(p.pl_pct)+'</td></tr>';}).join("")+'</table></div>';
var sets={held:held.concat(["SPY"]),watch:(q.corr.tickers||[]).filter(function(t){return (A(t).cls==="Equity"||t==="SPY");}),bonds:held.concat(["SPY","SHY","IEF","TLT","LQD","TIP","GLD"])};
var tk=(sets[st.cm]||sets.held).filter(function(t){return q.corr.tickers.indexOf(t)>=0;});
var ad=q.additions||{rows:[]},adT=ad.rows.filter(function(r){return r.kind==="candidate";}).slice(0,12).map(function(r){var a=A(r.t);
return '<div class="fd"><div class="ft">'+esc(r.t)+' <span class="fl" style="font-weight:400">'+MID+" "+esc(a.name||"")+'</span></div><div class="fx2">Move 10% in: <b style="color:var(--tx)">'+pts(r.d10)+'</b> '+MID+' 20% in: <b style="color:var(--tx)">'+pts(r.d20)+'</b> '+MID+" correlation "+f2(r.corr)+" "+MID+" its own volatility "+p1(r.vol,0)+(a.eu?" "+MID+" EU-listed: "+esc(a.eu):"")+'</div></div>';}).join("")||'<div class="fl">No candidates calculated.</div>';
var o=q.opt||{};
el.innerHTML=head("RISK DESK","Health check",tg)+
'<div class="g2"><div>'+blk("HEALTH CHECK "+MID+" WORST FIRST",'<span class="stg lvl">SCORE '+esc(H.score)+'/100</span>',fnd,"Limits come from risk level "+esc(pr.risk_level)+" ("+esc(pr.label)+")"+(pr.set?"":", a default until you set your own under SYSTEM")+". Score: "+esc(H.score_method)+". "+upd(q.as_of)+".")+'</div><div>'+
blk("POSITION BY POSITION",tg,prow,"Sorted by severity. Share of risk is the part of portfolio variance each position causes over "+esc(q.window_days)+" trading days.")+
blk("CORRELATION TABLE",tg,seg("cm",st.cm,[["held","HELD"],["bonds","+ BONDS"],["watch","WATCHLIST"]])+'<div class="ox gap">'+heat(tk)+'</div>',esc(q.corr.method)+", "+esc(q.corr.window_days)+" trading days to "+sd(q.corr.through)+". 1 = move together, 0 = unrelated, below 0 = opposite. Darker = stronger.")+'</div></div>'+
blk("YOUR WEIGHTS AGAINST FOUR TEXTBOOK MIXES",tg,seg("opt",st.opt,[["held","YOUR HOLDINGS ONLY"],["wide","WITH BONDS AND FUNDS"]])+'<div class="gap">'+optTable(o[st.opt])+'</div>',
(o.notes||[]).map(esc).join(" ")+" Caps in the wider set: "+p1(lim.stock_cap,0)+" per company (your profile), 35% per fund. YOUR TARGET is the highest estimated return with volatility at or below "+p1(lim.target_vol,0)+". These are comparisons, not instructions.")+
blk("WHAT LOWERS THE SWINGS MOST",tg,adT,"Starting volatility of the invested part: "+p1(ad.base_vol,1)+". Each row: "+esc(ad.method||"")+". Points are percentage points of yearly volatility; a minus sign means calmer. US-listed funds are used for their long price history; the last column names an EU-listed fund covering the same thing, to check at your broker.")+
slot("rk-shorts",null,blk("SHORT SELLING",'<span class="stg lvl">'+(q.shorts&&q.shorts.allowed?"ALLOWED":"OFF FOR YOUR PROFILE")+'</span>','<div class="fx2" style="font-size:12px;color:var(--dim)">'+esc(q.shorts?q.shorts.rule:"")+'</div>',"Change it under SYSTEM, People and risk profiles."))+slot("rk-extra",null,"");}

/* ---------- position panel ---------- */
function spark(t){var s=X.series,c=s&&s.close&&s.close[t];if(!c||c.length<5)return "";var mn=Math.min.apply(null,c),mx=Math.max.apply(null,c),n=c.length,
pts=c.map(function(v,i){return (i*300/(n-1)).toFixed(1)+","+(52-48*(v-mn)/((mx-mn)||1)).toFixed(1);}).join(" ");
return '<svg class="spark" viewBox="0 0 300 56" preserveAspectRatio="none" role="img" aria-label="One-year price line"><polyline points="'+pts+'" fill="none" stroke="var(--s1)" stroke-width="2" vector-effect="non-scaling-stroke"/></svg>'+
'<div class="src" style="margin-top:4px">One year of daily closes: low '+f2(mn)+", high "+f2(mx)+", now "+f2(c[n-1])+" (adjusted for dividends).</div>";}
function kv(a,b){return '<div class="kv2"><span>'+a+'</span><b>'+b+'</b></div>';}
function posHtml(t){
var a=A(t),tc=MC.tech(t)||{},P=pos().filter(function(p){return p.t===t;})[0],dg=S.digest&&S.digest.as_of,q=X.quant;
var known=!!(a.name||tc.price||P),picks=[];((S.history&&S.history.entries)||[]).forEach(function(e){(e.picks||[]).forEach(function(p){if(p.ticker===t)picks.push({at:e.as_of,p:p});});});
((S.digest&&S.digest.picks)||[]).forEach(function(p){if(p.ticker===t)picks.push({at:dg,p:p});});picks.sort(function(x,y){return x.at<y.at?1:-1;});
var mine=((S.ledger&&S.ledger.entries)||[]).filter(function(e){return e.ticker===t&&e.status==="applied"&&(e.why||e.exit_plan);}).slice(-1)[0],lp=picks[0];
var h='<div class="pp-top"><button class="back" data-mc="back">'+LARR+' BACK</button><div style="flex:1;min-width:0"><div class="lbl">// POSITION PANEL</div><div style="font-weight:800;font-size:16px">'+esc(t)+' <span class="fl" style="font-size:11px;font-weight:400">'+esc(a.name||"")+'</span></div></div></div>';
if(!known)return h+'<div class="msg"><b>'+esc(t)+' is not on the watchlist.</b> Nothing is recorded for it yet.</div><div class="gap"><button class="btn" data-mc="askq" data-q="Please add '+esc(t)+' to the watchlist and tell me what the records would need to research it.">Ask the Council to add it</button></div>';
h+='<div class="tl2" style="margin-bottom:12px">'+t2("Price",tc.price!=null?"$"+f2(tc.price):(a.last!=null?"$"+f2(a.last):DASH),"1D "+sp(a.ret_1D)+" "+MID+" 1M "+sp(a.ret_1M))+
(P?t2("Weight",p1(P.w),sp(P.pl)+" since purchase"):t2("Held","NO","on the watchlist"))+'</div>';
h+=blk("THESIS",lp?tag(lp.at,9):'<span class="stg stale">NO VIEW YET</span>',(mine?'<div class="q me"><b>Your note when you bought:</b> '+esc(mine.why||"")+(mine.exit_plan?' <b>Exit:</b> '+esc(mine.exit_plan):"")+'</div>':'<div class="fx2 fl" style="font-size:12px">You logged no reason for this trade.</div>')+
(lp?'<div class="q"><b>Council, '+esc(MC.when(lp.at))+" ("+esc(lp.p.lean||"no lean")+"):</b> "+esc(lp.p.why||lp.p.brief||"")+'</div>':""),"Data: your trade log and the pipeline's latest pick for this ticker.");
h+=slot("pp-card",t,"");
h+=slot("pp-hold",t,blk("HOLD PLAN",NB,'<div class="nbx">A projection of what holding this position should look like, updated every run. <span class="fl">Upgrade item 16.</span></div>'));
h+=blk("VALUATION",tc.fair_value!=null?tag(dg,9):'<span class="stg stale">NO DATA YET</span>',(tc.fair_value!=null?kv("Fair value (outside model)","$"+f2(tc.fair_value))+kv("Price against it",sp(tc.price/tc.fair_value-1,0))+(tc.analyst_consensus_target!=null?kv("Analysts' average target","$"+f2(tc.analyst_consensus_target)):""):"")+
slot("pp-dcf",t,'<div class="nbx gap">'+NB+' Our own valuation with editable assumptions. <span class="fl">Upgrade item 8.</span></div>'),tc.fair_value!=null?"Method: "+esc(tc.fair_value_method||"not stated")+". "+upd(dg)+".":"");
h+=slot("pp-earn",t,blk("LATEST EARNINGS REVIEW",NB,(tc.next_earnings_date?kv("Next report",esc(sd(tc.next_earnings_date))):"")+'<div class="nbx gap">A review after each earnings call: revenue, margins, guidance and tone against expectations. <span class="fl">Upgrade item 9.</span></div>',tc.next_earnings_date?"Date from the pipeline, "+upd(dg)+".":""));
h+=slot("pp-smart",t,blk("SMART-MONEY ACTIVITY",NB,'<div class="nbx">Insider, politician and large-fund trades, with trade date and filing date. <span class="fl">Upgrade item 10.</span></div>'));
h+=slot("pp-dec",t,blk("OPEN DECISION CARD",NB,'<div class="nbx">An order ticket with entry, stop and take-profit prices when one is open. <span class="fl">Upgrade item 13.</span></div>'));
var others=pos().filter(function(p){return p.t!==t;}).map(function(p){return kv("Correlation with "+esc(p.t),f2(rho(t,p.t)));}).join("");
h+=blk("RISK",q?tag(q.as_of,14):'<span class="stg stale">NO DATA YET</span>',spark(t)+kv("Volatility a year",p1(a.vol_1y,0))+kv("Beta to the S&P 500",f2(a.beta_1y))+kv("From 12-month high",sp(a.from_high_1y,0))+kv("Worst fall in 12 months",sp(a.mdd_1y,0))+others,q?"Data: "+psrc()+" daily prices, "+esc(q.window_days)+" trading days. "+upd(q.as_of)+".":"");
h+=blk("ABOUT",'',kv("Sector",'<i class="sw" style="background:'+col(a.sector)+'"></i>'+esc(a.sector||DASH))+kv("Country",esc(a.country||DASH))+kv("Earns mostly in",esc(a.ccy||DASH))+kv("Theme",esc(a.theme||DASH)),"Hand-kept reference list.");
return h+'<div class="row"><button class="btn sm" data-mc="logit" data-t="'+esc(t)+'">Log a trade in '+esc(t)+'</button><button class="btn sm" data-mc="askq" data-q="What do the records say about '+esc(t)+' right now?">Ask the Council about '+esc(t)+'</button></div>';}
function openPos(t){st.open=t;var el=$("ppanel");if(!el){el=document.createElement("div");el.id="ppanel";el.className="ppanel";el.setAttribute("role","dialog");el.setAttribute("aria-label","Position panel");document.body.appendChild(el);}
el.innerHTML=posHtml(t);el.hidden=false;el.scrollTop=0;setTimeout(function(){if(st.open)el.classList.add("on");},30);
try{history.pushState({pp:t},"",location.hash);}catch(e){}}
function closePos(viaPop){var el=$("ppanel");if(!el||!st.open)return;st.open=null;el.classList.remove("on");setTimeout(function(){if(!st.open)el.hidden=true;},230);
if(!viaPop&&history.state&&history.state.pp){try{history.back();}catch(e){}}}

/* ---------- research ---------- */
function ideas(){var held={},out={},order=["Watchlist","Researched","Valued","Proposed","Approved","Open","Closed"];
function put(t,stage,why){var i=order.indexOf(stage);if(!out[t]||order.indexOf(out[t].s)<i)out[t]={s:stage,why:why};}
((S.digest&&S.digest.technicals)?Object.keys(S.digest.technicals):[]).forEach(function(t){put(t,"Watchlist","followed by the pipeline");});
((S.theses&&S.theses.theses)||[]).forEach(function(x){if(x.ticker)put(x.ticker,"Researched","has a written thesis");});
((S.research&&S.research.notes)||[]).forEach(function(n){if(n.ticker)put(n.ticker,"Researched","has a research note");});
var cut=Date.now()-14*86400000;((S.history&&S.history.entries)||[]).forEach(function(e){if(new Date(e.as_of).getTime()>cut)(e.picks||[]).forEach(function(p){if(p.lean==="bullish"||p.lean==="bearish")put(p.ticker,"Proposed","Council leaned "+p.lean+" on "+sd(e.as_of));});});
((X.cards&&X.cards.cards)||[]).forEach(function(c){if(c.valued)put(c.t,"Valued","our own valuation exists");});
MC.positions().forEach(function(p){held[p.ticker]=1;put(p.ticker,"Open","you hold it");});
((S.ledger&&S.ledger.entries)||[]).forEach(function(e){if(e.action==="sell"&&e.status==="applied"&&!e.undone_by&&!held[e.ticker])put(e.ticker,"Closed","sold on "+sd(e.at));});
return {order:order,map:out};}
function renderResearch(){var el=$("v-research");if(!el)return;var I=ideas(),dg=S.digest&&S.digest.as_of,all=Object.keys(I.map).sort();
var track='<div class="trk">'+I.order.map(function(sg){var its=all.filter(function(t){return I.map[t].s===sg;});
return '<div class="col"><div class="ch">'+sg+" ("+its.length+")</div><div>"+(its.map(function(t){return '<button class="idea" data-mc="pos" data-t="'+esc(t)+'" title="'+esc(I.map[t].why)+'"><i style="background:'+col(A(t).sector)+'"></i>'+esc(t)+'</button>';}).join("")||((sg==="Valued"||sg==="Approved")?NB:'<span class="fl" style="font-size:11px">none</span>'))+'</div></div>';}).join("")+'</div>';
var notes=((S.research&&S.research.notes)||[]).map(function(n){return '<a class="lrow" style="text-decoration:none" href="'+esc(n.url)+'"><span class="a">'+esc(n.title)+'</span><span class="b r">'+esc(sd(n.date))+'</span><span class="b" style="grid-column:1/-1">'+esc(n.summary||"")+'</span></a>';}).join("")||'<div class="fl">No notes yet.</div>';
var tools=[[7,"Research card","news, analyst ratings and announcements with sources and dates"],[8,"Valuation","five-year cash-flow forecast, fair value per share, editable assumptions, spreadsheet"],[9,"Earnings reviewer","a review after each earnings call"],
[10,"Smart-money tracker","insiders, politicians and big funds, trade date and filing date"],[11,"Real-world signals lab","test whether an outside data series really leads a share price"],[12,"Backtester","test a rule against the S&P 500 after costs"]];
el.innerHTML=head("RESEARCH DESK","Research",tag(dg,9))+
blk("OPEN A TICKER",'','<div class="mini" style="margin-top:0"><input id="rs-in" type="text" list="rs-list" autocapitalize="characters" autocorrect="off" spellcheck="false" maxlength="12" placeholder="Ticker, e.g. NVO" aria-label="Ticker"><datalist id="rs-list">'+all.map(function(t){return '<option value="'+esc(t)+'">';}).join("")+'</datalist><button data-mc="rs-go">OPEN</button></div>',"Opens everything recorded for that ticker: thesis, valuation, risk and the research tools as they are built.")+
blk("IDEA PIPELINE",tag(dg,9),track,"Each idea sits at the furthest stage the records support: watchlist (followed by the pipeline), researched (a note or thesis exists), valued (our own valuation), proposed (Council leaned bullish or bearish in the last 14 days), approved (your yes on a decision card), open (you hold it), closed (you sold it). Dot colour = sector.")+
'<div class="g2"><div>'+blk("RESEARCH NOTES",'',notes,"Written notes published in the repository.")+'</div><div>'+
blk("RESEARCH TOOLS",'',tools.map(function(x){var tl=TOOLS[x[0]];return '<div class="ck"><span class="n">'+x[0]+'</span><span><b>'+x[1]+'</b><br><span class="fl">'+esc(tl&&tl.note?tl.note:x[2])+'</span></span>'+(tl?(tl.open?'<button class="btn sm" data-mc="tool" data-v="'+x[0]+'">Open</button>':'<span class="stg live">BUILT</span>'):NB)+'</div>';}).join(""),"Each tool keeps its place here until it is built.")+'</div></div>'+slot("rs-extra",null,"");}

/* ---------- council ---------- */
function renderCouncil(){var el=$("v-council");if(!el)return;var dg=S.digest&&S.digest.as_of,stt=S.status||{},q=X.quant,msgs=MC.chatList().slice(-4);
function ag(cls,name,role,data,at,lim,auto,extra){var late=!at||wkH(at)>lim;
return '<div class="ag '+cls+'"><div class="an"><i class="sd'+(late?" late":"")+'" title="'+(late?"late":"on schedule")+'"></i>'+name+'<span style="margin-left:auto" class="stg lvl">'+auto+'</span></div><div class="ar2">'+role+'</div>'+
kv("Uses",data)+kv("Last run",at?esc(MC.when(at))+" ("+esc(MC.ago(at))+")"+(late?' <span class="stg stale">LATE</span>':""):"never")+(extra||"")+'</div>';}
var chat='<div class="src" style="margin-top:8px">Latest messages</div>'+(msgs.map(function(m){return '<div class="q'+(m.from==="ben"?" me":"")+'"><b>'+(m.from==="ben"?"You":"Councillor")+" "+MID+" "+esc(MC.when(m.at))+":</b> "+esc(m.text)+'</div>';}).join("")||'<div class="q">No messages yet.</div>')+
'<div class="mini"><input id="cc-in" type="text" maxlength="900" placeholder="Ask the Councillor" aria-label="Ask the Councillor"><button data-mc="cc-go">SEND</button></div><div id="cc-stat"></div><div class="src">The answer appears here, under CHAT, and on your phone. It explains and reports; it does not place orders.</div>';
var lastMsg=(MC.chatList().filter(function(m){return m.from!=="ben";}).slice(-1)[0]||{}).at;
el.innerHTML=head("COMMAND CHAIN","Council",tag(dg,9))+'<div class="org">'+
'<div class="ag me"><div class="an"><i class="sd"></i>You<span style="margin-left:auto" class="stg lvl">DECIDES AND PLACES EVERY ORDER</span></div><div class="ar2">Sets the risk profile, the goal and the rules; answers yes or no; places orders at the broker. Nothing in this system can trade.</div></div>'+
ag("cc","Councillor","Weighs what the analysts report, argues the bull and bear cases, gives a verdict with its reasons, and answers your questions.","the analysts' output, your records, the engine's risk numbers",lastMsg&&lastMsg>dg?lastMsg:dg,9,"A2 "+MID+" PREPARES, YOU DECIDE",chat)+
ag("","News Reader","Reads company news for every watched ticker and keeps only facts.","news search, Twelve Data, Alpha Vantage",dg,9,"A1 "+MID+" REPORTS")+
ag("","Data Analyst","Price against its averages, momentum, fair value and earnings dates for each ticker.","Twelve Data, FMP, Alpha Vantage",dg,9,"A1 "+MID+" REPORTS")+
ag("","Mispricing Scanner","Compares each price with fair value and analysts' targets and flags wide gaps.","the Data Analyst's numbers",dg,9,"A1 "+MID+" REPORTS")+
ag("","Consultant","Turns a pick into a size, using a mechanical rule against your cash.","treasury snapshot, risk profile",dg,9,"A2 "+MID+" PREPARES")+
ag("","Advisor","Long-term judgment on each pick and one question for you each week.","picks, track record",dg,9,"A1 "+MID+" REPORTS")+
ag("","Bookkeeper","Exchange rate, paper portfolio, price alerts, the daily brief and the evening summary.","Twelve Data, Alpha Vantage, MNB",stt.books_ran_at,12,"A3 "+MID+" KEEPS RECORDS")+
ag("","Inbox clerk","Records the trades you log, applies settings, forwards new picks to your phone.","your entries from the app",stt.inbox_last_entry_at,40,"A3 "+MID+" KEEPS RECORDS")+
ag("","Calculation engine","Not an AI: plain code for correlations, volatility, the health check and the optimiser comparison.",psrc()+" price history, treasury snapshot",q&&q.as_of,14,"A3 "+MID+" KEEPS RECORDS")+'</div>'+
slot("cc-extra",null,"")+'<div class="src">Autonomy levels: A1 observes and reports. A2 prepares a decision for your yes or no. A3 keeps the records on its own. No agent has a level that can place an order. A hollow amber dot means the agent is later than its schedule.</div>';}

/* ---------- system ---------- */
function loadRuns(){if(Date.now()-st.runsAt<600000)return;st.runsAt=Date.now();
Promise.all([fetch(GH+"/commits?per_page=60").then(function(r){return r.ok?r.json():null;}),fetch(GH+"/actions/runs?per_page=30").then(function(r){return r.ok?r.json():null;})])
.then(function(r){st.runs={commits:r[0],actions:r[1]&&r[1].workflow_runs,at:new Date().toISOString()};renderSystem();}).catch(function(){});}
function checklist(){var q=X.quant||{},o=q.opt||{};function d(ok,part){return ok?'<span class="stg live">BUILT</span>':(part?'<span class="stg stale">PARTLY</span>':NB);}
function fin(rows){return rows.map(function(r){var f=DONE[r[0]],v=null;if(f){try{v=f();}catch(e){}}return v==null?r:[r[0],r[1],d(v===true,v==="part")];});}
return fin([[1,"Analyst and councillor prompts rewritten",d(!!(S.digest&&S.digest.rulebook))],[2,"Risk profile per person",d(!!(q.profile&&q.profile.set),!!q.profile)],[3,"Portfolio health check",d(!!q.health)],
[4,"Diversification maths",d(!!o.held)],[5,"Bonds in the analysis",d(!!o.wide)],[6,"Shorts with safeguards",d(false,!!q.shorts)],[7,"Research card",d(false)],[8,"Valuation (DCF)",d(false)],[9,"Earnings reviewer",d(false)],
[10,"Smart-money tracker",d(false)],[11,"Real-world signals lab",d(false)],[12,"Backtester",d(false)],[13,"Decision cards",d(false)],[14,"Rebalance plan",d(false)],[15,"Timed plans",d(false)],[16,"Hold projection",d(false)],
[17,"Doomsday protocol",d(false,!!q.stress)],[18,"Morning check with yes / no",d(false)],[19,"Paper trading and track record",d(false,!!(S.paper&&S.paper.positions))],[20,"Several people with private logins",d(false)],[21,"Joint account with change log",d(false)]]);}
function renderSystem(){var el=$("v-system");if(!el)return;var q=X.quant,stt=S.status||{},src=sources(),pr=(q&&q.profile)||null;
var sr=src.map(function(s){var act=s.fix==="conn"?'<a class="btn sm" href="https://claude.ai/settings/connectors" target="_blank" rel="noopener">Reconnect</a>':(s.fix==="eng"?'<a class="btn sm" href="https://github.com/benipkun/market-council-state/actions" target="_blank" rel="noopener">Engine runs</a>':(s.fix==="net"?'<span class="fl" style="font-size:11px">needs www.mnb.hu allowed in the routine network settings</span>':""));
return '<div class="fd"><div class="ft" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap"><span class="stg '+(s.ok?"live":(s.opt?"sample":"stale"))+'">'+(s.ok?"LIVE":(s.opt?"NOT SET":"DOWN"))+'</span>'+esc(s.n)+'<span style="margin-left:auto">'+(s.ok?"":act)+'</span></div><div class="fx2">'+esc(s.use)+". "+esc(s.note)+". Last checked "+(s.at?esc(MC.when(s.at)):"never")+'.</div></div>';}).join("");
var runs='<div class="fl">Loading the run list from GitHub'+String.fromCharCode(8230)+'</div>';
if(st.runs&&st.runs.commits){var by={},order=[];st.runs.commits.forEach(function(c){var n=c.commit.author.name;if(!by[n]){by[n]={n:0,at:c.commit.author.date,msg:c.commit.message.split(NL)[0]};order.push(n);}by[n].n++;});
var wf={};(st.runs.actions||[]).forEach(function(r){if(!wf[r.name])wf[r.name]={at:r.created_at,res:r.conclusion||r.status};});
runs=order.map(function(n){return '<div class="fd"><div class="ft">'+esc(n)+' <span class="fl" style="font-weight:400">'+MID+" "+esc(MC.when(by[n].at))+" ("+esc(MC.ago(by[n].at))+")</span></div><div class='fx2'>"+esc(by[n].msg.slice(0,150))+" "+MID+" "+by[n].n+' of the last 60 commits</div></div>';}).join("")+
Object.keys(wf).map(function(n){return '<div class="fd"><div class="ft">'+esc(n)+' <span class="fl" style="font-weight:400">'+MID+" GitHub workflow "+MID+" "+esc(MC.when(wf[n].at))+'</span></div><div class="fx2">last result: '+esc(wf[n].res)+'</div></div>';}).join("");}
else if(st.runs)runs='<div class="fl">GitHub did not return the run list (rate limit). It will be tried again in ten minutes.</div>';
var pt=(S.paper&&S.paper.totals)||null,paper=pt?kv("Paper picks tracked",esc((S.paper.positions||[]).length))+[["open","Open now"],["closed","Closed"],["pl_usd","Picks, profit or loss"],["spy_pl_usd","Same money in the S&P 500 fund"],["diff_usd","Picks minus S&P 500"]].filter(function(k){return pt[k[0]]!=null;}).map(function(k){var v=pt[k[0]];return kv(k[1],k[0].indexOf("usd")>0?sm(v):esc(v));}).join(""):'<div class="fl">No paper portfolio yet.</div>';
var L=pr?pr.limits:null,prof=pr?kv("Person",esc(pr.name||pr.id))+kv("Risk level",esc(pr.risk_level)+" of 5 "+MID+" "+esc(pr.label))+kv("Time horizon",esc(pr.horizon_years)+" years")+kv("Largest loss you accept",esc(pr.max_loss_pct)+"%")+kv("Short selling",pr.allow_shorts?"on":"off")+
kv("Most in one company",p1(L.stock_cap,0))+kv("Risk per new idea",p1(L.risk_per_trade,2)+" of value")+kv("Volatility target",p1(L.target_vol,0)+" a year")+kv("Cash buffer",p1(L.min_cash,0)):'<div class="nbx">Needs the calculation engine.</div>';
var form='<details class="sub"><summary>Set or change your risk profile</summary><div class="two"><label class="fld"><span>Risk level (1 cautious '+DASH+' 5 aggressive)</span><select id="pr-lv">'+[1,2,3,4,5].map(function(n){return '<option'+(pr&&pr.risk_level===n?" selected":"")+'>'+n+'</option>';}).join("")+'</select></label>'+
'<label class="fld"><span>Time horizon (years)</span><input id="pr-hz" type="number" inputmode="numeric" min="1" max="40" value="'+esc(pr?pr.horizon_years:5)+'"></label></div><div class="two"><label class="fld"><span>Largest loss you accept (%)</span><input id="pr-ml" type="number" inputmode="numeric" min="5" max="90" value="'+esc(pr?pr.max_loss_pct:25)+'"></label>'+
'<label class="fld"><span>Short selling</span><select id="pr-sh"><option value="off">off</option><option value="on"'+(pr&&pr.allow_shorts?" selected":"")+'>on (needs level 4 or 5)</option></select></label></div><div class="gap"><button class="btn" data-mc="pr-save" style="width:100%">Save risk profile</button></div><div id="pr-stat"></div></details>';
el.innerHTML=head("SYSTEM","System",tag(stt.books_ran_at,12))+
(q&&q.stress?blk("MARKET STRESS LEVEL",tag(q.as_of,14),'<div style="font-size:19px;font-weight:800">'+esc(String(q.stress.level).toUpperCase())+'</div>'+kv("S&P 500 fund against its 12-month high",sp(q.stress.spy_from_high,1))+kv("Against its 200-day average",sp(q.stress.spy_vs_200d,1))+kv("20-day volatility, yearly rate",p1(q.stress.spy_vol_20d,0))+
'<div class="src">'+q.stress.rules.map(esc).join(". ")+'.</div>'+slot("sy-doom",null,'<div class="nbx gap">'+NB+' What to sell, in what order, what to move into and when to return. <span class="fl">Upgrade item 17.</span></div>'),"Prices to "+sd(q.stress.as_of)+", "+psrc()+"."):"")+
'<div class="g2"><div>'+blk("DATA SOURCES",'<span class="stg lvl">'+src.filter(function(s){return s.ok;}).length+"/"+src.filter(function(s){return !s.opt;}).length+' LIVE</span>',sr,"Connector status comes from the last bookkeeping run; engine sources from the last engine run.")+
blk("PEOPLE AND RISK PROFILES",pr?(pr.set?'<span class="stg live">SET BY YOU</span>':'<span class="stg stale">DEFAULT '+MID+' NOT SET</span>'):NB,prof+form,"The profile sets the limits used by the health check and by every suggested size. More people with private logins: upgrade item 20.")+'</div><div>'+
blk("ROUTINE RUNS",st.runs?tag(st.runs.at,2):'',runs,"Read live from the repository's commit history and workflow runs.")+
blk("PAPER-TRADING TRACK RECORD",'<span class="stg paper">PAPER</span>',paper+'<div class="gap"><button class="btn sm" data-tab="review">Open the full track record '+ARROW+'</button></div>',"Pretend money following the Council's picks against the S&P 500 fund. "+upd(S.paper&&S.paper.as_of)+".")+'</div></div>'+
slot("sy-extra",null,"")+blk("UPGRADE CHECKLIST",'',checklist().map(function(x){return '<div class="ck"><span class="n">'+x[0]+'</span><span>'+esc(x[1])+'</span>'+x[2]+'</div>';}).join(""),"A row turns to BUILT only when its data exists in the repository.");
if(MC.cur()==="system")loadRuns();}

/* ---------- wiring ---------- */
function ask(text,box){text=String(text||"").split(NL).join(" ").trim().slice(0,1000);if(!text){MC.toast("Type a question first.",true);return Promise.resolve(false);}
return MC.send("ask: "+text+NL,"ask",text,box||"cmd-stat","<b>Sent.</b> The Council usually answers within a few minutes, under COUNCIL and on your phone.");}
function fileIn(f){if(!f)return;if(f.size>200000||!(f.type.indexOf("text")===0||/[.](txt|csv|md|json)$/i.test(f.name))){MC.toast("Only text files up to 200 KB for now (txt, csv, md, json).",true);return;}
var rd=new FileReader();rd.onload=function(){var t=String(rd.result||""),low=t.toLowerCase();
if((low.indexOf("bought")>=0||low.indexOf("sold")>=0)&&t.length<1500&&$("paste")){$("paste").value=t;MC.show("log");var pb=$("paste-box");if(pb)pb.open=true;MC.parsePaste();MC.toast("Read into the Log form. Check it, then press Log it.");return;}
$("cmd-in").value=("File "+f.name+": "+t.split(NL).join(" ")).slice(0,900);$("cmd-in").focus();
MC.toast("The start of the file is in the box. Messages are stored in your public repository, so remove anything private, add your question, then send.");};rd.readAsText(f);}
function renderMC(){[renderStrip,renderTodayTop,renderMap,renderRisk,renderResearch,renderCouncil,renderSystem].forEach(function(f){try{f();}catch(e){if(window.console)console.error(e);}});}
var loadingX=false,againX=false;
function loadX(){if(loadingX){againX=true;return;}loadingX=true;var ks=Object.keys(EXTRA);
function fin(){loadingX=false;MCX.render();if(againX){againX=false;loadX();}}
Promise.all(ks.map(function(k){return MC.get(EXTRA[k]).catch(function(){return null;});})).then(function(r){ks.forEach(function(k,i){if(r[i])X[k]=r[i];});fin();},fin);}
document.addEventListener("click",function(e){
var b=e.target.closest("[data-mc]");if(!b){if(e.target.id==="pf-show"||e.target.id==="pf-hide")setTimeout(renderMC,0);return;}
var a=b.dataset.mc,v=b.dataset.v;
if(a==="rng"){st.rng=v;renderMap();}else if(a==="pv"){st.pview=v;renderMap();}else if(a==="xd"){st.xdim=v;renderMap();}
else if(a==="opt"){st.opt=v;renderRisk();}else if(a==="cm"){st.cm=v;renderRisk();}
else if(a==="pos"){openPos(b.dataset.t);}else if(a==="back"){closePos();}
else if(a==="corr"){var r=rho(b.dataset.a,b.dataset.b),i=$("map-info");if(i)i.innerHTML="<b style='color:var(--tx)'>"+esc(b.dataset.a)+" and "+esc(b.dataset.b)+": correlation "+f2(r)+"</b> over "+esc(X.quant.corr.window_days)+" trading days. "+(Math.abs(r)<0.3?"They mostly move independently.":(r>=0.6?"They tend to move together.":(r>0?"They share some of their moves.":"They tend to move in opposite directions.")));}
else if(a==="rs-go"){var t=($("rs-in").value||"").trim().toUpperCase();if(t)openPos(t);}
else if(a==="tool"){var tl=TOOLS[v];if(tl&&tl.open)tl.open();}
else if(a==="cc-go"){ask($("cc-in").value,"cc-stat").then(function(ok){if(ok){$("cc-in").value="";}});}
else if(a==="cmd-go"){ask($("cmd-in").value).then(function(ok){if(ok)$("cmd-in").value="";});}
else if(a==="askq"){closePos();$("cmd-in").value=b.dataset.q;$("cmd-in").focus();window.scrollTo(0,0);}
else if(a==="logit"){closePos();MC.prefill({t:b.dataset.t,act:"buy"});}
else if(a==="pr-save"){var lv=$("pr-lv").value,hz=Math.round(num($("pr-hz").value)||0),ml=Math.round(num($("pr-ml").value)||0),sh=$("pr-sh").value;
if(!(hz>=1&&hz<=40)||!(ml>=5&&ml<=90)){MC.toast("Enter a horizon of 1 to 40 years and a loss of 5 to 90%.",true);return;}
MC.send("profile ben level "+lv+" horizon "+hz+" maxloss "+ml+" shorts "+sh+NL,"setting","risk profile: level "+lv+", "+hz+" years, max loss "+ml+"%, shorts "+sh,"pr-stat");}
});
document.addEventListener("keydown",function(e){if(e.key==="Escape"&&st.open){closePos();return;}if(e.key!=="Enter")return;var id=e.target&&e.target.id;
if(id==="cmd-in"){e.preventDefault();ask($("cmd-in").value).then(function(ok){if(ok)$("cmd-in").value="";});}
else if(id==="cc-in"){e.preventDefault();ask($("cc-in").value,"cc-stat").then(function(ok){if(ok)$("cc-in").value="";});}
else if(id==="rs-in"){e.preventDefault();var t=($("rs-in").value||"").trim().toUpperCase();if(t)openPos(t);}
else if(e.target&&e.target.dataset&&e.target.dataset.mc==="pos"){openPos(e.target.dataset.t);}});
window.addEventListener("popstate",function(){if(st.open)closePos(true);});
var cf=$("cmd-file");if(cf)cf.addEventListener("change",function(){fileIn(cf.files[0]);cf.value="";});
var cb=$("cmd");if(cb){cb.addEventListener("dragover",function(e){e.preventDefault();});cb.addEventListener("drop",function(e){e.preventDefault();fileIn(e.dataTransfer&&e.dataTransfer.files[0]);});}
MC.onShow=function(t){if(t==="system")loadRuns();};
window.MCX={X:X,st:st,S:S,slots:SL,tools:TOOLS,done:DONE,extra:EXTRA,A:A,blk:blk,tag:tag,nb:nb,kv:kv,sp:sp,sm:sm,p1:p1,f2:f2,sd:sd,upd:upd,col:col,pos:pos,rho:rho,seg:seg,head:head,pts:pts,wkH:wkH,t2:t2,NB:NB,
render:function(){renderMC();if(st.open){var pe=$("ppanel"),ae=document.activeElement;if(pe&&!(ae&&ae.tagName==="INPUT"&&pe.contains(ae))){var y=pe.scrollTop;pe.innerHTML=posHtml(st.open);pe.scrollTop=y;}}},reload:function(){loadX();},openPos:openPos,closePos:closePos,ask:ask};
fetch("mc/modules.json",{cache:"no-store"}).then(function(r){return r.ok?r.json():[];}).then(function(list){(list||[]).forEach(function(n){if(/^[a-z0-9]+[.]js$/.test(n)){var s=document.createElement("script");s.src="mc/"+n;document.body.appendChild(s);}});}).catch(function(){});
MC.hooks.push(function(){renderMC();loadX();});
renderMC();loadX();
})();
