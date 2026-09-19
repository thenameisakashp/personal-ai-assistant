import os
import sqlite3
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from google import genai
from google.genai import types

from supabase import create_client, Client

from assistant_config import (
    ASSISTANT_NAME,
    ASSISTANT_INSTRUCTIONS,
    CREATOR_NAME,
    CREATOR_RESPONSE,
    OWNERSHIP_RESPONSE,
    AMBIGUOUS_AKASHH_RESPONSE,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv(
    "SUPABASE_PUBLISHABLE_KEY"
)
SUPABASE_SECRET_KEY = os.getenv(
    "SUPABASE_SECRET_KEY"
)
GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY"
)


if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL is missing from .env"
    )

if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "SUPABASE_PUBLISHABLE_KEY is missing from .env"
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from .env"
    )


# ============================================================
# GEMINI
# ============================================================

GEMINI_MODEL = "gemini-3.6-flash"


# ============================================================
# CLIENTS
# ============================================================

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_PUBLISHABLE_KEY
)

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)


# ============================================================
# FASTAPI
# ============================================================

app = FastAPI(
    title=f"{ASSISTANT_NAME} Personal AI Assistant"
)

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static"
)


# ============================================================
# DATABASE
# ============================================================

DB_PATH = BASE_DIR / "assistant.db"


def get_db():

    conn = sqlite3.connect(
        DB_PATH,
        timeout=10
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_db():

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # --------------------------------------------------------
    # Existing database migration
    # --------------------------------------------------------

    cursor.execute(
        "PRAGMA table_info(messages)"
    )

    message_columns = [
        row["name"]
        for row in cursor.fetchall()
    ]

    if "user_id" not in message_columns:

        cursor.execute(
            "ALTER TABLE messages ADD COLUMN user_id TEXT"
        )

    cursor.execute(
        "PRAGMA table_info(memories)"
    )

    memory_columns = [
        row["name"]
        for row in cursor.fetchall()
    ]

    if "user_id" not in memory_columns:

        cursor.execute(
            "ALTER TABLE memories ADD COLUMN user_id TEXT"
        )

    conn.commit()
    conn.close()


init_db()


# ============================================================
# AUTHENTICATION
# ============================================================

def get_current_user(request: Request):

    authorization = request.headers.get(
        "Authorization"
    )

    if not authorization:
        return None

    if not authorization.startswith("Bearer "):
        return None

    access_token = authorization.replace(
        "Bearer ",
        "",
        1
    ).strip()

    if not access_token:
        return None

    try:

        response = supabase.auth.get_user(
            access_token
        )

        if response and response.user:
            return response.user

    except Exception as e:

        print(
            "Authentication error:",
            repr(e)
        )

    return None


def require_user(request: Request):

    user = get_current_user(request)

    if not user:

        return None, JSONResponse(
            status_code=401,
            content={
                "detail": "Authentication required"
            }
        )

    return user, None


# ============================================================
# USER NAME
# ============================================================

def get_user_name(user):

    metadata = user.user_metadata or {}

    name = (
        metadata.get("name")
        or metadata.get("full_name")
    )

    if name:
        return str(name).strip()

    if user.email:
        return user.email.split("@")[0]

    return "User"


# ============================================================
# MESSAGE DATABASE
# ============================================================

def save_message(
    user_id: str,
    role: str,
    content: str
):

    try:

        conn = get_db()

        conn.execute("""
            INSERT INTO messages
            (user_id, role, content)
            VALUES (?, ?, ?)
        """, (
            user_id,
            role,
            content
        ))

        conn.commit()
        conn.close()

    except Exception as e:

        print(
            "Database save message error:",
            repr(e)
        )


def get_conversation(
    user_id: str,
    limit: int = 30
):

    try:

        conn = get_db()

        rows = conn.execute("""
            SELECT role, content
            FROM messages
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (
            user_id,
            limit
        )).fetchall()

        conn.close()

        rows = list(
            reversed(rows)
        )

        return [
            {
                "role": row["role"],
                "content": row["content"]
            }
            for row in rows
        ]

    except Exception as e:

        print(
            "Database conversation error:",
            repr(e)
        )

        return []


# ============================================================
# MEMORY DATABASE
# ============================================================

def save_memory(
    user_id: str,
    memory: str
):

    if not memory:
        return

    memory = memory.strip()

    if not memory:
        return

    try:

        conn = get_db()

        existing = conn.execute("""
            SELECT id
            FROM memories
            WHERE user_id = ?
            AND LOWER(memory) = LOWER(?)
        """, (
            user_id,
            memory
        )).fetchone()

        if not existing:

            conn.execute("""
                INSERT INTO memories
                (user_id, memory)
                VALUES (?, ?)
            """, (
                user_id,
                memory
            ))

            conn.commit()

        conn.close()

    except Exception as e:

        print(
            "Database save memory error:",
            repr(e)
        )


def get_memories(
    user_id: str
):

    try:

        conn = get_db()

        rows = conn.execute("""
            SELECT id, memory, created_at
            FROM memories
            WHERE user_id = ?
            ORDER BY id DESC
        """, (
            user_id,
        )).fetchall()

        conn.close()

        return [
            {
                "id": row["id"],
                "memory": row["memory"],
                "created_at": row["created_at"]
            }
            for row in rows
        ]

    except Exception as e:

        print(
            "Database memories error:",
            repr(e)
        )

        return []


def delete_memory(
    user_id: str,
    memory_id: int
):

    try:

        conn = get_db()

        conn.execute("""
            DELETE FROM memories
            WHERE id = ?
            AND user_id = ?
        """, (
            memory_id,
            user_id
        ))

        conn.commit()
        conn.close()

    except Exception as e:

        print(
            "Delete memory error:",
            repr(e)
        )


def clear_memories(
    user_id: str
):

    try:

        conn = get_db()

        conn.execute("""
            DELETE FROM memories
            WHERE user_id = ?
        """, (
            user_id,
        ))

        conn.commit()
        conn.close()

    except Exception as e:

        print(
            "Clear memories error:",
            repr(e)
        )


# ============================================================
# LOCAL MEMORY EXTRACTION
# ============================================================
#
# No Gemini request is used here.
#
# This keeps normal messages at ONE Gemini call.
#
# ============================================================

def extract_local_memories(
    user_message: str
):

    text = user_message.strip()

    if not text:
        return []

    memories = []

    # --------------------------------------------------------
    # NAME
    # --------------------------------------------------------

    name_patterns = [

        r"\bmy name is ([A-Za-z][A-Za-z .'-]{1,40})[.!]?$",

        r"\bcall me ([A-Za-z][A-Za-z .'-]{1,40})[.!]?$",

    ]

    for pattern in name_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value:

                memories.append(
                    f"User's name is {value}"
                )

                return memories

    # --------------------------------------------------------
    # REMEMBER
    # --------------------------------------------------------

    remember_patterns = [

        r"^remember that (.+)$",

        r"^remember (.+)$",

        r"^please remember that (.+)$",

        r"^don't forget that (.+)$",

        r"^do not forget that (.+)$",

    ]

    for pattern in remember_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value:

                memories.append(
                    f"User wants remembered: {value}"
                )

                return memories

    # --------------------------------------------------------
    # EDUCATION
    # --------------------------------------------------------

    education_patterns = [

        r"\bi am studying (.+)",

        r"\bi'm studying (.+)",

        r"\bi study (.+)",

        r"\bi am a student of (.+)",

    ]

    for pattern in education_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value:

                memories.append(
                    f"User studies {value}"
                )

                return memories

    # --------------------------------------------------------
    # PREFERENCES
    # --------------------------------------------------------

    preference_patterns = [

        r"\bi like (.+)",

        r"\bi love (.+)",

        r"\bi prefer (.+)",

    ]

    for pattern in preference_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:

            value = match.group(1).strip()

            if value:

                memories.append(
                    f"User likes {value}"
                )

                return memories

    # --------------------------------------------------------
    # FAVORITE
    # --------------------------------------------------------

    favorite_pattern = re.search(
        r"\bmy favorite (.+?) is (.+)",
        text,
        re.IGNORECASE
    )

    if favorite_pattern:

        category = (
            favorite_pattern
            .group(1)
            .strip()
        )

        value = (
            favorite_pattern
            .group(2)
            .strip()
        )

        if category and value:

            memories.append(
                f"User's favorite {category} is {value}"
            )

            return memories

    return memories


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(
    text: str
):

    text = text.lower().strip()

    text = re.sub(
        r"[^\w\s]",
        " ",
        text
    )

    text = re.sub(
        r"\s+",
        " ",
        text
    )

    return text.strip()


# ============================================================
# AKASHH DETECTION
# ============================================================

def mentions_akashh(
    text: str
):

    normalized = normalize_text(
        text
    )

    return bool(
        re.search(
            r"\bakashh?\b",
            normalized
        )
    )


# ============================================================
# CREATOR QUESTION
# ============================================================

def is_creator_question(
    text: str
):

    normalized = normalize_text(
        text
    )

    patterns = [

        r"\bwho built you\b",
        r"\bwho is your builder\b",

        r"\bwho made you\b",
        r"\bwho created you\b",

        r"\bwho is your creator\b",
        r"\bwho developed you\b",

        r"\bwho is your developer\b",

        r"\btell me about your builder\b",
        r"\btell me about your creator\b",
        r"\btell me about your developer\b",

        r"\bakashh.*built you\b",
        r"\bakash.*built you\b",

        r"\bakashh.*created you\b",
        r"\bakash.*created you\b",

        r"\bakashh.*made you\b",
        r"\bakash.*made you\b",

        r"\bakashh.*developed you\b",
        r"\bakash.*developed you\b",

        r"\bakashh.*your builder\b",
        r"\bakash.*your builder\b",

        r"\bakashh.*your creator\b",
        r"\bakash.*your creator\b",

    ]

    return any(
        re.search(
            pattern,
            normalized
        )
        for pattern in patterns
    )


# ============================================================
# OWNERSHIP QUESTION
# ============================================================

def is_ownership_question(
    text: str
):

    normalized = normalize_text(
        text
    )

    patterns = [

        r"\bwhose ai assistant are you\b",

        r"\bwhose assistant are you\b",

        r"\bwho do you belong to\b",

        r"\bwho owns you\b",

        r"\bwho is your owner\b",

    ]

    return any(
        re.search(
            pattern,
            normalized
        )
        for pattern in patterns
    )


# ============================================================
# AMBIGUOUS AKASHH QUESTION
# ============================================================

def is_ambiguous_akashh_question(
    text: str
):

    if not mentions_akashh(text):
        return False

    if is_creator_question(text):
        return False

    patterns = [

        r"\bwho is akashh?\b",

        r"\bdo you know akashh?\b",

        r"\bdo you know about akashh?\b",

        r"\btell me about akashh?\b",

        r"\bwhat do you know about akashh?\b",

        r"\bwho's akashh?\b",

    ]

    return any(
        re.search(
            pattern,
            text,
            re.IGNORECASE
        )
        for pattern in patterns
    )


# ============================================================
# GEMINI HISTORY
# ============================================================

def build_gemini_history(
    conversation
):

    contents = []

    for message in conversation:

        role = message.get(
            "role"
        )

        content = message.get(
            "content"
        )

        if not content:
            continue

        if role == "user":

            contents.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(
                            text=content
                        )
                    ]
                )
            )

        elif role == "assistant":

            contents.append(
                types.Content(
                    role="model",
                    parts=[
                        types.Part.from_text(
                            text=content
                        )
                    ]
                )
            )

    return contents


# ============================================================
# CHAT
# ============================================================

@app.post("/chat")
async def chat(
    request: Request
):

    user, error = require_user(
        request
    )

    if error:
        return error

    # ========================================================
    # READ REQUEST
    # ========================================================

    try:

        body = await request.json()

    except Exception:

        return JSONResponse(
            status_code=400,
            content={
                "detail": "Invalid request body."
            }
        )

    user_message = str(
        body.get(
            "message",
            ""
        )
    ).strip()

    if not user_message:

        return JSONResponse(
            status_code=400,
            content={
                "detail": "Message cannot be empty."
            }
        )

    user_id = str(
        user.id
    )

    # ========================================================
    # AMBIGUOUS AKASHH
    # ========================================================

    if is_ambiguous_akashh_question(
        user_message
    ):

        save_message(
            user_id,
            "user",
            user_message
        )

        save_message(
            user_id,
            "assistant",
            AMBIGUOUS_AKASHH_RESPONSE
        )

        print(
            "Iraa: handled ambiguous Akashh question locally."
        )

        return {
            "response": AMBIGUOUS_AKASHH_RESPONSE
        }

    # ========================================================
    # OWNERSHIP
    # ========================================================

    if is_ownership_question(
        user_message
    ):

        save_message(
            user_id,
            "user",
            user_message
        )

        save_message(
            user_id,
            "assistant",
            OWNERSHIP_RESPONSE
        )

        print(
            "Iraa: handled ownership question locally."
        )

        return {
            "response": OWNERSHIP_RESPONSE
        }

    # ========================================================
    # CREATOR
    # ========================================================

    if is_creator_question(
        user_message
    ):

        save_message(
            user_id,
            "user",
            user_message
        )

        save_message(
            user_id,
            "assistant",
            CREATOR_RESPONSE
        )

        print(
            "Iraa: handled creator question locally."
        )

        return {
            "response": CREATOR_RESPONSE
        }

    # ========================================================
    # USER NAME
    # ========================================================

    user_name = get_user_name(
        user
    )

    # ========================================================
    # SAVE USER MESSAGE
    # ========================================================

    save_message(
        user_id,
        "user",
        user_message
    )

    # ========================================================
    # LOCAL MEMORY EXTRACTION
    # ========================================================

    detected_memories = extract_local_memories(
        user_message
    )

    for memory in detected_memories:

        save_memory(
            user_id,
            memory
        )

    # Automatically remember account name.

    if user_name and user_name != "User":

        save_memory(
            user_id,
            f"User's account name is {user_name}"
        )

    # ========================================================
    # GET CONVERSATION
    # ========================================================

    conversation = get_conversation(
        user_id,
        limit=30
    )

    # ========================================================
    # GET MEMORIES
    # ========================================================

    memories = get_memories(
        user_id
    )

    memories = memories[:30]

    if memories:

        memory_text = "\n".join(
            f"- {item['memory']}"
            for item in memories
        )

    else:

        memory_text = (
            "No long-term memories available."
        )

    # ========================================================
    # PERSONAL CONTEXT
    # ========================================================

    personal_context = f"""

CURRENT AUTHENTICATED USER:

Account name:
{user_name}

Only use the account name when relevant.

============================================================

CREATOR INFORMATION:

Creator:
{CREATOR_NAME}

Important:
Do not reveal creator information unless the user explicitly
asks about the creator, builder, developer, maker, or ownership.

============================================================

LONG-TERM USER MEMORY:

{memory_text}

============================================================

PRIVACY:

Only reveal information relevant to the current question.

Never expose another user's information.

Never expose passwords, API keys, tokens, or private
authentication information.
"""

    # ========================================================
    # GEMINI HISTORY
    # ========================================================

    gemini_history = build_gemini_history(
        conversation
    )

    # ========================================================
    # GEMINI API
    # ========================================================

    try:

        response = gemini_client.models.generate_content(

            model=GEMINI_MODEL,

            contents=gemini_history,

            config=types.GenerateContentConfig(

                system_instruction=(
                    ASSISTANT_INSTRUCTIONS
                    + "\n\n"
                    + personal_context
                ),

                max_output_tokens=2048
            )
        )

        assistant_message = (
            response.text
            if response.text
            else ""
        ).strip()

        if not assistant_message:

            assistant_message = (
                "I'm here. How can I help you?"
            )

    except Exception as e:

        print()
        print(
            "============================================"
        )
        print(
            "GEMINI API ERROR"
        )
        print(
            "============================================"
        )
        print(
            type(e).__name__
        )
        print(
            repr(e)
        )
        print(
            "============================================"
        )
        print()

        error_text = str(e).lower()

        if (
            "429" in error_text
            or "resource_exhausted" in error_text
            or "rate limit" in error_text
            or "quota" in error_text
        ):

            assistant_message = (
                "Gemini's API limit has been reached "
                "right now. Please try again shortly."
            )

        elif (
            "401" in error_text
            or "403" in error_text
            or "api key" in error_text
            or "permission" in error_text
            or "unauthorized" in error_text
        ):

            assistant_message = (
                "I couldn't access the Gemini API. "
                "Please check the Gemini API key "
                "and configuration."
            )

        elif (
            "404" in error_text
            or "not_found" in error_text
            or "not found" in error_text
        ):

            assistant_message = (
                "The configured Gemini model is unavailable. "
                "Please check the Gemini model configuration."
            )

        else:

            assistant_message = (
                "I'm having a temporary problem generating "
                "that response. Please try again."
            )

    # ========================================================
    # SAVE ASSISTANT RESPONSE
    # ========================================================

    save_message(
        user_id,
        "assistant",
        assistant_message
    )

    # ========================================================
    # RETURN
    # ========================================================

    return {
        "response": assistant_message
    }


# ============================================================
# MEMORY API
# ============================================================

@app.get("/memory")
async def memory(
    request: Request
):

    user, error = require_user(
        request
    )

    if error:
        return error

    user_id = str(
        user.id
    )

    return {
        "messages": get_conversation(
            user_id,
            limit=50
        )
    }


@app.get("/memories")
async def memories(
    request: Request
):

    user, error = require_user(
        request
    )

    if error:
        return error

    user_id = str(
        user.id
    )

    return {
        "memories": get_memories(
            user_id
        )
    }


@app.delete("/memories/{memory_id}")
async def remove_memory(
    memory_id: int,
    request: Request
):

    user, error = require_user(
        request
    )

    if error:
        return error

    user_id = str(
        user.id
    )

    delete_memory(
        user_id,
        memory_id
    )

    return {
        "success": True
    }


@app.delete("/memories")
async def remove_all_memories(
    request: Request
):

    user, error = require_user(
        request
    )

    if error:
        return error

    user_id = str(
        user.id
    )

    clear_memories(
        user_id
    )

    return {
        "success": True
    }


# ============================================================
# PAGES
# ============================================================

@app.get("/")
async def home():

    return FileResponse(
        STATIC_DIR / "index.html"
    )


@app.get("/app")
async def application():

    return FileResponse(
        STATIC_DIR / "app.html"
    )


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "assistant": ASSISTANT_NAME,
        "ai_provider": "Google Gemini",
        "model": GEMINI_MODEL,
        "memory_extraction": "local",
        "ai_calls_per_message": 1
    }