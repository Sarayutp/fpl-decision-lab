const {test, expect} = require('@playwright/test');
const fs = require('node:fs/promises');
const path = require('node:path');

test('help menu opens a complete guide with valid contents and dashboard links', async ({page}) => {
  await page.goto('/');
  await page.getByRole('navigation', {name:'เมนูหลัก'}).getByRole('link', {name:'วิธีใช้งาน',exact:true}).click();
  await expect(page).toHaveURL(/\/guide.html$/);
  await expect(page.getByRole('heading', {level:1})).toHaveText('คู่มือใช้งาน FPL Decision Lab');
  await expect(page.locator('a[aria-current="page"]')).toHaveText('วิธีใช้งาน');
  await expect(page.locator('#guide-content h2')).toHaveCount(22);
  await expect(page.getByRole('navigation', {name:'สารบัญคู่มือ'}).getByRole('link')).toHaveCount(22);
  await page.getByRole('navigation', {name:'สารบัญคู่มือ'}).getByRole('link', {name:/07\. Transfers/}).click();
  await expect(page).toHaveURL(/#guide-07$/);
  await expect(page.locator('#guide-07')).toBeInViewport();
  await page.getByRole('navigation', {name:'เมนูหลัก'}).getByRole('link', {name:'Transfers',exact:true}).click();
  await expect(page).toHaveURL(/\/index.html#transfer-advisor$/);
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
});

test('guide is reachable during dashboard load failure and reads without JavaScript or team data', async ({page, browser, baseURL}) => {
  await page.goto('/?qaState=error');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','error');
  await page.getByRole('link', {name:'วิธีใช้งาน',exact:true}).click();
  await expect(page.locator('#guide-19')).toContainText('แก้ปัญหา');
  const offlineJS = await browser.newContext({javaScriptEnabled:false,baseURL,serviceWorkers:'block'});
  try {
    const plain = await offlineJS.newPage();
    const dataRequests=[];
    plain.on('request', r=>{if(r.url().includes('/data/'))dataRequests.push(r.url());});
    await plain.route('**/data/**', route=>route.abort());
    await plain.goto('/guide.html');
    await expect(plain.locator('#guide-content h2')).toHaveCount(22);
    await plain.getByRole('link',{name:'เริ่มใช้งาน 5 ขั้นตอน'}).click();
    await expect(plain.locator('#guide-01')).toBeInViewport();
    await expect(plain.getByRole('link',{name:'ดาวน์โหลดคู่มือฉบับเต็ม'})).toBeVisible();
    expect(dataRequests).toEqual([]);
  } finally { await offlineJS.close(); }
});

test('download is the full canonical Thai Markdown, not snapshot or private browser data', async ({page}) => {
  await page.goto('/guide.html');
  const downloaded = page.waitForEvent('download');
  await page.getByRole('link',{name:'ดาวน์โหลดคู่มือฉบับเต็ม'}).click();
  const file = await downloaded;
  expect(file.suggestedFilename()).toBe('FPL-Decision-Lab-User-Guide-TH.md');
  const content=await fs.readFile(await file.path(),'utf8');
  expect(content).toBe(await fs.readFile(path.join(__dirname,'../../dashboard/guide.md'),'utf8'));
  expect(content.match(/^## \d{2}\. /gm)).toHaveLength(22);
});

test('print button invokes native printing and print styling keeps content readable', async ({page}) => {
  await page.goto('/guide.html');
  await page.evaluate(()=>{window.print=()=>document.body.dataset.printRequested='yes';});
  await page.getByRole('button',{name:'พิมพ์ / บันทึกเป็น PDF'}).click();
  await expect(page.locator('body')).toHaveAttribute('data-print-requested','yes');
  await page.emulateMedia({media:'print'});
  await expect(page.locator('.guide-actions')).toBeHidden();
  await expect(page.locator('.guide-sidebar')).toBeHidden();
  await expect(page.locator('#guide-22')).toBeVisible();
  expect(await page.locator('body').evaluate(el=>getComputedStyle(el).backgroundColor)).toBe('rgb(255, 255, 255)');
  expect(await page.locator('.guide-content strong').first().evaluate(el=>getComputedStyle(el).color)).toBe('rgb(20, 32, 27)');
});

for (const width of [375,768,1280]) {
  test(`guide at ${width}px has no page overflow and supports keyboard navigation`, async ({page}) => {
    await page.setViewportSize({width,height:900});
    await page.goto('/guide.html');
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
    for (const control of await page.locator('button:visible,summary:visible').all()) await expect(control).toHaveAccessibleName(/\S/);
    await page.keyboard.press('Tab');
    await expect(page.locator('.skip-link')).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page.locator('#guide-content')).toBeFocused();
    await expect(page.locator('#guide-01')).toBeInViewport();
    await page.getByRole('navigation',{name:'สารบัญคู่มือ'}).getByRole('link',{name:/19\. แก้ปัญหา/}).click();
    await expect(page.locator('#guide-19')).toBeInViewport();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth-innerWidth)).toBeLessThanOrEqual(1);
  });
}

test('installed offline cache keeps guide navigation separate from the dashboard', async ({page, context}) => {
  await page.goto('/');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await page.evaluate(async()=>{
    await navigator.serviceWorker.ready;
    if(!navigator.serviceWorker.controller) await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));
  });
  await page.goto('/guide.html?guideQA=online');
  await expect(page.locator('#guide-content h2')).toHaveCount(22);
  await context.setOffline(true);
  try {
    await page.goto('/guide.html?guideQA=offline');
    await expect(page.locator('#guide-content h2')).toHaveCount(22);
    await page.getByRole('navigation',{name:'เมนูหลัก'}).getByRole('link',{name:'This Gameweek',exact:true}).click();
    await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','offline');
    await expect(page.locator('#guide-content')).toHaveCount(0);
  } finally { await context.setOffline(false); }
});
