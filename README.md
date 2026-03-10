# 🌟 Ember — A Multimodal Sassy & Playful AI Waifu (Web UI) 🌟

A flirty, teasing, and highly interactive AI assistant that runs locally with a custom web interface. Ember combines a smart AI brain, dual vision modes, real-time voice, and an animated Live2D avatar — all in your browser.

> [!IMPORTANT]
> **This repo does NOT include the Live2D model or voice file** — these are private/paid assets.
> You must provide your own before running the project:
> - 🎭 **Live2D model** → place it in `static/model/your-model/`
> - 🎙️ **Voice reference** → place a `.wav` file in `static/audio/` and set its path in `.env`

---

## ✨ Key Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **Brain (DeepSeek)** | Super fast and smart responses, fine-tuned to have a playful and slightly mischievous personality |
| 👁️ | **Eyes (Dual Vision)** | She can literally *see* your screen or webcam! Toggle between **Local LLaVA** (private & uncensored) or **OpenAI GPT-4o-mini** (fast & accurate) |
| 🔊 | **Voice (Dual TTS)** | **ElevenLabs** for ultra-realistic cloud audio, or **Local GPT-SoVITS** (100% free & private). Action tags like `*winks*` are auto-filtered for maximum immersion |
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
├── data/                   ← Auto-created at runtime (gitignored)
├── .env                    ← Your API keys (gitignored)
├── requirements.txt
└── start_ember.bat         ← One-click launch (Windows)
```

---

## ⚙️ Full Setup Guide

### Step 1 — Clone & create virtual environment

```bash
git clone https://github.com/Ebrah20/ember-ai.git
cd ember-ai
python -m venv .venv
```

Activate it:
```powershell
# Windows
.venv\Scripts\activate
```
```bash
# macOS / Linux
source .venv/bin/activate
```
> ✅ You'll see `(.venv)` in your terminal. **Always activate it before running the project.**

---

### Step 2 — Install dependencies

```bash
pip install -r requirements.txt
```

---

### Step 3 — Add your Live2D model ⚠️

1. Place your model folder inside `static/model/`
   ```
   static/model/YOUR-MODEL/
   ├── YOUR-MODEL.model3.json
   ├── textures/
   └── ...
   ```

2. Open `static/js/live2d.js` and find this line (~line 260):
   ```js
   live2dModel = await PIXI.live2d.Live2DModel.from('/static/model/ebrah/ebrah.model3.json');
   ```
   Change it to match your model path:
   ```js
   live2dModel = await PIXI.live2d.Live2DModel.from('/static/model/YOUR-MODEL/YOUR-MODEL.model3.json');
   ```

---

### Step 4 — Setup GPT-SoVITS (Local TTS) ⚠️

> Skip this step if you plan to use **ElevenLabs** cloud TTS only.

1. Download GPT-SoVITS from the official repo:
   👉 **[github.com/RVC-Boss/GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS)**

2. Follow the installation instructions in that repo and launch the API server (default port: `9880`)

3. Place your voice reference `.wav` file in `static/audio/`

4. Set the path in `.env` (see Step 5)

---

### Step 5 — Configure `.env`

Create a file named `.env` in the project root:

```env
# Required
DEEPSEEK_API_KEY=sk-...

# Optional — for screen/camera vision
OPENAI_API_KEY=sk-...

# Optional — choose ElevenLabs OR local SoVITS
ELEVENLABS_API_KEY=...
ELEVENLABS_VOICE_ID=...

# Local TTS (SoVITS) settings
TTS_SERVER_URL=http://127.0.0.1:5050/generate_audio
SOVITS_API_URL=http://127.0.0.1:9880/tts
SOVITS_REF_AUDIO_PATH=static/audio/your-voice.wav
```

---

### Step 6 — Run

**Windows (one click)**
```
start_ember.bat
```

**Manual (two terminals)**
```bash
# Terminal 1 — Local TTS proxy (skip if using ElevenLabs)
python tts_server.py

# Terminal 2 — Main app
python app.py
```

Open **[http://localhost:5000](http://localhost:5000)** in your browser. 🎉
