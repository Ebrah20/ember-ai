// ─────────────────────────────────────────────────────────────────────────────
// app.js — Global state, settings init, DOMContentLoaded entry point
// ─────────────────────────────────────────────────────────────────────────────

// ── Shared global state ────────────────────────────────────────────────────────
let isMouseTrackingEnabled = false;
window.isMouseTrackingEnabled = false;

const STORAGE_KEYS = {
    mouseTracking: 'ember_mouse_tracking_enabled',
    visionProvider: 'ember_vision_provider',
    ttsProvider: 'ember_tts_provider',
    form: 'emberForm',
};

let currentForm = localStorage.getItem(STORAGE_KEYS.form) || '0';

// ── Settings panel ────────────────────────────────────────────────────────────
window.addEventListener('DOMContentLoaded', async () => {
    // Welcome message
    addMessage('ember', 'Ember', '*whimpers* I missed you... tell me what to do.');

    // Textarea auto-resize
    const input = document.getElementById('user-input');
    autoResizeTextarea();
    input.addEventListener('input', autoResizeTextarea);
    input.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });

    // Settings modal
    const modal          = document.getElementById('settings-modal');
    const openBtn        = document.getElementById('settings-btn');
    const closeBtn       = document.getElementById('settings-close');
    const trackingToggle = document.getElementById('mouse-tracking-toggle');
    const visionSelect   = document.getElementById('vision-provider');
    const ttsSelect      = document.getElementById('tts-provider');
    const formToggleBtn  = document.getElementById('form-toggle-btn');

    const openSettings  = () => { modal.classList.add('open');    modal.setAttribute('aria-hidden', 'false'); };
    const closeSettings = () => { modal.classList.remove('open'); modal.setAttribute('aria-hidden', 'true');  };

    openBtn.addEventListener('click', openSettings);
    closeBtn.addEventListener('click', closeSettings);
    modal.addEventListener('click', e => { if (e.target === modal) closeSettings(); });
    document.addEventListener('keydown', e => { if (e.key === 'Escape' && modal.classList.contains('open')) closeSettings(); });

    // Restore saved providers
    const savedVision = localStorage.getItem(STORAGE_KEYS.visionProvider);
    if (savedVision && ['local', 'openai'].includes(savedVision)) visionSelect.value = savedVision;

    const savedTts = localStorage.getItem(STORAGE_KEYS.ttsProvider);
    if (savedTts && ['local', 'elevenlabs'].includes(savedTts)) ttsSelect.value = savedTts;

    // Restore mouse tracking
    const savedTracking = localStorage.getItem(STORAGE_KEYS.mouseTracking) === '1';
    trackingToggle.checked = savedTracking;
    isMouseTrackingEnabled = savedTracking;
    window.isMouseTrackingEnabled = savedTracking;

    // Restore outfit form
    currentForm = localStorage.getItem(STORAGE_KEYS.form) || '0';
    updateFormToggleButton();

    // Save on change
    visionSelect.addEventListener('change', () => localStorage.setItem(STORAGE_KEYS.visionProvider, visionSelect.value));
    ttsSelect.addEventListener('change',    () => localStorage.setItem(STORAGE_KEYS.ttsProvider, ttsSelect.value));

    trackingToggle.addEventListener('change', e => {
        isMouseTrackingEnabled = e.target.checked;
        window.isMouseTrackingEnabled = isMouseTrackingEnabled;
        localStorage.setItem(STORAGE_KEYS.mouseTracking, isMouseTrackingEnabled ? '1' : '0');
        if (typeof window.setMouseTrackingEnabled === 'function') window.setMouseTrackingEnabled(isMouseTrackingEnabled);
    });
    if (typeof window.setMouseTrackingEnabled === 'function') window.setMouseTrackingEnabled(isMouseTrackingEnabled);

    formToggleBtn.addEventListener('click', () => {
        currentForm = currentForm === '0' ? '1' : '0';
        localStorage.setItem(STORAGE_KEYS.form, currentForm);
        setModelForm(currentForm);
    });

    // Boot Live2D
    await initLive2D();
});
