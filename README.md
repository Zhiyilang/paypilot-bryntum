# PayPilot Schedule — AI + PayPal aware project scheduler

A working proof-of-concept for the **PayPal "Build What's Next with AI + PayPal"**
hackathon (Bryntum prize category). It shows how a payments API changes what
you can build around scheduling: a late/unpaid phase **visibly blocks** the next
phase, and an AI suggests how to reroute the moment a payment is late.

## Why it fits the brief
- **PayPal API** — server creates real PayPal sandbox checkout orders
  (`/v2/checkout/orders`); degrades to a mock order when no credentials are set,
  so the demo runs anywhere.
- **Bryntum Scheduler** — the Gantt/timeline UI; click a phase to pay and
  unblock its dependents.
- **AI** — `/api/ai/advise` is a deterministic scheduling advisor: when a phase
  is overdue & unpaid it recommends rerouting dependents and a polite "chase
  them nicely" reminder flow (the exact warm-up idea from the Bryntum brief).

## Run
```bash
pip install -r requirements.txt
# optional: export PAYPAL_CLIENT_ID=... PAYPAL_SECRET=...  (sandbox)
python app.py
# open http://localhost:5000
```
Click a 🔒/⏳ phase → "Pay" (PayPal) → it unblocks the next phase. Click
**🤖 AI: reroute late payments** for advice.

## Demo video
≤3 min screen recording: load the board → show a blocked phase → click Pay
(PayPal mock order) → dependent unblocks → click AI advise.

## Stack
Python 3 + Flask (zero other runtime deps) · Bryntum Scheduler (CDN trial) ·
PayPal REST SDK-free calls. MIT licensed.
