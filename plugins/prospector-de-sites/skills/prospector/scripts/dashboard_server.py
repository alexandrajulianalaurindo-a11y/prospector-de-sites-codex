#!/usr/bin/env python3
"""Servidor local do dashboard com API SQLite, sem dependências externas."""

from __future__ import annotations

import argparse
import json
import mimetypes
import sqlite3
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


ALLOWED = {"nome", "email", "telefone", "whatsapp", "status", "valor", "manutencao", "obs", "contratoStatus", "pago", "docCliente", "endCliente"}
STATUSES = {"novo", "redesenhado", "publicado", "proposta", "respondeu", "fechado", "descartado", "frio"}


class App(BaseHTTPRequestHandler):
    root: Path

    def log_message(self, fmt: str, *args) -> None:
        print("dashboard:", fmt % args)

    def db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.root / "prospector.db")
        conn.row_factory = sqlite3.Row
        return conn

    def json_response(self, value, status=200) -> None:
        body = json.dumps(value, ensure_ascii=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/leads":
            db = self.db(); data = [dict(r) for r in db.execute("SELECT * FROM leads ORDER BY atualizado DESC")]; db.close(); return self.json_response(data)
        relative = "dashboard.html" if path == "/" else unquote(path.lstrip("/"))
        target = (self.root / relative).resolve()
        if self.root not in target.parents and target != self.root:
            return self.send_error(403)
        if not target.is_file():
            return self.send_error(404)
        body = target.read_bytes(); kind = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
        self.send_response(200); self.send_header("Content-Type", kind); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_PATCH(self) -> None:
        prefix = "/api/leads/"
        if not self.path.startswith(prefix):
            return self.send_error(404)
        slug = unquote(self.path[len(prefix):])
        length = int(self.headers.get("Content-Length", "0"))
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            data = {k: v for k, v in payload.items() if k in ALLOWED}
            if "status" in data and data["status"] not in STATUSES:
                raise ValueError("Status inválido")
            if not data:
                raise ValueError("Nenhum campo editável")
            sets = ",".join(f'"{k}"=?' for k in data) + ",atualizado=CURRENT_TIMESTAMP"
            db = self.db(); cur = db.execute(f"UPDATE leads SET {sets} WHERE slug=?", [*data.values(), slug]); db.commit(); db.close()
            if cur.rowcount != 1:
                return self.json_response({"erro": "Lead não encontrado"}, 404)
            return self.json_response({"ok": True})
        except Exception as exc:
            return self.json_response({"erro": str(exc)}, 400)


def main() -> int:
    p = argparse.ArgumentParser(); p.add_argument("--workspace", required=True); p.add_argument("--port", type=int, default=8765); p.add_argument("--no-browser", action="store_true"); args = p.parse_args()
    App.root = Path(args.workspace).expanduser().resolve()
    if not (App.root / "prospector.db").exists():
        raise FileNotFoundError("Execute prospector.py init primeiro")
    server = ThreadingHTTPServer(("127.0.0.1", args.port), App)
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Dashboard: {url}")
    if not args.no_browser:
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
