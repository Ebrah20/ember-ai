/**
 * lipsync.js — Real frequency-based lip sync for Ember AI.
 *
 * Uses Web Audio API AnalyserNode to analyse audio frequency data
 * and map it to Live2D mouth parameters (ParamMouthOpenY, ParamMouthForm).
 *
 * Usage:
 *   const ls = createLipSync();
 *   ls.connectAudio(audioElement); // call when audio starts playing
 *   ls.start();                    // begin driving Live2D params
 *   ls.stop();                     // stop when audio ends
 */

(function () {
  "use strict";

  let _audioCtx    = null;
  let _analyser    = null;
  let _dataArray   = null;
  let _rafId       = null;
  let _source      = null;
  let _isRunning   = false;

  // Smoothing state
  let _smoothMouthOpen = 0;
  const LERP_SPEED = 0.18;

  function getAudioContext() {
    if (!_audioCtx || _audioCtx.state === "closed") {
      _audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    }
    if (_audioCtx.state === "suspended") {
      _audioCtx.resume().catch(() => {});
    }
    return _audioCtx;
  }

  function ensureAnalyser() {
    const ctx = getAudioContext();
    if (_analyser) return _analyser;
    _analyser = ctx.createAnalyser();
    _analyser.fftSize = 256;
    _analyser.smoothingTimeConstant = 0.5;
    _dataArray = new Uint8Array(_analyser.frequencyBinCount);
    _analyser.connect(ctx.destination);
    return _analyser;
  }

  /**
   * Connect an HTML <audio> element to the lip sync analyser.
   * Call this just before (or right as) the audio starts playing.
   */
  function connectAudio(audioEl) {
    try {
      const ctx      = getAudioContext();
      const analyser = ensureAnalyser();

      // Disconnect old source
      if (_source) {
        try { _source.disconnect(); } catch (_) {}
        _source = null;
      }

      _source = ctx.createMediaElementSource(audioEl);
      _source.connect(analyser);
    } catch (e) {
      // Cross-origin or already-connected audio — degrade gracefully
      console.warn("[LipSync] Could not connect audio:", e.message);
    }
  }

  /**
   * Get current mouth-open value (0–1) from frequency data.
   * Uses low-to-mid frequencies which correspond to vocal energy.
   */
  function getMouthOpen() {
    if (!_analyser || !_dataArray) return 0;
    _analyser.getByteFrequencyData(_dataArray);

    // Average energy in the 80–2000 Hz band (bins ~2 to ~50 for FFT size 256, 44100 Hz)
    const start = 2, end = 50;
    let sum = 0;
    for (let i = start; i < end && i < _dataArray.length; i++) {
      sum += _dataArray[i];
    }
    const avg  = sum / (end - start);
    const norm = Math.min(1, avg / 100); // normalise 0–100 → 0–1
    return norm;
  }

  function _tick() {
    if (!_isRunning) return;

    const raw = getMouthOpen();
    // Lerp toward target for smooth animation
    _smoothMouthOpen += (raw - _smoothMouthOpen) * LERP_SPEED;
    const mouthValue = Math.max(0, Math.min(1, _smoothMouthOpen));

    // Drive Live2D param via setCoreParam (defined in live2d.js)
    if (typeof setCoreParam === "function") {
      setCoreParam("ParamMouthOpenY", mouthValue);
      // Optionally drive MouthForm — midrange energy → slightly wider / rounder
      const form = 0.3 + mouthValue * 0.4;
      setCoreParam("ParamMouthForm", form);
    }

    _rafId = requestAnimationFrame(_tick);
  }

  function start() {
    if (_isRunning) return;
    _isRunning = true;
    _smoothMouthOpen = 0;
    _rafId = requestAnimationFrame(_tick);
    console.log("[LipSync] started");
  }

  function stop() {
    _isRunning = false;
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
    _smoothMouthOpen = 0;
    // Set mouth closed
    if (typeof setCoreParam === "function") {
      setCoreParam("ParamMouthOpenY", 0);
      setCoreParam("ParamMouthForm",  0.3);
    }
    console.log("[LipSync] stopped");
  }

  // Export to window so chat.js can use it
  window.EmberLipSync = { connectAudio, start, stop };
})();
