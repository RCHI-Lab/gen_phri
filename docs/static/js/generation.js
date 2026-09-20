// A recorded sequence, synchronized to native video time so seeking, buffering,
// pausing and reduced motion cannot leave the critic on a different candidate.
(() => {
  const section = document.querySelector('.construction');
  const video = section.querySelector('video');
  const tabs = [...section.querySelectorAll('[data-stage]')];
  const phases = [...section.querySelectorAll('[data-generation-phase]')];
  let defaultTimeline = { initial: 0, feedback: 3, regenerate: 7, revised: 8.2, end: 15 };
  const timeline = () => examples?.[active].timeline_seconds || defaultTimeline;
  const $ = id => document.getElementById(id);
  let examples, active = tabs[0].dataset.stage, currentPhase;
  let pendingSeek = null;
  let inView = false, request = 0, mediaURL = null, loadedStage = null;
  const canAutoplay = () => document.documentElement.dataset.motionPaused !== 'true' && !document.hidden;
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let feedbackKey = null;

  function showFeedback(text, phase) {
    const key = `${active}:${phase}:${text}`;
    if (feedbackKey === key) return;
    feedbackKey = key;
    const target = $('stage-feedback');
    target.replaceChildren();
    const animate = phase !== 'initial' && phase !== 'error' && !reduceMotion.matches && canAutoplay();
    if (!animate) {
      target.textContent = text;
      return;
    }
    // A quick, continuous reveal like the YAML specification, with softly
    // fading characters rather than discrete words or a block cursor.
    // Full text stays in the DOM for stable layout and one announcement.
    const characters = [...text];
    characters.forEach((character, index) => {
      const span = document.createElement('span');
      span.className = 'critic-character';
      span.textContent = character;
      span.style.setProperty('--character-delay', `${450 * index / characters.length}ms`);
      target.append(span);
    });
  }

  function setMediaError(failed) {
    section.dataset.mediaError = String(failed);
    phases.forEach(button => {
      button.disabled = failed;
    });
    $('stage-status').hidden = !failed;
    if (failed && examples) showFeedback(examples[active].feedback, 'error');
  }

  async function loadMedia(play = false) {
    if (!examples) return;
    if (loadedStage === active) {
      if (play) video.play().catch(() => {});
      return;
    }
    const token = ++request;
    const stage = active;
    const example = examples[stage];
    setMediaError(false);
    video.pause();
    video.poster = example.poster;
    video.removeAttribute('src');
    delete video.dataset.src;
    video.load();
    pendingSeek = { time: 0, play };
    $('stage-status').textContent = 'Loading recorded sequence…';
    try {
      // The short clips use local blobs to support accurate seeking
      // on basic static preview servers that do not implement HTTP byte ranges.
      const response = await fetch(example.video);
      if (!response.ok) throw new Error('Replay unavailable');
      const blob = await response.blob();
      if (request !== token) return;
      if (mediaURL) URL.revokeObjectURL(mediaURL);
      mediaURL = URL.createObjectURL(blob);
      loadedStage = stage;
      video.controls = false;
      video.src = mediaURL;
      video.load();
    } catch (error) {
      if (request !== token) return;
      loadedStage = null;
      setMediaError(true);
      $('stage-status').textContent = 'Replay could not load. Choose the stage again to retry.';
      console.warn(error.message);
    }
  }
  const loading = fetch('data/scenario-generation.json').then(response => {
    if (!response.ok) throw new Error('Recorded examples unavailable');
    return response.json();
  }).then(data => {
    examples = data.stages;
    defaultTimeline = data.timeline_seconds;
    section.dataset.ready = 'true';
    video.controls = false; // The sequence and phase controls keep the subject unobscured.
    selectStage(tabs.find(tab => tab.dataset.stage === active), false);
  }).catch(() => {
    $('stage-status').textContent = 'Example records could not load. Reload to try again.';
    section.dataset.ready = 'error';
    $('stage-status').hidden = false;
    video.controls = true;
    if (video.dataset.src) {
      video.src = video.dataset.src;
      delete video.dataset.src;
      video.load();
    }
  });

  function sync() {
    section.dataset.playing = String(!video.paused);
    if (section.dataset.mediaError === 'true') return;
    const t = video.currentTime;
    const at = timeline();
    const phase = t + 0.001 < at.feedback ? 'initial' : t + 0.001 < at.revised ? 'feedback' : 'revised';
    section.style.setProperty('--generation-progress', `${Math.min(t / at.end, 1) * 100}%`);
    if (!examples) return;
    if (phase === currentPhase && section.dataset.activeStage === active) return;
    currentPhase = phase;
    section.dataset.phase = phase;
    section.dataset.activeStage = active;
    phases.forEach(button => button.setAttribute('aria-pressed', String(button.dataset.generationPhase === phase)));
    const example = examples[active];
    showFeedback(phase === 'revised' ? example.resultFeedback : example.feedback, phase);
    $('stage-severity').textContent = phase === 'revised' ? example.afterSeverity : example.beforeSeverity;
  }

  function seek(time, play = false) {
    if (!Number.isFinite(video.duration)) {
      pendingSeek = { time, play };
      if (!video.getAttribute('src') && !request) loadMedia(play);
      pendingSeek = { time, play };
      return;
    }
    video.currentTime = time;
    if (play) video.play().catch(() => {});
    else video.pause();
    currentPhase = null;
    sync();
  }
  function selectStage(button, userInitiated = true) {
    active = button.dataset.stage;
    if (!examples) return;
    const example = examples[active];
    const shouldPlay = userInitiated && document.documentElement.dataset.motionPaused !== 'true' && !document.hidden;
    tabs.forEach(tab => {
      tab.setAttribute('aria-selected', String(tab === button));
      tab.tabIndex = tab === button ? 0 : -1;
    });
    $('stage-panel').setAttribute('aria-labelledby', button.id);
    $('stage-task').textContent = example.task;
    showFeedback(example.feedback, 'initial');
    video.setAttribute('aria-label', `${example.task}: initial attempt, critic feedback, and regeneration`);
    if (userInitiated || inView) {
      loadedStage = null;
      loadMedia(shouldPlay || (!userInitiated && canAutoplay()));
    }
    currentPhase = null;
    sync();
  }
  tabs.forEach((button, index) => {
    button.addEventListener('click', () => selectStage(button));
    button.addEventListener('keydown', event => {
      let next;
      if (['ArrowRight', 'ArrowDown'].includes(event.key)) next = (index + 1) % tabs.length;
      if (['ArrowLeft', 'ArrowUp'].includes(event.key)) next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      tabs[next].focus();
      selectStage(tabs[next]);
    });
  });
  phases.forEach(button => button.addEventListener('click', () => {
    const phase = button.dataset.generationPhase;
    seek(timeline()[phase], phase !== 'feedback');
  }));
  const togglePlayback = () => {
    if (section.dataset.mediaError === 'true') return;
    if (video.paused) seek(video.ended ? 0 : video.currentTime, true);
    else video.pause();
  };
  video.addEventListener('click', () => { if (!video.controls) togglePlayback(); });
  video.addEventListener('keydown', event => {
    if (video.controls || ![' ', 'k', 'K'].includes(event.key)) return;
    event.preventDefault();
    togglePlayback();
  });
  video.addEventListener('loadedmetadata', () => {
    if (pendingSeek) {
      const request = pendingSeek;
      pendingSeek = null;
      seek(request.time, request.play);
    }
  });
  ['timeupdate', 'seeked', 'play', 'pause', 'ended'].forEach(event => video.addEventListener(event, sync));
  video.addEventListener('error', () => {
    loadedStage = null;
    setMediaError(true);
    $('stage-status').textContent = 'Replay unavailable. The recorded feedback remains below.';
  });
  const observer = new IntersectionObserver(entries => {
    inView = entries[0].isIntersecting;
    section.dataset.visible = String(inView);
    if (inView) loadMedia(canAutoplay());
    else {
      video.pause();
      if (pendingSeek) pendingSeek.play = false;
    }
  }, { threshold: 0.2 });
  observer.observe(video);
  window.addEventListener('site-motion-change', event => {
    if (event.detail.paused) {
      video.pause();
      if (pendingSeek) pendingSeek.play = false;
    } else if (inView) loadMedia(true);
  });
  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      video.pause();
      if (pendingSeek) pendingSeek.play = false;
    } else if (inView && canAutoplay()) loadMedia(true);
  });
  loading.then(sync);
})();
