# Personal AI Assistant

Milestone 1: local AI chat using Python, FastAPI, and the Google Gemini Responses API.

## Setup

1. Create a virtual environment:
   `python -m venv venv`

2. Activate it on Windows:
   `venv\Scripts\activate`

3. Install dependencies:
   `pip install -r requirements.txt`

4. Copy `.env.example` to `.env`.

5. Put your OpenAI API key in `.env`.

6. Start the server:
   `uvicorn main:app --reload`

7. Open:
   `http://127.0.0.1:8000`

Never commit your `.env` file or expose your API key in frontend JavaScript.
