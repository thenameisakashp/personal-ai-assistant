import os
import sqlite3
import secrets
from pathlib import Path

from assistant_config import ASSISTANT_NAME, ASSISTANT_INSTRUCTIONS
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from openai import OpenAI


# =========================
# CONFIGURATION
# =========================

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


# =========================
# DATABASE
# =========================

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

        # Sessions
        db.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
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


# =========================
# AUTHENTICATION
# =========================

def get_current_user(request: Request):

    token = request.cookies.get("session_token")

    if not token:
        return None

    with get_db() as db:

        row = db.execute(
            """
            SELECT users.id, users.username
            FROM sessions
            JOIN users ON users.id = sessions.user_id
            WHERE sessions.token = ?
            """,
            (token,)
        ).fetchone()

    return row


# =========================
# SIGNUP
# =========================

@app.post("/signup")
async def signup(data: dict):

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    )


    if not username or not password:

        return JSONResponse(
            {
                "error":
                "Username and password are required."
            },
            status_code=400
        )


    if len(username) < 3:

        return JSONResponse(
            {
                "error":
                "Username must be at least 3 characters."
            },
            status_code=400
        )


    if len(password) < 4:

        return JSONResponse(
            {
                "error":
                "Password must be at least 4 characters."
            },
            status_code=400
        )


    with get_db() as db:

        existing = db.execute(
            "SELECT id FROM users WHERE username = ?",
            (username,)
        ).fetchone()


        if existing:

            return JSONResponse(
                {
                    "error":
                    "Username already exists."
                },
                status_code=400
            )


        cursor = db.execute(
            """
            INSERT INTO users (username, password)
            VALUES (?, ?)
            """,
            (username, password)
        )

        user_id = cursor.lastrowid


        token = secrets.token_urlsafe(32)


        db.execute(
            """
            INSERT INTO sessions (token, user_id)
            VALUES (?, ?)
            """,
            (token, user_id)
        )


        db.commit()


    response = JSONResponse(
        {
            "message": "Account created.",
            "username": username
        }
    )


    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax"
    )


    return response


# =========================
# LOGIN
# =========================

@app.post("/login")
async def login(data: dict):

    username = str(
        data.get("username", "")
    ).strip()

    password = str(
        data.get("password", "")
    )


    with get_db() as db:

        user = db.execute(
            """
            SELECT id, username
            FROM users
            WHERE username = ?
            AND password = ?
            """,
            (username, password)
        ).fetchone()


        if not user:

            return JSONResponse(
                {
                    "error":
                    "Invalid username or password."
                },
                status_code=401
            )


        token = secrets.token_urlsafe(32)


        db.execute(
            """
            INSERT INTO sessions (token, user_id)
            VALUES (?, ?)
            """,
            (token, user["id"])
        )


        db.commit()


    response = JSONResponse(
        {
            "message": "Logged in.",
            "username": user["username"]
        }
    )


    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        samesite="lax"
    )


    return response


# =========================
# LOGOUT
# =========================

@app.post("/logout")
async def logout(request: Request):

    token = request.cookies.get(
        "session_token"
    )


    if token:

        with get_db() as db:

            db.execute(
                "DELETE FROM sessions WHERE token = ?",
                (token,)
            )

            db.commit()


    response = JSONResponse(
        {
            "message": "Logged out."
        }
    )


    response.delete_cookie(
        "session_token"
    )


    return response


# =========================
# CURRENT USER
# =========================

@app.get("/me")
async def me(request: Request):

    user = get_current_user(request)


    if not user:

        return {
            "logged_in": False
        }


    return {
        "logged_in": True,
        "username": user["username"]
    }
# =========================
# CHAT
# =========================

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


def extract_memories(user_message):

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=(
            "You are a memory extraction system for a personal AI assistant. "
            "Read the user's message and identify useful long-term personal facts "
            "that should be remembered for future conversations. "
            "Only extract facts about the user, their preferences, goals, "
            "projects, or information likely to remain useful. "
            "Do not save temporary requests, greetings, questions, or ordinary "
            "conversation. Return one memory per line. "
            "If there is nothing worth remembering, return exactly: NONE."
        ),
        input=user_message
    )

    result = response.output_text.strip()

    if result.upper() == "NONE":
        return []

    memories = []

    for line in result.splitlines():

        line = line.strip()
        line = line.lstrip("-•*").strip()

        if line:
            memories.append(line)

    return memories


@app.post("/chat")
async def chat(data: dict):

    user_message = str(
        data.get("message", "")
    ).strip()

    if not user_message:

        return {
            "reply": "Please enter a message."
        }


    # Save user message

    with get_db() as db:

        db.execute(
            """
            INSERT INTO messages (role, content)
            VALUES (?, ?)
            """,
            ("user", user_message)
        )

        db.commit()


    # Extract long-term memories

    try:

        new_memories = extract_memories(
            user_message
        )

        for memory in new_memories:

            save_memory(memory)

    except Exception as error:

        print(
            "Memory extraction error:",
            error
        )


    # Get conversation

    conversation = get_conversation()


    # Get long-term memories

    memories = get_memories()

    memory_text = "\n".join(
        f"- {item['memory']}"
        for item in memories
    )

    messages = get_conversation()

    response = client.responses.create(
        model="gpt-5.6-luna",
        instructions=ASSISTANT_INSTRUCTIONS,
        input=messages
)

    assistant_reply = response.output_text


    # Save assistant response

    with get_db() as db:

        db.execute(
            """
            INSERT INTO messages (role, content)
            VALUES (?, ?)
            """,
            ("assistant", assistant_reply)
        )

        db.commit()


    return {
        "reply": assistant_reply
    }
# =========================
# CONVERSATION MEMORY
# =========================

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


@app.get("/memory")
async def memory():

    return {
        "messages": get_conversation()
    }


# =========================
# LONG-TERM MEMORIES
# =========================

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


@app.get("/memories")
async def memories():

    return {
        "memories": get_memories()
    }


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


@app.delete("/memories")
async def clear_memories():

    with get_db() as db:

        db.execute("DELETE FROM memories")

        db.commit()

    return {
        "message": "Long-term memories cleared."
    }


# =========================
# WEBSITE
# =========================

@app.get("/")
async def home():

    return FileResponse(
        BASE_DIR / "static" / "index.html"
    )

# =========================
# WEBSITE
# =========================

@app.get("/")
async def home():

    return FileResponse(
        BASE_DIR / "static" / "index.html"
    )