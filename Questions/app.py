from flask import Flask, Blueprint, request, jsonify
from pathlib import Path
import joblib
import json
import re

bp = Blueprint("questions", __name__)

BASE_DIR = Path(__file__).resolve().parent

# =====================================================
# LOAD MODEL
# =====================================================

MODEL_PATH = "naive_bayes_model.pkl"

model = joblib.load(BASE_DIR / MODEL_PATH)

print("✅ Naive Bayes model loaded")


# =====================================================
# LOAD KNOWLEDGE BASE
# =====================================================

JSON_PATH = "cultural_knowledge.json"

with open(BASE_DIR / JSON_PATH, "r", encoding="utf-8") as f:
    cultural_data = json.load(f)

print("✅ Cultural knowledge base loaded")


# =====================================================
# SETTINGS
# =====================================================

CONFIDENCE_THRESHOLD = 0.45


# =====================================================
# HOME ROUTE
# =====================================================

@bp.route("/")
def home():

    return jsonify({
        "success": True,
        "message": "Sri Lanka Cultural Intelligence API Running"
    })


# =====================================================
# HEALTH CHECK
# =====================================================

@bp.route("/health")
def health():

    return jsonify({
        "status": "healthy"
    })


# =====================================================
# PREDICT ROUTE
# =====================================================

@bp.route("/predict", methods=["POST"])
def predict():

    try:

        data = request.get_json()

        # =============================================
        # VALIDATE INPUT
        # =============================================

        if not data:
            return jsonify({
                "success": False,
                "error": "JSON body is required"
            }), 400

        question = data.get("question", "").strip()

        if question == "":
            return jsonify({
                "success": False,
                "error": "Question is required"
            }), 400

        # =============================================
        # BASIC GIBBERISH CHECK
        # =============================================

        # Minimum length
        if len(question) < 3:

            return jsonify({
                "success": True,
                "question": question,
                "predicted_intent": "unknown",
                "confidence": 0.0,
                "response": {
                    "title": "Unknown Input",
                    "description": "Input is too short.",
                    "guidance": [
                        "Please enter a meaningful cultural or tourism-related question."
                    ]
                }
            })

        # Must contain letters
        if not re.search(r"[a-zA-Z]", question):

            return jsonify({
                "success": True,
                "question": question,
                "predicted_intent": "unknown",
                "confidence": 0.0,
                "response": {
                    "title": "Unknown Input",
                    "description": "No valid text detected.",
                    "guidance": [
                        "Please enter a readable question."
                    ]
                }
            })

        # Too many special characters
        special_char_ratio = len(
            re.findall(r"[^a-zA-Z0-9\s]", question)
        ) / len(question)

        if special_char_ratio > 0.5:

            return jsonify({
                "success": True,
                "question": question,
                "predicted_intent": "unknown",
                "confidence": 0.0,
                "response": {
                    "title": "Unknown Input",
                    "description": "Input appears invalid or noisy.",
                    "guidance": [
                        "Please enter a proper tourism or cultural question."
                    ]
                }
            })

        # =============================================
        # PREDICT PROBABILITIES
        # =============================================

        probabilities = model.predict_proba([question])[0]

        max_prob = float(max(probabilities))

        best_index = probabilities.argmax()

        predicted_intent = model.classes_[best_index]

        # =============================================
        # CONFIDENCE THRESHOLD
        # =============================================

        if max_prob < CONFIDENCE_THRESHOLD:

            predicted_intent = "unknown"

            response_data = {
                "title": "Unknown Question",
                "description": "The system could not understand the question.",
                
            }

        else:

            response_data = cultural_data.get(
                predicted_intent,
                {
                    "title": "No Data",
                    "description": "No cultural guidance available."
                }
            )

        # =============================================
        # FINAL RESPONSE
        # =============================================

        return jsonify({

            "success": True,

            "question": question,

            "predicted_intent": predicted_intent,

            "confidence": round(max_prob, 4),

            "response": response_data

        })

    except Exception as e:

        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# =====================================================
# RUN SERVER
# =====================================================

if __name__ == "__main__":

    app = Flask(__name__)
    app.register_blueprint(bp)
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )