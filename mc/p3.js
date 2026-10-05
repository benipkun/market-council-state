/* Market Council add-on 3: decision cards, rebalance plan, timed plans, hold plans, doomsday steps,
   morning check, paper book, backtester and signals lab (data: state/decisions.json, state/lab.json,
   state/paper_book.json). Answers are written as small files in answers/; nothing here places an order. */
(function(){
"use strict";
var M=window.MCX,MC=window.MC;if(!M||!MC)return;
var esc=MC.esc,num=MC.num,$=MC.$,MID=String.fromCharCode(183),DASH=String.fromCharCode(8212),MINUS=String.fromCharCode(8722),ELL=String.fromCharCode(8230);
var API="https://api.github.com/repos/benipkun/market-council-state",REPO="https://github.com/benipkun/market-council-state",LS="mc_answers";
M.extra.dec="state/decisions.json";M.extra.lab="state/lab.json";M.extra.pbook="state/paper_book.json";
var ui={bt:null,br:"trend200"},CH={};
var css=document.createElement("style");css.textContent=
".p3q{border-top:1px solid var(--bd);padding:11px 0}.p3q:first-child{border-top:0;padding-top:2px}.p3q .t{font-weight:800;font-size:13px}.p3q .d{font-size:12px;color:var(--dim);margin:3px 0 8px}"+
".p3b{display:flex;gap:8px}.p3b button{flex:1;min-height:44px;border:1px solid var(--bd);border-radius:3px;background:var(--sf);color:var(--tx);font:inherit;font-weight:800;font-size:12px;letter-spacing:.06em;text-transform:uppercase}"+
".p3b button.y{border-color:var(--ac);color:var(--ac);background:var(--acs)}.p3b button:disabled{opacity:.5}"+
".p3o{border:1px solid var(--bd);border-radius:3px;padding:8px 10px;margin-top:6px;font-size:12px;color:var(--dim);overflow-wrap:anywhere}.p3o b{color:var(--tx)}"+
".p3o .s{display:inline-block;letter-spacing:.08em;font-size:10px;font-weight:800;border:1px solid var(--bd);border-radius:2px;padding:1px 5px;margin-right:7px;color:var(--tx)}"+
".p3c{position:relative;margin:6px 0 2px}.p3c svg{display:block;width:100%;height:auto;touch-action:pan-y}.p3c text{font-family:var(--mono);font-size:9.5px;fill:var(--dim)}.p3c text.e{fill:var(--tx);font-weight:700}"+
".p3tip{position:absolute;top:0;width:150px;background:var(--sf2);border:1px solid var(--bd);border-radius:3px;padding:6px 8px;font-size:11px;color:var(--tx);pointer-events:none}.p3tip i{display:inline-block;width:8px;height:8px;border-radius:2px;margin-right:6px}"+
".p3s{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:8px}.p3s select{flex:1;min-width:120px;height:42px;font:inherit;font-size:14px;padding:0 8px;border:1px solid var(--bd);border-radius:3px;background:var(--bg);color:var(--tx)}"+
".p3l{font-size:12px;color:var(--dim);margin:0;padding-left:16px}.p3l li{margin-top:4px}"+
".p3d{border-top:1px solid var(--bd);margin-top:10px}.p3d>summary{padding:13px 0;cursor:pointer;font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--ac)}.p3w th,.p3w td{white-space:normal}.p3w td:first-child{min-width:92px}";document.head.appendChild(css);

/* ---------- small helpers ---------- */
function D(){return M.X.dec||null;}
function vis(){return MC.pfVisible();}
function amt(v){return vis()?esc(MC.money(v)):'<span class="fl">hidden</span>';}
function pc(v,d){return M.p1(v,d==null?0:d);}
function px(v){var n=num(v);return n==null?DASH:"$"+n.toFixed(2);}
function sg(v,d){var n=num(v);return n==null?DASH:(n>0?"+":(n<0?MINUS:""))+Math.abs(100*n).toFixed(d==null?1:d)+"%";}
function dl(s){return s?M.sd(s)+" "+String(s).slice(0,4):DASH;}
function list(a){return a&&a.length?'<ul class="p3l">'+a.map(function(x){return "<li>"+esc(x&&x.t?(vis()?x.t:x.plain):x)+"</li>";}).join("")+"</ul>":"";}
function ttl(c){return vis()?c.title:(c.title_plain||c.title);}
function local(){try{return JSON.parse(localStorage.getItem(LS)||"{}")||{};}catch(e){return {};}}
function setLocal(id,a){var L=local();L[id]={answer:a,at:new Date().toISOString()};Object.keys(L).forEach(function(k){if(Date.now()-new Date(L[k].at).getTime()>3*86400000)delete L[k];});try{localStorage.setItem(LS,JSON.stringify(L));}catch(e){}}
function stamp(){return new Date().toISOString().replace(/[-:]/g,"").replace(/[.][0-9]+Z$/,"")+"-"+Math.random().toString(36).slice(2,7);}
function post(obj,label,box){obj.at=new Date().toISOString().replace(/[.][0-9]+Z$/,"Z");var tok=MC.store(MC.K.tok),path="answers/"+stamp()+".json",body=JSON.stringify(obj);
function say(k,h){var e=box&&$(box);if(e)e.innerHTML='<div class="stat '+k+'">'+h+'</div>';else MC.toast(h,k==="err");}
if(!tok){window.open(REPO+"/new/main?filename="+encodeURIComponent(path)+"&value="+encodeURIComponent(body),"_blank","noopener");say("wait","<b>Finish on GitHub:</b> press <i>Commit changes</i>. Without a saved token the app cannot record it for you.");return Promise.resolve(true);}
say("wait","Recording"+ELL);
return fetch(API+"/contents/"+path,{method:"PUT",headers:{"Authorization":"Bearer "+tok,"Accept":"application/vnd.github+json","Content-Type":"application/json"},body:JSON.stringify({message:"Market Council answer: "+label,content:btoa(unescape(encodeURIComponent(body)))})})
.then(function(r){if(r.status===201){say("wait","<b>Recorded.</b> The engine takes it in within a few minutes.");return true;}say("err","GitHub returned "+r.status+". Nothing was recorded.");return false;})
.catch(function(){say("err","Could not reach GitHub. Nothing was recorded.");return false;});}
function said(id,engine,at){if(engine)return {a:engine,at:at,rec:true};var l=local()[id];return l?{a:l.answer,at:l.at,rec:false}:null;}

/* ---------- line chart with a hover read-out ---------- */
function chart(id,dates,series,opt){opt=opt||{};var W=340,H=176,L=40,R=78,T=8,B=20,n=dates.length,all=[];
series.forEach(function(s){s.vals.forEach(function(v){if(v>0)all.push(v);});});if(n<2||!all.length)return "";
var lo=Math.min.apply(null,all),hi=Math.max.apply(null,all),lg=!!opt.log;function f(v){return lg?Math.log(v):v;}
var a=f(lo),b=f(hi);if(b-a<1e-9)b=a+1e-9;
function X(i){return L+(W-L-R)*i/(n-1);}function Y(v){return T+(H-T-B)*(1-(f(v)-a)/(b-a));}
var fmt=opt.fmt||function(v){return sg(v-1,0);};
var grid=[lo,lg?Math.exp((a+b)/2):(lo+hi)/2,hi].map(function(v){var y=Y(v).toFixed(1);return '<line x1="'+L+'" x2="'+(W-R)+'" y1="'+y+'" y2="'+y+'" stroke="var(--bd)" stroke-width="1"/><text x="'+(L-5)+'" y="'+(+y+3)+'" text-anchor="end">'+fmt(v)+'</text>';}).join("");
var ends=series.map(function(s,i){return {i:i,y:Y(s.vals[n-1])};}).sort(function(p,q){return p.y-q.y;});
for(var k=1;k<ends.length;k++)if(ends[k].y-ends[k-1].y<11)ends[k].y=ends[k-1].y+11;
var lines=series.map(function(s){return '<path d="'+s.vals.map(function(v,i){return (i?"L":"M")+X(i).toFixed(1)+","+Y(v).toFixed(1);}).join("")+'" fill="none" stroke="'+s.color+'" stroke-width="2" stroke-linejoin="round"'+(s.dash?' stroke-dasharray="'+s.dash+'"':"")+'/>';}).join("");
var labs=ends.map(function(e){var s=series[e.i];return '<text class="e" x="'+(W-R+5)+'" y="'+(e.y+3).toFixed(1)+'">'+esc(s.short||s.name)+" "+fmt(s.vals[n-1])+'</text>';}).join("");
CH[id]={dates:dates,series:series,W:W,L:L,R:R,n:n,fmt:fmt};
return '<div class="p3c" data-id="'+id+'"><svg viewBox="0 0 '+W+" "+H+'" role="img" aria-label="'+esc(opt.label||"Line chart")+'">'+grid+lines+labs+
'<line class="xh" y1="'+T+'" y2="'+(H-B)+'" stroke="var(--dim)" stroke-width="1" visibility="hidden"/><text x="'+L+'" y="'+(H-5)+'">'+esc(dl(dates[0]))+'</text><text x="'+(W-R)+'" y="'+(H-5)+'" text-anchor="end">'+esc(dl(dates[n-1]))+'</text></svg><div class="p3tip" hidden></div></div>'+
'<div class="leg">'+series.map(function(s){return '<span><i style="background:'+s.color+'"></i>'+esc(s.name)+(s.dash?" (dashed)":"")+'</span>';}).join("")+'</div>';}
function hov(e){var box=e.target&&e.target.closest?e.target.closest(".p3c"):null;if(!box)return;var c=CH[box.dataset.id];if(!c)return;
var svg=box.querySelector("svg"),r=svg.getBoundingClientRect(),x=(e.clientX-r.left)*c.W/r.width,i=Math.max(0,Math.min(c.n-1,Math.round((x-c.L)/(c.W-c.L-c.R)*(c.n-1)))),xi=c.L+(c.W-c.L-c.R)*i/(c.n-1);
var ln=svg.querySelector(".xh");ln.setAttribute("x1",xi);ln.setAttribute("x2",xi);ln.setAttribute("visibility","visible");
var tip=box.querySelector(".p3tip");tip.innerHTML="<b>"+esc(dl(c.dates[i]))+"</b>"+c.series.map(function(s){return '<div><i style="background:'+s.color+'"></i>'+esc(s.short||s.name)+" "+c.fmt(s.vals[i])+'</div>';}).join("");
tip.hidden=false;tip.style.left=Math.min(r.width-152,Math.max(0,xi/c.W*r.width-75))+"px";}
document.addEventListener("pointermove",hov);document.addEventListener("pointerdown",hov);
M.chart=chart;

/* ---------- decision cards (item 13) ---------- */
function order(o,c){var h='<div class="p3o"><span class="s">'+esc(o.side.toUpperCase())+'</span><b>'+esc(o.ticker)+'</b> '+esc(o.name||"")+'<br>'+
(vis()?"Amount "+esc(MC.money(o.usd))+" ("+pc(o.pct_nav,1)+" of the portfolio)"+(o.qty?" "+MID+" about "+esc(o.qty)+" shares":""):pc(o.pct_nav,1)+" of the portfolio")+
'<br>Limit '+px(o.limit)+" "+MID+" last close "+px(o.ref_price)+(o.stop?'<br>Stop '+px(o.stop)+" (place it with the order) "+MID+" take-profit "+px(o.take_profit):"")+
(o.eu?'<br>EU-listed equivalent: <b>'+esc(o.eu)+'</b>':"")+(o.tax_note?'<br>'+esc(vis()?o.tax_note:(o.tax_plain||"")):"");
if(c.status==="approved")h+='<div class="gap"><button class="btn sm" data-p3="log" data-t="'+esc(o.ticker)+'" data-side="'+esc(o.side)+'" data-usd="'+esc(o.usd)+'">Placed it? Log this trade</button></div>';
return h+'</div>';}
function cardBody(c){var e=c.effect,h=(c.orders||[]).map(function(o){return order(o,c);}).join("");
h+='<div class="lbl" style="margin-top:10px">Why</div>'+list(c.why)+'<div class="lbl" style="margin-top:10px">Against it</div>'+list(c.against);
if(e)h+='<div style="margin-top:8px">'+M.kv("Volatility a year (estimate)",pc(e.vol_before)+" now, "+pc(e.vol_after_part)+" after this part, "+pc(e.vol_after_all)+" after all parts")+M.kv("Largest position",pc(e.largest_before)+" now, "+pc(e.largest_after_part)+" after this part, "+pc(e.largest_after_all)+" after all parts")+'</div>';
return h+'<div class="src">'+esc(c.method||"")+" Estimate, not advice. You place every order yourself.</div>";}
function cardState(c){var s=said(c.id,c.status==="approved"?"yes":(c.status==="declined"?"no":null),c.answered_at);
if(c.status==="open"&&!s)return '<div class="p3b"><button class="y" data-p3="ans" data-k="decision" data-id="'+esc(c.id)+'" data-v="yes">Approve</button><button data-p3="ans" data-k="decision" data-id="'+esc(c.id)+'" data-v="no">Decline</button></div>';
if(c.status==="open"||c.status==="approved"||c.status==="declined")return '<div class="q me">You said <b>'+(s.a==="yes"?"YES":"NO")+'</b> '+MID+" "+esc(MC.when(s.at))+(s.rec?(s.a==="yes"?". Place the orders yourself in your broker, then log each one.":". Not raised again for 14 days."):". Waiting for the engine to record it.")+'</div>';
return '<div class="q">'+esc(c.status.toUpperCase())+(c.closed_why?": "+esc(c.closed_why):(c.logged?": "+esc(c.logged):""))+'</div>';}
function cardTag(c){return c.status==="open"?M.tag(c.refreshed||c.created,14):'<span class="stg lvl">'+esc(c.status.toUpperCase())+'</span>';}
function cardBlock(c){return M.blk("DECISION CARD "+esc(c.id),cardTag(c),'<div style="font-weight:800;font-size:14px;margin-bottom:6px">'+esc(ttl(c))+'</div>'+cardState(c)+cardBody(c),"Raised "+esc(MC.when(c.created))+", expires "+esc(M.sd(c.expires))+".");}

/* ---------- today: the morning check (item 18) ---------- */
M.slots["td-dec"]=function(){setTimeout(paperInject,0);var d=D();if(!d||!d.morning)return "";var m=d.morning,byId={};(d.cards||[]).forEach(function(c){byId[c.id]=c;});
var qs=m.questions.map(function(q){var c=byId[q.id],s=c?null:said(q.id,q.answer,q.answered_at),h='<div class="p3q"><div class="t">'+esc(vis()?q.text:(q.text_plain||q.text))+'</div><div class="d">'+esc(q.detail||"")+'</div>';
if(c)h+=cardState(c)+'<details class="p3d"><summary>See the order ticket and the reasons</summary>'+cardBody(c)+'</details>';
else if(s)h+='<div class="q me">You said <b>'+(s.a==="yes"?esc(q.yes):esc(q.no))+'</b> '+MID+" "+esc(MC.when(s.at))+(s.rec?"":". Waiting for the engine to record it.")+'</div>';
else h+='<div class="p3b"><button class="y" data-p3="ans" data-k="morning" data-id="'+esc(q.id)+'" data-v="yes">'+esc(q.yes)+'</button><button data-p3="ans" data-k="morning" data-id="'+esc(q.id)+'" data-v="no">'+esc(q.no)+'</button></div>';
return h+'</div>';}).join("")||'<div class="nbx">Nothing needs a decision today.</div>';
var open=m.questions.filter(function(q){var c=byId[q.id];return c?(c.status==="open"&&!said(c.id,null)):!said(q.id,q.answer);}).length;
return M.blk("DECISIONS WAITING FOR YOU",open?'<span class="stg stale">'+open+" WAITING</span>":M.tag(d.as_of,14),'<div class="fl" style="font-size:12px;margin-bottom:4px">Morning check, '+esc(M.sd(m.date))+": "+esc(m.summary.join(" "))+'</div>'+qs+'<div id="p3-stat"></div>',
"Your answers are saved as small files in the repository and read by the engine. Phone message: "+esc(/^sent \d{4}-/.test(m.sent_note||"")?"sent "+MC.when(m.sent_note.slice(5)):(m.sent_note||"not sent yet today"))+". "+M.upd(d.as_of)+".");};

/* ---------- position panel: decision card and hold plan (items 13, 16) ---------- */
M.slots["pp-dec"]=function(t){var d=D();if(!d)return "";var cs=(d.cards||[]).filter(function(c){return (c.status==="open"||c.status==="approved")&&(c.ticker===t||(c.orders||[]).some(function(o){return o.ticker===t;}));});
if(cs.length)return cs.map(cardBlock).join("")+'<div id="p3-stat2"></div>';var r=(d.screen||[]).filter(function(x){return x.t===t;})[0];
return M.blk("OPEN DECISION CARD",'<span class="stg lvl">NONE OPEN</span>','<div class="nbx">'+(r?"No card for "+esc(t)+": "+esc(r.why)+".":"No rule has raised a card for "+esc(t)+".")+'</div>',"Cards are raised by written rules: a buy needs the price at least 20% under our own fair value and free cash; a sell is raised at your maximum loss; trims come from the rebalance plan. "+M.upd(d.as_of)+".");};
M.slots["pp-hold"]=function(t){var d=D();if(!d)return "";var h=d.holds&&d.holds[t];
if(!h)return M.blk("HOLD PLAN",'<span class="stg lvl">NOT HELD</span>','<div class="nbx">You do not hold '+esc(t)+', so there is no hold plan for it.</div>');
if(!h.range)return M.blk("HOLD PLAN",'<span class="stg stale">NO DATA</span>','<div class="nbx">'+esc(h.why||h.status)+'</div>');
var lv=h.levels.slice().sort(function(a,b){return b.price-a.price;}),s=h.since_buy,k=h.keep,ny=new Date(Date.now()+365*86400000).toISOString().slice(0,10);
var kp=k?'<div class="q me"><b>Your plan:</b> keep '+esc(t)+(k.target?" until "+px(k.target)+" ("+sg(k.to_target,0)+" from here)":"")+(k.by?", review by "+esc(dl(k.by)):"")+". Set "+esc(M.sd(k.set_at))+"."+(k.reached?" <b>Target reached.</b>":(k.overdue?" <b>The review date has passed.</b>":""))+'</div>'+
(k.chance_touch!=null?M.kv("Chance of touching the target before the date (model)",pc(k.chance_touch_no_drift)+" to "+pc(k.chance_touch))+M.kv("Chance of being above it on the date itself",pc(k.chance_above_on_date))+'<div class="src">'+esc(k.method)+'</div>':"")+
'<div class="gap"><button class="btn sm" data-p3="kstop" data-id="'+esc(k.id)+'">Stop keeping (allow trims again)</button></div><div id="kp-stat"></div>':
'<details class="p3d"><summary>Keep this position with a target</summary><div class="two"><label class="fld"><span>Target price (USD)</span><input id="kp-target" type="number" inputmode="decimal" step="0.01" placeholder="e.g. 80"></label>'+
'<label class="fld"><span>Review date</span><input id="kp-by" type="date" value="'+ny+'"></label></div><div class="gap"><button class="btn" style="width:100%" data-p3="keep" data-t="'+esc(t)+'">Keep it: do not propose trims</button></div>'+
'<div class="src">The rebalance plan then leaves this position alone. A card is raised when the target is reached or the review date passes. The health check still shows the concentration.</div></details><div id="kp-stat"></div>';
return M.blk("HOLD PLAN",M.tag(d.as_of,14),kp+'<div style="font-weight:800;font-size:13px;margin-top:8px">'+esc(h.status.charAt(0).toUpperCase()+h.status.slice(1))+'</div>'+
(s?'<div class="q">Bought '+esc(M.sd(s.date))+" at "+px(s.price)+". After "+s.days+" trading days the expected range was "+px(s.expected_low)+" to "+px(s.expected_high)+"; the price is "+px(h.price)+".</div>":"")+
'<div class="lbl" style="margin-top:10px">Where the price should be if nothing changes</div><div class="ox"><table class="mt"><tr><th>In</th><th>Low</th><th>Middle</th><th>High</th></tr>'+
h.range.map(function(r){return "<tr><td>"+r.months+(r.months===1?" month":" months")+"</td><td>"+px(r.low)+"</td><td>"+px(r.mid)+"</td><td>"+px(r.high)+"</td></tr>";}).join("")+'</table></div>'+
'<div class="lbl" style="margin-top:10px">Levels that matter (price now '+px(h.price)+')</div>'+lv.map(function(x){return M.kv(esc(x.name),px(x.price)+' <span class="fl">'+Math.abs(Math.round(100*(x.price/h.price-1)))+"% "+(x.price>=h.price?"above":"below")+"</span>");}).join("")+
'<div class="lbl" style="margin-top:10px">What would change the plan</div>'+list(h.triggers),esc(h.method)+" "+M.upd(d.as_of)+".");};

/* ---------- risk: rebalance plan, timed plans, range and goal (items 14, 15, 16) ---------- */
function planRows(p){return p.status==="stopped"?"stopped":(p.status==="finished"?"finished":"next "+(p.next?M.sd(p.next):DASH));}
M.slots["rk-extra"]=function(){var d=D();if(!d)return "";var r=d.rebalance,h="";
if(r){var rows=r.rows.map(function(x){return "<tr><td style='white-space:normal'><b>"+esc(x.t)+"</b> <span class='fl'>"+esc(x.name||"")+(x.eu?" "+MID+" EU: "+esc(x.eu):"")+"</span>"+(x.kept?' <span class="stg lvl">KEPT BY YOU</span>':"")+"</td><td>"+pc(x.now,1)+"</td><td>"+pc(x.target,1)+"</td><td>"+(Math.abs(x.change_usd)<1?DASH:(vis()?M.sm(x.change_usd):sg(x.target-x.now,1)))+"</td></tr>";}).join("");
h+=M.blk("REBALANCE PLAN",r.needed?'<span class="stg stale">PART '+r.part+" OF "+r.tranches+" DUE "+esc(M.sd(r.next_part_due)).toUpperCase()+"</span>":'<span class="stg live">IN BALANCE</span>',
(r.needed?"":'<div class="nbx">'+((r.kept||[]).length?"Nothing to rebalance: "+esc(r.kept.join(", "))+" is above the one-company limit, but you chose to keep it. That risk stays in the health check.":"Every position is inside its limit. Nothing to rebalance.")+'</div>')+'<div class="ox"><table class="mt"><tr><th>Position</th><th>Now</th><th>Target</th><th>Change</th></tr>'+rows+
"<tr><td><b>Cash</b></td><td>"+pc(r.cash_now,1)+"</td><td>"+pc(r.cash_target,1)+"</td><td></td></tr></table></div>"+
M.kv("Volatility a year (estimate)",pc(r.vol_before)+" now, "+pc(r.vol_after)+" after the plan (profile target "+pc(r.target_vol)+")")+M.kv("Largest position",pc(r.largest_before)+" now, "+pc(r.largest_after)+" after")+
M.kv("Cost of all the trades (estimate)",amt(r.cost_usd))+'<div class="gap"><button class="btn sm" data-tab="today">Open today\'s decision card</button></div>',esc(r.method)+" "+esc(r.note)+" "+M.upd(d.as_of)+".");}
var sp=d.spreading,pl=(d.plans||[]).map(function(p){return '<div class="fd"><div class="ft">'+(p.kind==="rebalance"?"Rebalance plan":esc(p.ticker)+" "+MID+" "+amt(p.usd)+" every "+esc(p.every==="2weeks"?"two weeks":p.every))+' <span class="fl" style="font-weight:400">'+MID+" "+esc(planRows(p))+'</span></div><div class="fx2">'+
(p.kind==="rebalance"?esc(p.note):p.done+" of "+p.times+" done"+(p.skipped?", "+p.skipped+" skipped":"")+(p.note?" "+MID+" "+esc(p.note):""))+
(p.kind!=="rebalance"&&p.status==="active"?' <button class="btn sm" style="margin-left:8px" data-p3="pstop" data-id="'+esc(p.id)+'">Stop</button>':"")+'</div></div>';}).join("")||'<div class="fl" style="font-size:12px">No timed plan yet.</div>';
var today=new Date().toISOString().slice(0,10);
h+=M.blk("TIMED PLANS",M.tag(d.as_of,14),pl+'<details class="p3d"><summary>Add a timed plan</summary><div class="two"><label class="fld"><span>Ticker</span><input id="tp-t" type="text" maxlength="12" autocapitalize="characters" autocorrect="off" spellcheck="false" placeholder="e.g. VEA"></label>'+
'<label class="fld"><span>Amount each time (USD)</span><input id="tp-a" type="number" inputmode="decimal" min="1" step="1" placeholder="25"></label></div><div class="two"><label class="fld"><span>How often</span><select id="tp-e"><option value="month">every month</option><option value="2weeks">every two weeks</option><option value="week">every week</option></select></label>'+
'<label class="fld"><span>How many times</span><input id="tp-n" type="number" inputmode="numeric" min="1" max="120" value="6"></label></div><label class="fld"><span>First date</span><input id="tp-s" type="date" value="'+today+'"></label>'+
'<div class="gap"><button class="btn" style="width:100%" data-p3="padd">Save the plan</button></div></details><div id="tp-stat"></div>',
(sp?"Spreading against buying at once: in "+pc(sp.lump_ahead_share)+" of "+sp.starts+" monthly starts since "+esc(String(sp.from).slice(0,4))+", putting everything into the S&P 500 fund on day one was ahead of six monthly parts a year later (average gap "+sg(sp.average_gap,1)+", worst "+sg(sp.worst_gap,0)+"). Spreading lowers regret, not expected return. ":"")+
"A plan only reminds you: each part due appears in the morning check; you place and log it yourself.");
var g=d.goal,pr=d.portfolio_range;
if(pr)h+=M.blk("TWELVE MONTHS AHEAD",M.tag(d.as_of,14),M.kv("Middle outcome",M.sp(pr.mid,0))+M.kv("Four times out of five between",M.sp(pr.low,0)+" and "+M.sp(pr.high,0))+
(g?'<div class="lbl" style="margin-top:10px">Your goal</div>'+M.kv("Goal",vis()?esc(Math.round(g.amount_huf).toLocaleString("hu-HU"))+" Ft by "+esc(g.by):"set, by "+esc(g.by))+M.kv("Chance of reaching it without adding money",pc(g.chance_without_adding))+
M.kv("Needed each month to reach it at the assumed return",vis()?esc(Math.round(g.monthly_needed_huf).toLocaleString("hu-HU"))+" Ft":'<span class="fl">hidden</span>'):""),
"Range from the portfolio's volatility over the last year ("+pc(pr.vol)+") around the engine's return estimate ("+pc(pr.mu,1)+" a year). Both are estimates; the range is wide because one share dominates. "+(g?esc(g.method):""));
return h;};

/* ---------- risk: short selling and its safeguards (item 6) ---------- */
M.slots["rk-shorts"]=function(){var d=D();if(!d||!d.shorts)return "";var s=d.shorts;
return M.blk("SHORT SELLING",'<span class="stg lvl">'+(s.allowed?"ALLOWED":"OFF FOR YOUR PROFILE")+'</span>','<div class="fl" style="font-size:12px">'+esc(s.rule)+'</div>'+
(s.ideas.length?'<div class="lbl" style="margin-top:10px">'+(s.allowed?"Qualifies today (see the decision cards)":"Would qualify, but no card is raised while short selling is off")+'</div>'+s.ideas.map(function(i){return M.kv("<b>"+esc(i.t)+"</b>",esc(i.why));}).join(""):'<div class="nbx gap">No share on the watchlist qualifies today.</div>')+
'<div class="lbl" style="margin-top:10px">Safeguards on every short card</div>'+list(s.safeguards),"Switch it under SYSTEM, People and risk profiles; it needs risk level 4 or 5 and a broker that offers short selling. "+M.upd(d.as_of)+".");};
M.done[6]=function(){var d=D();return !!(d&&d.shorts);};

/* ---------- system: doomsday protocol and its back-test (item 17) ---------- */
M.slots["sy-doom"]=function(){var d=D();if(!d||!d.doomsday)return "";var z=d.doomsday,bt=(M.X.lab&&M.X.lab.doomsday)||null,h='<div class="lbl" style="margin-top:12px">What to do at each level</div>';
["Watch","Defensive","Doomsday"].forEach(function(lv){var s=z.steps[lv];if(!s)return;h+='<div class="q'+(z.level===lv?" me":"")+'"><b style="color:var(--tx)">'+lv.toUpperCase()+(z.level===lv?" (NOW)":"")+"</b> "+esc(s.text)+
(s.sell&&s.sell.length?list(s.sell.map(function(x){return x.t+": sell "+(vis()?MC.money(x.usd):Math.round(100*x.share_of_position)+"% of the position")+" ("+x.why+")";})):"")+'</div>';});
h+='<div class="q"><b style="color:var(--tx)">COMING BACK</b> '+esc(z.return_rule)+'</div><div class="q'+(z.level==="Normal"?" me":"")+'"><b style="color:var(--tx)">TODAY: '+esc(String(z.level).toUpperCase())+"</b> "+esc(z.today||"")+'</div>';
if(bt&&bt.status==="ok"){var c=bt.curve;h+='<div class="lbl" style="margin-top:12px">Back-test, '+esc(String(bt.from).slice(0,4))+" to "+esc(String(bt.to).slice(0,4))+'</div><div style="font-size:12.5px;font-weight:700;margin:4px 0">'+esc(bt.verdict)+'</div>'+
chart("doom",c.dates,[{name:"Protocol",vals:c.protocol,color:"var(--s1)"},{name:"Hold throughout",short:"Hold",vals:c.hold,color:"var(--s2)"},{name:"200-day rule",short:"200-day",vals:c.trend200,color:"var(--dim)",dash:"4 3"}],{log:true,label:"Growth of one dollar: protocol, holding throughout and the 200-day rule",fmt:function(v){return "x"+v.toFixed(v<10?1:0);}})+
'<div class="ox"><table class="mt p3w"><tr><th></th><th>A year</th><th>Worst fall</th><th>Worst 12 months</th><th>Switches</th></tr>'+[["Protocol",bt.protocol],["Hold throughout",bt.hold],["200-day rule",bt.trend200]].map(function(r){return "<tr><td>"+r[0]+"</td><td>"+sg(r[1].cagr,1)+"</td><td>"+sg(r[1].mdd,0)+"</td><td>"+sg(r[1].worst_12m,0)+"</td><td>"+(r[1].switches==null?DASH:r[1].switches)+"</td></tr>";}).join("")+'</table></div>'+
'<details class="p3d"><summary>The '+bt.episodes.length+' deepest falls, one by one</summary><div class="ox"><table class="mt p3w"><tr><th>Peak</th><th>Low</th><th>Holding fell</th><th>Protocol fell</th><th>Protocol at recovery</th></tr>'+
bt.episodes.map(function(e){return "<tr><td>"+esc(dl(e.peak))+"</td><td>"+esc(dl(e.low))+"</td><td>"+sg(e.hold_fall,0)+"</td><td>"+sg(e.protocol_fall,0)+"</td><td>"+sg(e.protocol_at_recovery,0)+"</td></tr>";}).join("")+'</table></div>'+
'<div class="src">The last column is the price of safety: after most falls the protocol was still a few points behind when the market had fully recovered, because it buys back late.</div></details>'+
'<div class="src">'+esc(bt.method)+" Safe asset in the test: "+esc(bt.safe_asset)+". "+esc((M.X.lab||{}).price_note||"")+" "+M.upd(M.X.lab.as_of)+".</div>";}
else h+='<div class="nbx gap">The back-test has not run yet.</div>';
return h;};

/* ---------- research: backtester and signals lab (items 11, 12) ---------- */
var prevRs=M.slots["rs-extra"];
M.slots["rs-extra"]=function(){var top=prevRs?prevRs():"",lab=M.X.lab;if(!lab)return top;var b=lab.backtests,s=lab.signals,h="";
if(b&&b.rows&&b.rows.length){var ts=Object.keys(b.curves),t=ui.bt&&b.curves[ui.bt]?ui.bt:ts[0],rid=ui.br,c=b.curves[t],rs=b.rows.filter(function(r){return r.t===t;}),row=rs.filter(function(r){return r.rule===rid;})[0]||rs[0],rule=b.rules.filter(function(r){return r.id===row.rule;})[0],sm=b.summary,sn=b.span[t];
var ser=[{name:rule.name,short:"Rule",vals:c[row.rule],color:"var(--s1)"}];if(row.rule!=="hold")ser.push({name:"Buy and hold "+t,short:"Hold",vals:c.hold,color:"var(--s2)"});if(t!=="SPY")ser.push({name:"S&P 500 fund",short:"S&P",vals:c.spy,color:"var(--dim)",dash:"4 3"});
h+='<div id="p3-bt">'+M.blk("BACKTESTER",M.tag(lab.as_of,14),'<div style="font-size:12.5px;font-weight:700;margin-bottom:8px">Of '+sm.tests+" rule tests, "+sm.beat_both_halves+" beat the S&P 500 fund in both halves of the test and "+sm.beat_overall+" were ahead overall. "+sm.beat_own_hold+" beat simply holding the same share.</div>"+
'<div class="p3s"><select data-p3sel="bt" aria-label="Ticker">'+ts.map(function(x){return '<option'+(x===t?" selected":"")+'>'+esc(x)+'</option>';}).join("")+'</select><select data-p3sel="br" aria-label="Rule">'+b.rules.map(function(r){return '<option value="'+r.id+'"'+(r.id===row.rule?" selected":"")+'>'+esc(r.name)+'</option>';}).join("")+'</select></div>'+
'<div class="fl" style="font-size:12px">'+esc(rule.rule)+'</div>'+chart("bt",c.dates,ser,{label:rule.name+" on "+t+" against holding and the S&P 500 fund"})+
'<div style="font-weight:800;font-size:13px;margin-top:6px">'+esc(t)+", "+esc(rule.name)+": "+esc(row.verdict)+'.</div>'+M.kv("Result after costs",M.sp(row.total,0)+" ("+sg(row.cagr,1)+" a year)")+M.kv("S&P 500 fund, same days",M.sp(row.spy_total,0))+
M.kv("Difference, first half / second half",M.sp(row.h1_vs_spy,0)+" / "+M.sp(row.h2_vs_spy,0))+M.kv("Worst fall",sg(row.mdd,0)+" (fund "+sg(row.spy_mdd,0)+")")+M.kv("Trades / time invested",row.trades+" / "+pc(row.time_in))+
'<details class="p3d"><summary>Every rule on '+esc(t)+'</summary><div class="ox"><table class="mt p3w"><tr><th>Rule</th><th>Result</th><th>Against S&P</th><th>Worst fall</th><th>Trades</th></tr>'+rs.map(function(r){var n=b.rules.filter(function(q){return q.id===r.rule;})[0];return "<tr><td>"+esc(n.name)+"</td><td>"+M.sp(r.total,0)+"</td><td>"+M.sp(r.vs_spy,0)+"</td><td>"+sg(r.mdd,0)+"</td><td>"+r.trades+"</td></tr>";}).join("")+'</table></div></details>',
esc(b.method)+" Tested "+esc(dl(sn.from))+" to "+esc(dl(sn.to))+". Limits: "+esc(b.limits.join(" "))+" "+M.upd(lab.as_of)+".")+'</div>';}
if(s&&s.tested!=null){var passed=s.passed||[];function sigRow(z){return "<tr><td>"+esc(z.series)+" "+String.fromCharCode(8594)+" <b>"+esc(z.t)+"</b></td><td style='white-space:nowrap'>"+z.lag_weeks+" wk</td><td>"+M.f2(z.t_first,1)+"</td><td>"+M.f2(z.t_second,1)+"</td><td>"+sg(z.effect,1)+"</td></tr>";}
var th='<tr><th>Series and share</th><th>Lead</th><th>1st half</th><th>2nd half</th><th>Effect</th></tr>';
h+='<div id="p3-sig">'+M.blk("REAL-WORLD SIGNALS LAB",M.tag(lab.as_of,14),'<div style="font-size:12.5px;font-weight:700;margin-bottom:6px">'+s.tested+" lead tests run. "+passed.length+" held up in both halves of the history; about "+s.expected_by_chance+" would by luck alone."+(passed.length?"":" Nothing here is a usable signal.")+'</div>'+
(passed.length?'<div class="lbl">Held up in both halves</div><div class="ox"><table class="mt p3w">'+th+passed.map(sigRow).join("")+'</table></div>':"")+
'<details class="p3d"'+(passed.length?"":" open")+'><summary>The closest misses</summary><div class="ox"><table class="mt p3w">'+th+s.closest.slice(0,8).map(sigRow).join("")+'</table></div><div class="src">The half columns are t-statistics: 2 or more in both halves with the same sign is the bar. Effect = the share\'s return against the S&P 500 fund after a one-standard-deviation rise in the series.</div></details>'+
'<details class="p3d"><summary>Moves in the same week (not a lead)</summary>'+s.same_week.map(function(z){return M.kv(esc(z.series)+" and "+esc(z.t),"correlation "+M.f2(z.r,2));}).join("")+'<div class="src">Useful for understanding what a share is exposed to; no use for timing.</div></details>'+
'<details class="p3d"><summary>Add a series to test</summary><div class="two"><label class="fld"><span>CNBC symbol</span><input id="lb-s" type="text" maxlength="12" autocapitalize="characters" autocorrect="off" spellcheck="false" placeholder="e.g. @SI.1"></label><label class="fld"><span>Name</span><input id="lb-n" type="text" maxlength="40" placeholder="e.g. Silver"></label></div>'+
'<div class="gap"><button class="btn" style="width:100%" data-p3="ladd">Add it to the next run</button></div><div class="src">Tested now: '+esc(s.series.map(function(x){return x.name;}).join(", "))+(s.missing.length?". No data for: "+esc(s.missing.join(", ")):"")+'.</div></details><div id="lb-stat"></div>',
esc(s.method)+" Limits: "+esc(s.limits.join(" "))+" Source: CNBC daily closes. "+M.upd(lab.as_of)+".")+'</div>';}
return top+h;};

/* ---------- track record: the paper book (item 19) ---------- */
function paperHtml(){var b=M.X.pbook,d=D();if(!b||!b.start)return "";var s=b.summary||{},hist=b.history||[],h="";
h+=M.kv("Paper book (follows every card)",M.sp(s.paper,1))+M.kv("Same holdings, never traded",M.sp(s.frozen,1))+M.kv("Starting value in the S&P 500 fund",M.sp(s.spy,1))+M.kv("Cards followed / trades",(s.cards_followed||0)+" / "+(s.trades||0));
if(hist.length>=3){var p0=hist[0];h+=chart("pb",hist.map(function(x){return x.date;}),[{name:"Paper book",short:"Paper",vals:hist.map(function(x){return x.paper/p0.paper;}),color:"var(--s1)"},{name:"Never traded",short:"Frozen",vals:hist.map(function(x){return x.frozen/p0.frozen;}),color:"var(--s2)"},
{name:"S&P 500 fund",short:"S&P",vals:hist.map(function(x){return x.spy/p0.spy;}),color:"var(--dim)",dash:"4 3"}],{label:"Paper book against never trading and the S&P 500 fund"});}
else h+='<div class="nbx gap">The book started on '+esc(dl(b.start.date))+". The comparison chart appears after three trading days.</div>";
if((b.trades||[]).length)h+='<div class="lbl" style="margin-top:10px">Paper trades</div><div class="ox"><table class="mt p3w"><tr><th>Date</th><th>Trade</th><th>Price</th><th>Since</th><th>Card</th></tr>'+b.trades.slice(-20).reverse().map(function(t){return "<tr><td>"+esc(M.sd(t.date))+"</td><td>"+esc(t.side)+" "+esc(t.t)+"</td><td>"+px(t.price)+"</td><td>"+M.sp(t.move,1)+"</td><td>"+esc(t.card)+"</td></tr>";}).join("")+'</table></div>';
var cs=((d&&d.cards)||[]).slice().reverse();
if(cs.length)h+='<div class="lbl" style="margin-top:10px">Your answers</div>'+cs.slice(0,12).map(function(c){return '<div class="q"><b style="color:var(--tx)">'+esc(c.status.toUpperCase())+"</b> "+MID+" "+esc(ttl(c))+" "+MID+" raised "+esc(M.sd(c.created))+(c.note?" "+MID+" note: "+esc(c.note):"")+'</div>';}).join("");
return M.blk("PAPER BOOK: WHAT IF YOU FOLLOWED EVERY CARD",'<span class="stg paper">PAPER</span>',h,esc(b.rules||"")+" Since "+esc(dl(b.start.date))+". "+M.upd(b.as_of)+".");}
function paperInject(){var v=$("v-review");if(!v)return;var el=$("p3-paper");if(!el){el=document.createElement("div");el.id="p3-paper";v.insertBefore(el,v.firstChild);}else if(el!==v.firstElementChild){v.insertBefore(el,v.firstChild);}var h=paperHtml();if(el.innerHTML!==h)el.innerHTML=h;}
MC.hooks.push(paperInject);

/* ---------- tools, checklist, wiring ---------- */
function goTo(id){MC.show("research");setTimeout(function(){var e=$(id);if(e)e.scrollIntoView({block:"start"});},60);}
M.tools[11]={note:"Built: tests whether outside series lead your shares, with a second-half check.",open:function(){goTo("p3-sig");}};
M.tools[12]={note:"Built: six rules on every holding and watchlist share, against the S&P 500 fund after costs.",open:function(){goTo("p3-bt");}};
M.done[11]=function(){var l=M.X.lab;return !!(l&&l.signals&&l.signals.tested>0);};
M.done[12]=function(){var l=M.X.lab;return !!(l&&l.backtests&&l.backtests.rows&&l.backtests.rows.length);};
M.done[13]=function(){var d=D();return !!(d&&d.cards);};M.done[14]=function(){var d=D();return !!(d&&d.rebalance);};
M.done[15]=function(){var d=D();return !!(d&&d.plans);};M.done[16]=function(){var d=D();return !!(d&&d.holds);};
M.done[17]=function(){var d=D();return !!(d&&d.doomsday&&d.doomsday.backtest&&d.doomsday.backtest.status==="ok");};
M.done[18]=function(){var d=D();return !!(d&&d.morning);};M.done[19]=function(){var b=M.X.pbook;return !!(b&&b.start);};
document.addEventListener("change",function(e){var s=e.target&&e.target.dataset?e.target.dataset.p3sel:null;if(!s)return;ui[s]=e.target.value;M.render();});
document.addEventListener("click",function(e){var b=e.target.closest("[data-p3]");if(!b)return;var a=b.dataset.p3,id=b.dataset.id;
if(a==="ans"){var v=b.dataset.v,k=b.dataset.k,box=$("p3-stat2")&&b.closest("#ppanel")?"p3-stat2":"p3-stat";b.disabled=true;
post({kind:k,id:id,answer:v},v+" to "+id,box).then(function(ok){if(!ok){b.disabled=false;return;}setLocal(id,v);M.render();if(k==="morning"&&v==="yes"&&id.indexOf("books:")===0)MC.prefill({act:"buy"});});}
else if(a==="log"){M.closePos();MC.prefill({t:b.dataset.t,act:b.dataset.side,amt:b.dataset.usd});}
else if(a==="pstop"){b.disabled=true;post({kind:"plan_stop",id:id},"stop plan "+id,"tp-stat");}
else if(a==="kstop"){b.disabled=true;post({kind:"keep_stop",id:id},"stop keeping "+id,"kp-stat");}
else if(a==="keep"){var kt=b.dataset.t,tv=num($("kp-target").value),kb=$("kp-by").value;if(tv!=null&&!(tv>0)){MC.toast("The target must be a price above zero, or leave it empty.",true);return;}
if(kb&&!/^\d{4}-\d\d-\d\d$/.test(kb)){MC.toast("Pick a review date.",true);return;}b.disabled=true;
post({kind:"keep",id:"keep-"+kt.toLowerCase()+"-"+stamp().toLowerCase(),ticker:kt,target:tv,by:kb||null},"keep "+kt,"kp-stat").then(function(ok){if(!ok)b.disabled=false;});}
else if(a==="padd"){var t=($("tp-t").value||"").trim().toUpperCase(),am=num($("tp-a").value),n=Math.round(num($("tp-n").value)||0),st=$("tp-s").value;
if(!/^[A-Z0-9.]{1,12}$/.test(t)||!(am>=1)||!(n>=1&&n<=120)||!/^\d{4}-\d\d-\d\d$/.test(st)){MC.toast("Enter a ticker, an amount of at least 1, a first date and 1 to 120 times.",true);return;}
post({kind:"plan",id:"p"+stamp().toLowerCase(),ticker:t,usd:am,every:$("tp-e").value,start:st,times:n},"timed plan "+t,"tp-stat");}
else if(a==="ladd"){var sy=($("lb-s").value||"").trim().toUpperCase(),nm=($("lb-n").value||"").trim();if(!/^[A-Z0-9@.=^-]{1,12}$/.test(sy)){MC.toast("Enter a CNBC symbol, for example @SI.1 for silver.",true);return;}
post({kind:"lab",id:"lab-"+stamp().toLowerCase(),symbol:sy,name:nm||sy},"lab series "+sy,"lb-stat");}});
M.reload();
})();
