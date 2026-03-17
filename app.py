from flask import Flask, request, jsonify, redirect, url_for
import os, time, socket, shutil, sqlite3, json
from datetime import datetime

app = Flask(__name__)

START_TIME = time.time()
DB_PATH = os.getenv("DB_PATH", "notes.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            content TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        service_type TEXT NOT NULL,
        description TEXT,
        status TEXT NOT NULL,
        created_at TEXT NOT NULL,
        completed_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def db_connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_all_notes():
    conn = db_connect()
    rows = conn.execute(
        "SELECT id, content, created_at FROM notes ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return rows

def insert_note(content: str):
    conn = db_connect()
    conn.execute(
        "INSERT INTO notes (content, created_at) VALUES (?, ?)",
        (content, datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"))
    )
    conn.commit()
    conn.close()

def delete_note(note_id: int):
    conn = db_connect()
    conn.execute("DELETE FROM notes WHERE id = ?", (note_id,))
    conn.commit()
    conn.close()

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

def get_notes_summary(limit=5):
    """
    Returns (total_count, last_notes_list).
    Uses your existing DB helpers if present.
    """
    conn = db_connect()
    total = conn.execute("SELECT COUNT(*) AS c FROM notes").fetchone()["c"]
    rows = conn.execute(
        "SELECT id, content, created_at FROM notes ORDER BY id DESC LIMIT ?",
        (limit,)
    ).fetchall()
    conn.close()
    last_notes = [
        {"id": r["id"], "content": r["content"], "created_at": r["created_at"]}
        for r in rows
    ]
    return total, last_notes


def generate_report_data():
    """
    Serverless-style: compute on demand, no stored in-memory state.
    """
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    hostname = socket.gethostname()
    uptime_s = int(time.time() - START_TIME)

    # Notes summary from DB
    total_notes, last_notes = get_notes_summary(limit=5)

    # Vitals snapshot (no external libs)
    # If you already have cpu_usage_percent() and memory_info_mb(), use them.
    cpu = cpu_usage_percent() if "cpu_usage_percent" in globals() else None
    mem = memory_info_mb() if "memory_info_mb" in globals() else None

    disk = shutil.disk_usage(os.getcwd())
    disk_gb = {
        "total": round(disk.total / (1024**3), 2),
        "used": round(disk.used / (1024**3), 2),
        "free": round(disk.free / (1024**3), 2),
    }

    return {
        "generated_at": now,
        "hostname": hostname,
        "uptime_seconds": uptime_s,
        "notes": {
            "total": total_notes,
            "last_5": last_notes,
        },
        "vitals": {
            "cpu_percent": cpu,
            "memory_mb": mem,
            "disk_gb": disk_gb,
        },
        "app_name": os.getenv("APP_NAME", "Internal Utility Service"),
    }


def get_all_services():
    conn = db_connect()
    rows = conn.execute("""
        SELECT id, service_type, description, status, created_at, completed_at
        FROM services
        ORDER BY id DESC
    """).fetchall()
    conn.close()
    return rows


def get_service_by_id(service_id: int):
    conn = db_connect()
    row = conn.execute("""
        SELECT id, service_type, description, status, created_at, completed_at
        FROM services
        WHERE id = ?
    """, (service_id,)).fetchone()
    conn.close()
    return row


def insert_service(service_type: str, description: str):
    conn = db_connect()
    conn.execute("""
        INSERT INTO services (service_type, description, status, created_at, completed_at)
        VALUES (?, ?, ?, ?, ?)
    """, (
        service_type,
        description,
        "pending",
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC"),
        None
    ))
    conn.commit()
    conn.close()


def update_service_status(service_id: int, new_status: str):
    completed_at = None
    if new_status == "completed":
        completed_at = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    conn = db_connect()
    conn.execute("""
        UPDATE services
        SET status = ?, completed_at = ?
        WHERE id = ?
    """, (new_status, completed_at, service_id))
    conn.commit()
    conn.close()


def delete_service(service_id: int):
    conn = db_connect()
    conn.execute("DELETE FROM services WHERE id = ?", (service_id,))
    conn.commit()
    conn.close()

@app.get("/")
def home():
    uptime_s = int(time.time() - START_TIME)
    hostname = socket.gethostname()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    app_name = os.getenv("APP_NAME", "Internal Utility Service")
    notes = get_all_notes()

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
           {''.join(f"<li>{n['content']} <a href='/delete/{n['id']}' style='color:#c00; text-decoration:none;'>[delete]</a></li>" for n in notes)
          if notes else "<li><i>No notes yet.</i></li>"}
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
    notes = get_all_notes()
    return jsonify(notes=[
        {"id": n["id"], "content": n["content"], "created_at": n["created_at"]}
        for n in notes
    ])

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
        insert_note(note[:200])  # tiny safety limit
    return redirect(url_for("home"))

@app.get("/delete/<int:note_id>")
def delete_note_route(note_id: int):
    delete_note(note_id)
    return redirect(url_for("home"))


@app.get("/report.json")
def report_json():
    return jsonify(generate_report_data())


@app.get("/report")
def report():
    data = generate_report_data()
    notes_html = "".join(
        f"<li>#{n['id']} — {n['content']} <span style='color:#666;'>({n['created_at']})</span></li>"
        for n in data["notes"]["last_5"]
    ) or "<li><i>No notes found.</i></li>"

    mem = data["vitals"]["memory_mb"]
    cpu = data["vitals"]["cpu_percent"]
    disk = data["vitals"]["disk_gb"]

    return f"""
    <html>
      <head><title>On-Demand Report</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>On-Demand Report</h1>
        <p><a href="/">← Back</a></p>

        <h2>Metadata</h2>
        <ul>
          <li><b>Generated At:</b> {data["generated_at"]}</li>
          <li><b>App:</b> {data["app_name"]}</li>
          <li><b>Hostname:</b> {data["hostname"]}</li>
          <li><b>Uptime:</b> {data["uptime_seconds"]} seconds</li>
        </ul>

        <h2>Notes Summary</h2>
        <p><b>Total Notes:</b> {data["notes"]["total"]}</p>
        <h3>Last 5 Notes</h3>
        <ul>{notes_html}</ul>

        <h2>Vitals Snapshot</h2>
        <ul>
          <li><b>CPU:</b> {cpu if cpu is not None else "N/A"}%</li>
          <li><b>Memory:</b> {f"Total {mem['total']} MB, Used {mem['used']} MB, Free {mem['free']} MB" if mem else "N/A"}</li>
          <li><b>Disk:</b> Total {disk["total"]} GB, Used {disk["used"]} GB, Free {disk["free"]} GB</li>
        </ul>

        <p style="color:#666;">
          This feature demonstrates a <b>serverless-style</b> report generator: it executes <b>on demand</b>,
          is <b>stateless</b>, and pulls data from the database and system snapshot only when invoked.
        </p>

        <p>JSON output: <a href="/report.json">/report.json</a></p>
      </body>
    </html>
    """

@app.get("/services")
def services():
    services = get_all_services()

    rows_html = "".join(f"""
        <tr>
            <td>{s['id']}</td>
            <td>{s['service_type']}</td>
            <td>{s['description'] or ''}</td>
            <td>{s['status']}</td>
            <td>{s['created_at']}</td>
            <td>{s['completed_at'] or '-'}</td>
            <td>
                <a href="/services/{s['id']}">View</a> |
                <a href="/services/delete/{s['id']}" style="color:#c00;">Delete</a>
            </td>
        </tr>
    """ for s in services)

    if not rows_html:
        rows_html = """
        <tr>
            <td colspan="7"><i>No service requests yet.</i></td>
        </tr>
        """

    return f"""
    <html>
      <head><title>Service Management</title></head>
      <body style="font-family: sans-serif; max-width: 1000px; margin: 40px auto;">
        <h1>Service Management System</h1>
        <p><a href="/">← Back to Home</a></p>

        <h2>Create Service Request</h2>
        <form method="POST" action="/services/add">
          <label><b>Service Type:</b></label><br/>
          <select name="service_type">
            <option value="Generate Report">Generate Report</option>
            <option value="Run Vitals Check">Run Vitals Check</option>
            <option value="Export Notes">Export Notes</option>
            <option value="Archive Notes">Archive Notes</option>
          </select>
          <br/><br/>

          <label><b>Description:</b></label><br/>
          <input name="description" style="width: 70%;" placeholder="Optional description..." />
          <br/><br/>

          <button type="submit">Create Request</button>
        </form>

        <hr/>

        <h2>All Service Requests</h2>
        <table border="1" cellpadding="8" cellspacing="0" style="border-collapse: collapse; width: 100%;">
          <tr>
            <th>ID</th>
            <th>Service Type</th>
            <th>Description</th>
            <th>Status</th>
            <th>Created At</th>
            <th>Completed At</th>
            <th>Actions</th>
          </tr>
          {rows_html}
        </table>
      </body>
    </html>
    """

@app.post("/services/add")
def add_service():
    service_type = (request.form.get("service_type") or "").strip()
    description = (request.form.get("description") or "").strip()

    if service_type:
        insert_service(service_type, description[:300])

    return redirect(url_for("services"))


@app.get("/services/<int:service_id>")
def service_detail(service_id: int):
    service = get_service_by_id(service_id)

    if not service:
        return "<h1>Service request not found.</h1>", 404

    return f"""
    <html>
      <head><title>Service Request #{service['id']}</title></head>
      <body style="font-family: sans-serif; max-width: 760px; margin: 40px auto;">
        <h1>Service Request #{service['id']}</h1>
        <p><a href="/services">← Back to Service Management</a></p>

        <ul>
          <li><b>Service Type:</b> {service['service_type']}</li>
          <li><b>Description:</b> {service['description'] or '-'}</li>
          <li><b>Status:</b> {service['status']}</li>
          <li><b>Created At:</b> {service['created_at']}</li>
          <li><b>Completed At:</b> {service['completed_at'] or '-'}</li>
        </ul>

        <h2>Update Status</h2>
        <form method="POST" action="/services/update/{service['id']}">
          <select name="status">
            <option value="pending">pending</option>
            <option value="in_progress">in_progress</option>
            <option value="completed">completed</option>
            <option value="failed">failed</option>
          </select>
          <button type="submit">Update Status</button>
        </form>

        <p style="margin-top: 20px;">
          <a href="/services/delete/{service['id']}" style="color:#c00;">Delete this request</a>
        </p>
      </body>
    </html>
    """


@app.post("/services/update/<int:service_id>")
def service_update(service_id: int):
    new_status = (request.form.get("status") or "").strip()

    if new_status in ["pending", "in_progress", "completed", "failed"]:
        update_service_status(service_id, new_status)

    return redirect(url_for("service_detail", service_id=service_id))


@app.get("/services/delete/<int:service_id>")
def service_delete_route(service_id: int):
    delete_service(service_id)
    return redirect(url_for("services"))





if __name__ == "__main__":
    init_db()
    # Bind to 0.0.0.0 so it works in containers and remote IDEs
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port)