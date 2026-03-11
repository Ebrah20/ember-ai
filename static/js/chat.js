// ─────────────────────────────────────────────────────────────────────────────
// chat.js — API calls: sendMessage (streaming), sendAudio, sendVisionPrompt
// ─────────────────────────────────────────────────────────────────────────────

// ── State ─────────────────────────────────────────────────────────────────────
let isSendingMessage = false;
let isSendingAudio   = false;

// ── Audio chunk queue ─────────────────────────────────────────────────────────
// Ensures audio chunks play sequentially without overlap,
// even when TTS for chunk N+1 arrives before chunk N finishes playing.
const _audioQueue   = [];
let   _audioPlaying = false;

function _enqueueAudio(b64, mime, text) {
    _audioQueue.push({ b64, mime, text });
    if (!_audioPlaying) _drainAudioQueue();
}

function _drainAudioQueue() {
    if (_audioQueue.length === 0) { _audioPlaying = false; return; }
    _audioPlaying = true;
    const { b64, mime, text } = _audioQueue.shift();
    // playEmberAudio is defined in audio.js; we hook its onended to drain the queue
    _playAndContinue(b64, mime, text);
}

function _playAndContinue(b64, mime, text) {
    if (!b64) { _drainAudioQueue(); return; }
    try {
        const bytes  = atob(b64);
        const buffer = new Uint8Array(bytes.length);
        for (let i = 0; i < bytes.length; i++) buffer[i] = bytes.charCodeAt(i);
        const blob   = new Blob([buffer], { type: mime || 'audio/wav' });
        const url    = URL.createObjectURL(blob);
        const audio  = new Audio(url);

        // Sync lip anim if live2d available
        if (typeof setLipSync === 'function') setLipSync(true);

        audio.onended = () => {
            URL.revokeObjectURL(url);
            if (typeof setLipSync === 'function') setLipSync(false);
            _drainAudioQueue();
        };
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            if (typeof setLipSync === 'function') setLipSync(false);
            _drainAudioQueue();
        };
        audio.play().catch(() => _drainAudioQueue());
    } catch (e) {
        console.error('[AudioQueue] play error:', e);
        _drainAudioQueue();
    }
}

// ── Screen trigger detection ───────────────────────────────────────────────────
function hasScreenTrigger(text) {
    const n = text.toLowerCase();
    return ['look at my screen', 'see my screen', 'read my screen', 'شاشتي'].some(t => n.includes(t));
}

// ── Send text message (streaming) ─────────────────────────────────────────────
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

    let fullText = '';

    try {
        const res = await fetch('/ask_stream', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message:          msg,
                tts_provider:     ttsProvider,
                vision_provider:  visionProvider,
                frontend_image:   frontendImage,
                vision_mode:      visionMode,
            }),
        });

        if (!res.ok) throw new Error(`/ask_stream failed: ${res.status}`);

        const reader  = res.body.getReader();
        const decoder = new TextDecoder();
        let   buf     = '';

        // Stream reading loop
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });

            // SSE lines are separated by double-newline
            const parts = buf.split('\n\n');
            buf = parts.pop(); // keep incomplete tail

            for (const part of parts) {
                const line = part.trim();
                if (!line.startsWith('data:')) continue;
                try {
                    const event = JSON.parse(line.slice(5).trim());

                    if (event.type === 'chunk') {
                        fullText += event.text;
                        setMessageText(emberMessage, fullText);
                        // Enqueue audio chunk — plays as soon as previous finishes
                        if (event.audio_base64) {
                            _enqueueAudio(event.audio_base64, event.audio_mime, event.text);
                        }
                        // React to wink keywords in reply
                        if (typeof hasWinkKeyword === 'function' && hasWinkKeyword(event.text)) doWink();
                    }
                    else if (event.type === 'done') {
                        setMessageText(emberMessage, event.full_text || fullText);
                    }
                    else if (event.type === 'error') {
                        setMessageText(emberMessage, event.message || 'Something went wrong.');
                    }
                } catch { /* ignore parse errors */ }
            }
        }
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

// Expose playEmberAudio for gamer.js (delegates to the queue)
function playEmberAudio(b64, mime, text) {
    _enqueueAudio(b64, mime, text || '');
}
