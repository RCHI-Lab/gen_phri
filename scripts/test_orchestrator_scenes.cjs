// Real-browser checks: paired scenes load, orbit/zoom/reset, and survive tab changes.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8011/docs/#orchestration');
  assert.equal(await page.locator('#orchestration .action-scene').count(), 8, 'Eight interactive scene hosts');
  for (const id of ['retry', 'accept', 'resume', 'backtrack']) {
    await page.locator(`[data-orchestration-tab="${id}"]`).click();
    await page.locator(`#action-${id} .action-comparison`).scrollIntoViewIfNeeded();
    await page.waitForFunction(id => [...document.querySelectorAll(`#action-${id} .action-scene`)].every(el => el.dataset.state === 'ready'), id, { timeout: 120000 });
    const canvases = page.locator(`#action-${id} canvas`);
    assert.equal(await canvases.count(), 2);
    assert.equal(await page.locator('#orchestration canvas').count(), 2, 'Reuse only two WebGL contexts');
    await canvases.first().focus();
    const before = await canvases.first().screenshot();
    await page.keyboard.press('ArrowRight');
    await page.waitForTimeout(300);
    assert.notDeepEqual(await canvases.first().screenshot(), before, `${id}: orbit changes rendered view`);
    const rotated = await canvases.first().screenshot();
    await page.keyboard.press('+');
    await page.waitForTimeout(300);
    assert.notDeepEqual(await canvases.first().screenshot(), rotated, `${id}: zoom changes rendered view`);
    await page.locator(`#action-${id} [data-reset-scenes]`).click();
    await page.waitForTimeout(300);
    await canvases.first().focus();
    assert.deepEqual(await canvases.first().screenshot(), before, `${id}: reset restores the original view`);
    await page.locator(`[data-orchestration-tab="${id}"]`).focus();
    await page.locator(`#action-${id} .action-reasoning`).scrollIntoViewIfNeeded();
    await page.locator('#orchestration').screenshot({ path: `/tmp/orchestrator-scene-${id}.png` });
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.locator('[data-orchestration-tab="retry"]').click();
  await page.waitForFunction(() => document.querySelector('#action-retry .action-scene').dataset.state === 'ready', null, {timeout:120000});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  await page.locator('#action-retry .action-reasoning').scrollIntoViewIfNeeded();
  await page.locator('#orchestration').screenshot({ path: '/tmp/orchestrator-scene-mobile.png' });
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('PASS: all eight real 3D scenes load; orbit, zoom, reset, tab switching, two-context limit, mobile layout.');
})().catch(error => { console.error(error); process.exit(1); });
