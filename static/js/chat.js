// ─────────────────────────────────────────────────────────────────────────────
// chat.js — API calls: sendMessage, sendAudio, sendVisionPrompt
// ─────────────────────────────────────────────────────────────────────────────

// ── State ─────────────────────────────────────────────────────────────────────
let isSendingMessage = false;
let isSendingAudio   = false;

// ── Screen trigger detection ───────────────────────────────────────────────────
function hasScreenTrigger(text) {
    const n = text.toLowerCase();
    return ['look at my screen', 'see my screen', 'read my screen', 'شاشتي'].some(t => n.includes(t));
}

// ── Send text message ─────────────────────────────────────────────────────────
async function sendMessage(frontendImage = null, visionMode = null) {
    if (isSendingMessage) return;
    const input = document.getElementById('user-input');
    const msg = input.value.trim();
    if (!msg) return;

    if (!frontendImage && !visionMode && hasScreenTrigger(msg)) {
        try {
            frontendImage = await captureScreenFrame();
            visionMode = 'screen';
        } catch (e) {
            console.error(e);
            addMessage('ember', 'System', 'Use the screen button or approve the browser screen picker first.');
            return;
        }
    }

    addMessage('user', 'You', msg);
    if (hasWinkKeyword(msg)) doWink();

    input.value = '';
    autoResizeTextarea();

    const ttsProvider    = document.getElementById('tts-provider').value;
    const visionProvider = document.getElementById('vision-provider').value;
    const hasVision      = Boolean(frontendImage || visionMode);
    const emberMeta      = hasVision ? { ttsProvider, visionProvider } : { ttsProvider };
    const emberMessage   = addMessage('ember', 'Ember', '', emberMeta);
    isSendingMessage = true;

    try {
        const res = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: msg,
                tts_provider: ttsProvider,
                vision_provider: visionProvider,
                frontend_image: frontendImage,
                vision_mode: visionMode,
            }),
        });
        if (!res.ok) throw new Error(`/ask failed: ${res.status}`);
        const payload = await res.json();
        const replyText = payload.reply || '...';
        setMessageText(emberMessage, replyText);
        playEmberAudio(payload.audio_base64, payload.audio_mime, replyText);
    } catch (e) {
        console.error(e);
        setMessageText(emberMessage, 'Message failed. Try again.');
    } finally {
        isSendingMessage = false;
        setVisionLoading(activeVisionButton, false);
    }
}

// ── Send voice audio ──────────────────────────────────────────────────────────
async function sendAudio(blob, frontendImage = null) {
    if (isSendingAudio) return;
    isSendingAudio = true;

    const ttsProvider    = document.getElementById('tts-provider').value;
    const visionProvider = document.getElementById('vision-provider').value;
    const emberMeta      = frontendImage ? { ttsProvider, visionProvider } : { ttsProvider };
    const fd = new FormData();
    fd.append('file', blob, blob.type.includes('wav') ? 'rec.wav' : 'rec.webm');
    fd.append('tts_provider', ttsProvider);
    fd.append('vision_provider', visionProvider);
    if (frontendImage) fd.append('frontend_image', frontendImage);

    const userMessage  = addMessage('user', 'You', '🎤 ...');
    const emberMessage = addMessage('ember', 'Ember', '', emberMeta);

    try {
        const res = await fetch('/transcribe', { method: 'POST', body: fd });
        if (!res.ok) throw new Error(`/transcribe failed: ${res.status}`);
        const payload = await res.json();
        setMessageText(userMessage, payload.user_text || '...');
        const replyText = payload.reply || '...';
        setMessageText(emberMessage, replyText);
        playEmberAudio(payload.audio_base64, payload.audio_mime, replyText);
    } catch (e) {
        console.error(e);
        setMessageText(emberMessage, 'Voice request failed. Try again.');
    } finally {
        isSendingAudio = false;
        if (isHandsFree) setTimeout(startAutoRecording, 500);
    }
}

// ── Send vision prompt ────────────────────────────────────────────────────────
async function sendVisionPrompt(text, button) {
    if (isSendingMessage) return;
    setVisionLoading(button, true);
    const isScreen  = text.toLowerCase() === 'look at my screen';
    const visionMode = isScreen ? 'screen' : 'camera';
    try {
        const input = document.getElementById('user-input');
        const customText = input.value.trim();
        input.value = customText || text;
        autoResizeTextarea();
        const frontendImage = isScreen ? await captureScreenFrame() : null;
        await sendMessage(frontendImage, visionMode);
    } catch (e) {
        console.error(e);
        addMessage('ember', 'System', isScreen
            ? 'Screen selection was cancelled or failed.'
            : 'Vision request failed. Try again.');
        setVisionLoading(button, false);
    }
}
