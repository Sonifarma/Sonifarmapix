// npm install playwright; PIX_TEST_PASSWORD must identify a fictional local test user.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:process.env.CHROMIUM_EXECUTABLE||'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  const page=await browser.newPage({viewport:{width:1440,height:1000}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8080');
  await page.locator('#login .logo').evaluate(img=>img.decode());
  assert.equal(await page.locator('#login .logo').evaluate(img=>img.naturalWidth>0),true);
  await page.locator('#username').fill('visual');
  await page.locator('#password').fill(process.env.PIX_TEST_PASSWORD);
  await page.locator('#loginform button').click();
  await page.locator('#panel').waitFor({state:'visible'});
  await page.locator('#synced').filter({hasText:'Atualizado às'}).waitFor();
  assert.equal(await page.locator('#rows').innerText(),'Nenhum recebimento encontrado para este período.');
  assert.equal(await page.locator('#tabPanel').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(0, 119, 125)');
  await page.screenshot({path:'/workspace/sonifarma-setup/pix-desktop.png',fullPage:true});
  await page.locator('#tabAdmin').click();
  await page.locator('#users').filter({hasText:'visual'}).waitFor();
  assert.equal(await page.locator('#pageTitle').innerText(),'Gerência');
  await page.route('**/api/itau/sandbox',async route=>{
   const body=route.request().postDataJSON();
   assert.equal(body.token,'fictional-sandbox-token');
   assert.ok(body.inicio.endsWith('Z'));
   await route.fulfill({json:{items:[{id:'E_FICTICIO_12345',received_at:'2020-09-10T13:03:33Z',description:'<script>fictício</script>',amount_cents:11000,returned_cents:1000}],total_cents:11000,returned_cents:1000,page:0,pages:1,warnings:['O sandbox retornou registros fora do período solicitado. São dados de teste.']}});
  });
  await page.locator('#sandboxToken').fill('fictional-sandbox-token');
  await page.locator('#sandboxSubmit').click();
  await page.locator('#sandboxMessage').filter({hasText:'SANDBOX · 1 registros'}).waitFor();
  assert.equal(await page.locator('#sandboxToken').inputValue(),'');
  assert.ok((await page.locator('#sandboxRows').innerText()).includes('<script>fictício</script>'));
  assert.equal(await page.locator('#sandboxRows script').count(),0);
  assert.equal(await page.locator('#sandboxWarning').isVisible(),true);
  await page.unroute('**/api/itau/sandbox');
  await page.route('**/api/itau/sandbox',route=>route.fulfill({status:502,json:{detail:'Token expirado'}}));
  await page.locator('#sandboxToken').fill('fictional-sandbox-token');
  await page.locator('#sandboxSubmit').click();
  await page.locator('#sandboxMessage').filter({hasText:'Falha na consulta: Token expirado'}).waitFor();
  assert.equal(await page.locator('#sandboxRows tr').count(),0);
  assert.equal(await page.locator('#sandboxToken').inputValue(),'');
  await page.setViewportSize({width:390,height:844});
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await page.locator('#tabPanel').click();
  for(const width of [390,768]){
   await page.setViewportSize({width,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   assert.equal(await page.locator('#tabPanel').isVisible(),true);
  }
  await page.screenshot({path:'/workspace/sonifarma-setup/pix-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: logo, login, receipt empty state, CRM palette, navigation, users, mobile/tablet overflow, sandbox form/results/errors/token clearing, no JS errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
