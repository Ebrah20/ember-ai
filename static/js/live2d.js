// ─────────────────────────────────────────────────────────────────────────────
// live2d.js — Live2D model init, parameter control, expressions, mouse tracking
// ─────────────────────────────────────────────────────────────────────────────

// ── Model state ───────────────────────────────────────────────────────────────
let live2dApp        = null;
let live2dModel      = null;
let live2dBaseScale  = 0.2;
let manualScale      = null;
let modelRawWidth    = 0;
let modelRawHeight   = 0;
let talkingIntervalId = null;
let isDraggingModel  = false;
let dragOffset       = { x: 0, y: 0 };

// Outfit & Cloak
let darkOutfitActive = false;
let cloakActive      = false;
let outfitTickerFn   = null;

// ── Look-at / Mouse Tracking ──────────────────────────────────────────────────
let lookAtTarget  = { x: 0, y: 0 };
let lookAtCurrent = { x: 0, y: 0 };
let lookAtTickerFn = null;
const LOOK_LERP_SPEED = 0.08;

function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function applyLookAt(x, y) {
    const core = getCoreModel();
    if (!core) return;
    const cx = clamp(x, -1, 1);
    const cy = clamp(y, -1, 1);
    const angleX = core.getParameterIndex('ParamAngleX');
    const angleY = core.getParameterIndex('ParamAngleY');
    const eyeX   = core.getParameterIndex('ParamEyeBallX');
    const eyeY   = core.getParameterIndex('ParamEyeBallY');
    if (angleX >= 0) core.setParameterValueByIndex(angleX, cx * 30);
    if (angleY >= 0) core.setParameterValueByIndex(angleY, -cy * 30);
    if (eyeX   >= 0) core.setParameterValueByIndex(eyeX, cx);
    if (eyeY   >= 0) core.setParameterValueByIndex(eyeY, -cy);
}

function startLerpToCenter() {
    if (lookAtTickerFn || !live2dApp) return;
    lookAtTickerFn = () => {
        lookAtCurrent.x += (lookAtTarget.x - lookAtCurrent.x) * LOOK_LERP_SPEED;
        lookAtCurrent.y += (lookAtTarget.y - lookAtCurrent.y) * LOOK_LERP_SPEED;
        applyLookAt(lookAtCurrent.x, lookAtCurrent.y);
        if (
            Math.abs(lookAtTarget.x - lookAtCurrent.x) < 0.001 &&
            Math.abs(lookAtTarget.y - lookAtCurrent.y) < 0.001
        ) {
            applyLookAt(lookAtTarget.x, lookAtTarget.y);
            live2dApp.ticker.remove(lookAtTickerFn);
            lookAtTickerFn = null;
        }
    };
    live2dApp.ticker.add(lookAtTickerFn);
}

function applyModelFocus(x, y) {
    lookAtTarget.x = x; lookAtTarget.y = y;
    if (isMouseTrackingEnabled) {
        lookAtCurrent.x = x; lookAtCurrent.y = y;
        applyLookAt(x, y);
    }
}

window.setMouseTrackingEnabled = function(enabled) {
    isMouseTrackingEnabled = Boolean(enabled);
    window.isMouseTrackingEnabled = isMouseTrackingEnabled;
    if (!isMouseTrackingEnabled) {
        lookAtTarget.x = 0; lookAtTarget.y = 0;
        startLerpToCenter();
    }
};

// ── Core model helpers ────────────────────────────────────────────────────────
function getCoreModel() {
    return live2dModel?.internalModel?.coreModel ?? null;
}

function setCoreParam(paramId, value) {
    const core = getCoreModel();
    if (!core) return;
    const idx = core.getParameterIndex(paramId);
    if (idx >= 0) core.setParameterValueByIndex(idx, value);
}

// ── Library check ─────────────────────────────────────────────────────────────
function ensureLive2DLibraries() {
    return Boolean(window.Live2DCubismCore && window.PIXI && window.PIXI.live2d?.Live2DModel);
}

// ── Motion & Expression helpers ────────────────────────────────────────────────
function getMotionGroups() {
    const settings = live2dModel?.internalModel?.settings;
    return settings?.motions ? Object.keys(settings.motions) : [];
}

function getExpressionNames() {
    const expressions = live2dModel?.internalModel?.settings?.expressions || [];
    return expressions
        .map(e => e.Name || e.name || e.File || e.file)
        .filter(Boolean);
}

function findExpressionName(keywords) {
    const expressions = getExpressionNames();
    if (!expressions.length) return null;
    for (const kw of keywords) {
        const match = expressions.find(name => name.toLowerCase().includes(kw));
        if (match) return match;
    }
    return null;
}

function triggerExpressionByName(name) {
    if (!live2dModel || typeof live2dModel.expression !== 'function') return false;
    try {
        live2dModel.expression(name);
        return true;
    } catch (error) {
        const fallback = findExpressionName([name.toLowerCase()]);
        if (fallback && fallback !== name) {
            try { live2dModel.expression(fallback); return true; } catch (e) {
                console.error('Live2D expression fallback failed:', e);
            }
        }
        console.error('Live2D expression trigger failed:', error);
        return false;
    }
}

function startRandomMotionFromGroups(groups, priority = 3) {
    if (!live2dModel || !groups.length) return false;
    if (typeof live2dModel.motion === 'function') {
        const group = groups[Math.floor(Math.random() * groups.length)];
        try { live2dModel.motion(group, undefined, priority); return true; }
        catch (e) { console.error('Live2D motion trigger failed:', e); }
    }
    const mm = live2dModel?.internalModel?.motionManager;
    if (mm && typeof mm.startRandomMotion === 'function') {
        const group = groups[Math.floor(Math.random() * groups.length)];
        try { mm.startRandomMotion(group, priority); return true; }
        catch (e) { console.error('Live2D random motion fallback failed:', e); }
    }
    return false;
}

function startIdleMotion() {
    const groups = getMotionGroups();
    if (!groups.length) return;
    const idleGroups = groups.filter(g => /idle|home|main/i.test(g));
    startRandomMotionFromGroups(idleGroups.length ? idleGroups : groups, 1);
}

// ── Auto-Blink ────────────────────────────────────────────────────────────────
function startAutoBlink() {
    function doBlink() {
        const core = getCoreModel();
        if (!core) return;
        const idxL = core.getParameterIndex('ParamEyeLOpen');
        const idxR = core.getParameterIndex('ParamEyeROpen');
        if (idxL >= 0) core.setParameterValueByIndex(idxL, 0);
        if (idxR >= 0) core.setParameterValueByIndex(idxR, 0);
        setTimeout(() => {
            const c2 = getCoreModel();
            if (!c2) return;
            if (idxL >= 0) c2.setParameterValueByIndex(idxL, 1);
            if (idxR >= 0) c2.setParameterValueByIndex(idxR, 1);
        }, 120);
    }
    function scheduleNextBlink() {
        setTimeout(() => { doBlink(); scheduleNextBlink(); }, 3000 + Math.random() * 3000);
    }
    scheduleNextBlink();
}

// ── Wink ──────────────────────────────────────────────────────────────────────
const WINK_KEYWORDS = ['wink', '\u{1F609}', 'secret', 'joke', 'اغمزي', 'اغمز', 'غمزة', 'غمزي'];
function hasWinkKeyword(text) {
    const n = text.toLowerCase();
    return WINK_KEYWORDS.some(k => n.includes(k));
}
function doWink() {
    const core = getCoreModel();
    if (!core) return;
    const idxL = core.getParameterIndex('ParamEyeLOpen');
    if (idxL < 0) return;
    core.setParameterValueByIndex(idxL, 0);
    setTimeout(() => { const c2 = getCoreModel(); if (c2) c2.setParameterValueByIndex(idxL, 1); }, 400);
    triggerExpressionByName(findExpressionName(['happy', 'smile']) || 'happy');
}

// ── Expression sync with AI reply ─────────────────────────────────────────────
function syncExpressionWithReply(replyText) {
    const normalized = replyText.toLowerCase();
    const hasAny = words => words.some(w => normalized.includes(w));
    if (hasWinkKeyword(replyText)) { doWink(); return; }
    if (hasAny(['blush', 'shy']))  { triggerExpressionByName(findExpressionName(['blush', 'shy']) || 'look blush'); return; }
    if (hasAny(['smirk', 'giggle', 'smile', 'tease', 'happy'])) { triggerExpressionByName(findExpressionName(['happy', 'smile', 'smirk', 'giggle']) || 'happy'); return; }
    if (hasAny(['pout', 'angry', 'mad', 'glare'])) { triggerExpressionByName(findExpressionName(['angry', 'pout', 'mad']) || 'angry'); return; }
    if (hasAny(['sigh', 'sad', 'whimper']))         { triggerExpressionByName(findExpressionName(['sad', 'sigh', 'whimper']) || 'sad'); return; }
}

// ── Talking / Lip-sync ────────────────────────────────────────────────────────
function setEmberTalking(isTalking) {
    if (!live2dModel) return;
    if (!isTalking) {
        if (talkingIntervalId) { clearInterval(talkingIntervalId); talkingIntervalId = null; }
        // If real lip sync is available, stop it; otherwise close mouth manually
        if (window.EmberLipSync) {
            window.EmberLipSync.stop();
        } else {
            const core = getCoreModel();
            const mouthIdx = core?.getParameterIndex?.('ParamMouthOpenY');
            if (core && typeof mouthIdx === 'number' && mouthIdx >= 0)
                core.setParameterValueByIndex(mouthIdx, 0);
        }
        return;
    }
    if (window.EmberLipSync) {
        // Real frequency-based lip sync (started by chat.js when audio element is ready)
        window.EmberLipSync.start();
    } else {
        // Fallback: random mouth animation
        if (talkingIntervalId) clearInterval(talkingIntervalId);
        const core = getCoreModel();
        const mouthIdx = core?.getParameterIndex?.('ParamMouthOpenY');
        if (!core || typeof mouthIdx !== 'number' || mouthIdx < 0) return;
        talkingIntervalId = setInterval(() => {
            core.setParameterValueByIndex(mouthIdx, 0.2 + Math.random() * 0.75);
        }, 90);
    }
}

function triggerReplyAnimation(replyText) {
    if (!replyText) return;
    syncExpressionWithReply(replyText);
    setEmberTalking(true);
    const duration = Math.max(900, Math.min(2400, replyText.length * 20));
    setTimeout(() => setEmberTalking(false), duration);
}

// ── Outfit & Cloak ────────────────────────────────────────────────────────────
function setModelForm(formValue) {
    currentForm = formValue === '1' ? '1' : '0';
    localStorage.setItem(STORAGE_KEYS.form, currentForm);
    updateFormToggleButton();
    if (!live2dModel) return;
    darkOutfitActive = (currentForm === '1');
    if (outfitTickerFn && live2dApp) { live2dApp.ticker.remove(outfitTickerFn); outfitTickerFn = null; }
    if (darkOutfitActive) {
        setCoreParam('Param65', 10.0);
        outfitTickerFn = () => setCoreParam('Param65', 10.0);
        if (live2dApp) live2dApp.ticker.add(outfitTickerFn);
    } else {
        setCoreParam('Param65', 0.0);
    }
}

function toggleCloak() {
    cloakActive = !cloakActive;
    const btn = document.getElementById('cloak-toggle-btn');
    if (btn) btn.textContent = cloakActive ? '🔴 Remove Cloak' : '🌑 Equip Cloak';
    if (!live2dModel) return;
    setCoreParam('Param67', cloakActive ? 10.0 : 0.0);
}

// ── Layout ────────────────────────────────────────────────────────────────────
function layoutLive2DModel() {
    const canvas = document.getElementById('live2d-canvas');
    if (!live2dApp || !live2dModel || !canvas) return;
    const width  = canvas.clientWidth  || canvas.width;
    const height = canvas.clientHeight || canvas.height;
    if (!width || !height) return;
    live2dApp.renderer.resize(width, height);
    if (manualScale !== null) {
        live2dModel.anchor.set(0.5, 0.5);
        live2dModel.scale.set(manualScale);
        live2dModel.position.set(width * 0.5, height * 0.8);
        return;
    }
    const safeW = modelRawWidth  || live2dModel.width  || 1;
    const safeH = modelRawHeight || live2dModel.height || 1;
    live2dBaseScale = Math.min(width / safeW, height / safeH) * 1.85;
    live2dModel.anchor.set(0.5, 0.5);
    live2dModel.scale.set(live2dBaseScale);
    live2dModel.position.set(width * 0.5, (height * 0.72));
}

// ── Interactions ──────────────────────────────────────────────────────────────
function bindLive2DInteractions(canvas) {
    if (!live2dModel) return;
    live2dModel.interactive = false;
    live2dModel.cursor = 'default';
    live2dModel.autoInteract = false;
    if (live2dModel.internalModel) {
        live2dModel.internalModel.autoInteract = false;
        if (Array.isArray(live2dModel.internalModel.hitAreas)) live2dModel.internalModel.hitAreas.length = 0;
        if (typeof live2dModel.internalModel.tap === 'function') live2dModel.internalModel.tap = () => {};
    }

    canvas.addEventListener('pointerdown', e => {
        isDraggingModel = true;
        dragOffset.x = e.clientX - live2dModel.position.x;
        dragOffset.y = e.clientY - live2dModel.position.y;
    });

    canvas.addEventListener('pointermove', e => {
        if (!live2dModel) return;
        if (isDraggingModel) {
            live2dModel.position.set(e.clientX - dragOffset.x, e.clientY - dragOffset.y);
            return;
        }
        if (!isMouseTrackingEnabled) return;
        const rect = canvas.getBoundingClientRect();
        const nx = clamp(((e.clientX - rect.left) / rect.width)  * 2 - 1, -1, 1);
        const ny = clamp(((e.clientY - rect.top)  / rect.height) * 2 - 1, -1, 1);
        lookAtCurrent.x = nx; lookAtCurrent.y = ny;
        applyLookAt(nx, ny);
    });

    canvas.addEventListener('pointerup', () => { isDraggingModel = false; });
    canvas.addEventListener('pointerleave', () => {
        isDraggingModel = false;
        lookAtTarget.x = 0; lookAtTarget.y = 0;
        startLerpToCenter();
    });

    canvas.addEventListener('wheel', e => {
        e.preventDefault();
        const zoomFactor = e.deltaY < 0 ? 1.05 : 0.95;
        manualScale = (manualScale !== null ? manualScale : live2dModel.scale.x) * zoomFactor;
        manualScale = Math.max(0.01, Math.min(10.0, manualScale));
        live2dModel.scale.set(manualScale);
        const w = canvas.clientWidth || canvas.width;
        const h = canvas.clientHeight || canvas.height;
        live2dModel.position.set(w * 0.5, h * 0.8);
    }, { passive: false });
}

// ── Init ──────────────────────────────────────────────────────────────────────
async function initLive2D() {
    const canvas           = document.getElementById('live2d-canvas');
    const characterSpace   = document.getElementById('character-space');
    const placeholderTitle = document.querySelector('#character-space .character-title');
    const placeholderSub   = document.querySelector('#character-space .character-subtitle');

    if (!canvas) { console.error('Live2D canvas not found.'); return; }
    if (!ensureLive2DLibraries()) {
        console.error('Live2D libraries failed to load.');
        if (placeholderTitle) placeholderTitle.textContent = 'Error loading model.';
        if (placeholderSub)   placeholderSub.textContent   = 'Check console.';
        return;
    }

    live2dApp = new PIXI.Application({
        view: canvas, resizeTo: canvas.parentElement,
        autoStart: true, antialias: true, backgroundAlpha: 0,
    });

    try {
        live2dModel = await PIXI.live2d.Live2DModel.from('/static/model/ebrah/ebrah.model3.json');
        console.log('Expressions:', live2dModel?.internalModel?.motionManager?.expressionManager?.expressions?.map(e => e.name) || []);
        const bounds = live2dModel.getLocalBounds();
        modelRawWidth  = Math.max(1, bounds.width  || live2dModel.width  || 1);
        modelRawHeight = Math.max(1, bounds.height || live2dModel.height || 1);
        live2dApp.stage.addChild(live2dModel);
        layoutLive2DModel();
        bindLive2DInteractions(canvas);
        if (typeof window.setMouseTrackingEnabled === 'function') {
            window.setMouseTrackingEnabled(isMouseTrackingEnabled);
        }
        setModelForm(localStorage.getItem(STORAGE_KEYS.form) || '0');
        startIdleMotion();
        startAutoBlink();
        if (characterSpace) characterSpace.classList.add('model-ready');
        window.addEventListener('resize', layoutLive2DModel);
    } catch (error) {
        console.error('Live2D Load Error:', error);
        if (placeholderTitle) placeholderTitle.textContent = 'Error loading model.';
        if (placeholderSub)   placeholderSub.textContent   = 'Check console.';
    }
}
