#!/usr/bin/env python3
"""Teste local sem rede para os principais invariantes do plugin."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

from dashboard_server import App
from http.server import ThreadingHTTPServer


HERE = Path(__file__).resolve().parent
CLI = HERE / "prospector.py"
PUB = HERE / "publicar.py"


def run(*args: str) -> None:
    subprocess.run([sys.executable, str(CLI), *args], check=True, capture_output=True, text=True)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="prospector-test-") as tmp:
        root = Path(tmp)
        run("init", "--workspace", str(root))
        leads = [{
            "nome": "Clínica Exemplo", "nicho": "clínica", "cidade": "Campinas",
            "nota": 4.9, "avaliacoes": 127, "email": "contato@example.test",
            "whatsapp": "5511999999999", "siteAntigo": "https://example.com",
            "motivo": "Layout datado e CTA ausente", "status": "novo",
            "fontes": ["https://example.com"],
        }]
        inp = root / "input.json"
        inp.write_text(json.dumps(leads, ensure_ascii=False), encoding="utf-8")
        run("upsert", "--workspace", str(root), "--input", str(inp))
        site = root / "sites" / "clinica-exemplo"
        site.mkdir(parents=True)
        (site / "index.html").write_text('<!doctype html><html><head><meta name="robots" content="noindex,nofollow,noarchive"></head><body><h1>Clínica Exemplo</h1><img src="data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=="></body></html>', encoding="utf-8")
        run("editor", "--workspace", str(root), "--slug", "clinica-exemplo")
        run("comparar", "--workspace", str(root))
        run("capa", "--workspace", str(root), "--slug", "clinica-exemplo")
        run("fila", "--workspace", str(root), "--slug", "clinica-exemplo")
        subprocess.run([sys.executable, str(PUB), "--workspace", str(root), "--dry-run"], check=True, capture_output=True, text=True)
        expected = ["prospector.db", "leads.csv", "leads.json", "dashboard.html", "comparar.html", "fila-publicacao.json", "sites/clinica-exemplo/editor.html", "sites/clinica-exemplo/proposta.html"]
        missing = [x for x in expected if not (root / x).exists()]
        if missing:
            raise AssertionError(f"Arquivos ausentes: {missing}")
        if "PROSPECTOR-EDITOR-START" not in (site / "editor.html").read_text(encoding="utf-8"):
            raise AssertionError("Editor não foi injetado")
        if "noindex" not in (site / "proposta.html").read_text(encoding="utf-8"):
            raise AssertionError("Capa sem noindex")
        App.root = root
        server = ThreadingHTTPServer(("127.0.0.1", 0), App)
        thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            request = urllib.request.Request(base + "/api/leads/clinica-exemplo", data=b'{"status":"redesenhado"}', headers={"Content-Type": "application/json"}, method="PATCH")
            urllib.request.urlopen(request, timeout=3).read()
            fetched = json.loads(urllib.request.urlopen(base + "/api/leads", timeout=3).read())
            if fetched[0]["status"] != "redesenhado":
                raise AssertionError("Dashboard não persistiu alteração")
        finally:
            server.shutdown(); server.server_close(); thread.join(timeout=2)
    print("OK: pipeline local validado")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
