"""
core/memory.py — JSON + ChromaDB memory operations.
"""

import os
import json
import time
import hashlib

from config import (
    MEMORY_FILE, MAX_MEMORY_ITEMS, SYSTEM_PROMPT,
    memory_collection, memory_lock, conversation_lock,
)


def load_memory() -> list:
    with memory_lock:
        if os.path.exists(MEMORY_FILE):
            try:
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, list):
                        return data
            except (OSError, json.JSONDecodeError) as e:
                print(f"Memory load warning: {e}")
    return [{"role": "system", "content": SYSTEM_PROMPT}]


def save_memory(history: list) -> None:
    trimmed = [history[0]] + history[-20:] if len(history) > 21 else history
    tmp_path = f"{MEMORY_FILE}.tmp"
    with memory_lock:
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(trimmed, f, ensure_ascii=False, indent=4)
        os.replace(tmp_path, MEMORY_FILE)


def query_long_term(text: str) -> str:
    """Return recalled memories as a formatted string, or empty string."""
    if memory_collection is None:
        return ""
    try:
        results = memory_collection.query(query_texts=[text], n_results=3)
        if results.get("documents") and results["documents"][0]:
            recalled = "\n".join(results["documents"][0])
            return f"\n\nRecall these past memories:\n{recalled}"
    except Exception as e:
        print(f"Memory query warning: {e}")
    return ""


def store_exchange(user_input: str, full_reply: str) -> None:
    """Store a user↔Ember exchange in ChromaDB and save JSON history."""
    signature = hashlib.sha1(f"{user_input}\n{full_reply}".encode()).hexdigest()

    # ChromaDB
    try:
        if (
            memory_collection is not None
            and full_reply.strip()
            and "connection to the void is flickering" not in full_reply.lower()
        ):
            memory_collection.add(
                documents=[f"User: {user_input} | Ember: {full_reply}"],
                ids=[signature],
                metadatas=[{"created_at": time.time()}],
            )
    except Exception as e:
        if "already exists" not in str(e).lower():
            print(f"Memory store warning: {e}")

    # Trim old ChromaDB entries
    try:
        if memory_collection is not None and memory_collection.count() > MAX_MEMORY_ITEMS:
            overflow = memory_collection.count() - MAX_MEMORY_ITEMS
            stored = memory_collection.get(include=["metadatas"])
            items = list(zip(stored.get("ids", []), stored.get("metadatas", [])))
            items.sort(key=lambda item: item[1].get("created_at", 0) if item[1] else 0)
            ids_to_delete = [item[0] for item in items[:overflow]]
            if ids_to_delete:
                memory_collection.delete(ids=ids_to_delete)
    except Exception as e:
        print(f"Memory trim warning: {e}")

    # JSON history
    with conversation_lock:
        latest_history = load_memory()
        if not latest_history or latest_history[0].get("role") != "system":
            latest_history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
        else:
            latest_history[0]["content"] = SYSTEM_PROMPT
        latest_history.append({"role": "user", "content": user_input})
        latest_history.append({"role": "assistant", "content": full_reply})
        save_memory(latest_history)
