from flask import Flask, request, jsonify, redirect, url_for
import os, time, socket
from datetime import datetime

app = Flask(__name__)

START_TIME = time.time()
NOTES = []  # in-memory (ephemeral) notes storage

@app.get("/")
def home():
    uptime_s = int(time.time() - START_TIME)
    hostname = socket.gethostname()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    app_name = os.getenv("APP_NAME", "Internal Utility Service")

    return f"""
    <html>
      <head><title>{app_name}</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>{app_name}</h1>
        <p><b>Status:</b> OK</p>
        <p><b>Time:</b> {now}</p>
        <p><b>Hostname:</b> {hostname}</p>
        <p><b>Uptime:</b> {uptime_s} seconds</p>

        <hr/>
        <h2>Notes</h2>
        <form method="POST" action="/add">
          <input name="note" placeholder="Add a note..." style="width: 70%;" />
          <button type="submit">Add</button>
        </form>

        <ul>
          {''.join(f"<li>{n}</li>" for n in NOTES[::-1]) if NOTES else "<li><i>No notes yet.</i></li>"}
        </ul>

        <p style="color:#666;">
          Notes are stored <b>in memory</b> and will reset if the container/app restarts.
        </p>

        <p>
          <a href="/health">/health</a> • <a href="/notes">/notes</a>
        </p>
      </body>
    </html>
    """

@app.get("/health")
def health():
    return jsonify(status="ok")

@app.get("/notes")
def get_notes():
    return jsonify(notes=NOTES)

@app.post("/add")
def add_note():
    note = (request.form.get("note") or "").strip()
    if note:
        NOTES.append(note[:200])  # tiny safety limit
    return redirect(url_for("home"))

if __name__ == "__main__":
    # Bind to 0.0.0.0 so it works in containers and remote IDEs
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)