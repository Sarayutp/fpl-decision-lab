const {test,expect} = require('@playwright/test');
const fs = require('node:fs');

async function capturePair(page) {
  await page.goto('/');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await page.locator('#transfer-free-transfers').selectOption('1');
  await page.locator('[data-planner-select="save"]').click();
  await page.locator('#compare-label').fill('เก็บชิปไว้ก่อน');
  await page.locator('#compare-capture-a').click();
  await page.locator('[data-planner-select="triple_captain"]').click();
  await page.locator('#compare-label').fill('ทดลอง Triple Captain');
  await page.locator('#compare-capture-b').click();
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','true');
}

test('A/B persists, exports and deletes only the selected slot without saving the Planner',async({page})=>{
  await page.setViewportSize({width:375,height:812});
  await capturePair(page);
  await expect(page.locator('#compare-difference')).toContainText('B − A: +');
  await expect(page.locator('#planner-saved-status')).toContainText('ยังไม่ได้บันทึก');
  await page.reload();
  await expect(page.locator('[data-compare-slot="A"]')).toContainText('เก็บชิปไว้ก่อน');
  await expect(page.locator('[data-compare-slot="B"]')).toContainText('ทดลอง Triple Captain');
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','true');
  await expect(page.locator('#planner-saved-status')).toContainText('ยังไม่เลือกชิป');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  await expect(page.getByRole('region',{name:'ตารางเปรียบเทียบแผน A/B',exact:true})).toBeVisible();
  const downloaded=page.waitForEvent('download');
  await page.locator('#compare-export').click();
  const download=await downloaded;
  expect(download.suggestedFilename()).toBe('fpl-compare-990001-gw3.json');
  const payload=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  expect(payload.teamId).toBe(990001);expect(payload.statuses.A).toBe('current');
  expect(payload.slots.A.lineup.picks).toHaveLength(15);expect(payload.slots.B.chip).toBe('triple_captain');
  expect(payload.difference).toBeGreaterThan(0);
  await page.getByText('ลบเฉพาะแผน A',{exact:true}).click();
  await page.getByRole('button',{name:'ยืนยันลบแผน A',exact:true}).click();
  await page.reload();
  await expect(page.locator('[data-compare-slot="A"]')).toHaveAttribute('data-status','empty');
  await expect(page.locator('[data-compare-slot="B"]')).toContainText('ทดลอง Triple Captain');
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','false');
});

test('changed bank invalidates both saved plans until both are recaptured',async({page})=>{
  await capturePair(page);
  await page.locator('#transfer-bank').fill('1.0');await page.locator('#transfer-bank').press('Tab');
  await expect(page.locator('[data-compare-slot="A"]')).toHaveAttribute('data-status','changed');
  await expect(page.locator('[data-compare-slot="B"]')).toHaveAttribute('data-status','changed');
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','false');
  await page.locator('#compare-capture-b').click();
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','false');
  await page.locator('[data-planner-select="save"]').click();await page.locator('#compare-capture-a').click();
  await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','true');
});

for(const state of ['offline','stale','deadline','mismatch']) {
  test(`${state} cannot turn an old comparison into an actionable delta`,async({page})=>{
    await capturePair(page);
    await page.goto(`/?qaState=${state}`);
    await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind',state);
    await expect(page.locator('#compare-capture-a')).toBeDisabled();
    await expect(page.locator('#compare-capture-b')).toBeDisabled();
    await expect(page.locator('#compare-difference')).toHaveAttribute('data-comparable','false');
    if(state==='mismatch') await expect(page.locator('#compare-board')).not.toContainText('ทดลอง Triple Captain');
    else await expect(page.locator('[data-compare-slot="B"]')).toHaveAttribute('data-status','readonly');
  });
}
