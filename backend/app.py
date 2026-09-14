import os
import requests
import firebase_admin

from firebase_admin import credentials, auth
from flask import Flask, jsonify, request
from pypdf import PdfReader
from flask_cors import CORS
from dotenv import load_dotenv


# Load environment variables
load_dotenv()


# Firebase Admin
import base64
import json

firebase_json = base64.b64decode(
    os.environ["FIREBASE_SERVICE_ACCOUNT_BASE64"]
).decode("utf-8")

cred = credentials.Certificate(json.loads(firebase_json))
firebase_admin.initialize_app(cred)


# Flask
app = Flask(__name__)
CORS(app)


# ============================================================
# HOME
# ============================================================

@app.route("/")
def home():
    return jsonify({
        "message": "Welcome to Sayan AI!",
        "status": "Backend is running"
    })


# ============================================================
# HEALTH
# ============================================================

@app.route("/health")
def health():
    return jsonify({
        "status": "healthy"
    })


# ============================================================
# TEST GEMINI
# ============================================================

@app.route("/test-gemini")
def test_gemini():

    api_key = os.environ["GEMINI_API_KEY"]

    url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": api_key
    }

    data = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Say hello to Sayan AI in one short sentence."
                    }
                ]
            }
        ]
    }

    response = requests.post(
        url,
        headers=headers,
        json=data,
        timeout=120
    )

    if not response.ok:
        return jsonify({
            "error": response.text
        }), response.status_code

    result = response.json()

    text = result["candidates"][0]["content"]["parts"][0]["text"]

    return jsonify({
        "response": text
    })


# ============================================================
# FIREBASE TOKEN VERIFICATION
# ============================================================

def verify_token():

    auth_header = request.headers.get("Authorization")

    if not auth_header or not auth_header.startswith("Bearer "):
        return None

    id_token = auth_header.split("Bearer ")[1]

    try:

        decoded_token = auth.verify_id_token(id_token)

        print(
            "✅ Firebase token verified:",
            decoded_token.get("uid")
        )

        return decoded_token

    except Exception as e:

        print(
            "❌ Firebase token verification failed:",
            str(e)
        )

        return None


# ============================================================
# DOCUMENT ANALYSIS
# ============================================================

@app.route("/analyze", methods=["POST"])
def analyze():

    # Verify Firebase user
    user = verify_token()

    if not user:
        return jsonify({
            "error": "Authentication required"
        }), 401

    print("CONTENT TYPE:", request.content_type)
    print("FILES:", request.files)

    # Check file
    if "file" not in request.files:
        return jsonify({
            "error": "No file uploaded"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "error": "No file selected"
        }), 400

    try:

        # ----------------------------------------------------
        # Extract PDF text
        # ----------------------------------------------------

        reader = PdfReader(file)

        document_text = ""

        for page in reader.pages:
            document_text += page.extract_text() or ""

        if not document_text.strip():

            return jsonify({
                "error": "Could not extract text from this PDF."
            }), 400

        # Limit document size
        document_text = document_text[:12000]

        print(
            "📄 Extracted characters:",
            len(document_text)
        )

        # ----------------------------------------------------
        # Gemini API
        # ----------------------------------------------------

        api_key = os.environ["GEMINI_API_KEY"]

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        prompt = f"""
You are Sayan AI, a document understanding assistant.

Analyze this document and provide:

1. Document Type
2. Purpose
3. Important Fields
4. Required Documents
5. Missing Information
6. Step-by-Step Instructions

Use simple language.
Use clear headings and bullet points.

DOCUMENT:
{document_text}
"""

        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        print("🤖 Sending document to Gemini...")

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=120
        )

        print(
            "Gemini response status:",
            response.status_code
        )

        if not response.ok:

            return jsonify({
                "error": response.text
            }), response.status_code

        result = response.json()

        text = result["candidates"][0]["content"]["parts"][0]["text"]

        print("✅ Gemini analysis completed")

        return jsonify({
            "filename": file.filename,
            "analysis": text
        })

    except Exception as e:

        print(
            "❌ ANALYZE ERROR:",
            str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# CHAT WITH DOCUMENT
# ============================================================

@app.route("/chat", methods=["POST"])
def chat():

    # Verify Firebase user
    user = verify_token()

    if not user:
        return jsonify({
            "error": "Authentication required"
        }), 401

    data = request.get_json()

    if not data:
        return jsonify({
            "error": "Invalid request"
        }), 400

    document_text = data.get("document", "")
    question = data.get("question", "")

    if not document_text or not question:

        return jsonify({
            "error": "Document and question are required"
        }), 400

    try:

        api_key = os.environ["GEMINI_API_KEY"]

        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent"

        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": api_key
        }

        # Limit document size
        document_text = document_text[:12000]

        prompt = f"""
You are Sayan AI.

Answer the user's question using ONLY the document provided below.

If the answer is not present in the document,
clearly say that the information is not available
in the document.

DOCUMENT:
{document_text}

USER QUESTION:
{question}
"""

        data = {
            "contents": [
                {
                    "parts": [
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        }

        print("💬 Sending question to Gemini...")

        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=120
        )

        if not response.ok:

            return jsonify({
                "error": response.text
            }), response.status_code

        result = response.json()

        text = result["candidates"][0]["content"]["parts"][0]["text"]

        print("✅ Chat response received")

        return jsonify({
            "answer": text
        })

    except Exception as e:

        print(
            "❌ CHAT ERROR:",
            str(e)
        )

        return jsonify({
            "error": str(e)
        }), 500


# ============================================================
# START SERVER
# ============================================================

if __name__ == "__main__":
    app.run(debug=True)