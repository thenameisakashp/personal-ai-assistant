import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "assistant.db"

load_dotenv(BASE_DIR / ".env")

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("OPENAI_API_KEY is missing from .env")

client = OpenAI(api_key=api_key)

app = FastAPI(title="Personal AI Assistant")


app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)


# -------------------------
# DATABASE
# -------------------------

def get_db():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with get_db() as db:

        # Users
        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Conversation history
        db.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Long-term memories
        db.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        db.commit()


init_db()


# -------------------------
# CONVERSATION MEMORY
# -------------------------

def get_conversation():

    with get_db() as db:
        rows = db.execute(
            "SELECT role, content FROM messages ORDER BY id ASC"
        ).fetchall()

    return [
        {
            "role": row["role"],
            "content": row["content"]
        }
        for row in rows
    ]


# -------------------------
# LONG-TERM MEMORY
# -------------------------

def get_memories():

    with get_db() as db:
        rows = db.execute(
            "SELECT id, memory FROM memories ORDER BY id ASC"
        ).fetchall()

    return [
        {
            "id": row["id"],
            "memory": row["memory"]
        }
        for row in rows
    ]


def save_memory(memory):

    memory = memory.strip()

    if not memory:
        return

    with get_db() as db:

        # Avoid storing the exact same memory twice
        existing = db.execute(
            "SELECT id FROM memories WHERE memory = ?",
            (memory,)
        ).fetchone()

        if existing:
            return

        db.execute(
            "INSERT INTO memories (memory) VALUES (?)",
            (memory,)
        )

        db.commit()


# -------------------------
# MEMORY EXTRACTION
# -------------------------

def extract_memories(user_message):

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=(
            "You are a memory extraction system for a personal AI assistant. "
            "Read the user's message and identify useful long-term personal facts "
            "that should be remembered for future conversations. "
            "Only extract facts about the user, their preferences, goals, projects, "
            "or other information that is likely to remain useful. "
            "Do not save temporary requests, greetings, questions, or ordinary conversation. "
            "Return one memory per line. "
            "If there is nothing worth remembering, return exactly: NONE"
        ),
        input=user_message
    )

    result = response.output_text.strip()

    if result.upper() == "NONE":
        return []

    memories = []

    for line in result.splitlines():

        line = line.strip()

        if not line:
            continue

        # Remove common bullet formatting
        line = line.lstrip("-•*").strip()

        if line:
            memories.append(line)

    return memories


# -------------------------
# AI CHAT
# -------------------------

@app.post("/chat")
async def chat(data: dict):

    user_message = str(data.get("message", "")).strip()

    if not user_message:
        return {
            "reply": "Please enter a message."
        }

    # Save user message
    with get_db() as db:

        db.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            ("user", user_message)
        )

        db.commit()

    # Extract useful long-term memories
    try:

        new_memories = extract_memories(user_message)

        for memory in new_memories:
            save_memory(memory)

    except Exception as error:

        print("Memory extraction error:", error)

    # Get conversation
    conversation = get_conversation()

    # Get long-term memories
    memories = get_memories()

    memory_text = "\n".join(
        f"- {item['memory']}"
        for item in memories
    )

    instructions = (
        "You are a helpful personal AI assistant. "
        "Use the conversation history to understand context. "
        "Use the user's long-term memories when they are relevant. "
        "Do not mention the memory system unless the user asks about it. "
        "Be clear, practical, and friendly.\n\n"
        "USER'S LONG-TERM MEMORIES:\n"
        f"{memory_text if memory_text else 'No long-term memories yet.'}"
    )

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=instructions,
        input=conversation
    )

    assistant_reply = response.output_text

    # Save assistant response
    with get_db() as db:

        db.execute(
            "INSERT INTO messages (role, content) VALUES (?, ?)",
            ("assistant", assistant_reply)
        )

        db.commit()

    return {
        "reply": assistant_reply
    }


# -------------------------
# LOAD CONVERSATION
# -------------------------

@app.get("/memory")
async def memory():

    return {
        "messages": get_conversation()
    }


# -------------------------
# VIEW LONG-TERM MEMORIES
# -------------------------

@app.get("/memories")
async def memories():

    return {
        "memories": get_memories()
    }


# -------------------------
# CLEAR CONVERSATION
# -------------------------

@app.delete("/memory")
async def clear_memory():

    with get_db() as db:

        db.execute("DELETE FROM messages")
        db.commit()

    return {
        "message": "Conversation memory cleared."
    }


# -------------------------
# CLEAR LONG-TERM MEMORIES
# -------------------------

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: int):

    with get_db() as db:

        db.execute(
            "DELETE FROM memories WHERE id = ?",
            (memory_id,)
        )

        db.commit()

    return {
        "message": "Memory deleted."
    }


# -------------------------
# WEBSITE
# -------------------------

@app.get("/")
async def home():

    return FileResponse(
        BASE_DIR / "static" / "index.html"
    )