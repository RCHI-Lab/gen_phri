// Run with Playwright available in NODE_PATH and the preview server on port 8011.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.goto('http://127.0.0.1:8011/docs/#orchestration');
  assert.equal(await page.locator('#orchestration video').count(), 0);
  assert.equal(await page.locator('#orchestration img').count(), 8);
  const tabs = page.locator('[data-orchestration-tab]');
  await tabs.first().waitFor({ timeout: 4000 });
  assert.equal(await tabs.count(), 4);
  assert.equal(await page.locator('#orchestration .action-tabs small, #orchestration [aria-hidden="true"]').count(), 0);
  for (const id of ['retry', 'resume', 'backtrack', 'accept']) {
    await page.locator(`[data-orchestration-tab="${id}"]`).click();
    assert.equal(await page.locator('#orchestration [role="tabpanel"]:visible').count(), 1);
    assert.equal(await page.locator(`#action-${id}`).isVisible(), true);
    assert.equal(await page.locator(`#action-${id} .comparison-pane`).count(), 2);
    assert((await page.locator(`#action-${id} .action-reasoning`).innerText()).split(/\s+/).length < 45, `${id}: too much reasoning copy`);
    const task = await page.locator(`#action-${id} .prompt-box`).innerText();
    assert(task.startsWith('Task: '));
    assert(task.split(/\s+/).length <= 8, `${id}: task should be a concise label`);
    assert.equal(await page.locator(`#action-${id} .action-metadata dt`).allTextContents().then(labels => labels.join(', ')), 'Stage, Critic Flags');
    await page.locator(`#action-${id} .action-comparison`).scrollIntoViewIfNeeded();
    await page.waitForFunction(id => [...document.querySelectorAll(`#action-${id} img, #action-${id} video`)].every(el =>
      el.tagName === 'IMG' ? el.complete && el.naturalWidth > 0 : el.readyState >= 2), id);
    await page.locator(`#action-${id} .action-reasoning`).scrollIntoViewIfNeeded();
    assert(await page.locator(`#action-${id} .action-reasoning`).isVisible());
    await page.locator('#orchestration').screenshot({ path: `/tmp/orchestration-${id}.png` });
  }
  await tabs.first().focus();
  await page.keyboard.press('End');
  assert.equal(await tabs.last().getAttribute('aria-selected'), 'true');
  await page.keyboard.press('ArrowRight');
  assert.equal(await tabs.first().getAttribute('aria-selected'), 'true');
  for (const width of [390, 768]) {
    await page.setViewportSize({ width, height: 900 });
    for (const id of ['retry', 'resume', 'backtrack', 'accept']) {
      await page.locator(`[data-orchestration-tab="${id}"]`).click();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}: ${id}`);
      await page.locator(`#action-${id} .action-reasoning`).scrollIntoViewIfNeeded();
      await page.locator('#orchestration').screenshot({ path: `/tmp/orchestration-${id}-${width}.png` });
    }
  }
  const assets = await page.locator('#orchestration img, #orchestration video').evaluateAll(media => media.flatMap(el =>
    el.tagName === 'IMG' ? [el.src] : [el.poster, el.currentSrc || el.src]));
  for (const url of assets) assert.equal((await page.request.get(url)).status(), 200, url);
  const plain = await browser.newPage({ javaScriptEnabled: false });
  await plain.goto('http://127.0.0.1:8011/docs/#orchestration');
  assert.equal(await plain.locator('.action-panel:visible').count(), 4);
  assert.deepEqual(errors, []);
  await browser.close();
  console.log('PASS: four action examples, keyboard navigation, reduced motion, media, desktop/tablet/mobile layouts.');
})().catch(error => { console.error(error); process.exit(1); });
