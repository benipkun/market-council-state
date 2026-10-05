/* Market Council add-on 1: the Councillor's challenge to each pick (rulebook ops/COUNCILLOR.md). */
(function(){
"use strict";
var M=window.MCX,MC=window.MC;if(!M||!MC)return;var esc=MC.esc;
M.extra.council="state/council.json";
function latest(t){var v=(M.X.council&&M.X.council.verdicts)||[];v=v.filter(function(x){return x.ticker===t;});return v.length?v[v.length-1]:null;}
M.slots["pp-card"]=function(t){var c=latest(t);
if(!c)return M.blk("COUNCILLOR CHALLENGE",'<span class="stg stale">NO VERDICT YET</span>','<div class="nbx">The Councillor tests each new bullish or bearish pick against the engine numbers before it reaches you. No pick on '+esc(t)+' has been through it yet.</div>',"Rulebook: ops/COUNCILLOR.md in the repository.");
var L={stands:"STANDS",weak:"WEAK",fails:"FAILS"}[c.verdict]||"CANNOT JUDGE";
return M.blk("COUNCILLOR CHALLENGE",c.stale?'<span class="stg stale">STALE INPUTS</span>':M.tag(c.at,80),
'<div style="font-weight:800;font-size:15px">'+L+' <span class="fl" style="font-weight:400;font-size:11px">'+esc(c.lean||"")+' pick</span></div>'+
(c.decided_by||[]).map(function(s){return '<div class="q me">'+esc(s)+'</div>';}).join("")+
(c.against||[]).map(function(s){return '<div class="q">Against: '+esc(s)+'</div>';}).join("")+
M.kv("Size the risk profile allows",c.size_usd?esc(MC.money(c.size_usd)):"none")+
'<div class="src">'+esc(c.size_basis||"")+(c.missing&&c.missing.length?" Missing: "+esc(c.missing.join("; "))+".":"")+'</div>',
"Data: the digest, the engine's numbers and the paper record at the time of the verdict, "+M.upd(c.at)+". Worked out from written rules; an estimate, not advice.");};
M.done[1]=function(){return "part";};
M.reload();
})();
