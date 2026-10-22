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
  await page.locator('#tabPanel').click();
  for(const width of [390,768]){
   await page.setViewportSize({width,height:844});
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
   assert.equal(await page.locator('#tabPanel').isVisible(),true);
  }
  await page.screenshot({path:'/workspace/sonifarma-setup/pix-mobile.png',fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: logo, login, receipt empty state, CRM palette, navigation, users, mobile/tablet overflow, no JS errors');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
