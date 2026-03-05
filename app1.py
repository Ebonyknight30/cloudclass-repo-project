from flask import Flask

app = Flask(__name__)

@app.get("/")
def home():
    return "Hello from app1 (port 5000)\n"

if __name__ == "__main__":
    app.run(port=5000, debug=False)