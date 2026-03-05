from flask import Flask

app = Flask(__name__)

@app.get("/")
def home():
    return "Hello from app2 (port 5001)\n"

if __name__ == "__main__":
    app.run(port=5001, debug=False)