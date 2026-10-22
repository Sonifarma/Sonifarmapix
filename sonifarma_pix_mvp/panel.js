const $=id=>document.getElementById(id),money=c=>(c/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});let role='',page=1,pages=1,known=null,interval=null;
async function api(url,options={}){let r=await fetch(url,{credentials:'same-origin',cache:'no-store',...options});if(!r.ok){let x=await r.json().catch(()=>({detail:'Erro de conexão'}));throw Error(x.detail||'Erro '+r.status)}return r.json()}
const json=(method,data)=>({method,headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
function localDate(d){return new Date(d).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})}
function today(){return new Intl.DateTimeFormat('en-CA',{timeZone:'America/Sao_Paulo',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())}
function tone(){if(!$('sound').checked)return;try{const A=window.AudioContext||window.webkitAudioContext,c=new A(),o=c.createOscillator(),g=c.createGain();o.frequency.value=840;g.gain.value=.07;o.connect(g);g.connect(c.destination);o.start();o.stop(c.currentTime+.18);o.onended=()=>c.close()}catch(e){}}
async function start(user){role=user.role;$('login').classList.add('hidden');$('panel').classList.remove('hidden');$('identity').textContent=user.username+' · '+(role==='gerencia'?'Gerência':'Caixa');$('tabAdmin').classList.toggle('hidden',role!=='gerencia');$('export').classList.toggle('hidden',role!=='gerencia');$('start').value=today();$('end').value=today();$('sandboxStart').value=today()+'T00:00';$('sandboxEnd').value=today()+'T23:59';await refresh();interval=setInterval(refresh,5000)}
async function refresh(){try{const q=new URLSearchParams({start:$('start').value,end:$('end').value,search:$('search').value,page:String(page)}),[data,last]=await Promise.all([api('/api/pix?'+q),api('/api/latest')]);pages=data.pages;$('total').textContent=money(data.total_cents);$('count').textContent=data.count;$('pages').textContent='Página '+page+' de '+pages;$('prev').disabled=page<=1;$('next').disabled=page>=pages;$('rows').replaceChildren();for(let p of data.items){let tr=document.createElement('tr');for(let s of [localDate(p.received_at),p.payer||'Não informado',p.id,money(p.amount_cents)]){let td=document.createElement('td');td.textContent=s;tr.appendChild(td)}$('rows').appendChild(tr)}if(!data.items.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=4;td.textContent='Nenhum recebimento encontrado para este período.';td.style.textAlign='center';tr.appendChild(td);$('rows').appendChild(tr)}let x=last.item;$('latest').textContent=x?money(x.amount_cents):'—';$('latestDate').textContent=x?localDate(x.received_at):'Sem dados';$('synced').textContent='Atualizado às '+new Date().toLocaleTimeString('pt-BR');$('simulator').textContent=last.simulator?'Habilitado para testes':'Desabilitado';if(x){if(known!==null&&known!==x.id)tone();known=x.id}}catch(e){$('synced').textContent='Falha de atualização: '+e.message;if(e.message.includes('Sessao')){clearInterval(interval);location.reload()}}}
$('loginform').onsubmit=async e=>{e.preventDefault();$('message').textContent='';try{await start(await api('/api/login',json('POST',{username:$('username').value,password:$('password').value})))}catch(err){$('message').textContent=err.message}};
$('logout').onclick=async()=>{await api('/api/logout',{method:'POST'}).catch(()=>{});location.reload()};$('filter').onclick=()=>{page=1;refresh()};$('prev').onclick=()=>{if(page>1){page--;refresh()}};$('next').onclick=()=>{if(page<pages){page++;refresh()}};
$('export').onclick=()=>{let q=new URLSearchParams({start:$('start').value,end:$('end').value,search:$('search').value});location.href='/api/report.csv?'+q};
$('tabPanel').onclick=()=>{show('receipts');};$('tabAdmin').onclick=async()=>{show('admin');await loadUsers()};function show(name){$('pageTitle').textContent=name==='receipts'?'Recebimentos':'Gerência';$('pageDescription').textContent=name==='receipts'?'Acompanhe os lançamentos e consulte o histórico por período.':'Gerencie os acessos e consulte as configurações do monitor.';$('tabPanel').setAttribute('aria-current',name==='receipts'?'page':'false');$('tabAdmin').setAttribute('aria-current',name==='admin'?'page':'false');$('receipts').classList.toggle('hidden',name!=='receipts');$('admin').classList.toggle('hidden',name!=='admin');$('tabPanel').classList.toggle('active',name==='receipts');$('tabAdmin').classList.toggle('active',name==='admin')}
async function loadUsers(){try{let u=await api('/api/users');$('users').replaceChildren();for(let x of u){let tr=document.createElement('tr');for(let t of [x.username,x.role,x.active?'Ativo':'Inativo']){let td=document.createElement('td');td.textContent=t;tr.appendChild(td)}$('users').appendChild(tr)}}catch(e){$('userMessage').textContent=e.message}}
$('userform').onsubmit=async e=>{e.preventDefault();try{await api('/api/users',json('POST',{username:$('newuser').value,password:$('newpass').value,role:$('newrole').value}));$('userMessage').textContent='Usuário criado';$('newpass').value='';await loadUsers()}catch(err){$('userMessage').textContent=err.message}};
api('/api/me').then(start).catch(()=>{});

$('sandboxform').onsubmit=async e=>{
 e.preventDefault();
 const button=$('sandboxSubmit');button.disabled=true;
 $('sandboxRows').replaceChildren();$('sandboxWarning').classList.add('hidden');
 $('sandboxMessage').textContent='Consultando o sandbox Itaú…';
 try{
  const payload={token:$('sandboxToken').value.trim(),inicio:$('sandboxStart').value+':00Z',fim:$('sandboxEnd').value+':00Z',pagina:Number($('sandboxPage').value),itens:100};
  $('sandboxToken').value='';
  const data=await api('/api/itau/sandbox',json('POST',payload));
  for(const item of data.items){
   const tr=document.createElement('tr');
   for(const text of [localDate(item.received_at),item.description||'Não informada',item.id,money(item.returned_cents),money(item.amount_cents)]){
    const td=document.createElement('td');td.textContent=text;tr.appendChild(td);
   }
   $('sandboxRows').appendChild(tr);
  }
  if(!data.items.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=5;td.textContent='Nenhum recebimento de teste retornado.';tr.appendChild(td);$('sandboxRows').appendChild(tr)}
  $('sandboxMessage').textContent='SANDBOX · '+data.items.length+' registros nesta página · Bruto: '+money(data.total_cents)+' · Devolvido: '+money(data.returned_cents)+' · Página '+data.page+' / '+data.pages+' páginas informadas';
  if(data.warnings.length){$('sandboxWarning').textContent=data.warnings.join(' ');$('sandboxWarning').classList.remove('hidden')}
 }catch(err){$('sandboxMessage').textContent='Falha na consulta: '+err.message}
 finally{$('sandboxToken').value='';button.disabled=false}
};
