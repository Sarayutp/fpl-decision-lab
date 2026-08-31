const {test, expect} = require('@playwright/test');

test('เลือกทีม → รับคำแนะนำ → บันทึกแผน → copy briefing', async ({page, context}) => {
  await context.grantPermissions(['clipboard-read','clipboard-write']);
  await page.goto('/');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await expect(page.locator('#identity-team-name')).toHaveText('QA United');
  await page.locator('#team-id-input').fill('990001');
  await page.locator('#save-team-id').click();
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await page.locator('#use-recommended').click();
  await expect(page.locator('#lab-player-count')).toHaveText('15/15');
  await page.locator('[data-planner-select="save"]').first().click();
  await page.locator('[data-planner-path="roll"]').click();
  await page.locator('#save-planner').click();
  await expect(page.locator('#planner-saved-status')).toContainText('บันทึกแผน GW3');
  await page.locator('#decision-note').fill('QA regression');
  await page.locator('#record-decision').click();
  await expect(page.locator('#decision-log-list')).toContainText('QA regression');
  await page.locator('[name="actualPoints"]').fill('60');
  await page.locator('[name="samePlan"]').check();
  await page.getByRole('button',{name:'บันทึกผล GW3'}).click();
  await expect(page.locator('#decision-log-list')).toContainText('ผลจริง 60');
  await page.locator('#copy-briefing').click();
  await expect.poll(() => page.evaluate(() => navigator.clipboard.readText())).toContain('Team ID: 990001');
  await page.reload();
  await expect(page.locator('#decision-log-list')).toContainText('QA regression');
  await expect(page.locator('#planner-saved-status')).toContainText('บันทึกแผน GW3');
});

for (const [state, kind, visible] of [['partial','partial',true],['offline','offline',true],['stale','stale',true],['deadline','deadline',true],['mismatch','mismatch',true],['incompatible','incompatible',false],['error','error',false],['empty','empty',true]]) {
  test(`${state} renders an explicit safe state`, async ({page}) => {
    await page.goto(`/?qaState=${state}`);
    await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind',kind);
    await expect(page.locator('#dashboard-content')).toBeVisible({visible});
    if (['offline','stale','deadline','mismatch','empty'].includes(state)) await expect(page.locator('#save-planner')).toBeDisabled();
    if (['partial','mismatch'].includes(state)) await expect(page.locator('#copy-briefing')).toBeDisabled();
  });
}

for (const width of [375,768,1280]) {
  test(`${width}px meets responsive, labels, contrast and keyboard baselines`, async ({page}) => {
    await page.setViewportSize({width,height:900});
    const started = Date.now();
    await page.goto('/');
    await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
    expect(Date.now()-started).toBeLessThan(10000);
    await expect(page.getByRole('navigation',{name:'เมนูหลัก'})).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
    const controls = page.locator('input:visible,select:visible,textarea:visible,button:visible');
    for (const control of await controls.all()) await expect(control).toHaveAccessibleName(/\S/);
    const contrast = await page.evaluate(() => {
      const css = getComputedStyle(document.documentElement);
      const luminance = name => css.getPropertyValue(name).trim().slice(1).match(/../g)
        .map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4)
        .reduce((sum,n,i)=>sum+n*[.2126,.7152,.0722][i],0);
      return [['--ink','--bg'],['--muted','--surface-2']].map(pair=>{
        const [light,dark] = pair.map(luminance).sort((a,b)=>b-a);
        return (light+.05)/(dark+.05);
      });
    });
    for (const ratio of contrast) expect(ratio).toBeGreaterThanOrEqual(4.5);
    await page.keyboard.press('Tab'); await expect(page.locator('.skip-link')).toBeFocused();
    expect(await page.locator('.skip-link').evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe('none');
    await page.keyboard.press('Enter');
    await expect(page.locator('main')).toBeFocused();
  });
}

test('reduced motion disables smooth scrolling and lengthy transitions', async ({page}) => {
  await page.emulateMedia({reducedMotion:'reduce'});
  await page.goto('/');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  const motion = await page.evaluate(() => ({
    scroll:getComputedStyle(document.documentElement).scrollBehavior,
    transition:getComputedStyle(document.querySelector('#copy-briefing')).transitionDuration,
    animation:getComputedStyle(document.querySelector('#captain-list')).animationDuration,
  }));
  expect(motion.scroll).toBe('auto');
  for (const value of [motion.transition,motion.animation]) {
    for (const duration of value.split(',')) expect(parseFloat(duration)).toBeLessThanOrEqual(.00001);
  }
});
