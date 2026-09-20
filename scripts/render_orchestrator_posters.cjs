// Re-render fallback thumbnails from the same interactive scenes shown on the site.
const { chromium } = require('playwright');
const path = require('node:path');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1100 }, deviceScaleFactor: 2, reducedMotion: 'reduce' });
  await page.goto('http://127.0.0.1:8011/docs/#orchestration');
  for (const action of ['retry', 'accept', 'resume', 'backtrack']) {
    await page.locator(`[data-orchestration-tab="${action}"]`).click();
    await page.locator(`#action-${action} .action-comparison`).scrollIntoViewIfNeeded();
    await page.waitForFunction(action => [...document.querySelectorAll(`#action-${action} .action-scene`)].every(host => host.dataset.state === 'ready'), action, { timeout: 120000 });
    await page.locator(`#action-${action} [data-reset-scenes]`).click();
    const canvases = page.locator(`#action-${action} canvas`);
    for (const [index, side] of ['before', 'after'].entries()) {
      await canvases.nth(index).screenshot({ path: path.join(__dirname, `../docs/media/orchestrator/scenes/${action}-${side}.jpg`), type: 'jpeg', quality: 90 });
    }
    console.log(`Rendered ${action} before/after from exported recorded scenes.`);
  }
  await browser.close();
})().catch(error => { console.error(error); process.exit(1); });
