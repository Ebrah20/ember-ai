/**
 * gamer.js — Gamer Mode frontend module for Ember AI.
 *
 * Responsibilities:
 *  - Toggle button wiring → POST /api/gamer_mode
 *  - SSE connection to /api/gamer_stream
 *  - On SSE event: play audio + display Ember's comment in chat
 */

(function () {
  "use strict";

  let gamerActive = false;
  let sseSource = null;

  // ── Toggle button ──────────────────────────────────────────────────────────
  function initGamerMode() {
    const btn = document.getElementById("gamer-mode-btn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
      gamerActive = !gamerActive;
      btn.textContent = gamerActive ? "⚔️ Gamer Mode: ON" : "⚔️ Gamer Mode: OFF";
      btn.style.background = gamerActive
        ? "linear-gradient(135deg, #ff6b35, #e63946)"
        : "";

      try {
        await fetch("/api/gamer_mode", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ active: gamerActive }),
        });
      } catch (err) {
        console.warn("[GamerMode] toggle failed:", err);
      }

      if (gamerActive) {
        connectSSE();
      } else {
        disconnectSSE();
      }
    });
  }

  // ── SSE connection ─────────────────────────────────────────────────────────
  function connectSSE() {
    if (sseSource) return; // already connected
    sseSource = new EventSource("/api/gamer_stream");

    sseSource.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.ping) return; // heartbeat

        const { text, audio_base64, audio_mime } = data;

        // Show Ember's comment in chat
        if (typeof addMessage === "function" && text) {
          addMessage("ember", "Ember 🎮", text);
        }

        // Play audio
        if (typeof playEmberAudio === "function" && audio_base64) {
          playEmberAudio(audio_base64, audio_mime || "audio/wav", text || "");
        }
      } catch (e) {
        console.warn("[GamerMode] SSE parse error:", e);
      }
    };

    sseSource.onerror = () => {
      console.warn("[GamerMode] SSE error — will retry automatically.");
    };

    console.log("[GamerMode] SSE connected → /api/gamer_stream");
  }

  function disconnectSSE() {
    if (sseSource) {
      sseSource.close();
      sseSource = null;
      console.log("[GamerMode] SSE disconnected.");
    }
  }

  // ── Init ───────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", initGamerMode);
})();
