// Native media and keyboard-accessible controls; no build step required.
(() => {
  const motionPreference = window.matchMedia('(prefers-reduced-motion: reduce)');
  let motionPaused = motionPreference.matches;
  const motionButtons = [...document.querySelectorAll('.motion-toggle')];
  const siteNav = document.querySelector('.site-nav');
  const heroMotionButton = document.getElementById('hero-motion-toggle');
  function syncNavigation() {
    const visible = window.scrollY > 80;
    siteNav.classList.toggle('is-visible', visible);
    siteNav.inert = !visible;
    heroMotionButton.inert = visible;
    heroMotionButton.classList.toggle('is-covered', visible);
  }
  window.addEventListener('scroll', syncNavigation, { passive: true });
  window.addEventListener('pageshow', syncNavigation);
  syncNavigation();
  const hero = document.getElementById('hero-video');
  const visibleVideos = new Set();
  const videos = [...document.querySelectorAll('video:not(#sim-video):not(.stage-video)')];

  videos.filter(video => video.dataset.playbackRate).forEach(video => {
    const rate = Number(video.dataset.playbackRate);
    video.defaultPlaybackRate = rate;
    video.playbackRate = rate;
    video.addEventListener('loadedmetadata', () => { video.playbackRate = rate; });
  });

  function loadVideo(video) {
    if (video.dataset.src) {
      video.preload = 'metadata';
      video.src = video.dataset.src;
      delete video.dataset.src;
      video.load();
    }
  }
  function playVideo(video) {
    loadVideo(video);
    video.play().catch(() => {}); // The poster and native controls remain usable.
  }
  // Videos marked data-click-to-play stay on their thumbnail until the viewer starts them.
  function isAutoplayable(video) {
    return !('clickToPlay' in video.dataset);
  }
  function syncMotionButton() {
    motionButtons.forEach(button => {
      button.setAttribute('aria-pressed', String(motionPaused));
      button.innerHTML = motionPaused ? 'Play videos <span aria-hidden="true">▷</span>' : 'Pause videos <span aria-hidden="true">Ⅱ</span>';
    });
    document.documentElement.dataset.motionPaused = String(motionPaused);
  }
  function setMotion(paused) {
    motionPaused = paused;
    syncMotionButton();
    videos.forEach(video => {
      if (paused) video.pause();
      else if (isAutoplayable(video) && visibleVideos.has(video) && !document.hidden) playVideo(video);
    });
    window.dispatchEvent(new CustomEvent('site-motion-change', { detail: { paused } }));
  }
  syncMotionButton();
  motionButtons.forEach(button => button.addEventListener('click', () => setMotion(!motionPaused)));
  motionPreference.addEventListener('change', event => setMotion(event.matches));

  document.querySelectorAll('[data-click-to-play-player]').forEach(player => {
    const video = player.querySelector('video');
    const cover = player.querySelector('.walkthrough-cover');
    if (!video || !cover) return;
    cover.addEventListener('click', () => {
      player.classList.add('is-playing');
      delete video.dataset.clickToPlay; // From here it follows the usual scroll and motion rules.
      playVideo(video);
      video.focus({ preventScroll: true });
    });
  });

  document.querySelectorAll('a[href="#walkthrough-video"]').forEach(link => {
    link.addEventListener('click', event => {
      if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      const video = document.getElementById('walkthrough-video');
      if (isAutoplayable(video)) loadVideo(video);
      const bounds = video.getBoundingClientRect();
      if (!motionPreference.matches && Math.abs(bounds.top + bounds.height / 2 - window.innerHeight / 2) > 1) {
        // Deferred media above the film can resize while we scroll past it.
        const controller = new AbortController();
        const cancel = () => controller.abort();
        ['wheel', 'touchstart', 'keydown'].forEach(type => {
          window.addEventListener(type, cancel, { once: true, passive: true, signal: controller.signal });
        });
        window.addEventListener('scrollend', () => {
          cancel();
          const finalBounds = video.getBoundingClientRect();
          window.scrollTo({
            top: window.scrollY + finalBounds.top + finalBounds.height / 2 - window.innerHeight / 2,
            behavior: 'instant'
          });
        }, { once: true, signal: controller.signal });
      }
      window.scrollTo({
        top: window.scrollY + bounds.top + bounds.height / 2 - window.innerHeight / 2,
        behavior: motionPreference.matches ? 'instant' : 'smooth'
      });
      history.pushState(null, '', link.hash);
      const cover = video.closest('[data-click-to-play-player]')?.querySelector('.walkthrough-cover');
      (cover && !isAutoplayable(video) ? cover : video).focus({ preventScroll: true });
    });
  });

  const videoObserver = new IntersectionObserver(entries => {
    entries.forEach(({ target: video, isIntersecting }) => {
      if (isIntersecting) {
        visibleVideos.add(video);
        if (!isAutoplayable(video)) return; // The cover button loads and starts these.
        loadVideo(video); // Native play controls work even when autoplay is paused.
        if (!motionPaused && !document.hidden) playVideo(video);
      } else {
        visibleVideos.delete(video);
        video.pause();
      }
    });
  }, { threshold: 0.2 });
  videos.forEach(video => {
    videoObserver.observe(video);
    // Explicit playback also loads deferred sources when reduced motion is on.
    video.addEventListener('pointerdown', () => loadVideo(video), { once: true });
    video.addEventListener('keydown', () => loadVideo(video), { once: true });
  });
  document.querySelectorAll('[data-video-disclosure]').forEach(disclosure => {
    disclosure.addEventListener('toggle', () => {
      if (disclosure.open) return; // Opening uses the normal visibility/loading rules.
      disclosure.querySelectorAll('video').forEach(video => {
        video.pause();
        visibleVideos.delete(video);
      });
    });
  });
  document.addEventListener('visibilitychange', () => {
    videos.forEach(video => {
      if (document.hidden) video.pause();
      else if (!motionPaused && isAutoplayable(video) && visibleVideos.has(video)) playVideo(video);
    });
  });

  document.querySelectorAll('[data-hero]').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('[data-hero]').forEach(other => other.setAttribute('aria-pressed', String(other === button)));
      hero.poster = `media/hero-${button.dataset.hero}.jpg`;
      hero.src = `media/hero-${button.dataset.hero}.mp4`;
      hero.load();
      if (!motionPaused && visibleVideos.has(hero)) playVideo(hero);
    });
  });

  // All examples remain readable without JavaScript; enhance them into tabs.
  const actionTabs = [...document.querySelectorAll('[data-orchestration-tab]')];
  const actionPanels = [...document.querySelectorAll('.action-panel')];
  function selectAction(button) {
    actionTabs.forEach(tab => {
      const selected = tab === button;
      tab.setAttribute('aria-selected', String(selected));
      tab.tabIndex = selected ? 0 : -1;
    });
    actionPanels.forEach(panel => {
      panel.hidden = panel.id !== `action-${button.dataset.orchestrationTab}`;
      if (panel.hidden) panel.querySelectorAll('video').forEach(video => {
        video.pause();
        visibleVideos.delete(video);
      });
    });
    window.dispatchEvent(new CustomEvent('orchestrator-action-change', { detail: { action: button.dataset.orchestrationTab } }));
  }
  if (actionTabs.length) {
    actionTabs[0].parentElement.setAttribute('role', 'tablist');
    actionTabs.forEach((button, index) => {
      button.setAttribute('role', 'tab');
      button.setAttribute('aria-controls', `action-${button.dataset.orchestrationTab}`);
      button.addEventListener('click', () => selectAction(button));
      button.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight') next = (index + 1) % actionTabs.length;
        if (event.key === 'ArrowLeft') next = (index - 1 + actionTabs.length) % actionTabs.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = actionTabs.length - 1;
        if (next === undefined) return;
        event.preventDefault();
        actionTabs[next].focus();
        selectAction(actionTabs[next]);
      });
    });
    actionPanels.forEach(panel => {
      panel.setAttribute('role', 'tabpanel');
      panel.tabIndex = 0;
    });
    selectAction(actionTabs.find(tab => tab.dataset.orchestrationTab === 'backtrack'));
    const sceneObserver = new IntersectionObserver(entries => {
      if (!entries.some(entry => entry.isIntersecting)) return;
      sceneObserver.disconnect();
      import('./orchestrator-scenes.js').catch(error => {
        document.querySelectorAll('.action-scene-status').forEach(status => {
          status.textContent = '3D scenes could not load. Reload the page to try again.';
        });
        console.warn('Could not load orchestrator scene viewer:', error);
      });
    }, { rootMargin: '100px' });
    sceneObserver.observe(document.getElementById('orchestration'));
  }

  // Keep the existing 50-task viewer, but defer Three.js until it is nearby.
  const gallery = document.getElementById('sim-demos');
  const galleryObserver = new IntersectionObserver(entries => {
    if (!entries.some(entry => entry.isIntersecting)) return;
    galleryObserver.disconnect();
    import('./sim-demos.js').catch(() => {
      document.getElementById('sim-grid').textContent = 'The interactive explorer could not load. Reload the page to try again.';
      document.getElementById('sim-viewer-status').textContent = '3D viewer unavailable.';
    });
  }, { rootMargin: '600px' });
  galleryObserver.observe(gallery);

  const navLinks = [...document.querySelectorAll('.site-nav nav a')];
  const navObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => {
      if (!entry.isIntersecting) return;
      navLinks.forEach(link => {
        if (link.hash === `#${entry.target.id}`) link.setAttribute('aria-current', 'location');
        else link.removeAttribute('aria-current');
      });
    });
  }, { rootMargin: '-15% 0px -60% 0px' });
  navLinks.forEach(link => navObserver.observe(document.querySelector(link.hash)));
})();
