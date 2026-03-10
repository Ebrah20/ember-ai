# 🌟 Ember — A Multimodal Sassy & Playful AI Waifu (Web UI) 🌟

A flirty, teasing, and highly interactive AI assistant that runs locally with a custom web interface. Ember combines a smart AI brain, dual vision modes, real-time voice, and an animated Live2D avatar — all in your browser.

---

## ✨ Key Features

| | Feature | Description |
|---|---------|-------------|
| 🧠 | **Brain (DeepSeek)** | Super fast and smart responses, fine-tuned to have a playful and slightly mischievous personality |
| 👁️ | **Eyes (Dual Vision)** | She can literally *see* your screen or webcam! Toggle between **Local LLaVA** (private & uncensored) or **OpenAI GPT-4o-mini** (fast & accurate) |
| 🔊 | **Voice (Dual TTS)** | Seamless voice interactions — **ElevenLabs** for ultra-realistic audio, or **Local GPT-SoVITS** (100% free & private). Action tags like `*winks*` are auto-filtered for maximum immersion |
| 👂 | **Ears (Faster-Whisper)** | Local speech-to-text for hands-free voice conversations |
| 🧠 | **Memory (ChromaDB)** | She remembers past conversations and inside jokes |
| 🎭 | **Avatar (Live2D + PixiJS)** | Not a static model! Custom parameter injection lets her swap outfits (Dark Dress / Cloak) without breaking facial expressions. Her text is parsed in real-time — tell a joke or type 😉 and she actually winks. Plus a custom lerp mouse-tracking system for buttery-smooth eye contact |

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
│   ├── audio/ember.wav     ← SoVITS reference voice
│   ├── css/style.css
│   ├── js/main.js
│   └── model/ebrah/        ← Live2D model files
├── templates/index.html
├── data/                   ← Runtime data (gitignored)
│   ├── memory.json
│   ├── chroma_db/
│   └── vision_captures/
├── .env                    ← API keys (gitignored)
├── requirements.txt
└── start_ember.bat         ← One-click launch (Windows)
```

---

## ⚙️ Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure `.env`
```env
DEEPSEEK_API_KEY=sk-...
OPENAI_API_KEY=sk-...              # Optional, for vision
ELEVENLABS_API_KEY=...             # Optional, for cloud TTS
ELEVENLABS_VOICE_ID=...
TTS_SERVER_URL=http://127.0.0.1:5050/generate_audio
SOVITS_API_URL=http://127.0.0.1:9880/tts
SOVITS_REF_AUDIO_PATH=static/audio/ember.wav
```

### 3. Run

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
