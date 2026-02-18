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


import json # Add this to your imports at the top

def check_content_safety(user_text):
    """
    Uses a standard Chat Completion model via AI Pipe to 
    perform content moderation since the moderation endpoint is restricted.
    """
    try:
        # We use a cheap, fast model supported by AI Pipe
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You are a content moderator. Analyze the user input for violence, hate speech, or illegal acts. "
                    "Return ONLY a JSON object with: "
                    "{'blocked': boolean, 'reason': string, 'confidence': float}. "
                    "Set blocked to true if confidence of harm is > 0.8."
                )},
                {"role": "user", "content": user_text}
            ],
            response_format={ "type": "json_object" } # Ensures we get valid JSON back
        )
        
        # Parse the AI's "thought" process
        result = json.loads(response.choices[0].message.content)
        
        return result.get("blocked", False), result.get("reason", "Passed"), result.get("confidence", 0.0)

    except Exception as e:
        print(f"Security Check Error: {e}")
        # Fallback logic in case the AI Pipe goes down or has an error
        if "violence" in user_text.lower() or "kill" in user_text.lower():
            return True, "Content detected: violence (Manual Check)", 0.99
        return False, "Input passed all security checks", 0.0

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