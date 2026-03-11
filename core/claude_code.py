"""
core/claude_code.py — Claude Code CLI integration for Ember AI.

Trigger:  user message starts with `!code` OR `!كود`
Example:  "!code write a Python function to sort a list"
          "!كود اكتب لي سكريبت يحول PDF لـ text"

How:
  1. detect_code_command() checks if input is a code request
  2. run_claude_code() calls the `claude` CLI via subprocess
  3. Returns a summary for Ember to speak + full output for display
"""

import re
import subprocess
import shlex

# ── Trigger detection ─────────────────────────────────────────────────────────
_CODE_PREFIXES = ("!code", "!كود", "!برمج", "!اكواد")


def detect_code_command(user_input: str) -> tuple[bool, str]:
    """
    Returns (is_code_command, cleaned_prompt).
    If True, cleaned_prompt is the coding task without the prefix.
    """
    stripped = user_input.strip()
    for prefix in _CODE_PREFIXES:
        if stripped.lower().startswith(prefix):
            prompt = stripped[len(prefix):].strip()
            return True, prompt
    return False, user_input


# ── Claude CLI execution ───────────────────────────────────────────────────────
def run_claude_code(prompt: str, timeout: int = 60) -> tuple[str, str]:
    """
    Run `claude -p <prompt>` and return (spoken_summary, full_output).
    spoken_summary is short enough for TTS.
    full_output is the complete CLI response for display.
    """
    if not prompt.strip():
        return "Please give me a coding task after the !code command.", ""

    try:
        result = subprocess.run(
            ["claude", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            encoding="utf-8",
            errors="replace",
        )
        output = (result.stdout or "").strip()
        errors = (result.stderr or "").strip()

        if result.returncode != 0 and not output:
            msg = errors or "Claude returned an error with no output."
            return f"Claude had an issue: {msg[:200]}", msg

        if not output:
            return "Claude returned an empty response.", ""

        # Build a short spoken summary (first 2 sentences or 200 chars)
        summary = _make_summary(output)
        return summary, output

    except FileNotFoundError:
        return (
            "The Claude CLI is not installed. Please run: npm install -g @anthropic-ai/claude-code",
            "",
        )
    except subprocess.TimeoutExpired:
        return "That took too long — Claude timed out. Try a simpler prompt.", ""
    except Exception as e:
        return f"Unexpected error running Claude: {e}", ""


def _make_summary(text: str) -> str:
    """Extract a short TTS-friendly summary from long Claude output."""
    # Strip markdown code blocks for the summary
    clean = re.sub(r"```.*?```", "[code block]", text, flags=re.DOTALL)
    clean = re.sub(r"`[^`]+`", lambda m: m.group().strip("`"), clean)
    clean = clean.strip()

    # Take first 2 sentences max, cap at 300 chars
    sentences = re.split(r"(?<=[.!?])\s+", clean)
    summary   = " ".join(sentences[:2])
    if len(summary) > 300:
        summary = summary[:300].rsplit(" ", 1)[0] + "..."
    return summary or clean[:200]
