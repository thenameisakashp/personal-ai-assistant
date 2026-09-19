import os
import re
import sqlite3
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from supabase import create_client, Client
from google import genai
from google.genai import types

import assistant_config


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_PUBLISHABLE_KEY = os.getenv("SUPABASE_PUBLISHABLE_KEY")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing in .env")

if not SUPABASE_PUBLISHABLE_KEY:
    raise RuntimeError(
        "SUPABASE_PUBLISHABLE_KEY is missing in .env"
    )

if not SUPABASE_SECRET_KEY:
    raise RuntimeError(
        "SUPABASE_SECRET_KEY is missing in .env"
    )

if not GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY is missing in .env"
    )


# ============================================================
# GEMINI CONFIGURATION
# ============================================================

# The order matters.
#
# 1. 3.6 Flash = primary model because it has already
#    responded successfully in your environment.
#
# 2. 3.5 Flash-Lite = lightweight fallback for speed.
#
# 3. 3.7 Flash = final fallback.
#
GEMINI_MODELS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.7-flash",
]


# Only retry temporary failures twice.
GEMINI_RETRIES = 2


# Short exponential backoff:
#
# attempt 1 -> 0.5 sec
# attempt 2 -> 1.0 sec
#
GEMINI_RETRY_BASE_DELAY = 0.5


# ============================================================
# PERFORMANCE LIMITS
# ============================================================

# Only send the most recent conversation messages to Gemini.
#
# This prevents long conversations from becoming slower and
# keeps the prompt reasonably small.
MAX_HISTORY_MESSAGES = 20


# Only use the latest 20 long-term memories in the prompt.
MAX_MEMORY_ITEMS = 20


# Prevent a very large collection of memories from making
# every Gemini request unnecessarily large.
MAX_MEMORY_CHARS = 4000


# Limit generated output so normal answers return faster.
MAX_OUTPUT_TOKENS = 1536


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
    title="Iraa Personal AI Assistant",
    description="Personal AI Assistant powered by Gemini",
    version="1.0.0"
)


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

STATIC_DIR = BASE_DIR / "static"

DATABASE_PATH = BASE_DIR / "assistant.db"


# ============================================================
# STATIC FILES
# ============================================================

if STATIC_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(
            directory=str(STATIC_DIR)
        ),
        name="static"
    )


# ============================================================
# DATABASE
# ============================================================

def get_db():

    conn = sqlite3.connect(
        str(DATABASE_PATH),
        check_same_thread=False
    )

    conn.row_factory = sqlite3.Row

    return conn


def init_database():

    conn = get_db()

    cursor = conn.cursor()


    # --------------------------------------------------------
    # Messages
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # --------------------------------------------------------
    # Memories
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            memory TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)


    # --------------------------------------------------------
    # Migration: messages.user_id
    # --------------------------------------------------------

    try:

        cursor.execute(
            "PRAGMA table_info(messages)"
        )

        message_columns = [
            row["name"]
            for row in cursor.fetchall()
        ]


        if "user_id" not in message_columns:

            cursor.execute(
                """
                ALTER TABLE messages
                ADD COLUMN user_id TEXT
                """
            )

    except Exception as e:

        print(
            "Messages migration error:",
            e
        )


    # --------------------------------------------------------
    # Migration: memories.user_id
    # --------------------------------------------------------

    try:

        cursor.execute(
            "PRAGMA table_info(memories)"
        )

        memory_columns = [
            row["name"]
            for row in cursor.fetchall()
        ]


        if "user_id" not in memory_columns:

            cursor.execute(
                """
                ALTER TABLE memories
                ADD COLUMN user_id TEXT
                """
            )

    except Exception as e:

        print(
            "Memories migration error:",
            e
        )


    conn.commit()

    conn.close()


# Initialize database when server starts.
init_database()


# ============================================================
# REQUEST MODELS
# ============================================================

class ChatRequest(BaseModel):

    message: str


# ============================================================
# NETWORK ERROR DETECTION
# ============================================================

def is_network_error(
    error: Exception
) -> bool:

    error_text = str(error).lower()


    network_keywords = [

        "connecttimeout",

        "readtimeout",

        "timeout",

        "timed out",

        "handshake operation timed out",

        "connection reset",

        "connection refused",

        "temporary failure",

        "network is unreachable",

        "name or service not known",

    ]


    return any(
        keyword in error_text
        for keyword in network_keywords
    )


# ============================================================
# SUPABASE AUTHENTICATION
# ============================================================

def get_current_user(
    request: Request
):

    authorization = request.headers.get(
        "Authorization"
    )


    if not authorization:

        raise HTTPException(
            status_code=401,
            detail="Authentication required."
        )


    if not authorization.startswith(
        "Bearer "
    ):

        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header."
        )


    access_token = authorization.replace(
        "Bearer ",
        "",
        1
    ).strip()


    if not access_token:

        raise HTTPException(
            status_code=401,
            detail="Missing access token."
        )


    # --------------------------------------------------------
    # Supabase authentication retry
    # --------------------------------------------------------

    for attempt in range(3):

        try:

            response = supabase.auth.get_user(
                access_token
            )


            if (
                not response
                or not response.user
            ):

                raise HTTPException(
                    status_code=401,
                    detail="Invalid or expired session."
                )


            return response.user


        except HTTPException:

            raise


        except Exception as e:

            print(
                f"Authentication attempt "
                f"{attempt + 1}/3 failed:",
                repr(e)
            )


            if is_network_error(e):

                if attempt < 2:

                    time.sleep(
                        0.4 * (2 ** attempt)
                    )

                    continue


                raise HTTPException(
                    status_code=503,
                    detail=(
                        "Authentication service is temporarily "
                        "unavailable. Please try again."
                    )
                )


            raise HTTPException(
                status_code=401,
                detail="Invalid or expired session."
            )


    raise HTTPException(
        status_code=503,
        detail=(
            "Authentication service temporarily unavailable."
        )
    )


# ============================================================
# SAVE MESSAGE
# ============================================================

def save_message(
    user_id: str,
    role: str,
    content: str
):

    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        INSERT INTO messages
        (user_id, role, content)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            role,
            content
        )
    )


    conn.commit()

    conn.close()


# ============================================================
# GET MESSAGES
# ============================================================

def get_messages(
    user_id: str,
    limit: int = MAX_HISTORY_MESSAGES
):

    conn = get_db()

    cursor = conn.cursor()


    # Get newest messages first.
    #
    # This is more useful than ORDER BY id ASC LIMIT 20,
    # which would keep returning the oldest messages.
    cursor.execute(
        """
        SELECT role, content
        FROM messages
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            limit
        )
    )


    rows = cursor.fetchall()

    conn.close()


    # Gemini needs chronological order.
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


# ============================================================
# SAVE MEMORY
# ============================================================

def save_memory(
    user_id: str,
    memory: str
):

    if not memory.strip():

        return


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT id
        FROM memories
        WHERE user_id = ?
        AND LOWER(memory) = LOWER(?)
        """,
        (
            user_id,
            memory.strip()
        )
    )


    existing = cursor.fetchone()


    if not existing:

        cursor.execute(
            """
            INSERT INTO memories
            (user_id, memory)
            VALUES (?, ?)
            """,
            (
                user_id,
                memory.strip()
            )
        )


    conn.commit()

    conn.close()


# ============================================================
# GET MEMORIES
# ============================================================

def get_memories(
    user_id: str
):

    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        SELECT id, memory, created_at
        FROM memories
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """,
        (
            user_id,
            MAX_MEMORY_ITEMS
        )
    )


    rows = cursor.fetchall()

    conn.close()


    memories = []

    total_chars = 0


    for row in rows:

        memory = row["memory"]


        # Prevent a large memory prompt.
        if total_chars + len(memory) > MAX_MEMORY_CHARS:

            break


        memories.append(
            {
                "id": row["id"],
                "memory": memory,
                "created_at": row["created_at"]
            }
        )


        total_chars += len(memory)


    return memories


# ============================================================
# MEMORY EXTRACTION
# ============================================================

def extract_memory(
    user_message: str,
    user_id: str
):

    text = user_message.strip()


    if not text:

        return


    memory_patterns = [

        # Name
        (
            r"\bmy name is ([a-zA-Z][a-zA-Z ]{1,40})",
            "The user's name is {}."
        ),

        # Likes
        (
            r"\bi like ([^.!,?]+)",
            "The user likes {}."
        ),

        # Favorite
        (
            r"\bmy favorite (?:thing|food|movie|song|color|game|sport)? ?is ([^.!,?]+)",
            "The user's favorite is {}."
        ),

        # Goals
        (
            r"\bi want to ([^.!,?]+)",
            "The user's goal is to {}."
        ),

        # Projects
        (
            r"\bi am working on ([^.!,?]+)",
            "The user is working on {}."
        ),

        # Building
        (
            r"\bi am building ([^.!,?]+)",
            "The user is building {}."
        ),

        # Studying
        (
            r"\bi am studying ([^.!,?]+)",
            "The user is studying {}."
        ),

        # Learning
        (
            r"\bi am learning ([^.!,?]+)",
            "The user is learning {}."
        ),
    ]


    for pattern, template in memory_patterns:

        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )


        if not match:

            continue


        value = match.group(1).strip()


        if len(value) < 2:

            continue


        memory = template.format(
            value
        )


        save_memory(
            user_id,
            memory
        )


        print(
            "MEMORY SAVED:",
            memory
        )


        break


# ============================================================
# GEMINI HISTORY
# ============================================================

def convert_history_for_gemini(
    messages
):

    history = []


    for message in messages:

        role = message.get(
            "role"
        )

        content = message.get(
            "content"
        )


        if not content:

            continue


        if role == "assistant":

            gemini_role = "model"

        elif role == "user":

            gemini_role = "user"

        else:

            continue


        history.append(
            {
                "role": gemini_role,
                "parts": [
                    {
                        "text": content
                    }
                ]
            }
        )


    return history


# ============================================================
# IRAA SYSTEM INSTRUCTION
# ============================================================

def build_system_instruction(
    memories
):

    memory_text = ""


    if memories:

        memory_lines = []


        for item in memories:

            memory_lines.append(
                f"- {item['memory']}"
            )


        memory_text = (
            "\n\nKnown information about the user:\n"
            + "\n".join(memory_lines)
        )


    else:

        memory_text = (
            "\n\nNo long-term user memories "
            "are currently available."
        )


    return (
        assistant_config.ASSISTANT_INSTRUCTIONS
        + "\n\n"
        + memory_text
    )


# ============================================================
# GEMINI TRANSIENT ERROR DETECTION
# ============================================================

def is_gemini_transient_error(
    error: Exception
) -> bool:

    error_text = str(error).lower()


    transient_keywords = [

        "503",

        "unavailable",

        "high demand",

        "429",

        "resource exhausted",

        "rate limit",

        "500",

        "502",

        "504",

        "internal server error",

        "deadline exceeded",

        "timeout",

        "temporarily unavailable",

    ]


    return any(
        keyword in error_text
        for keyword in transient_keywords
    )


# ============================================================
# GEMINI RESPONSE GENERATION
# ============================================================

def generate_gemini_response(
    user_message: str,
    conversation,
    memories
):

    gemini_history = convert_history_for_gemini(
        conversation
    )


    system_instruction = build_system_instruction(
        memories
    )


    print()
    print("--------------------------------------------")
    print("Gemini request")
    print(
        "Primary model:",
        GEMINI_MODELS[0]
    )
    print(
        "Fallback models:",
        ", ".join(GEMINI_MODELS[1:])
    )
    print(
        "History messages:",
        len(gemini_history)
    )
    print(
        "Memory items:",
        len(memories)
    )
    print("--------------------------------------------")


    last_error = None


    # ========================================================
    # MODEL LOOP
    # ========================================================

    for model_index, model_name in enumerate(
        GEMINI_MODELS
    ):


        # ====================================================
        # RETRY LOOP
        # ====================================================

        for attempt in range(
            GEMINI_RETRIES
        ):

            try:

                print(
                    f"Trying model {model_name} "
                    f"(attempt {attempt + 1}/"
                    f"{GEMINI_RETRIES})"
                )


                chat_session = (
                    gemini_client.chats.create(

                        model=model_name,

                        history=gemini_history,

                        config=(
                            types.GenerateContentConfig(

                                system_instruction=
                                    system_instruction,

                                max_output_tokens=
                                    MAX_OUTPUT_TOKENS
                            )
                        )
                    )
                )


                response = (
                    chat_session.send_message(
                        message=user_message
                    )
                )


                if not response:

                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )


                text = getattr(
                    response,
                    "text",
                    None
                )


                if not text:

                    raise RuntimeError(
                        "Gemini response contained no text."
                    )


                print()
                print(
                    "--------------------------------------------"
                )
                print(
                    "Gemini response successful"
                )
                print(
                    "Model used:",
                    model_name
                )
                print(
                    "--------------------------------------------"
                )


                return text.strip()


            except Exception as e:

                last_error = e


                print()
                print(
                    "--------------------------------------------"
                )
                print(
                    "GEMINI ERROR"
                )
                print(
                    "Model:",
                    model_name
                )
                print(
                    "Attempt:",
                    attempt + 1
                )
                print(
                    "Error type:",
                    type(e).__name__
                )
                print(
                    "Error:",
                    repr(e)
                )
                print(
                    "--------------------------------------------"
                )


                # --------------------------------------------
                # TEMPORARY ERROR
                # --------------------------------------------

                if is_gemini_transient_error(e):

                    if attempt < GEMINI_RETRIES - 1:

                        delay = (
                            GEMINI_RETRY_BASE_DELAY
                            * (2 ** attempt)
                        )


                        print(
                            f"Temporary Gemini error. "
                            f"Retrying in "
                            f"{delay:.1f}s..."
                        )


                        time.sleep(
                            delay
                        )


                        continue


                    print(
                        f"Retries exhausted for "
                        f"{model_name}."
                    )


                    if (
                        model_index
                        <
                        len(GEMINI_MODELS) - 1
                    ):

                        print(
                            "Switching to next Gemini model..."
                        )


                    break


                # --------------------------------------------
                # NON-TRANSIENT ERROR
                # --------------------------------------------

                print(
                    "Non-transient Gemini error."
                )


                raise


    # ========================================================
    # ALL MODELS FAILED
    # ========================================================

    print()
    print(
        "============================================"
    )
    print(
        "ALL GEMINI MODELS FAILED"
    )
    print(
        "============================================"
    )


    if last_error:

        raise last_error


    raise RuntimeError(
        "All Gemini models failed."
    )


# ============================================================
# CHAT ENDPOINT
# ============================================================

@app.post("/chat")
async def chat(
    request: Request,
    data: ChatRequest
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    user_message = (
        data.message.strip()
    )


    if not user_message:

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )


    print()
    print(
        "============================================"
    )
    print(
        "IRAA CHAT"
    )
    print(
        "============================================"
    )
    print(
        "User ID:",
        user_id
    )
    print(
        "User:",
        user_message
    )
    print(
        "============================================"
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

    try:

        extract_memory(
            user_message,
            user_id
        )

    except Exception as e:

        print(
            "Memory extraction error:",
            repr(e)
        )


    # ========================================================
    # GET RECENT CONVERSATION
    # ========================================================

    conversation = get_messages(
        user_id,
        limit=MAX_HISTORY_MESSAGES
    )


    # The current message is already stored in the database.
    #
    # Do not send it twice to Gemini.
    if conversation:

        conversation_history = (
            conversation[:-1]
        )

    else:

        conversation_history = []


    # ========================================================
    # GET MEMORIES
    # ========================================================

    memories = get_memories(
        user_id
    )


    # ========================================================
    # GENERATE RESPONSE
    # ========================================================

    try:

        assistant_response = (
            generate_gemini_response(

                user_message=user_message,

                conversation=
                    conversation_history,

                memories=memories
            )
        )


    except Exception as e:

        error_text = str(
            e
        ).lower()


        print()
        print(
            "============================================"
        )
        print(
            "FINAL GEMINI FAILURE"
        )
        print(
            "============================================"
        )
        print(
            repr(e)
        )
        print(
            "============================================"
        )


        # ----------------------------------------------------
        # RATE LIMIT
        # ----------------------------------------------------

        if (
            "429" in error_text
            or "rate limit" in error_text
            or "resource exhausted" in error_text
        ):

            assistant_response = (
                "I'm temporarily receiving too many "
                "requests. Please try again in a moment."
            )


        # ----------------------------------------------------
        # SERVICE UNAVAILABLE
        # ----------------------------------------------------

        elif (
            "503" in error_text
            or "unavailable" in error_text
            or "high demand" in error_text
        ):

            assistant_response = (
                "Gemini is temporarily busy right now. "
                "Please try again in a few seconds."
            )


        # ----------------------------------------------------
        # AUTHENTICATION / API KEY
        # ----------------------------------------------------

        elif (
            "401" in error_text
            or "403" in error_text
            or "api key" in error_text
            or "permission" in error_text
        ):

            assistant_response = (
                "I'm having trouble connecting to my AI "
                "service. Please check the Gemini API "
                "configuration."
            )


        # ----------------------------------------------------
        # MODEL NOT FOUND
        # ----------------------------------------------------

        elif (
            "404" in error_text
            or "not found" in error_text
        ):

            assistant_response = (
                "The configured AI model is currently "
                "unavailable. Please check the Gemini "
                "model configuration."
            )


        # ----------------------------------------------------
        # GENERAL ERROR
        # ----------------------------------------------------

        else:

            assistant_response = (
                "I ran into a temporary problem while "
                "processing that. Please try again."
            )


    # ========================================================
    # SAVE ASSISTANT RESPONSE
    # ========================================================

    save_message(
        user_id,
        "assistant",
        assistant_response
    )


    print()
    print(
        "============================================"
    )
    print(
        "IRAA RESPONSE"
    )
    print(
        "============================================"
    )
    print(
        assistant_response
    )
    print(
        "============================================"
    )


    # IMPORTANT:
    #
    # The frontend expects `response`.
    #
    return {
        "response": assistant_response
    }


# ============================================================
# GET CONVERSATION
# ============================================================

@app.get("/memory")
async def memory(
    request: Request
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    messages = get_messages(
        user_id,
        limit=100
    )


    return {
        "messages": messages
    }


# ============================================================
# GET LONG-TERM MEMORIES
# ============================================================

@app.get("/memories")
async def memories(
    request: Request
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    return {
        "memories": get_memories(
            user_id
        )
    }


# ============================================================
# DELETE ALL MEMORIES
# ============================================================

@app.delete("/memories")
async def delete_memories(
    request: Request
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        DELETE FROM memories
        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


    conn.commit()


    deleted_count = (
        cursor.rowcount
    )


    conn.close()


    return {
        "success": True,
        "deleted": deleted_count
    }


# ============================================================
# DELETE ONE MEMORY
# ============================================================

@app.delete("/memories/{memory_id}")
async def delete_memory(
    memory_id: int,
    request: Request
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        DELETE FROM memories
        WHERE id = ?
        AND user_id = ?
        """,
        (
            memory_id,
            user_id
        )
    )


    conn.commit()


    deleted_count = (
        cursor.rowcount
    )


    conn.close()


    if deleted_count == 0:

        raise HTTPException(
            status_code=404,
            detail="Memory not found."
        )


    return {
        "success": True
    }


# ============================================================
# CLEAR CONVERSATION
# ============================================================

@app.delete("/memory")
async def clear_memory(
    request: Request
):

    user = get_current_user(
        request
    )


    user_id = str(
        user.id
    )


    conn = get_db()

    cursor = conn.cursor()


    cursor.execute(
        """
        DELETE FROM messages
        WHERE user_id = ?
        """,
        (
            user_id,
        )
    )


    conn.commit()


    deleted_count = (
        cursor.rowcount
    )


    conn.close()


    return {
        "success": True,
        "deleted": deleted_count
    }


# ============================================================
# CURRENT USER
# ============================================================

@app.get("/me")
async def me(
    request: Request
):

    user = get_current_user(
        request
    )


    metadata = (
        user.user_metadata
        or {}
    )


    name = (
        metadata.get("name")
        or metadata.get("full_name")
        or metadata.get("display_name")
        or (
            user.email.split("@")[0]
            if user.email
            else "User"
        )
    )


    return {
        "id": str(user.id),
        "email": user.email,
        "name": name
    }


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "assistant": (
            assistant_config.ASSISTANT_NAME
        ),
        "gemini_models": GEMINI_MODELS
    }


# ============================================================
# MAIN PAGE
# ============================================================

@app.get("/")
async def home():

    index_file = (
        STATIC_DIR / "index.html"
    )


    if not index_file.exists():

        raise HTTPException(
            status_code=404,
            detail="index.html not found."
        )


    return FileResponse(
        str(index_file)
    )


# ============================================================
# APP PAGE
# ============================================================

@app.get("/app")
async def application():

    app_file = (
        STATIC_DIR / "app.html"
    )


    if not app_file.exists():

        raise HTTPException(
            status_code=404,
            detail="app.html not found."
        )


    return FileResponse(
        str(app_file)
    )


# ============================================================
# STARTUP
# ============================================================

@app.on_event("startup")
async def startup_event():

    print()

    print(
        "============================================"
    )

    print(
        "IRAA PERSONAL AI ASSISTANT"
    )

    print(
        "============================================"
    )

    print(
        "Assistant:",
        assistant_config.ASSISTANT_NAME
    )

    print(
        "Database:",
        DATABASE_PATH
    )

    print(
        "Gemini models:"
    )


    for model in GEMINI_MODELS:

        print(
            "  -",
            model
        )


    print(
        "Max history:",
        MAX_HISTORY_MESSAGES
    )

    print(
        "Max memories:",
        MAX_MEMORY_ITEMS
    )

    print(
        "Max output tokens:",
        MAX_OUTPUT_TOKENS
    )

    print(
        "============================================"
    )

    print(
        "Server ready."
    )

    print(
        "============================================"
    )