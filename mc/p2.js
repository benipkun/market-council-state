/* Market Council add-on 2: research card, valuation, earnings review and smart money (data: research/cards/). */
(function(){
"use strict";
var M=window.MCX,MC=window.MC;if(!M||!MC)return;
var esc=MC.esc,num=MC.num,C={},asked={},ED={},DASH=String.fromCharCode(8212),MID=String.fromCharCode(183),ELL=String.fromCharCode(8230);
M.extra.cards="research/cards/index.json";M.extra.smart="state/smart_money.json";
var css=document.createElement("style");css.textContent=".p2d{border-top:1px solid var(--bd);margin-top:8px}.p2d>summary{padding:13px 0;cursor:pointer;font-size:11px;font-weight:800;letter-spacing:.07em;text-transform:uppercase;color:var(--ac)}"+
".p2g{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin:2px 0 8px}.p2f{display:block;font-size:10.5px;color:var(--dim)}"+
".p2f input{display:block;width:100%;height:42px;margin-top:3px;font-size:16px;padding:0 8px;border:1px solid var(--bd);border-radius:3px;background:var(--bg);color:var(--tx);font-family:inherit}"+
".q a{color:var(--ac)}";document.head.appendChild(css);
function card(t){if(C[t])return C[t];if(!asked[t]){asked[t]=1;MC.get("research/cards/"+t+".json").then(function(c){if(c&&c.ticker){C[t]=c;}else asked[t]=2;M.render();},function(){asked[t]=2;M.render();});}return null;}
function wait(t,label){return M.blk(label,asked[t]===2?'<span class="stg stale">NO CARD</span>':'<span class="stg stale">LOADING</span>','<div class="nbx">'+(asked[t]===2?"No research card exists for "+esc(t)+" yet. Cards are built for holdings and the watchlist.":"Loading the research card"+ELL)+'</div>');}
function usd(v){var n=num(v);return n==null?DASH:"$"+n.toFixed(2);}
function big(v){var n=num(v);if(n==null)return DASH;var a=Math.abs(n);return (n<0?String.fromCharCode(8722):"")+"$"+(a>=1e9?(a/1e9).toFixed(1)+"bn":(a>=1e6?(a/1e6).toFixed(1)+"m":Math.round(a/1e3)+"k"));}
function run(a){var prev=a.base_revenue,pv=0,f=0;for(var y=1;y<=5;y++){var g=a.growth_start+(a.growth_end-a.growth_start)*(y-1)/4,rv=prev*(1+g),e=rv*a.ebit_margin,tx=Math.max(0,e)*a.tax_rate;
f=e-tx+rv*a.da_pct_revenue-rv*a.capex_pct_revenue-(rv-prev)*a.working_capital_pct_of_growth;pv+=f/Math.pow(1+a.wacc,y);prev=rv;}
var tv=f*(1+a.terminal_growth)/(a.wacc-a.terminal_growth);return (pv+tv/Math.pow(1+a.wacc,5)-a.net_debt)/a.shares;}
var prev1=M.slots["pp-card"];
M.slots["pp-card"]=function(t){var c=card(t),top=prev1?prev1(t):"";if(!c)return top+wait(t,"RESEARCH CARD");var a=c.analysts,h="";
if(a)h+=M.kv("Analysts ("+esc(a.brokers||"?")+" brokers)",esc(a.rating||DASH)+" "+MID+" "+esc(a.buy)+" buy / "+esc(a.hold)+" hold / "+esc(a.sell)+" sell")+
M.kv("Their price targets","low "+usd(a.target_low)+" "+MID+" average "+usd(a.target_mean)+" "+MID+" high "+usd(a.target_high))+M.kv("Average target against price",M.sp(a.upside,0));
else h+='<div class="fl" style="font-size:12px">'+esc(c.note||"No analyst data from the source.")+'</div>';
h+='<div class="lbl" style="margin-top:10px">News</div>'+((c.news||[]).map(function(n){return '<div class="q"><a href="'+esc(n.url)+'" target="_blank" rel="noopener">'+esc(n.title)+'</a><br><span class="fl">'+esc(n.publisher||"")+" "+MID+" "+esc(n.date||"")+'</span></div>';}).join("")||'<div class="q">No recent articles from the source.</div>');
h+='<div class="lbl" style="margin-top:10px">Company filings</div>'+((c.filings||[]).map(function(f){return '<div class="q">'+(f.url?'<a href="'+esc(f.url)+'" target="_blank" rel="noopener">'+esc(f.form)+'</a>':esc(f.form))+(f.what?" "+esc(f.what):"")+" "+MID+" filed "+esc(M.sd(f.filed))+(f.period?" "+MID+" period "+esc(M.sd(f.period)):"")+'</div>';}).join("")||'<div class="q">No filings listed by the source.</div>');
return top+M.blk("RESEARCH CARD",M.tag(c.as_of,14),h,"Sources: Nasdaq analyst research, Nasdaq news feed, SEC filings as listed by Nasdaq. "+M.upd(c.as_of)+".");};
M.slots["pp-dcf"]=function(t){var c=card(t);if(!c)return "";var v=c.valuation||{};
if(v.status!=="valued")return '<div class="nbx gap"><b style="color:var(--tx)">Our own valuation: '+esc(v.status||"not available")+'.</b> '+esc(v.reason||"")+'</div>';
var A=ED[t]||v.assumptions,fair=v.fair_value_per_share==null?null:(ED[t]?run(A):v.fair_value_per_share),mos=fair&&fair>0?1-v.price/fair:null,
F=[["growth_start","Sales growth, year 1"],["growth_end","Sales growth, year 5"],["ebit_margin","Operating margin"],["tax_rate","Tax rate"],["wacc","Discount rate"],["terminal_growth","Growth after year 5"]];
var h='<div class="lbl" style="margin-top:12px">Our own valuation '+MID+' estimate</div>'+M.kv("Fair value per share",fair==null?"not shown (foreign statements)":usd(fair)+(ED[t]?' <span class="stg stale">YOUR INPUTS</span>':""))+M.kv("Price",usd(v.price))+M.kv("Margin of safety",fair==null?DASH:M.sp(mos,0))+
'<details class="p2d"'+(ED[t]?" open":"")+'><summary>Assumptions (edit and recalculate)</summary><div class="p2g">'+F.map(function(f){return '<label class="p2f"><span>'+f[1]+' (%)</span><input id="dv-'+f[0]+'" type="number" inputmode="decimal" step="0.1" value="'+(100*A[f[0]]).toFixed(1)+'"></label>';}).join("")+
'</div><div class="row gap"><button class="btn sm" data-p2="recalc" data-t="'+esc(t)+'">Recalculate</button><button class="btn sm" data-p2="reset" data-t="'+esc(t)+'">Back to the engine values</button></div>'+
M.kv("Capital spending, share of sales",M.p1(A.capex_pct_revenue,1))+M.kv("Depreciation, share of sales",M.p1(A.da_pct_revenue,1))+M.kv("Working capital, share of new sales",M.p1(A.working_capital_pct_of_growth,1))+M.kv("Net debt",big(1000*A.net_debt))+M.kv("Shares",(A.shares/1e6).toFixed(2)+" bn")+'</details>';
h+='<details class="p2d"><summary>Five-year forecast</summary><div class="ox"><table class="mt"><tr><th>Year</th><th>Sales</th><th>Operating profit</th><th>Tax</th><th>Capital spending</th><th>Working capital</th><th>Free cash flow</th></tr>'+
(v.forecast||[]).map(function(r){return '<tr><td>'+r.year+'</td><td>'+big(1000*r.revenue)+'</td><td>'+big(1000*r.ebit)+'</td><td>'+big(1000*r.tax)+'</td><td>'+big(1000*r.capex)+'</td><td>'+big(1000*r.working_capital)+'</td><td>'+big(1000*r.fcf)+'</td></tr>';}).join("")+
'</table></div>'+M.kv("Value after year 5",big(1000*v.terminal_value))+M.kv("Whole-business value today",big(1000*v.enterprise_value))+'<div class="src">Engine values; your edits change the fair value above, not this table.</div></details>';
var s=v.sensitivity||{};if(s.fair_value)h+='<details class="p2d"><summary>Sensitivity: discount rate against long-run growth</summary><div class="ox"><table class="mt"><tr><th>Discount rate</th>'+s.terminal_growth.map(function(g){return '<th>growth '+M.p1(g,1)+'</th>';}).join("")+'</tr>'+
s.fair_value.map(function(row,i){return '<tr><td>'+M.p1(s.wacc[i],1)+'</td>'+row.map(function(x){return '<td>'+usd(x)+'</td>';}).join("")+'</tr>';}).join("")+'</table></div></details>';
h+='<div class="lbl" style="margin-top:10px">Risks to this number</div>'+((v.risks||[]).map(function(r){return '<div class="q">'+esc(r)+'</div>';}).join("")||'<div class="q">None flagged by the rules.</div>')+
'<div class="row gap"><a class="btn sm" href="research/cards/'+esc(t)+'-valuation.csv" download>Download spreadsheet (CSV)</a></div><div class="src">'+esc(v.method||"")+" Source: "+esc(v.source||"")+". "+M.upd(v.as_of)+'.</div>';return h;};
M.slots["pp-earn"]=function(t){var c=card(t);if(!c)return wait(t,"LATEST EARNINGS REVIEW");var e=c.earnings;if(!e)return M.blk("LATEST EARNINGS REVIEW",'<span class="stg stale">NO DATA</span>','<div class="nbx">The source lists no earnings history for '+esc(t)+'.</div>');
var r=e.review,n=(e.next||[])[0];
return M.blk("LATEST EARNINGS REVIEW",M.tag(c.as_of,14),M.kv("Quarter",esc(r.quarter)+" "+MID+" reported "+esc(M.sd(r.reported)))+M.kv("Earnings per share","$"+M.f2(r.eps)+" against $"+M.f2(r.consensus)+" expected")+M.kv("Surprise",M.sp(r.surprise_pct==null?null:r.surprise_pct/100,0))+
M.kv("Share price, next day",M.sp(r.move_1d,1))+M.kv("Share price, five days",M.sp(r.move_5d,1))+M.kv("Beat expectations",esc(r.beats_in_last_4)+" of the last "+e.history.length+" quarters")+
(n?M.kv("Next quarter ("+esc(n.quarter)+")","$"+M.f2(n.consensus_eps)+" expected "+MID+" revisions "+esc(n.revisions_up)+" up / "+esc(n.revisions_down)+" down"):""),esc(r.limits)+" Source: "+esc(e.source)+", price reaction from the engine's price history. "+M.upd(c.as_of)+".");};
M.slots["pp-smart"]=function(t){var c=card(t);if(!c)return wait(t,"SMART-MONEY ACTIVITY");var s=c.smart_money;if(!s)return M.blk("SMART-MONEY ACTIVITY",'<span class="stg stale">NO DATA</span>','<div class="nbx">'+esc(c.note||"Nothing listed.")+'</div>');
var i=s.insiders||{},n=s.institutions||{},k=(s.known_investors||{}).holders||[];
var h='<div class="lbl">Insiders, last 90 days</div>'+M.kv("Open-market purchases",esc(i.open_market_buys_90d)+" "+MID+" "+big(i.buy_value_90d))+M.kv("Open-market sales",esc(i.open_market_sales_90d)+" "+MID+" "+big(i.sale_value_90d))+
((i.trades||[]).slice(0,5).map(function(x){return '<div class="q"><b style="color:var(--tx)">'+esc(String(x.type||"").replace(/^[A-Z] - /,""))+'</b> '+MID+" "+esc(x.insider)+(x.title&&x.title!=="See Remarks"?" ("+esc(x.title)+")":"")+'<br>traded '+esc(M.sd(x.traded))+" "+MID+" filed "+esc(M.sd(x.filed))+" "+MID+" "+big(Math.abs(num(x.value)||0))+" at "+usd(x.price)+'</div>';}).join("")||'<div class="q">No insider trades listed in the last year.</div>');
h+='<div class="lbl" style="margin-top:10px">Big funds</div>'+M.kv("Held by institutions",n.held_pct==null?DASH:n.held_pct.toFixed(0)+"%")+((n.top||[]).slice(0,4).map(function(x){return M.kv(esc(x.holder),(x.shares/1e6).toFixed(1)+"m shares "+MID+" "+(x.change>0?"+":(x.change<0?String.fromCharCode(8722):""))+Math.abs(x.change/1e6).toFixed(1)+"m");}).join(""));
h+='<div class="lbl" style="margin-top:10px">Well-known investors</div>'+(k.slice(0,5).map(function(x){return M.kv(esc(x.investor),esc(x.pct_of_their_portfolio)+"% of their portfolio"+(x.recent_activity?" "+MID+" "+esc(x.recent_activity):""));}).join("")||'<div class="q">None of the tracked investors report holding it.</div>');
h+='<div class="nbx gap"><span class="stg stale">NOT AVAILABLE</span> Politicians: '+esc((s.politicians||{}).reason||"no source")+'.</div>';
return M.blk("SMART-MONEY ACTIVITY",M.tag(c.as_of,14),h,"Insiders: "+esc(i.source||"no source")+". Funds: "+esc(n.source||"")+". Investors: "+esc((s.known_investors||{}).source||"")+". "+(i.kept?"Insider list kept from "+esc(M.sd(i.as_of))+" because the source did not answer in the latest run. ":"")+((s.known_investors||{}).kept?"Investor list kept from "+esc(M.sd(s.known_investors.as_of))+" because the source did not answer in the latest run. ":"")+"Fund data is quarterly and can be 45 days old. "+M.upd(c.as_of)+".");};
M.slots["rs-extra"]=function(){var ix=M.X.cards,sm=M.X.smart;if(!ix)return "";
var rows=(ix.cards||[]).map(function(x){return '<tr><td><button class="idea" style="margin:0" data-mc="pos" data-t="'+esc(x.t)+'">'+esc(x.t)+(x.held?" "+MID+" held":"")+'</button></td><td>'+(x.fair==null?'<span class="fl">'+(x.valued?"no per-share figure":"not valued")+'</span>':usd(x.fair))+'</td><td>'+M.sp(x.mos,0)+'</td><td>'+usd(x.target)+'</td><td>'+esc(x.rating||DASH)+'</td><td>'+esc(x.insider_buys_90d==null?DASH:x.insider_buys_90d)+" / "+esc(x.insider_sales_90d==null?DASH:x.insider_sales_90d)+'</td></tr>';}).join("");
var al=((sm&&sm.alerts)||[]).map(function(a){return '<div class="q me"><b>'+esc(a.ticker)+" "+MID+" "+esc(a.what)+'</b> by '+esc(a.insider)+" "+MID+" "+big(a.value)+'<br>traded '+esc(M.sd(a.traded))+" "+MID+" filed "+esc(M.sd(a.filed))+'</div>';}).join("")||'<div class="q">Nothing relevant in the last 14 days.</div>';
return M.blk("VALUATION BOARD",M.tag(ix.as_of,14),'<div class="ox"><table class="mt"><tr><th>Ticker</th><th>Our fair value</th><th>Margin of safety</th><th>Analysts\' target</th><th>Rating</th><th>Insider buys / sales 90d</th></tr>'+rows+'</table></div>',"Tap a ticker for the full card. Fair value is the engine's five-year cash-flow estimate; a minus margin means the price is above it. "+M.upd(ix.as_of)+".")+
M.blk("SMART-MONEY ALERTS",M.tag(sm&&sm.as_of,14),al,esc((sm&&sm.rule)||""));};
[7,8,9,10].forEach(function(n){M.tools[n]={note:"Built: open any holding or watchlist ticker to see it.",open:function(){MC.show("research");var i=MC.$("rs-in");if(i){i.focus();window.scrollTo(0,0);}}};
M.done[n]=function(){return !!(M.X.cards&&M.X.cards.cards&&M.X.cards.cards.length);};});
document.addEventListener("click",function(e){var b=e.target.closest("[data-p2]");if(!b)return;var t=b.dataset.t,c=C[t];if(!c||!c.valuation)return;
if(b.dataset.p2==="reset"){delete ED[t];M.render();return;}
var a={},base=c.valuation.assumptions,ok=true;Object.keys(base).forEach(function(k){a[k]=base[k];});
["growth_start","growth_end","ebit_margin","tax_rate","wacc","terminal_growth"].forEach(function(k){var v=num(MC.$("dv-"+k).value);if(v==null)ok=false;else a[k]=v/100;});
if(!ok||a.wacc<=a.terminal_growth+0.005){MC.toast("The discount rate must be above the long-run growth rate, and every field needs a number.",true);return;}
ED[t]=a;M.render();});
M.reload();
})();
