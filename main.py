from flask import Flask, request
import requests
import os

app = Flask(__name__)

HUGGINGFACE_API_KEY = os.getenv("shh")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")

def get_huggingface_reply(message):
    url = "https://api-inference.huggingface.co/models/microsoft/DialoGPT-medium"
    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "inputs": message
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        output = response.json()
        if isinstance(output, list) and len(output) > 0:
            if "generated_text" in output[0]:
                return output[0]["generated_text"]
            elif isinstance(output[0], dict) and "generated_text" in output[0]:
                return output[0]["generated_text"]
        elif isinstance(output, dict) and "generated_text" in output:
            return output["generated_text"]
        return "🤖 Model responded, but no text was generated."
    else:
        return "It didn't work, try again. The model didn't meet your reply/question."

@app.route("/", methods=["GET"])
def home():
    return "✅ Bot is online!"

@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == VERIFY_TOKEN:
            return challenge, 200
        else:
            return "❌ Verification failed", 403

    elif request.method == "POST":
        data = request.get_json()

        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event["sender"]["id"]
                message = messaging_event.get("message", {}).get("text")

                if message:
                    try:
                        # Get Hugging Face response
                        reply = get_huggingface_reply(message)

                    except Exception as e:
                        print(f"❌ Error: {e}")
                        reply = "It didn't work, try again. The model didn't meet your reply/question."

                    # Send message back to user via Send API
                    send_url = "https://graph.facebook.com/v18.0/me/messages"
                    params = {"access_token": PAGE_ACCESS_TOKEN}
                    headers = {"Content-Type": "application/json"}
                    payload = {
                        "recipient": {"id": sender_id},
                        "message": {"text": reply}
                    }
                    requests.post(send_url, params=params, headers=headers, json=payload)

        return "✅ Message received", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
