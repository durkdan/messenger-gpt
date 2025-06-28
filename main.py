from flask import Flask, request, jsonify
from apscheduler.schedulers.background import BackgroundScheduler
import datetime
import requests

app = Flask(__name__)

# Simulated in-memory storage
memory = {
    "last_ping": None,
    "weather": None,
    "events": []
}

def fetch_weather():
    # Placeholder for actual weather fetching logic
    memory["weather"] = {
        "temperature": "25C",
        "condition": "Sunny",
        "fetched_at": datetime.datetime.utcnow().isoformat()
    }
    print("Weather updated:", memory["weather"])

def schedule_event(event):
    memory["events"].append(event)
    print("Scheduled event:", event)

@app.route("/")
def index():
    return "Hello from Flask App!"

@app.route("/ping", methods=["POST"])
def ping():
    data = request.get_json()
    memory["last_ping"] = datetime.datetime.utcnow().isoformat()
    return jsonify({"message": "Ping received", "timestamp": memory["last_ping"]})

@app.route("/weather")
def get_weather():
    return jsonify(memory.get("weather", {}))

@app.route("/events", methods=["POST"])
def add_event():
    event = request.get_json()
    schedule_event(event)
    return jsonify({"message": "Event scheduled"})

@app.route("/events")
def list_events():
    return jsonify(memory.get("events", []))

# Schedule weather updates every hour
scheduler = BackgroundScheduler()
scheduler.add_job(fetch_weather, "interval", hours=1)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
