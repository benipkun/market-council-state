/* Market Council add-on 4: the house strategy (data: state/strategy.json). Paper only: this screen
   shows what the strategy would hold and how its rules did in the back-test; it changes no decision card. */
(function(){
"use strict";
var M=window.MCX,MC=window.MC;if(!M||!MC)return;
var esc=MC.esc,num=MC.num,$=MC.$,MID=String.fromCharCode(183),DASH=String.fromCharCode(8212),MINUS=String.fromCharCode(8722);
M.extra.strat="state/strategy.json";
var css=document.createElement("style");css.textContent=
".p4r{display:grid;grid-template-columns:22px 1fr;gap:4px 8px;padding:9px 0;border-top:1px solid var(--bd);font-size:12.5px}.p4r:first-child{border-top:0}.p4r .n{color:var(--dim);font-weight:800}.p4r .f{grid-column:2;font-size:11.5px;color:var(--dim)}"+
".p4c{padding:9px 0;border-top:1px solid var(--bd);font-size:12px;color:var(--dim)}.p4c:first-child{border-top:0}.p4c b{color:var(--tx)}.p4c .u{display:inline-block;font-size:9.5px;font-weight:800;letter-spacing:.08em;border:1px solid var(--bd);border-radius:2px;padding:1px 5px;margin-left:6px;color:var(--tx)}"+
".p4k{display:flex;justify-content:space-between;gap:8px;font-size:12px;padding:3px 0;color:var(--dim)}.p4k b{color:var(--tx);white-space:nowrap}";document.head.appendChild(css);
function pc(v,d){return M.p1(v,d==null?0:d);}
function sg(v,d){var n=num(v);return n==null?DASH:(n>0?"+":(n<0?MINUS:""))+Math.abs(100*n).toFixed(d==null?1:d)+"%";}
function fall(v){var n=num(v);return n==null?DASH:MINUS+Math.abs(100*n).toFixed(0)+"%";}
function dl(s){return s?M.sd(s)+" "+String(s).slice(0,4):DASH;}
function mn(s){return String(s==null?"":s).replace(/-(?=\d)/g,MINUS);}
function det(sum,body,open){return '<details class="p3d"'+(open?" open":"")+'><summary>'+sum+'</summary>'+body+'</details>';}
/* frequent trading: short-term rules judged after real fees (lab.tactical) */
function sleeveHtml(){var lab=M.X.lab,t=lab&&lab.tactical;if(!t||t.status!=="ok")return "";var f=t.fee,best=t.rules.filter(function(r){return r.id===t.best;})[0];
function yr(x){return x&&x.a_year!=null?(x.a_year<=-0.999?"wiped out":sg(x.a_year,1)):DASH;}
var rows=t.rules.map(function(r){var sl=r.sleeve||{};return "<tr><td style='white-space:normal'>"+(r.id===t.best?"<b>"+esc(r.name)+"</b>":esc(r.name))+"</td><td>"+esc(r.trades)+"</td><td>"+(r.avg_gross==null?DASH:sg(r.avg_gross,2))+"</td><td>"+yr(sl.near_zero)+"</td><td>"+yr(sl.pct_only)+"</td><td>"+yr(sl.usd_1000)+"</td></tr>";}).join("");
var det2=t.rules.map(function(r){if(!r.sleeve)return det(esc(r.name),'<div class="fl" style="font-size:12px">'+esc(r.rule)+" Too few trades to judge.</div>");var sl=r.sleeve;
return det(esc(r.name)+(r.passes?"":" "+MID+" fails after costs"),'<div class="fl" style="font-size:12px;margin-bottom:6px">'+esc(r.rule)+'</div>'+
M.kv("Trades in the test",esc(r.trades)+" (about "+esc(r.per_month)+" a month)")+M.kv("Winning trades",pc(r.win_rate))+M.kv("Average win / average loss",sg(r.avg_win,1)+" / "+sg(r.avg_loss,1))+M.kv("Worst single trade",sg(r.worst,0))+
M.kv("Typical holding time",esc(r.median_days)+" trading days")+M.kv("Average per trade after 0.25% each way, first half / second half",sg(r.h1_net,2)+" / "+sg(r.h2_net,2))+
M.kv("Smallest trade that pays the minimum fee on average",r.breakeven_stake?"$"+Math.round(r.breakeven_stake):"none")+
'<div class="ox"><table class="mt p3w"><tr><th>Run as a sleeve of four trades</th><th>A year</th><th>Worst fall</th><th>Fees paid</th></tr>'+["near_zero","pct_only","usd_5000","usd_1000","usd_200"].map(function(k){var x=sl[k];return "<tr><td>"+esc(x.label)+"</td><td>"+yr(x)+"</td><td>"+fall(x.worst_fall)+"</td><td>$"+Math.round(x.fees)+"</td></tr>";}).join("")+'</table></div>'+
(r.open.length?'<div class="lbl" style="margin-top:8px">In a trade now, on paper</div>'+r.open.map(function(o){return M.kv("<b>"+esc(o.t)+"</b> since "+esc(M.sd(o.since))+" at $"+M.f2(o.entry),M.sp(o.ret,1));}).join(""):'<div class="fl" style="font-size:12px;margin-top:6px">No open paper trade under this rule.</div>')+
(r.paper?M.kv("Paper trades closed since "+esc(dl(r.paper.since)),esc(r.paper.closed)+", sum "+M.sp(r.paper.sum_net,1)):""));}).join("");
return M.blk("FREQUENT TRADING: DOES IT PAY?",'<span class="stg paper">PAPER</span>','<div style="font-size:12.5px;font-weight:700">'+esc(mn(t.verdict))+'</div>'+
'<div class="q"><b style="color:var(--tx)">What one trade costs you:</b> '+pc(f.pct,2)+" of the order, but at least about $"+M.f2(f.min_usd)+" (one euro). A 100-dollar trade therefore costs about "+pc(2*f.min_usd/100,1)+" to get in and out; only above about 450 dollars does it fall to "+pc(2*f.pct,1)+".</div>"+
'<div class="ox"><table class="mt p3w"><tr><th>Rule</th><th>Trades</th><th>Average before costs</th><th>No-commission broker</th><th>Your broker, 0.25%</th><th>Your broker, $1,000 sleeve</th></tr>'+rows+'</table></div>'+
'<div class="src">The last three columns are yearly results of a sleeve holding at most four trades at once. '+(t.cash_yield?"For comparison, short Treasuries pay about "+pc(t.cash_yield,1)+" a year without trading.":"")+'</div>'+det2+
'<div class="q">'+(best?"The idea itself is not the problem: before costs the rules make money. Costs and trade size decide the result. With a small sleeve at this broker, frequent trading is a way of paying fees.":"No rule survived its costs in both halves of the test.")+" The rules keep running on paper here so you can watch them without paying.</div>",
esc(t.method)+" Tested "+esc(dl(t.from))+" to "+esc(dl(t.to))+" on "+t.universe.length+" shares and funds: "+esc(t.universe.join(", "))+". Fees: "+esc(f.note)+" Limits: "+esc(t.limits.join(" "))+" "+M.upd(lab.as_of)+".");}
function html(){var s=M.X.strat;if(!s)return '<div class="msg">The strategy file has not been written yet. It appears after the next engine run.</div>';
if(s.status!=="ok"||!s.backtest)return M.head("HOUSE STRATEGY","Strategy",'<span class="stg stale">NO DATA</span>')+'<div class="msg">The engine could not load the price history for the strategy ('+esc(s.status)+').</div>';
var bt=s.backtest,ch=bt.chosen,core=s.core,vis=MC.pfVisible(),h=M.head("HOUSE STRATEGY","Strategy",'<span class="stg paper">PAPER</span>');
h+=M.blk("THE IDEA",'<span class="stg lvl">VERSION '+esc(s.version)+'</span>','<div style="font-size:13px;font-weight:700">'+esc(s.summary)+'</div><div class="q me">'+esc(bt.verdict)+'</div>'+
'<div class="q"><b style="color:var(--tx)">Why this mix for you:</b> '+esc(ch.why)+'</div>'+(s.rules_note?'<div class="q">'+esc(s.rules_note)+'</div>':"")+
'<div class="q">What the test shows plainly: these techniques make the ride smoother; they did not beat simply holding the S&P 500 fund on return. Funds get their higher returns by borrowing on top of mixes like this, which this account cannot do.</div>',
"Built from your risk profile (level "+esc(s.profile.level)+", maximum loss "+pc(s.profile.max_loss)+"). Change the profile under SYSTEM and the choice is made again. "+M.upd(s.as_of)+".");
h+=M.blk("THE RULES",'',s.rules.map(function(r){return '<div class="p4r"><span class="n">'+r.n+'</span><span>'+esc(r.rule)+'</span><span class="f">Borrowed from: '+esc(r.from)+'</span></div>';}).join(""),"Rules are fixed at go-live ("+esc(dl(s.go_live))+"). Everything after that date is a real test of them.");
var tg=s.target.filter(function(x){return x.weight>0.0005;}).map(function(x){return "<tr><td style='white-space:normal'><b>"+esc(x.t)+"</b> <span class='fl'>"+esc(x.name)+(x.eu?" "+MID+" EU: "+esc(x.eu):"")+"</span></td><td>"+(x.kind==="core"?"core":(x.kind==="share"?"share":"parked"))+"</td><td>"+pc(x.weight,1)+"</td></tr>";}).join("");
var keeps=(M.X.dec&&M.X.dec.keeps)||{};
var gap=s.holdings_gap.map(function(g){return "<tr><td style='white-space:normal'><b>"+esc(g.t)+"</b>"+(g.in_strategy?"":(keeps[g.t]?' <span class="fl">kept by your decision</span>':' <span class="fl">not in the strategy</span>'))+"</td><td>"+pc(g.now,1)+"</td><td>"+pc(g.target,1)+"</td></tr>";}).join("");
var sig=core.assets.map(function(a){return "<tr><td style='white-space:normal'><b>"+esc(a.t)+"</b> <span class='fl'>"+esc(a.name)+"</span></td><td>"+pc(a.vol_60d)+"</td><td>"+(a.above_avg?"above":"below")+"</td><td>"+pc(a.weight,1)+"</td></tr>";}).join("");
h+=M.blk("WHAT IT WOULD HOLD TODAY",M.tag(s.as_of,14),'<div class="ox"><table class="mt p3w"><tr><th>Holding</th><th>Part</th><th>Weight</th></tr>'+tg+'</table></div>'+
'<div class="lbl" style="margin-top:12px">Against what you hold</div><div class="ox"><table class="mt"><tr><th>Position</th><th>You</th><th>Strategy</th></tr>'+gap+'</table></div>'+
'<div class="q">'+pc(s.outside_strategy)+" of your portfolio is in shares the strategy would not hold today. This is a comparison, not an instruction: the strategy is on paper and raises no decision card.</div>"+
det("How today's core weights come about",'<div class="ox"><table class="mt p3w"><tr><th>Asset</th><th>60-day volatility</th><th>Against 200-day average</th><th>Core weight</th></tr>'+sig+'</table></div>'+
M.kv("Estimated volatility of the core",pc(core.est_vol,1)+" (cap "+pc(core.volatility_cap)+")")+M.kv("Scaled down by the cap",core.scale<0.999?"to "+pc(core.scale)+" of full size":"no")+M.kv("Parked in short Treasuries",pc(core.parked.weight,1))+
'<div class="src">'+(core.trend_rule?"An asset below its 200-day average is not held.":"The trend column is shown for information; the trend rule is not part of your version.")+" The mix in force was set at the last month end, "+esc(dl(core.in_force_since))+".</div>"),
"Fund tickers are US-listed stand-ins; in the EU buy the listed equivalent if your broker offers it. Prices to "+esc(dl(core.date))+". "+M.upd(s.as_of)+".");
var cv=bt.curve,chart=M.chart&&cv&&cv.core?M.chart("strat",cv.dates,[{name:"House core",short:"Core",vals:cv.core,color:"var(--s1)"},{name:"S&P 500 fund",short:"S&P",vals:cv.spy,color:"var(--s2)"},{name:"60% shares, 40% bonds",short:"60/40",vals:cv.sixty,color:"var(--dim)",dash:"4 3"}],
{log:true,label:"Growth of one dollar: house core, S&P 500 fund and 60/40",fmt:function(v){return "x"+v.toFixed(v<10?1:0);}}):"";
var rows=bt.variants.map(function(v){return "<tr><td style='white-space:normal'>"+(v.chosen?"<b>"+esc(v.name)+"</b> "+'<span class="stg live">CHOSEN</span>':esc(v.name))+(v.candidate&&!v.within_limit?' <span class="fl">over your limit</span>':"")+"</td><td>"+sg(v.cagr,1)+"</td><td>"+fall(v.mdd)+"</td><td>"+fall(v.worst_12m)+"</td><td>"+M.f2(v.sharpe,2)+"</td></tr>";}).join("");
var halves=bt.variants.map(function(v){return "<tr><td style='white-space:normal'>"+esc(v.name)+"</td><td>"+sg(v.h1_cagr,1)+" / "+fall(v.h1_mdd)+"</td><td>"+sg(v.h2_cagr,1)+" / "+fall(v.h2_mdd)+"</td><td>"+pc(v.avg_parked)+"</td></tr>";}).join("");
var rb=bt.robustness;
h+=M.blk("BACK-TEST, "+esc(String(bt.from).slice(0,4))+" TO "+esc(String(bt.to).slice(0,4)),M.tag(s.as_of,14),'<div style="font-size:12.5px;font-weight:700">'+esc(bt.verdict)+'</div>'+chart+
'<div class="ox"><table class="mt p3w"><tr><th>Mix</th><th>A year</th><th>Worst fall</th><th>Worst 12 months</th><th>Return per unit of risk</th></tr>'+rows+'</table></div>'+
'<div class="src">Candidates had to keep their worst fall within '+pc(bt.fall_limit)+" to be eligible. Return per unit of risk is the return above short Treasuries divided by the volatility (higher is better).</div>"+
det("Each half of the test on its own",'<div class="ox"><table class="mt p3w"><tr><th>Mix</th><th>First half: a year / worst fall</th><th>Second half</th><th>Average parked</th></tr>'+halves+'</table></div>')+
det("Does it hang on the exact settings?",M.kv("Runs with nearby settings",esc(rb.runs))+M.kv("Return a year, lowest / middle / highest",sg(rb.cagr[0],1)+" / "+sg(rb.cagr[1],1)+" / "+sg(rb.cagr[2],1))+
M.kv("Worst fall, deepest / middle / shallowest",fall(rb.mdd[0])+" / "+fall(rb.mdd[1])+" / "+fall(rb.mdd[2]))+M.kv("Runs that stayed inside your limit",pc(rb.within_limit_share))+'<div class="src">'+esc(rb.what)+'</div>'),
esc(bt.method)+" "+esc(bt.income_note)+" Limits: "+esc(bt.limits.join(" "))+" "+M.upd(s.as_of)+".");
var ed=s.edge,er=ed.rows.map(function(r){return det('<b style="color:var(--tx)">'+esc(r.t)+"</b> "+MID+" "+r.score+" of "+r.of+(r.qualifies?' <span class="stg live">QUALIFIES</span>':"")+(r.held?' <span class="fl">held</span>':""),
r.checks.map(function(c){return '<div class="p4k"><span>'+esc(c.name)+'<br><span class="fl">'+esc(mn(c.detail))+'</span></span><b>'+(c.pass===true?"PASS":(c.pass===false?"FAIL":"NO DATA"))+'</b></div>';}).join("")+
'<div class="gap"><button class="btn sm" data-mc="pos" data-t="'+esc(r.t)+'">Open '+esc(r.t)+'</button></div>');}).join("");
h+=M.blk("SHARE SCORECARD",M.tag(s.as_of,14),'<div class="fl" style="font-size:12px">'+esc(ed.note)+" Qualifying shares share at most "+pc(ed.max)+" of the portfolio.</div>"+
(ed.picks.length?'<div class="q me">Qualifies today: '+ed.picks.map(function(p){return "<b>"+esc(p.t)+"</b> at "+pc(p.weight,1)+" of the portfolio with a stop "+pc(p.stop_pct)+" below the entry";}).join("; ")+".</div>":'<div class="q">No share qualifies today, so the whole strategy sits in the core.</div>')+er,
"Checks use our own valuation, Nasdaq statements and earnings, OpenInsider and Dataroma, and the engine's price history. This part cannot be back-tested; it is tracked forward from go-live.");
h+=sleeveHtml();
var tr=s.track;
h+=M.blk("PAPER RECORD SINCE GO-LIVE",'<span class="stg paper">PAPER</span>',(tr.days?"":'<div class="nbx">Go-live was '+esc(dl(tr.since))+". The record starts with the next trading day.</div>")+
M.kv("House core",M.sp(tr.core,1))+M.kv("S&P 500 fund",M.sp(tr.spy,1))+M.kv("60% shares, 40% bonds",M.sp(tr.sixty,1))+M.kv("Your holdings, never traded",M.sp(tr.your_holdings,1)),
"Since "+esc(dl(tr.since))+", "+esc(tr.days)+" trading days. The core figure is the rules applied to real prices after go-live, with estimated income and costs.");
var grp=[["yes","What we use"],["partly","What we use in part"],["not now","Not now"],["no","Out of reach"]];
h+=M.blk("CONCEPT LIBRARY: WHAT HEDGE FUNDS DO",'<span class="stg lvl">'+s.concepts.length+" CONCEPTS</span>",grp.map(function(g,gi){var it=s.concepts.filter(function(c){return c.use===g[0];});if(!it.length)return "";
return det(g[1]+" ("+it.length+")",it.map(function(c){return '<div class="p4c"><b>'+esc(c.name)+'</b><span class="u">'+esc(String(c.who).toUpperCase())+'</span><br>'+esc(c.idea)+'<br><span class="fl">Evidence: '+esc(c.evidence)+'</span><br><b>For us:</b> '+esc(c.ours)+'</div>';}).join(""),gi===0);}).join(""),
"Hand-written reference. The sources are well-known published studies; nothing here is a claim about any fund's results.");
h+=M.blk("CHANGE THE STRATEGY",'','<div class="fl" style="font-size:12px">Three dials change it: your maximum loss and risk level (under SYSTEM), whether the trend rule is on, and how much may go into single shares. Tell the Council what you want different and the rules are rewritten and tested again before anything changes.</div>'+
'<div class="gap"><button class="btn sm" data-mc="askq" data-q="Change the house strategy: ">Tell the Council what to change</button></div>',"The strategy stays on paper until you say it may set the rebalance plan.");
return h;}
function render(){var el=$("v-strategy");if(!el)return;var h=html();if(el.__h!==h){var open={};Array.prototype.forEach.call(el.querySelectorAll("details"),function(d,i){if(d.open)open[i]=1;});var had=el.__h!=null;el.innerHTML=h;el.__h=h;
if(had)Array.prototype.forEach.call(el.querySelectorAll("details"),function(d,i){d.open=!!open[i];});}}
var prevCc=M.slots["cc-extra"];
M.slots["cc-extra"]=function(){setTimeout(render,0);var top=prevCc?prevCc():"",s=M.X.strat;
if(!s||s.status!=="ok"||!s.backtest)return top;
return top+M.blk("HOUSE STRATEGY",'<span class="stg paper">PAPER</span>','<div style="font-size:12.5px">'+esc(s.summary)+'</div><div class="gap"><button class="btn sm" data-tab="strategy">Open the strategy</button></div>',esc(s.backtest.verdict));};
MC.hooks.push(render);
M.reload();
})();
