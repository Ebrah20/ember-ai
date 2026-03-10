# 🌟 Ember — A Multimodal Sassy & Playful AI Waifu (Web UI) 🌟

A flirty, teasing, and highly interactive AI assistant that runs locally with a custom web interface. Ember combines a smart AI brain, dual vision modes, real-time voice, and an animated Live2D avatar — all in your browser.

> [!IMPORTANT]
> **This repo does NOT include the Live2D model or voice file** — these are private/paid assets.
> You must provide your own:
> - **Live2D model** → place it in `static/model/your-model/`
> - **Voice reference** → place a `.wav` file in `static/audio/` and update `.env`

---

## ✨ Key Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **Brain (DeepSeek)** | Super fast and smart responses, fine-tuned to have a playful and slightly mischievous personality |
| 👁️ | **Eyes (Dual Vision)** | She can literally *see* your screen or webcam! Toggle between **Local LLaVA** (private & uncensored) or **OpenAI GPT-4o-mini** (fast & accurate) |
| 🔊 | **Voice (Dual TTS)** | Seamless voice interactions — **ElevenLabs** for ultra-realistic audio, or **Local GPT-SoVITS** (100% free & private). Action tags like `*winks*` are auto-filtered for maximum immersion |
| 👂 | **Ears (Faster-Whisper)** | Local speech-to-text for hands-free voice conversations |
| 🧠 | **Memory (ChromaDB)** | She remembers past conversations and inside jokes |
| 🎭 | **Avatar (Live2D + PixiJS)** | Not a static model! Custom parameter injection lets her swap outfits without breaking facial expressions. Her text is parsed in real-time — type 😉 and she actually winks. Custom lerp mouse-tracking for buttery-smooth eye contact |

---

## 🛠️ Tech Stack

| Role | Technology |
|------|-----------|
| **LLM** | DeepSeek API |
| **Memory** | ChromaDB |
| **VLM** | Ollama (LLaVA), OpenAI API |
| **TTS** | ElevenLabs, GPT-SoVITS |
| **STT** | Faster-Whisper |
| **Frontend / UI** | Vanilla JS, PixiJS, Live2D Cubism SDK |

---

## 🗂️ Project Structure

```
Ember_Project/
├── app.py                  ← Flask entry point
├── config.py               ← All config, API clients, constants
├── tts_server.py           ← SoVITS TTS microservice proxy
├── core/
│   ├── brain.py            ← AI chat, TTS, vision logic
│   └── memory.py           ← JSON + ChromaDB memory
├── routes/
│   └── api.py              ← Flask HTTP routes (Blueprint)
├── static/
│   ├── audio/              ← ⚠️ Add your voice .wav here (not included)
│   ├── css/style.css
│   ├── js/                 ← ui, audio, live2d, chat, app modules
│   └── model/              ← ⚠️ Add your Live2D model here (not included)
├── templates/index.html
├── data/                   ← Runtime data (gitignored)
├── .env                    ← API keys (gitignored)
├── requirements.txt
└── start_ember.bat         ← One-click launch (Windows)
```

---

## ⚙️ Setup

### 1. Create & activate virtual environment
```bash
python -m venv .venv
```
```powershell
# Windows
.venv\Scripts\activate
```
```bash
# macOS / Linux
source .venv/bin/activate
```
> You'll see `(.venv)` in your terminal — always activate it before running the project.

---

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

---

### 3. Add your assets ⚠️

**Live2D Model:**
- Place your model folder inside `static/model/`
- Update the model path in `static/js/live2d.js`:
```js
// Find this line and change the path to your model:
live2dModel = await PIXI.live2d.Live2DModel.from('/static/model/YOUR-MODEL/YOUR-MODEL.model3.json');
```

**Voice Reference (for GPT-SoVITS):**
- Place your `.wav` reference audio in `static/audio/`
- Update `SOVITS_REF_AUDIO_PATH` in `.env`

---

### 4. Setup GPT-SoVITS v3 (Local TTS)

1. Download **[GPT-SoVITS-v3lora-20250228](https://github.com/RVC-Boss/GPT-SoVITS/releases)**
2. Launch the API server (default port `9880`)
3. Configure `.env`:
```env
SOVITS_API_URL=http://127.0.0.1:9880/tts
SOVITS_REF_AUDIO_PATH=static/audio/your-voice.wav
```

---

### 5. Configure `.env`
```env
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...              # Optional, for vision
ELEVENLABS_API_KEY=...             # Optional, for cloud TTS
ELEVENLABS_VOICE_ID=...
TTS_SERVER_URL=http://127.0.0.1:5050/generate_audio
SOVITS_API_URL=http://127.0.0.1:9880/tts
SOVITS_REF_AUDIO_PATH=static/audio/your-voice.wav
```

---

### 6. Run

**Windows (one click)**
```
start_ember.bat
```

**Manual**
```bash
# Terminal 1 — TTS proxy (if using local SoVITS)
python tts_server.py

# Terminal 2 — Main app
python app.py
```

Open **http://localhost:5000** in your browser.

---

## 🌐 Share via Ngrok

```bash
ngrok http 5000 --host-header="localhost:5000"
```

All API calls use relative paths — zero configuration changes needed.
