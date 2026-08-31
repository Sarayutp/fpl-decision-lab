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

test('mobile is keyboard reachable and has no page-level horizontal overflow', async ({page}) => {
  await page.setViewportSize({width:375,height:812}); await page.goto('/');
  await expect(page.locator('#runtime-state')).toHaveAttribute('data-kind','ready');
  await expect(page.getByRole('navigation',{name:'เมนูหลัก'})).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
  await page.keyboard.press('Tab'); await expect(page.locator('.skip-link')).toBeFocused();
  expect(await page.locator('.skip-link').evaluate(el => getComputedStyle(el).outlineStyle)).not.toBe('none');
});
