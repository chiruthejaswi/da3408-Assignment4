"""Tiny webhook sink so you can SEE Alertmanager notifications. Run: python alert_receiver.py"""
import json
from http.server import BaseHTTPRequestHandler, HTTPServer


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
        for a in body.get("alerts", []):
            print(f"[{a['status'].upper():8}] {a['labels'].get('alertname')} - "
                  f"{a['annotations'].get('summary', '')}", flush=True)
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass


print("Listening for alerts on :5001/alert")
HTTPServer(("0.0.0.0", 5001), Handler).serve_forever()
