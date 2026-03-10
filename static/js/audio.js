// ─────────────────────────────────────────────────────────────────────────────
// audio.js — Microphone recording, silence detection, TTS playback, Hands-Free
// ─────────────────────────────────────────────────────────────────────────────

// ── State ─────────────────────────────────────────────────────────────────────
let isHandsFree = false;
let mediaRecorder;
let mediaStream;
let audioChunks = [];
let silenceTimer;
let audioContext, analyser;
let isRecording = false;
let animationFrameId;
let currentEmberAudio = null;

// ── Screen capture ────────────────────────────────────────────────────────────
async function captureScreenFrame() {
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    try {
        const video = document.createElement('video');
        video.srcObject = stream;
        video.muted = true;
        await video.play();

        const canvas = document.getElementById('screen-capture-canvas');
        const track = stream.getVideoTracks()[0];
        const settings = track.getSettings();
        canvas.width  = settings.width  || video.videoWidth  || 1280;
        canvas.height = settings.height || video.videoHeight || 720;

        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        return canvas.toDataURL('image/jpeg', 0.92);
    } finally {
        stream.getTracks().forEach(t => t.stop());
    }
}

// ── Resource cleanup ──────────────────────────────────────────────────────────
function cleanupAudioResources() {
    isRecording = false;
    clearTimeout(silenceTimer);
    if (animationFrameId) { cancelAnimationFrame(animationFrameId); animationFrameId = null; }
    if (mediaStream)      { mediaStream.getTracks().forEach(t => t.stop()); mediaStream = null; }
    if (audioContext)     { audioContext.close(); audioContext = null; }
    analyser = null;
}

// ── Silence detection ──────────────────────────────────────────────────────────
function detectSilence() {
    if (!isRecording || !analyser) return;
    const data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteFrequencyData(data);
    const vol = data.reduce((a, b) => a + b) / data.length;
    if (vol > 10) {
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
            if (isRecording && mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }, 1500);
    }
    animationFrameId = requestAnimationFrame(detectSilence);
}

// ── Auto recording (Hands-Free) ───────────────────────────────────────────────
async function startAutoRecording() {
    if (!isHandsFree || isRecording) return;
    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        mediaStream = stream;
        audioContext = new (window.AudioContext || window.webkitAudioContext)();
        analyser = audioContext.createAnalyser();
        const source = audioContext.createMediaStreamSource(stream);
        source.connect(analyser);

        const preferredMime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
            ? 'audio/webm;codecs=opus' : '';
        mediaRecorder = preferredMime
            ? new MediaRecorder(stream, { mimeType: preferredMime })
            : new MediaRecorder(stream);
        audioChunks = [];
        mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
        mediaRecorder.onstop = async () => {
            isRecording = false;
            cleanupAudioResources();
            if (!isHandsFree) return;
            const blobType = mediaRecorder?.mimeType || 'audio/webm';
            const blob = new Blob(audioChunks, { type: blobType });
            if (blob.size > 3000) await sendAudio(blob);
            else if (isHandsFree) startAutoRecording();
        };
        mediaRecorder.start();
        isRecording = true;
        clearTimeout(silenceTimer);
        silenceTimer = setTimeout(() => {
            if (isRecording && mediaRecorder && mediaRecorder.state !== 'inactive') {
                mediaRecorder.stop();
            }
        }, 4000);
        detectSilence();
    } catch (e) {
        console.error(e);
        isHandsFree = false;
        document.getElementById('auto-btn').classList.remove('active');
        document.getElementById('auto-btn').innerText = '🔁 Start Hands-Free';
        cleanupAudioResources();
    }
}

async function toggleHandsFree() {
    const btn = document.getElementById('auto-btn');
    if (!isHandsFree) {
        isHandsFree = true;
        btn.classList.add('active');
        btn.innerText = '⏹️ Stop';
        startAutoRecording();
    } else {
        isHandsFree = false;
        btn.classList.remove('active');
        btn.innerText = '🔁 Start Hands-Free';
        if (mediaRecorder && mediaRecorder.state !== 'inactive') mediaRecorder.stop();
        else cleanupAudioResources();
    }
}

// ── TTS Playback ──────────────────────────────────────────────────────────────
function playEmberAudio(audioBase64, audioMime, replyText) {
    if (!audioBase64) {
        if (typeof triggerReplyAnimation === 'function') triggerReplyAnimation(replyText || '');
        return;
    }
    if (currentEmberAudio) { currentEmberAudio.pause(); currentEmberAudio = null; }
    if (typeof syncExpressionWithReply === 'function') syncExpressionWithReply(replyText || '');

    const mime  = audioMime || 'audio/wav';
    const audio = new Audio(`data:${mime};base64,${audioBase64}`);
    currentEmberAudio = audio;

    const onStop = () => {
        if (typeof setEmberTalking === 'function') setEmberTalking(false);
        if (currentEmberAudio === audio) currentEmberAudio = null;
    };
    audio.onplay  = () => { if (typeof setEmberTalking === 'function') setEmberTalking(true); };
    audio.onended = onStop;
    audio.onerror = onStop;
    audio.play().catch(err => { console.error('Audio playback failed:', err); onStop(); });
}
