from flask import Flask, request
import requests

load_balancer = Flask(__name__)

targets = ["http://127.0.0.1:5000", "http://127.0.0.1:5001"]
index = 0

@load_balancer.route("/", methods=["GET", "POST"])
def balance():
    global index
    target = targets[index]
    index = (index + 1) % len(targets)

    resp = requests.request(
        method=request.method,
        url=target,
        data=request.get_data(),
        headers={k: v for k, v in request.headers if k.lower() != "host"},
        allow_redirects=False,
    )
    return (resp.content, resp.status_code, resp.headers.items())

if __name__ == "__main__":
    load_balancer.run(host="0.0.0.0", port=3000)