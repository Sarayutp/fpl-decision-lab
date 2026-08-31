const {test,expect}=require('@playwright/test');
const fs=require('node:fs');

async function readyCard(page) {
  await page.goto('/');await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await page.locator('#transfer-free-transfers').selectOption('1');
  await page.locator('[data-planner-select="save"]').click();
  await page.locator('#compare-label').fill('PRIVATE_LABEL_NOT_FOR_SHARING');
  await page.locator('#compare-capture-a').click();
  await page.locator('#decision-share > summary').click();
  await page.locator('#share-card-create').click();
  await expect(page.locator('#share-card-preview')).toBeVisible();
}

test('preview, PNG, text and clipboard contain only the reviewed card, not account details',async({page,context})=>{
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  const outbound=[];page.on('request',r=>{if(/^https?:/.test(r.url())&&(r.method()!=='GET'||!r.url().startsWith('http://127.0.0.1:8011/'))) outbound.push(r.url());});
  await readyCard(page);
  const text=await page.locator('#share-card-text').innerText();
  for(const secret of ['PRIVATE_LABEL','990001','QA United','QA Manager','sellingPrices','contextKey']) expect(text).not.toContain(secret);
  expect(text).toContain('Snapshot');expect(text).toContain('ฉบับร่าง');expect(text).toContain('ไม่รับประกัน');
  await expect(page.locator('#planner-saved-status')).toContainText('ยังไม่ได้บันทึก');
  await expect(page.locator('#decision-log-list')).not.toContainText('PRIVATE_LABEL');
  for(const kind of ['png','txt']) {
    const downloading=page.waitForEvent('download');await page.locator('#share-card-'+kind).click();
    const download=await downloading;expect(download.suggestedFilename()).toBe(`fpl-card-gw3-A.${kind}`);
    const bytes=fs.readFileSync(await download.path());
    if(kind==='txt') expect(bytes.toString('utf8')).toBe(text);
    else {expect(bytes.subarray(0,8).toString('hex')).toBe('89504e470d0a1a0a');expect(bytes.readUInt32BE(16)).toBe(800);expect(bytes.readUInt32BE(20)).toBeGreaterThan(800);}
  }
  await page.locator('#share-card-copy').click();
  await expect.poll(()=>page.evaluate(()=>navigator.clipboard.readText())).toBe(text);
  expect(outbound).toEqual([]);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  await page.reload();await page.locator('#decision-share > summary').click();
  await expect(page.locator('#share-card-preview')).toBeHidden();await expect(page.locator('#share-card-copy')).toBeDisabled();
  await expect(page.locator('[data-compare-slot="A"]')).toContainText('PRIVATE_LABEL');
});

test('changing bank removes preview; recapturing and switching slots require a new preview',async({page})=>{
  await readyCard(page);
  await page.locator('#transfer-bank').fill('1.0');await page.locator('#transfer-bank').press('Tab');
  await expect(page.locator('#share-card-preview')).toBeHidden();await expect(page.locator('#share-card-create')).toBeDisabled();
  await expect(page.locator('#share-card-image')).not.toHaveAttribute('src',/./);
  await page.locator('#compare-capture-a').click();await page.locator('#share-card-create').click();
  await expect(page.locator('#share-card-preview')).toBeVisible();
  await page.locator('[data-planner-select="triple_captain"]').click();await page.locator('#compare-capture-b').click();
  await page.locator('#share-card-slot').selectOption('B');await expect(page.locator('#share-card-preview')).toBeHidden();
  await page.locator('#share-card-create').click();await expect(page.locator('#share-card-text')).toContainText('แผน B');
  await expect(page.locator('#share-card-text')).toContainText('Triple Captain');
  await page.getByText('ลบเฉพาะแผน B',{exact:true}).click();await page.getByRole('button',{name:'ยืนยันลบแผน B',exact:true}).click();
  await expect(page.locator('#share-card-preview')).toBeHidden();await expect(page.locator('#share-card-copy')).toBeDisabled();
});

test('clipboard and canvas failures offer text download without claiming success',async({page})=>{
  await page.addInitScript(()=>{HTMLCanvasElement.prototype.getContext=()=>null;
    Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('denied'))}});document.execCommand=()=>false;});
  await readyCard(page);await expect(page.locator('#share-card-png')).toBeDisabled();
  await expect(page.locator('#share-card-txt')).toBeEnabled();
  await page.locator('#share-card-copy').click();await expect(page.locator('#toast')).toContainText('คัดลอกไม่ได้');
  const downloading=page.waitForEvent('download');await page.locator('#share-card-txt').click();
  expect((await downloading).suggestedFilename()).toBe('fpl-card-gw3-A.txt');
});

for(const state of ['offline','stale','deadline','mismatch']) test(`${state} disables card exports even when A/B is stored`,async({page})=>{
  await readyCard(page);await page.goto(`/?qaState=${state}`);
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind',state);
  await page.locator('#decision-share > summary').click();
  for(const id of ['create','png','txt','copy']) await expect(page.locator('#share-card-'+id)).toBeDisabled();
  await expect(page.locator('#share-card-preview')).toBeHidden();
});
