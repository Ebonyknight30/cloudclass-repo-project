from flask import Flask, request, jsonify, redirect, url_for
import os, time, socket, shutil
from datetime import datetime

app = Flask(__name__)

START_TIME = time.time()
NOTES = []  # in-memory (ephemeral) notes storage

def cpu_usage_percent():
    with open("/proc/stat", "r") as f:
        cpu_line_1 = f.readline()
    time.sleep(0.15)
    with open("/proc/stat", "r") as f:
        cpu_line_2 = f.readline()

    def parse(line):
        parts = list(map(int, line.split()[1:]))
        idle = parts[3]
        total = sum(parts)
        return idle, total

    idle1, total1 = parse(cpu_line_1)
    idle2, total2 = parse(cpu_line_2)

    idle_delta = idle2 - idle1
    total_delta = total2 - total1

    if total_delta == 0:
        return 0.0

    return round(100 * (1 - idle_delta / total_delta), 1)


def memory_info_mb():
    mem_total = mem_free = 0
    with open("/proc/meminfo", "r") as f:
        for line in f:
            if line.startswith("MemTotal"):
                mem_total = int(line.split()[1]) / 1024
            elif line.startswith("MemAvailable"):
                mem_free = int(line.split()[1]) / 1024
    return {
        "total": round(mem_total, 1),
        "used": round(mem_total - mem_free, 1),
        "free": round(mem_free, 1),
    }

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

@app.get("/vitals")
def vitals():
    uptime_s = int(time.time() - START_TIME)
    hostname = socket.gethostname()
    cpu = cpu_usage_percent()
    mem = memory_info_mb()

    disk = shutil.disk_usage(os.getcwd())
    disk_total = round(disk.total / (1024**3), 2)
    disk_used = round(disk.used / (1024**3), 2)
    disk_free = round(disk.free / (1024**3), 2)

    return f"""
    <html>
      <head><title>Server Vitals</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>Server Vitals</h1>
        <p><a href="/">← Back to Home</a></p>

        <h2>System</h2>
        <ul>
          <li><b>Hostname:</b> {hostname}</li>
          <li><b>Uptime:</b> {uptime_s} seconds</li>
          <li><b>CPU Usage:</b> {cpu}%</li>
        </ul>

        <h2>Memory (MB)</h2>
        <ul>
          <li><b>Total:</b> {mem["total"]}</li>
          <li><b>Used:</b> {mem["used"]}</li>
          <li><b>Free:</b> {mem["free"]}</li>
        </ul>

        <h2>Disk (GB)</h2>
        <ul>
          <li><b>Total:</b> {disk_total}</li>
          <li><b>Used:</b> {disk_used}</li>
          <li><b>Free:</b> {disk_free}</li>
        </ul>

        <p style="color:#666;">
          This page demonstrates an additional product feature providing
          lightweight server diagnostics for cloud deployments.
        </p>
      </body>
    </html>
    """

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