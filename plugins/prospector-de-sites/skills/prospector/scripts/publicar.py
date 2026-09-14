#!/usr/bin/env python3
"""Publica a fila do Prospector por SFTP com chave ou FTP/FTPS.

Credenciais são lidas de variáveis de ambiente ou de .prospector-secrets.
O arquivo de segredos nunca é incluído em logs ou snapshots.
"""

from __future__ import annotations

import argparse
import ftplib
import json
import os
import posixpath
import shlex
import stat
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def read_dotenv(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    if os.name != "nt":
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            raise PermissionError(f"Proteja {path} com chmod 600 antes de publicar")
    result: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result


def secrets(root: Path) -> dict[str, str]:
    values = read_dotenv(root / ".prospector-secrets")
    for key in ("PROSPECTOR_HOST", "PROSPECTOR_PORT", "PROSPECTOR_USER", "PROSPECTOR_PASSWORD", "PROSPECTOR_KEY_FILE"):
        if os.environ.get(key):
            values[key] = os.environ[key]
    return values


def safe_remote(value: str) -> str:
    normalized = posixpath.normpath("/" + value).lstrip("/")
    if normalized.startswith("../") or not normalized.startswith("public_html/"):
        raise ValueError(f"Destino remoto inválido: {value}")
    return normalized


def mkdir_ftp(ftp: ftplib.FTP, remote_dir: str) -> None:
    current = ""
    for part in remote_dir.split("/"):
        current = f"{current}/{part}" if current else part
        try:
            ftp.mkd(current)
        except ftplib.error_perm as exc:
            if not str(exc).startswith("550"):
                raise


def publish_ftp(protocol: str, host: str, port: int, user: str, password: str, items: list[dict]) -> None:
    klass = ftplib.FTP_TLS if protocol == "ftps" else ftplib.FTP
    ftp = klass()
    ftp.connect(host, port, timeout=30)
    ftp.login(user, password)
    if protocol == "ftps":
        ftp.prot_p()
    for item in items:
        remote = safe_remote(item["remote"])
        mkdir_ftp(ftp, posixpath.dirname(remote))
        with open(item["local"], "rb") as stream:
            ftp.storbinary(f"STOR {remote}", stream)
    ftp.quit()


def publish_sftp(host: str, port: int, user: str, key_file: str, items: list[dict]) -> None:
    if not key_file:
        raise ValueError("SFTP exige PROSPECTOR_KEY_FILE. Use chave restrita ou configure FTPS.")
    key = Path(key_file).expanduser().resolve()
    if not key.exists():
        raise FileNotFoundError(key)
    dirs = sorted({posixpath.dirname(safe_remote(x["remote"])) for x in items})
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as batch:
        batch_path = Path(batch.name)
        for directory in dirs:
            current = ""
            for part in directory.split("/"):
                current = f"{current}/{part}" if current else part
                batch.write(f"-mkdir {shlex.quote(current)}\n")
        for item in items:
            batch.write(f"put {shlex.quote(str(Path(item['local']).resolve()))} {shlex.quote(safe_remote(item['remote']))}\n")
    try:
        cmd = ["sftp", "-b", str(batch_path), "-P", str(port), "-i", str(key), f"{user}@{host}"]
        subprocess.run(cmd, check=True)
    finally:
        batch_path.unlink(missing_ok=True)


def main() -> int:
    p = argparse.ArgumentParser(description="Publica fila do Prospector de Sites")
    p.add_argument("--workspace", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    root = Path(args.workspace).expanduser().resolve()
    cfg = json.loads((root / "prospector-config.json").read_text(encoding="utf-8"))
    queue_path = root / "fila-publicacao.json"
    queue = json.loads(queue_path.read_text(encoding="utf-8"))
    items = queue.get("itens", [])
    if not items:
        raise ValueError("Fila vazia")
    for item in items:
        local = Path(item["local"]).resolve()
        if root not in local.parents or not local.is_file():
            raise ValueError(f"Arquivo local inválido: {local}")
        safe_remote(item["remote"])
    if args.dry_run:
        print(json.dumps({"itensValidos": len(items), "destinos": [x["remote"] for x in items]}, ensure_ascii=False, indent=2))
        return 0
    secret = secrets(root)
    host_cfg = cfg.get("hostgator", {})
    host = secret.get("PROSPECTOR_HOST") or host_cfg.get("servidor")
    user = secret.get("PROSPECTOR_USER") or host_cfg.get("usuario")
    protocol = str(host_cfg.get("protocolo") or "sftp").lower()
    default_port = 22 if protocol == "sftp" else (21 if protocol == "ftp" else 21)
    port = int(secret.get("PROSPECTOR_PORT") or host_cfg.get("porta") or default_port)
    if not host or not user:
        raise ValueError("Servidor e usuário não configurados")
    if protocol == "sftp":
        publish_sftp(host, port, user, secret.get("PROSPECTOR_KEY_FILE", ""), items)
    elif protocol in {"ftp", "ftps"}:
        password = secret.get("PROSPECTOR_PASSWORD", "")
        if not password:
            raise ValueError("Defina PROSPECTOR_PASSWORD em .prospector-secrets")
        publish_ftp(protocol, host, port, user, password, items)
    else:
        raise ValueError("Protocolo deve ser sftp, ftps ou ftp")
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    done = root / f"fila-publicada-{stamp}.json"
    queue_path.rename(done)
    print(f"Publicados {len(items)} arquivo(s). Fila arquivada em {done.name}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
