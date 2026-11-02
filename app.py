"""
PayPilot Schedule — an AI + PayPal aware project scheduler.

Built for the PayPal "Build What's Next with AI + PayPal" hackathon
(Bryntum prize category). A late/unpaid phase visibly blocks the next
phase; when a payment clears (or is late) the AI suggests how to reroute.

ZERO third-party dependencies — pure Python stdlib (http.server).
PayPal calls degrade gracefully to a mock order when no sandbox
credentials are set, so the demo runs anywhere.
"""
import os
import json
import uuid
import datetime
import urllib.request
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BOARD = {
    "project": "Agency Delivery Board",
    "currency": "USD",
    "tasks": [
        {"id": "t1", "name": "Discovery & Design", "start": "2026-11-05",
         "end": "2026-11-09", "phase": 1, "amount": 200, "paid": True,
         "depends_on": None},
        {"id": "t2", "name": "Build MVP", "start": "2026-11-10",
         "end": "2026-11-16", "phase": 2, "amount": 500, "paid": False,
         "depends_on": "t1"},
        {"id": "t3", "name": "QA & Hardening", "start": "2026-11-17",
         "end": "2026-11-21", "phase": 3, "amount": 300, "paid": False,
         "depends_on": "t2"},
        {"id": "t4", "name": "Launch", "start": "2026-11-22",
         "end": "2026-11-24", "phase": 4, "amount": 250, "paid": False,
         "depends_on": "t3"},
    ],
}


def _today():
    return datetime.date.today().isoformat()


def _blocked_status(tasks):
    by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        if t["depends_on"]:
            pred = by_id.get(t["depends_on"])
            if pred and not pred["paid"]:
                t["blocked"] = True
                t["block_reason"] = f"waiting on {pred['name']} payment (${pred['amount']})"
            else:
                t["blocked"] = False
        else:
            t["blocked"] = not t["paid"]
    return tasks


def board_payload():
    tasks = _blocked_status([dict(t) for t in BOARD["tasks"]])
    return {"project": BOARD["project"], "currency": BOARD["currency"],
            "today": _today(), "tasks": tasks}


def pay_payload(task_id):
    task = next((t for t in BOARD["tasks"] if t["id"] == task_id), None)
    if not task:
        return None
    cid, secret = os.environ.get("PAYPAL_CLIENT_ID"), os.environ.get("PAYPAL_SECRET")
    if cid and secret:
        order = _create_paypal_order(cid, secret, task["amount"])
        if order:
            return {"order": order, "mock": False}
    return {"order_id": "MOCK-" + uuid.uuid4().hex[:16].upper(),
            "amount": task["amount"], "mock": True,
            "note": "set PAYPAL_CLIENT_ID/PAYPAL_SECRET for live orders"}


def confirm_pay(task_id):
    task = next((t for t in BOARD["tasks"] if t["id"] == task_id), None)
    if task:
        task["paid"] = True
    return task


def advise_payload(tasks=None, today=None):
    tasks = tasks or BOARD["tasks"]
    today = today or _today()
    late, blocked = [], []
    for t in tasks:
        if not t.get("paid"):
            if t.get("start") and t["start"] < today:
                late.append(t)
            if t.get("blocked"):
                blocked.append(t)
    advice = []
    for t in late:
        advice.append({"task": t["name"], "severity": "high",
                       "text": (f"Phase {t['phase']} '{t['name']}' (${t['amount']}) is "
                                f"overdue and unpaid. Auto-reroute dependents and send a "
                                f"polite 'chase them nicely' reminder.")})
    for t in blocked:
        advice.append({"task": t["name"], "severity": "medium",
                       "text": (f"'{t['name']}' is blocked: {t.get('block_reason','')}. "
                                f"Hold resources until the upstream payment clears.")})
    if not advice:
        advice.append({"task": "board", "severity": "ok",
                       "text": "All phases paid and unblocked. No reroute needed."})
    return {"advice": advice, "generated_at": today}


def _create_paypal_order(cid, secret, amount):
    try:
        auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
        req = urllib.request.Request(
            "https://api-m.sandbox.paypal.com/v2/checkout/orders",
            data=json.dumps({"intent": "CAPTURE",
                             "purchase_units": [{"amount": {"currency_code": "USD",
                                                           "value": str(amount)}}]}).encode(),
            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(req, timeout=20) as r:
            d = json.loads(r.read().decode())
            return {"id": d.get("id"), "status": d.get("status")}
    except Exception:
        return None


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, obj=None, html=None):
        self.send_response(code)
        if html is not None:
            body = html.encode()
            self.send_header("Content-Type", "text/html; charset=utf-8")
        else:
            body = json.dumps(obj).encode()
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path.startswith("/?"):
            try:
                with open(os.path.join(os.path.dirname(__file__),
                                       "templates", "index.html"), encoding="utf-8") as f:
                    html = f.read().replace("{{ project }}", BOARD["project"])
                self._send(200, html=html)
            except Exception as e:
                self._send(500, {"error": str(e)})
        elif self.path == "/api/board":
            self._send(200, board_payload())
        else:
            self._send(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw or b"{}")
        except Exception:
            data = {}
        if self.path == "/api/pay":
            res = pay_payload(data.get("task_id"))
            self._send(200, res if res else {"error": "unknown task"})
        elif self.path == "/api/pay/confirm":
            confirm_pay(data.get("task_id"))
            self._send(200, {"ok": True})
        elif self.path == "/api/ai/advise":
            self._send(200, advise_payload(data.get("tasks"), data.get("today")))
        else:
            self._send(404, {"error": "not found"})

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"PayPilot Schedule on http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
