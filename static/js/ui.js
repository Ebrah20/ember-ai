// ─────────────────────────────────────────────────────────────────────────────
// ui.js — DOM helpers, chat messages, vision button state
// ─────────────────────────────────────────────────────────────────────────────

// ── Global UI State ───────────────────────────────────────────────────────────
let activeVisionButton = null;

// ── Chat Messages ─────────────────────────────────────────────────────────────
function formatProviderLabel(type, value) {
    if (type === 'tts') return value === 'elevenlabs' ? 'TTS: ElevenLabs' : 'TTS: Local';
    return value === 'local' ? 'Vision: Local' : 'Vision: OpenAI';
}

function setMessageText(messageNode, text) {
    if (messageNode && messageNode._textNode) {
        messageNode._textNode.textContent = text;
    }
}

function addMessage(cssClass, speaker, text, meta = {}) {
    const box = document.getElementById('chat-box');
    const msg = document.createElement('div');
    msg.className = `message ${cssClass}`;

    const label = document.createElement('div');
    label.className = 'message-label';
    const speakerNode = document.createElement('span');
    speakerNode.textContent = `${speaker}:`;
    label.appendChild(speakerNode);

    if (cssClass === 'ember' && meta.ttsProvider) {
        const badge = document.createElement('span');
        badge.className = 'provider-badge tts';
        badge.textContent = formatProviderLabel('tts', meta.ttsProvider);
        label.appendChild(badge);
    }
    if (cssClass === 'ember' && meta.visionProvider) {
        const badge = document.createElement('span');
        badge.className = 'provider-badge vision';
        badge.textContent = formatProviderLabel('vision', meta.visionProvider);
        label.appendChild(badge);
    }

    const textNode = document.createElement('div');
    textNode.className = 'message-text';
    textNode.textContent = text;

    msg.appendChild(label);
    msg.appendChild(textNode);
    msg._textNode = textNode;
    box.appendChild(msg);
    box.scrollTop = box.scrollHeight;
    return msg;
}

function updateChat(user, reply) {
    const box = document.getElementById('chat-box');
    if (user) {
        const last = box.lastElementChild;
        if (last && last.classList.contains('user')) setMessageText(last, user);
        else addMessage('user', 'You', user);
    }
    addMessage('ember', 'Ember', reply);
}

// ── Textarea ──────────────────────────────────────────────────────────────────
function autoResizeTextarea() {
    const input = document.getElementById('user-input');
    input.style.height = 'auto';
    input.style.height = `${Math.min(input.scrollHeight, 220)}px`;
}

// ── Vision button loading state ────────────────────────────────────────────────
function setVisionLoading(button, isLoading) {
    if (!button) return;
    if (isLoading) {
        button.classList.add('loading');
        button.disabled = true;
        if (!button.dataset.originalText) button.dataset.originalText = button.textContent;
        button.innerHTML = '<span class="vision-btn-content"><span class="vision-spinner"></span><span>Observing...</span></span>';
        activeVisionButton = button;
    } else {
        button.classList.remove('loading');
        button.disabled = false;
        button.textContent = button.dataset.originalText || button.textContent;
        if (activeVisionButton === button) activeVisionButton = null;
    }
}

// ── Outfit toggle button label ─────────────────────────────────────────────────
function updateFormToggleButton() {
    const btn = document.getElementById('form-toggle-btn');
    if (!btn) return;
    btn.textContent = currentForm === '1' ? '👗 Switch To Red Form' : '🖤 Switch To Dark Form';
}
