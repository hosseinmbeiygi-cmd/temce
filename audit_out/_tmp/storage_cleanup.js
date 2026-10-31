const { execFileSync } = require('child_process');
const API='http://127.0.0.1:8000/api/v1';
const USER='audit_ui_storage_20261031', PASS='AuditStorage-20261031!';
const UID='usr_c443b9d595154fa1adebc6b4';
const HOLD_SYMBOL='AUD-UI-COIN-STORAGE';
function db(sql){return execFileSync('docker',['exec','tse_timescaledb','psql','-U','quant_dev','-d','tse_quant_verify','-At','-F','|','-c',sql],{encoding:'utf8'}).trim();}
function redis(args){return execFileSync('docker',['exec','-e','REDISCLI_AUTH','tse_redis','redis-cli',...args],{encoding:'utf8',env:process.env}).trim();}
(async()=>{
  const r=await fetch(API+'/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:USER,password:PASS})});
  const token=(await r.json()).data.access_token;
  const H={Authorization:'Bearer '+token};
  const out={};
  // tokens: revoke (idempotent) + remove Redis meta/hash/index
  const list=await (await fetch(API+'/gold/tokens',{headers:H})).json();
  const ours=(list.data||[]).filter(t=>t.name.startsWith('AUD-UI-TOKEN'));
  out.tokens=[];
  for (const t of ours){
    await fetch(API+'/gold/tokens/'+t.token_id,{method:'DELETE',headers:H});
    const metaKey=`golddesk:api_tokens:meta:${t.token_id}`;
    const raw=redis(['GET',metaKey]);
    let meta=null; try{meta=JSON.parse(raw);}catch{}
    if (meta&&meta.token_hash) redis(['DEL',`golddesk:api_tokens:hash:${meta.token_hash}`]);
    redis(['DEL',metaKey]);
    out.tokens.push({token_id:t.token_id,name:t.name,metaRemoved:redis(['EXISTS',metaKey])==='0'});
  }
  // index cleanup
  const idxRaw=redis(['GET','golddesk:api_tokens:index']);
  out.indexBefore=idxRaw;
  try{
    let idx=JSON.parse(idxRaw||'[]');
    idx=idx.filter(id=>!ours.some(t=>t.token_id===id));
    redis(['SET','golddesk:api_tokens:index',JSON.stringify(idx)]);
    out.indexAfter=redis(['GET','golddesk:api_tokens:index']);
  }catch(e){out.indexError=String(e);}
  // portfolio/dca cleanup via API
  const delH=await fetch(API+'/gold/portfolio/holdings/7?force=true',{method:'DELETE',headers:H});
  out.deleteHoldingStatus=delH.status;
  const delD=await fetch(API+'/gold/portfolio/dca/2',{method:'DELETE',headers:H});
  out.deletePlanStatus=delD.status;
  // trades + any leftovers
  out.deletedTrades=db(`delete from gold_trades where user_id='${UID}' and symbol='${HOLD_SYMBOL}'`);
  out.deletedEvents=db(`delete from gold_alert_events where user_id='${UID}' and message like 'AUD-UI-%'`);
  out.deletedRules=db(`delete from gold_alert_rules where user_id='${UID}'`);
  out.leftovers={
    holdings:db(`select count(*) from gold_holdings where user_id='${UID}'`),
    trades:db(`select count(*) from gold_trades where user_id='${UID}'`),
    plans:db(`select count(*) from gold_dca_plans where user_id='${UID}'`),
    rules:db(`select count(*) from gold_alert_rules where user_id='${UID}'`),
    events:db(`select count(*) from gold_alert_events where user_id='${UID}'`),
    values:db(`select count(*) from gold_portfolio_values where user_id='${UID}'`),
    audit:db(`select count(*) from audit_trail where user_id='${UID}'`),
  };
  // delete user only if no user-scoped rows remain (audit is not test data and may be immutable)
  const blocking=['holdings','trades','plans','rules','events','values'].some(k=>out.leftovers[k]!=='0');
  out.userDeleted=false;
  if(!blocking){
    out.userDeleted=db(`delete from users where id='${UID}' and username='${USER}' returning id`).includes(UID);
  }
  out.userCount=db(`select count(*) from users where id='${UID}'`);
  out.redisRemaining=execFileSync('docker',['exec','-e','REDISCLI_AUTH','tse_redis','redis-cli','--scan','--pattern','golddesk:api_tokens:*'],{encoding:'utf8',env:process.env}).trim();
  console.log(JSON.stringify(out,null,2));
})().catch(e=>{console.error('FATAL',e);process.exit(1);});
