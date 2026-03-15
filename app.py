from flask import Flask, request, render_template_string, Response
from twilio.twiml.messaging_response import MessagingResponse
from twilio.rest import Client
from datetime import datetime
import sqlite3
import json
import re
import os

app = Flask(__name__)

# ========== SQLite Database (replaces Replit DB) ==========

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'institrack.db')

def init_db():
    """Initialize SQLite database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS kv_store (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    ''')
    conn.commit()
    conn.close()

def db_get(key, default=None):
    """Get a value from the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM kv_store WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default

def db_set(key, value):
    """Set a value in the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR REPLACE INTO kv_store (key, value) VALUES (?, ?)",
        (key, str(value))
    )
    conn.commit()
    conn.close()

def db_delete(key):
    """Delete a key from the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM kv_store WHERE key = ?", (key,))
    conn.commit()
    conn.close()

def db_keys():
    """Get all keys from the database"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM kv_store")
    keys = [row[0] for row in cursor.fetchall()]
    conn.close()
    return keys

def db_keys_starting_with(prefix):
    """Get all keys starting with a prefix"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT key FROM kv_store WHERE key LIKE ?", (prefix + '%',))
    keys = [row[0] for row in cursor.fetchall()]
    conn.close()
    return keys

# Initialize the database on startup
init_db()

# ========== Twilio Configuration ==========

TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_NUMBER = os.environ.get('TWILIO_PHONE_NUMBER', 'whatsapp:+14155238886')

# Initialize Twilio client if credentials exist
twilio_client = None
if TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN:
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

# Store user states in memory (for conversation flow)
user_state = {}
user_bus = {}
user_stop = {}

# Demo bus data
bus_stops = {
    "7": ["Stop A", "Stop B", "Stop C", "Stop D"],
    "12": ["Stop X", "Stop Y", "Stop Z"],
    "5": ["Stop M", "Stop N", "Stop O"]
}

# ========== Threshold Configuration (seconds) ==========
route_thresholds = {
    "7": {"Stop A>Stop B": 20, "Stop B>Stop C": 20, "Stop C>Stop D": 20},
    "12": {"Stop X>Stop Y": 20, "Stop Y>Stop Z": 20},
    "5": {"Stop M>Stop N": 20, "Stop N>Stop O": 20}
}

active_buses = {}

# ========== NLP Helper Functions ==========

def detect_intent(message):
    """Detects the user's intent from their message."""
    message = message.lower()
    if "reset" in message or "start over" in message or "new bus" in message:
        return "reset"
    elif "status" in message or "my details" in message or "what bus am i on" in message:
        return "status"
    return "unknown"

def extract_bus_number(message):
    """Extracts the bus number from the user's message using regex."""
    message = message.lower()
    for bus_num in bus_stops.keys():
        if re.search(r'\b' + re.escape(bus_num) + r'\b', message):
            return bus_num
    match = re.search(r'\d+', message)
    if match:
        potential_bus_num = match.group(0)
        if potential_bus_num in bus_stops:
            return potential_bus_num
    return None

def extract_stop_choice(message, stops):
    """Extracts the stop choice from the user's message."""
    message = message.lower()
    try:
        match_num = re.search(r'\b(1[0]?|[1-9])\b', message)
        if match_num:
            stop_index = int(match_num.group(1)) - 1
            if 0 <= stop_index < len(stops):
                return stop_index + 1

        for i, stop in enumerate(stops):
            if stop.lower() in message:
                return i + 1

        if "stop" in message or "station" in message:
            pass

    except ValueError:
        pass

    return None


# ========== Routes ==========

@app.route("/")
def home():
    return render_template_string(open('bus_signal_webpage.html').read())

@app.route("/test", methods=["GET"])
def test():
    """Test endpoint to verify server is running"""
    return {"status": "Server is running!", "url": "Your server is accessible"}

@app.route("/users")
def view_users():
    """View all registered users with better interface"""
    try:
        registered_users = []
        all_keys = db_keys()
        user_phones = set()

        for key in all_keys:
            if key.startswith('user_') and key.endswith('_state'):
                phone = key.replace('user_', '').replace('_state', '')
                if db_get(key) == 'registered':
                    user_phones.add(phone)

        for phone in user_phones:
            bus_num = db_get(f"user_{phone}_bus", "Not found")
            stop_name = db_get(f"user_{phone}_stop", "Not found")
            timestamp = db_get(f"user_{phone}_timestamp", "Not found")

            registered_users.append({
                "phone": phone,
                "bus": bus_num,
                "stop": stop_name,
                "time": timestamp
            })

        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>WhatsApp Bot Users</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                table { border-collapse: collapse; width: 100%; margin-top: 20px; }
                th, td { border: 1px solid #ddd; padding: 12px; text-align: left; }
                th { background-color: #f2f2f2; font-weight: bold; }
                tr:nth-child(even) { background-color: #f9f9f9; }
                .stats { background: #e7f3ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
                .btn { background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
            </style>
        </head>
        <body>
            <h1>🚌 InstiTrack - Registered Users</h1>
        """

        if not registered_users:
            html += "<div class='stats'>No registered users found</div></body></html>"
            return html

        total_users = len(registered_users)
        bus_counts = {}
        for user in registered_users:
            bus = user['bus']
            bus_counts[bus] = bus_counts.get(bus, 0) + 1

        html += f"""
            <div class='stats'>
                <h3>📊 Statistics</h3>
                <p><strong>Total Registered Users:</strong> {total_users}</p>
                <p><strong>Buses in use:</strong> {', '.join([f'Bus {bus} ({count} users)' for bus, count in bus_counts.items()])}</p>
            </div>

            <a href='/users/csv' class='btn'>📥 Download CSV</a>
            <a href='/users/reset' class='btn' style='background: #f44336; margin-left: 10px;' onclick='return confirm("Are you sure you want to delete ALL user data? This cannot be undone!")'>🗑️ Reset All Data</a>

            <table>
                <tr>
                    <th>📱 Phone Number</th>
                    <th>🚌 Bus Number</th>
                    <th>🚏 Bus Stop</th>
                    <th>📅 Registration Time</th>
                </tr>
        """

        for user in registered_users:
            html += f"<tr><td>+{user['phone']}</td><td>{user['bus']}</td><td>{user['stop']}</td><td>{user['time']}</td></tr>"

        html += "</table></body></html>"
        return html

    except Exception as e:
        return f"Error: {str(e)}"

@app.route("/users/csv")
def download_csv():
    """Download users data as CSV file"""
    try:
        registered_users = []
        all_keys = db_keys()
        user_phones = set()

        for key in all_keys:
            if key.startswith('user_') and key.endswith('_state'):
                phone = key.replace('user_', '').replace('_state', '')
                if db_get(key) == 'registered':
                    user_phones.add(phone)

        for phone in user_phones:
            bus_num = db_get(f"user_{phone}_bus", "Not found")
            stop_name = db_get(f"user_{phone}_stop", "Not found")
            timestamp = db_get(f"user_{phone}_timestamp", "Not found")

            registered_users.append({
                "phone": phone,
                "bus": bus_num,
                "stop": stop_name,
                "time": timestamp
            })

        csv_content = "Phone Number,Bus Number,Bus Stop,Registration Time\n"
        for user in registered_users:
            csv_content += f"+{user['phone']},{user['bus']},{user['stop']},{user['time']}\n"

        return Response(
            csv_content,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=whatsapp_users.csv"}
        )

    except Exception as e:
        return f"Error generating CSV: {str(e)}"

@app.route("/users/reset")
def reset_users():
    """Reset all user data"""
    try:
        all_keys = db_keys()
        deleted_count = 0
        for key in all_keys:
            if key.startswith('user_'):
                db_delete(key)
                deleted_count += 1

        user_state.clear()
        user_bus.clear()
        user_stop.clear()

        return f"""
        <html>
        <head><title>Reset Complete</title></head>
        <body style="font-family: Arial, sans-serif; margin: 20px;">
            <h1>✅ Data Reset Complete</h1>
            <p>Deleted {deleted_count} database entries.</p>
            <p>All user registrations have been cleared.</p>
            <a href="/users" style="background: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">← Back to Users Page</a>
        </body>
        </html>
        """

    except Exception as e:
        return f"Error resetting data: {str(e)}"

@app.route("/bus-signal", methods=["POST"])
def bus_signal():
    """Receive HTTP signal from device/webpage when bus reaches a location"""
    try:
        data = request.get_json()
        bus_num = str(data.get('bus_number'))
        location = data.get('location')

        if not bus_num or not location:
            return {"status": "error", "message": "bus_number and location required"}, 400

        # --- Duplicate Detection ---
        is_duplicate = False
        bus_state = active_buses.get(bus_num, {})
        if bus_state.get("last_stop") == location:
            is_duplicate = True

        # --- Determine stop index and next stop ---
        stops = bus_stops.get(bus_num, [])
        current_stop_index = -1
        next_stop = None
        threshold_seconds = 20

        if stops and location in stops:
            current_stop_index = stops.index(location)
            if current_stop_index < len(stops) - 1:
                next_stop = stops[current_stop_index + 1]
                threshold_key = f"{location}>{next_stop}"
                thresholds = route_thresholds.get(bus_num, {})
                threshold_seconds = thresholds.get(threshold_key, 20)

        # --- Update active bus state ---
        active_buses[bus_num] = {
            "last_stop": location,
            "last_stop_index": current_stop_index,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        # --- Notify users (skip if duplicate) ---
        all_keys = db_keys()
        notified_users = []
        failed_users = []

        if not is_duplicate:
            for key in all_keys:
                if key.startswith('user_') and key.endswith('_bus'):
                    phone_raw = key[5:-4]
                    phone_id = phone_raw.lstrip('+')

                    user_bus_num = db_get(key)
                    user_stop_name = db_get(f"user_{phone_raw}_stop")
                    if user_stop_name is None:
                        user_stop_name = db_get(f"user_{phone_id}_stop")

                    norm_user_bus = str(user_bus_num).strip().lstrip('0')
                    norm_bus_num = str(bus_num).strip().lstrip('0')
                    norm_user_stop = str(user_stop_name).strip().lower() if user_stop_name else ""
                    norm_location = str(location).strip().lower()

                    bus_match = norm_user_bus == norm_bus_num
                    stop_match = norm_user_stop == norm_location

                    if bus_match and stop_match:
                        if twilio_client:
                            try:
                                twilio_phone = '+' + phone_id
                                message = twilio_client.messages.create(
                                    from_=TWILIO_WHATSAPP_NUMBER,
                                    body=f"\U0001f68c Bus Alert!\n\nBus {bus_num} has reached {location}!\n\n\u2705 Your stop is coming up.",
                                    to=f"whatsapp:{twilio_phone}"
                                )
                                notified_users.append(phone_raw)
                            except Exception as e:
                                failed_users.append({"phone": phone_raw, "error": str(e)})
                        else:
                            notified_users.append(phone_raw)

        return {
            "status": "success",
            "message": f"Bus {bus_num} reached {location}",
            "stop_confirmed": location,
            "next_stop": next_stop,
            "threshold_seconds": threshold_seconds if next_stop else 0,
            "is_last_stop": next_stop is None and current_stop_index >= 0,
            "is_duplicate": is_duplicate,
            "notified_count": len(notified_users),
            "notified_users": notified_users,
            "failed_count": len(failed_users),
            "failed_users": failed_users if failed_users else None
        }, 200

    except Exception as e:
        return {"status": "error", "message": str(e)}, 500

@app.route("/bus-status/<bus_number>", methods=["GET"])
def bus_status(bus_number):
    state = active_buses.get(bus_number)
    if state:
        return {"status": "active", "bus": bus_number, **state}, 200
    return {"status": "inactive", "bus": bus_number}, 200

@app.route("/whatsapp", methods=["POST"])
def whatsapp():
    sender = request.form.get('From')
    body = request.form.get('Body')

    if not sender or not body:
        resp = MessagingResponse()
        resp.message("Error: Missing sender or message body")
        return str(resp)

    original_msg = body.strip()
    msg = original_msg.lower()

    resp = MessagingResponse()
    reply = ""

    intent = detect_intent(msg)

    if sender not in user_state:
        user_state[sender] = "ask_bus"
        reply = "👋 Hi! Welcome to InstiTrack.\n\nWhat's your bus number?"

    elif user_state[sender] == "ask_bus":
        if intent == 'reset':
            reply = "🔄 Let's start fresh! What's your bus number?"
        else:
            bus_num = extract_bus_number(original_msg)

            if bus_num:
                user_bus[sender] = bus_num
                user_state[sender] = "ask_stop"
                stops_list = "\n".join([f"{i+1}. {stop}" for i, stop in enumerate(bus_stops[bus_num])])
                reply = f"✅ Great! Bus {bus_num} it is.\n\n{stops_list}\n\nWhich stop is yours?"
            else:
                available_buses = ", ".join(bus_stops.keys())
                reply = f"❌ I couldn't find that bus number.\n\nAvailable buses are: {available_buses}"

    elif user_state[sender] == "ask_stop":
        if intent == 'reset':
            user_state[sender] = "ask_bus"
            reply = "🔄 Starting over! What's your bus number?"
        else:
            bus_num = user_bus.get(sender)
            if bus_num is None:
                user_state[sender] = "ask_bus"
                reply = "Something went wrong. Let's start over. What's your bus number?"
            else:
                stops = bus_stops.get(bus_num)
                if stops is None:
                    user_state[sender] = "ask_bus"
                    reply = "Something went wrong with the bus number. Let's start over. What's your bus number?"
                else:
                    stop_choice = extract_stop_choice(original_msg, stops)

                    if stop_choice:
                        chosen_stop = stops[stop_choice - 1]
                        user_stop[sender] = chosen_stop
                        user_state[sender] = "registered"

                        # Save to SQLite database
                        phone_clean = sender.replace("whatsapp:", "").strip("+") if sender else ""
                        db_set(f"user_{phone_clean}_bus", bus_num)
                        db_set(f"user_{phone_clean}_stop", chosen_stop)
                        db_set(f"user_{phone_clean}_state", "registered")
                        db_set(f"user_{phone_clean}_timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))

                        reply = f"🎉 Perfect! You're all set!\n\n📋 Your Registration:\n🚌 Bus: {bus_num}\n🚏 Stop: {chosen_stop}\n\n✅ You'll get notifications when your bus is approaching your stop!"
                    else:
                        stops_list = "\n".join([f"{i+1}. {stop}" for i, stop in enumerate(stops)])
                        reply = f"❌ I didn't understand which stop you meant.\n\nPlease choose from:\n{stops_list}"

    elif user_state[sender] == "registered":
        if intent == 'reset':
            user_state[sender] = "ask_bus"
            reply = "🔄 Let's register you again! What's your bus number?"
        elif intent == 'status':
            phone_clean = sender.replace("whatsapp:", "") if sender else ""
            bus_num = db_get(f"user_{phone_clean}_bus", "Unknown")
            stop_name = db_get(f"user_{phone_clean}_stop", "Unknown")
            reply = f"📋 Your Current Registration:\n🚌 Bus: {bus_num}\n🚏 Stop: {stop_name}\n\n✅ All set! You'll get bus alerts.\n\nSend 'reset' to change your registration."
        else:
            reply = "✅ You're already registered and will receive bus alerts!\n\nSend 'status' to see your details or 'reset' to change your registration."

    resp.message(reply)
    return str(resp)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)