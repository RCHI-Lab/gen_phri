// Breaks caught: stale feedback after changing stage, incorrect seek/replay state,
// autoplay despite reduced motion, and a critic column that overflows on mobile.
const { chromium } = require('playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ channel: 'chrome', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, reducedMotion: 'reduce' });
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto((process.env.BASE_URL || 'http://127.0.0.1:8012/docs/') + '#method');
    assert.equal(await page.locator('#stage-critic').count(), 1, 'Critic belongs beside the stage preview');
    assert.equal(await page.locator('.generation-playback, #stage-description, .generation-source, .stage-revision, .stage-outcome, #stage-critic-state').count(), 0);
    assert.equal(await page.locator('#stage-critic .stage-context .prompt-box').count(), 1);
    assert.equal(await page.locator('#generation-regenerate').count(), 0);
    for (const [stage, task] of [
      ['human-generation', 'Back-of-neck itch relief'],
      ['human-placement', 'Hand warming'],
      ['robot-placement', 'Back and leg bathing'],
      ['robot-motion', 'Spine assessment']
    ]) {
      await page.locator(`[data-stage="${stage}"]`).click();
      await page.waitForFunction(() => document.querySelector('.stage-video').readyState >= 2);
      assert.equal(await page.locator('#stage-task').innerText(), task);
      assert.equal(await page.locator('.stage-video').evaluate(v => v.paused), true);
      await page.locator('[data-generation-phase="feedback"]').click();
      await page.waitForFunction(() => document.querySelector('.construction').dataset.phase === 'feedback');
      assert(await page.locator('#stage-feedback').isVisible());
      const quote = await page.locator('#stage-feedback').innerText();
      assert(quote.length > 20);
      assert.equal(await page.locator('.critic-character').count(), 0, 'Reduced motion shows the whole critique immediately');
      await page.locator('[data-generation-phase="revised"]').click();
      await page.waitForFunction(() => document.querySelector('.construction').dataset.phase === 'revised');
      assert.equal(await page.locator('#stage-feedback').innerText(), { 'human-generation': 'Pose Accepted', 'human-placement': 'Placement Improved', 'robot-placement': 'Placement Accepted', 'robot-motion': 'Motion Accepted' }[stage]);
      await page.locator('[data-generation-phase="initial"]').click();
      await page.waitForFunction(() => document.querySelector('.construction').dataset.phase === 'initial');
      assert.equal(await page.locator('.stage-video').evaluate(v => v.paused), false);
      await page.locator('.stage-video').click();
    }
    await page.locator('[data-stage="robot-motion"]').focus();
    await page.keyboard.press('Home');
    assert.equal(await page.locator('[data-stage="human-generation"]').getAttribute('aria-selected'), 'true');
    await page.waitForFunction(() => document.querySelector('.stage-video').readyState >= 2);
    await page.locator('[data-generation-phase="feedback"]').click();
    await page.locator('.stage-video').click();
    await page.waitForFunction(() => document.querySelector('.construction').dataset.phase === 'revised');
    assert.equal(await page.locator('.stage-video').evaluate(v => v.paused), false);
    await page.locator('.stage-video').click();
    assert.equal(await page.locator('.stage-video').evaluate(v => v.paused), true);
    await page.locator('[data-generation-phase="initial"]').click();
    await page.waitForFunction(() => document.querySelector('.stage-video').currentTime < 1);
    await page.locator('.stage-video').click();
    for (const width of [1440, 1024, 768, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      await page.locator('.construction').scrollIntoViewIfNeeded();
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Overflow at ${width}`);
      assert(await page.locator('#stage-critic').isVisible());
      if (width === 1440) {
        const video = await page.locator('.stage-video').boundingBox();
        const critic = await page.locator('#stage-critic').boundingBox();
        assert(critic.x >= video.x + video.width, 'Critic is on the right');
      }
      await page.screenshot({ path: `/tmp/scenario-generation-${width}.png` });
    }
    assert.deepEqual(errors, []);
    const playing = await browser.newPage({ viewport: { width: 1440, height: 1000 } });
    await playing.goto((process.env.BASE_URL || 'http://127.0.0.1:8012/docs/') + '#method');
    await playing.waitForFunction(() => document.querySelector('.stage-video').currentTime > 0.1);
    assert.equal(await playing.locator('.critic-symbol').evaluate(el => getComputedStyle(el).animationName), 'critic-spin');
    await playing.waitForFunction(() => document.querySelector('.stage-video').currentTime > 3 && document.querySelector('.construction').dataset.phase === 'feedback', null, { timeout: 10000 });
    assert.equal(await playing.locator('.construction').getAttribute('data-phase'), 'feedback');
    assert.equal(await playing.locator('.critic-symbol').evaluate(el => getComputedStyle(el).animationName), 'none');
    await playing.waitForFunction(() => [...document.querySelectorAll('.critic-character')].some(el => Number(getComputedStyle(el).opacity) > 0));
    const characters = () => [...document.querySelectorAll('.critic-character')].map(el => Number(getComputedStyle(el).opacity));
    const early = await playing.evaluate(characters);
    assert(early.some(opacity => opacity > 0) && early.some(opacity => opacity === 0), 'Feedback reveals continuously');
    await playing.locator('.site-nav .motion-toggle').click();
    assert.equal(await playing.locator('.stage-video').evaluate(v => v.paused), true);
    assert.equal(await playing.locator('.critic-character').first().evaluate(el => getComputedStyle(el).animationPlayState), 'paused');
    await playing.locator('.site-nav .motion-toggle').click();
    await playing.waitForFunction(() => [...document.querySelectorAll('.critic-character')].every(el => Number(getComputedStyle(el).opacity) === 1));
    await playing.locator('[data-generation-phase="initial"]').click();
    assert.equal(await playing.locator('.critic-character').count(), 0, 'Replay clears the previous text reveal');
    await playing.close();
    const failed = await browser.newPage({ reducedMotion: 'reduce' });
    let rejectMedia = true;
    await failed.route('**/media/generation/human-generation.mp4', route => rejectMedia ? route.abort() : route.continue());
    await failed.goto((process.env.BASE_URL || 'http://127.0.0.1:8012/docs/') + '#method');
    await failed.waitForSelector('.construction[data-media-error=true]');
    assert(await failed.locator('#stage-feedback').isVisible(), 'Media errors must not hide the saved critique');
    assert(await failed.locator('[data-generation-phase="initial"]').isDisabled());
    rejectMedia = false;
    await failed.locator('[data-stage="human-generation"]').click();
    await failed.waitForFunction(() => document.querySelector('.stage-video').readyState >= 2);
    assert(await failed.locator('[data-generation-phase="initial"]').isEnabled());
    await failed.close();
    console.log('PASS: all four recorded replays, synchronized feedback, stage switching, keyboard controls, reduced motion, and responsive layout.');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exit(1); });
