import os
import html # Used for sanitizing (cleaning) text
from flask import Flask, request, jsonify
from openai import OpenAI
from flask_cors import CORS  # <--- NEW IMPORT 1/2

app = Flask(__name__)
CORS(app)  # <--- NEW LINE 2/2: This tells the browser "It's okay to talk to me"


# Initialize the OpenAI client (The "Brain" that detects bad words)
# You need an API Key here. In a real app, use environment variables!
api_key = os.environ.get("OPENAI_API_KEY") 

if not api_key:
    raise ValueError("No OPENAI_API_KEY found in environment variables!")

client = OpenAI(api_key=api_key, base_url="https://aipipe.org/openai/v1")


# --- Helper Function: The Bouncer's Logic ---
def check_content_safety(user_text):
    """
    Sends text to OpenAI to check for violence/hate.
    Returns: blocked (bool), reason (str), confidence (float)
    """
    try:
        # 1. Ask OpenAI: "Is this text bad?"
        response = client.moderations.create(input=user_text)
        result = response.results[0]
        
        # 2. Look at the scores (0.0 to 1.0)
        # We need to find the highest score among all bad categories
        highest_score = 0.0
        primary_reason = "None"

        # category_scores looks like: {'violence': 0.1, 'hate': 0.9, ...}
        scores = result.category_scores.model_dump() # Convert to dictionary
        
        for category, score in scores.items():
            if score > highest_score:
                highest_score = score
                primary_reason = category

        # 3. The Rule: Block if confidence is higher than 0.8 (80%)
        if highest_score > 0.8:
            return True, f"Content detected: {primary_reason}", highest_score
        
        return False, "Input passed all security checks", highest_score

    except Exception as e:
        # If OpenAI is down, we fail safely (or log the error)
        print(f"Error calling OpenAI: {e}")
        return False, "Safety check unavailable", 0.0

# --- The API Endpoint: The Door ---
@app.route('/validate', methods=['POST'])
def validate_input():
    # 1. Get the JSON data sent by the user
    data = request.get_json()
    
    # Check if data exists
    if not data or 'input' not in data:
        return jsonify({"error": "No input provided"}), 400

    user_input = data['input']
    user_id = data.get('userId', 'unknown')

    print(f"Checking input from User {user_id}...") # This is "Logging"

    # 2. Run the Security Check (The Bouncer)
    is_blocked, reason, confidence_score = check_content_safety(user_input)

    # 3. Sanitize the output (The "Pat Down")
    # This turns dangerous code like <script> into safe text &lt;script&gt;
    # This prevents XSS attacks if you display this text later.
    sanitized_text = html.escape(user_input)

    # 4. Prepare the response
    response_data = {
        "blocked": is_blocked,
        "reason": reason,
        "sanitizedOutput": sanitized_text if not is_blocked else None,
        "confidence": round(confidence_score, 4) # Round to 4 decimal places
    }

    # 5. Log blocked attempts (For the system administrator)
    if is_blocked:
        print(f"SECURITY ALERT: Blocked content from {user_id}. Reason: {reason}")
    
    # 6. Send the result back
    return jsonify(response_data), 200

if __name__ == '__main__':
    app.run(debug=True, port=5000)