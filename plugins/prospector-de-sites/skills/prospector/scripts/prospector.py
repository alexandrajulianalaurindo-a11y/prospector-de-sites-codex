#!/usr/bin/env python3
"""Ferramentas locais do Prospector de Sites.

Mantém o CRM SQLite e gera os artefatos estáticos usados pelo funil.
Somente biblioteca padrão; nenhuma ação externa é executada por este arquivo.
"""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import sqlite3
import sys
import shutil
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


STATUSES = ("novo", "redesenhado", "publicado", "proposta", "respondeu", "fechado", "descartado", "frio")
STATUS_RANK = {name: i for i, name in enumerate(STATUSES)}
SCHEMA = """
CREATE TABLE IF NOT EXISTS leads(
  slug TEXT PRIMARY KEY,
  nome TEXT NOT NULL,
  nicho TEXT DEFAULT '', cidade TEXT DEFAULT '', nota REAL, avaliacoes INTEGER DEFAULT 0,
  email TEXT DEFAULT '', telefone TEXT DEFAULT '', whatsapp TEXT DEFAULT '',
  siteAntigo TEXT DEFAULT '', motivo TEXT DEFAULT '', status TEXT DEFAULT 'novo',
  urlNova TEXT DEFAULT '', dataProposta TEXT DEFAULT '', followupEm TEXT DEFAULT '',
  valor REAL, obs TEXT DEFAULT '', contratoStatus TEXT DEFAULT 'pendente',
  contratoEm TEXT DEFAULT '', manutencao REAL, pago INTEGER DEFAULT 0,
  docCliente TEXT DEFAULT '', endCliente TEXT DEFAULT '', fontes TEXT DEFAULT '[]',
  originalPreview TEXT DEFAULT '', rascunhoStatus TEXT DEFAULT '',
  atualizado TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def slugify(value: str) -> str:
    import unicodedata
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", normalized).strip("-").lower()
    if not slug:
        raise ValueError("Não foi possível criar um slug válido")
    return slug[:80]


def workspace(value: str) -> Path:
    p = Path(value).expanduser().resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


def connect(root: Path) -> sqlite3.Connection:
    db = sqlite3.connect(root / "prospector.db")
    db.row_factory = sqlite3.Row
    db.executescript(SCHEMA)
    migrate(db)
    return db


def migrate(db: sqlite3.Connection) -> None:
    current = {r[1] for r in db.execute("PRAGMA table_info(leads)")}
    optional = {
        "followupEm": "TEXT DEFAULT ''", "fontes": "TEXT DEFAULT '[]'",
        "originalPreview": "TEXT DEFAULT ''", "rascunhoStatus": "TEXT DEFAULT ''",
    }
    for name, declaration in optional.items():
        if name not in current:
            db.execute(f'ALTER TABLE leads ADD COLUMN "{name}" {declaration}')
    db.commit()


def default_config(root: Path) -> dict:
    return {
        "workspace": str(root),
        "assinatura": {"nome": "", "apresentacao": "", "whatsapp": ""},
        "contratante": {"nome": "", "documento": "", "endereco": ""},
        "prospeccao": {"nichos": [], "cidade": "", "leadsPorBusca": 10, "maxAvaliados": 25},
        "envio": {"modo": "rascunho", "followupDias": 3},
        "hostgator": {"dominio": "", "servidor": "", "porta": 22, "usuario": "", "pastaBase": "clientes", "protocolo": "sftp"},
        "integracoes": {"googleSheetUrl": "", "notionDatabaseId": ""},
    }


def load_config(root: Path) -> dict:
    path = root / "prospector-config.json"
    if not path.exists():
        cfg = default_config(root)
        path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
        return cfg
    return json.loads(path.read_text(encoding="utf-8"))


def init(root: Path) -> None:
    (root / "sites").mkdir(exist_ok=True)
    load_config(root)
    with connect(root):
        pass
    ignore = root / ".gitignore"
    lines = set(ignore.read_text(encoding="utf-8").splitlines()) if ignore.exists() else set()
    lines.update({".prospector-secrets", "*.log", "__pycache__/"})
    ignore.write_text("\n".join(sorted(lines)) + "\n", encoding="utf-8")
    assets = Path(__file__).resolve().parent.parent / "assets"
    manual = assets / "manual.html"
    if manual.exists():
        shutil.copy2(manual, root / "manual.html")
    secret_example = assets / "segredos-exemplo.txt"
    if secret_example.exists():
        shutil.copy2(secret_example, root / ".prospector-secrets.example")
    snapshot(root)


def normalize_lead(raw: dict) -> dict:
    lead = dict(raw)
    lead["nome"] = str(lead.get("nome") or "").strip()
    if not lead["nome"]:
        raise ValueError("Lead sem nome")
    lead["slug"] = slugify(str(lead.get("slug") or lead["nome"]))
    lead["status"] = str(lead.get("status") or "novo").lower()
    if lead["status"] not in STATUS_RANK:
        raise ValueError(f"Status inválido: {lead['status']}")
    if isinstance(lead.get("fontes"), (list, dict)):
        lead["fontes"] = json.dumps(lead["fontes"], ensure_ascii=False)
    return lead


DB_FIELDS = [
    "slug", "nome", "nicho", "cidade", "nota", "avaliacoes", "email", "telefone", "whatsapp",
    "siteAntigo", "motivo", "status", "urlNova", "dataProposta", "followupEm", "valor", "obs",
    "contratoStatus", "contratoEm", "manutencao", "pago", "docCliente", "endCliente", "fontes",
    "originalPreview", "rascunhoStatus",
]


def upsert(root: Path, input_path: Path) -> int:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    leads = payload.get("leads", []) if isinstance(payload, dict) else payload
    if not isinstance(leads, list):
        raise ValueError("O JSON deve ser uma lista ou conter a chave leads")
    db = connect(root)
    count = 0
    for raw in leads:
        lead = normalize_lead(raw)
        old = db.execute("SELECT * FROM leads WHERE slug=?", (lead["slug"],)).fetchone()
        if old and STATUS_RANK.get(old["status"], 0) > STATUS_RANK[lead["status"]]:
            lead["status"] = old["status"]
        merged = {f: (lead[f] if f in lead else (old[f] if old else None)) for f in DB_FIELDS}
        merged["contratoStatus"] = merged["contratoStatus"] or "pendente"
        merged["pago"] = int(bool(merged["pago"]))
        cols = ",".join(DB_FIELDS)
        placeholders = ",".join("?" for _ in DB_FIELDS)
        updates = ",".join(f'"{f}"=excluded."{f}"' for f in DB_FIELDS if f != "slug")
        db.execute(
            f"INSERT INTO leads ({cols}) VALUES ({placeholders}) ON CONFLICT(slug) DO UPDATE SET {updates}, atualizado=CURRENT_TIMESTAMP",
            [merged[f] for f in DB_FIELDS],
        )
        count += 1
    db.commit()
    db.close()
    return count


def set_status(root: Path, slug: str, status: str, url: str = "", note: str = "") -> None:
    if status not in STATUS_RANK:
        raise ValueError(f"Status inválido: {status}")
    db = connect(root)
    row = db.execute("SELECT status,obs FROM leads WHERE slug=?", (slug,)).fetchone()
    if not row:
        raise ValueError(f"Lead não encontrado: {slug}")
    obs = row["obs"] or ""
    if note:
        obs = (obs + "\n" + note).strip()
    fields = ["status=?", "obs=?", "atualizado=CURRENT_TIMESTAMP"]
    values: list = [status, obs]
    if url:
        fields.append("urlNova=?")
        values.append(url)
    values.append(slug)
    db.execute(f"UPDATE leads SET {','.join(fields)} WHERE slug=?", values)
    db.commit()
    db.close()


def rows(root: Path) -> list[dict]:
    db = connect(root)
    data = [dict(r) for r in db.execute("SELECT * FROM leads ORDER BY atualizado DESC, nome")]
    db.close()
    for lead in data:
        try:
            lead["fontes"] = json.loads(lead.get("fontes") or "[]")
        except json.JSONDecodeError:
            lead["fontes"] = []
    return data


def dashboard_html(data: list[dict]) -> str:
    serialized = json.dumps(data, ensure_ascii=False).replace("</", "<\\/")
    return f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Prospector de Sites</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f5f5fb;color:#17172a;font-family:Inter,system-ui,sans-serif}}header{{padding:24px max(18px,4vw);background:#17172a;color:white;display:flex;align-items:end;justify-content:space-between;gap:20px;flex-wrap:wrap}}h1{{margin:0 0 5px}}nav{{display:flex;gap:8px;flex-wrap:wrap}}button,input,select,textarea{{font:inherit}}button{{border:0;border-radius:9px;padding:9px 12px;background:#6d5ef7;color:white;cursor:pointer}}nav button{{background:#2d2c43}}nav button.active{{background:#6d5ef7}}main{{padding:22px;overflow:auto}}.toolbar{{display:flex;gap:12px;margin-bottom:18px;align-items:center;flex-wrap:wrap}}.toolbar input{{min-width:280px;padding:11px;border:1px solid #d9d8e6;border-radius:10px}}.mode{{display:none}}.mode.active{{display:block}}.stats{{display:flex;gap:12px;flex-wrap:wrap;margin-bottom:20px}}.stat{{background:white;border:1px solid #e4e4ef;border-radius:14px;padding:14px 18px;min-width:150px}}.stat b{{font-size:22px}}.board{{display:grid;grid-template-columns:repeat(8,minmax(245px,1fr));gap:14px;align-items:start}}.col{{background:#ececf5;border-radius:16px;padding:12px;min-height:220px}}.col.over{{outline:3px solid #6d5ef7}}.col h2{{font-size:13px;text-transform:uppercase;letter-spacing:.04em}}.card{{background:white;border:1px solid #dedee9;border-radius:12px;padding:14px;margin:10px 0;box-shadow:0 4px 16px #1d17420a;cursor:grab}}.card h3{{margin:0 0 8px;font-size:16px}}.meta{{color:#6a687e;font-size:13px}}.actions{{display:flex;gap:8px;margin-top:10px}}.actions button{{padding:6px 9px;font-size:12px}}a{{color:#5848d8}}table{{width:100%;border-collapse:collapse;background:white;border-radius:14px;overflow:hidden}}th,td{{padding:12px;border-bottom:1px solid #ecebf3;text-align:left}}dialog{{border:0;border-radius:16px;max-width:620px;width:92%;box-shadow:0 30px 90px #0005}}dialog form{{display:grid;gap:10px}}dialog input,dialog textarea,dialog select{{padding:10px;border:1px solid #d8d7e4;border-radius:8px}}dialog textarea{{min-height:100px}}.funnel{{display:grid;gap:8px;max-width:760px}}.bar{{background:#6d5ef7;color:#fff;padding:14px;border-radius:10px}}@media(max-width:700px){{main{{padding:14px}}.toolbar input{{min-width:100%}}}}
</style></head><body><header><div><h1>Prospector de Sites</h1><small id="connection">Snapshot local · {html.escape(now_iso())}</small></div><nav><button data-mode="kanban" class="active">Kanban</button><button data-mode="funil">Funil</button><button data-mode="contratos">Contratos</button><button data-mode="financeiro">Financeiro</button></nav></header><main><div class="toolbar"><input id="search" placeholder="Buscar nome, nicho ou cidade"><span id="count"></span></div><section id="kanban" class="mode active"><div class="stats" id="stats"></div><div class="board" id="board"></div></section><section id="funil" class="mode"><div class="funnel" id="funnel"></div></section><section id="contratos" class="mode"><table><thead><tr><th>Cliente</th><th>Status</th><th>Enviado em</th><th>Pagamento</th></tr></thead><tbody id="contracts"></tbody></table></section><section id="financeiro" class="mode"><div class="stats" id="money"></div><table><thead><tr><th>Cliente</th><th>Projeto</th><th>Manutenção</th><th>Recebido</th></tr></thead><tbody id="financeRows"></tbody></table></section></main><dialog id="modal"><form method="dialog"><h2>Editar lead</h2><input name="nome" placeholder="Nome"><input name="email" placeholder="E-mail"><input name="telefone" placeholder="Telefone"><select name="status">{''.join(f'<option>{x}</option>' for x in STATUSES)}</select><input name="valor" type="number" step="0.01" placeholder="Valor"><input name="manutencao" type="number" step="0.01" placeholder="Manutenção"><textarea name="obs" placeholder="Observações"></textarea><div><button value="cancel">Cancelar</button> <button id="save" value="default">Salvar</button></div></form></dialog><script>
let leads={serialized};const statuses={json.dumps(list(STATUSES), ensure_ascii=False)},labels={{novo:'Novos',redesenhado:'Redesenhados',publicado:'Publicados',proposta:'Propostas',respondeu:'Responderam',fechado:'Fechados',descartado:'Descartados',frio:'Frios'}};let selected=null;
const esc=s=>String(s??'').replace(/[&<>\"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',"'":'&#39;'}}[c])),money=n=>'R$ '+(Number(n)||0).toLocaleString('pt-BR',{{minimumFractionDigits:2}}),filtered=()=>{{const q=document.querySelector('#search').value.toLowerCase();return leads.filter(x=>[x.nome,x.nicho,x.cidade,x.email].join(' ').toLowerCase().includes(q))}};
async function api(path,opt={{}}){{const r=await fetch(path,opt);if(!r.ok)throw Error(await r.text());return r.status===204?null:r.json()}}
async function load(){{try{{leads=await api('/api/leads');document.querySelector('#connection').textContent='Banco conectado · alterações são salvas';}}catch(e){{}}render()}}
async function patch(slug,data){{try{{await api('/api/leads/'+encodeURIComponent(slug),{{method:'PATCH',headers:{{'Content-Type':'application/json'}},body:JSON.stringify(data)}});await load()}}catch(e){{alert('Abra pelo servidor do Prospector para salvar alterações.')}}}}
function render(){{const list=filtered();document.querySelector('#count').textContent=list.length+' lead(s)';document.querySelector('#stats').innerHTML=`<div class="stat"><b>${{leads.length}}</b><br>leads</div><div class="stat"><b>${{leads.filter(x=>x.status==='proposta').length}}</b><br>propostas</div><div class="stat"><b>${{leads.filter(x=>x.status==='respondeu').length}}</b><br>respostas</div><div class="stat"><b>${{leads.filter(x=>x.status==='fechado').length}}</b><br>fechados</div>`;document.querySelector('#board').innerHTML=statuses.map(s=>`<section class="col" data-status="${{s}}"><h2>${{labels[s]}} (${{list.filter(x=>x.status===s).length}})</h2>${{list.filter(x=>x.status===s).map(card).join('')}}</section>`).join('');bindDrag();renderExtras();}}
function card(x){{return `<article class="card" draggable="true" data-slug="${{esc(x.slug)}}"><h3>${{esc(x.nome)}}</h3><div class="meta">${{esc(x.nicho)}} · ${{esc(x.cidade)}}<br>${{x.nota??'-'}} ★ · ${{x.avaliacoes||0}} avaliações</div><p>${{esc(x.motivo)}}</p>${{x.urlNova?`<a href="${{esc(x.urlNova)}}" target="_blank">Abrir site</a>`:''}}<div class="actions"><button onclick="edit('${{esc(x.slug)}}')">Editar</button></div></article>`}}
function bindDrag(){{let drag='';document.querySelectorAll('.card').forEach(c=>c.ondragstart=()=>drag=c.dataset.slug);document.querySelectorAll('.col').forEach(c=>{{c.ondragover=e=>{{e.preventDefault();c.classList.add('over')}};c.ondragleave=()=>c.classList.remove('over');c.ondrop=()=>{{c.classList.remove('over');if(drag)patch(drag,{{status:c.dataset.status}})}}}})}}
function renderExtras(){{document.querySelector('#funnel').innerHTML=statuses.slice(0,6).map(s=>{{const n=leads.filter(x=>x.status===s).length,w=leads.length?Math.max(12,n/leads.length*100):12;return `<div class="bar" style="width:${{w}}%">${{labels[s]}}: ${{n}}</div>`}}).join('');document.querySelector('#contracts').innerHTML=leads.filter(x=>x.status==='fechado'||x.contratoStatus!=='pendente').map(x=>`<tr><td>${{esc(x.nome)}}</td><td>${{esc(x.contratoStatus)}}</td><td>${{esc(x.contratoEm)}}</td><td>${{x.pago?'Pago':'Pendente'}}</td></tr>`).join('');const received=leads.filter(x=>x.pago).reduce((s,x)=>s+(Number(x.valor)||0),0),due=leads.filter(x=>x.status==='fechado'&&!x.pago).reduce((s,x)=>s+(Number(x.valor)||0),0),mrr=leads.filter(x=>x.status==='fechado').reduce((s,x)=>s+(Number(x.manutencao)||0),0);document.querySelector('#money').innerHTML=`<div class="stat"><b>${{money(received)}}</b><br>recebido</div><div class="stat"><b>${{money(due)}}</b><br>a receber</div><div class="stat"><b>${{money(mrr)}}</b><br>MRR</div><div class="stat"><b>${{money(mrr*12)}}</b><br>projeção 12 meses</div>`;document.querySelector('#financeRows').innerHTML=leads.filter(x=>x.status==='fechado').map(x=>`<tr><td>${{esc(x.nome)}}</td><td>${{money(x.valor)}}</td><td>${{money(x.manutencao)}}</td><td>${{x.pago?'Sim':'Não'}}</td></tr>`).join('')}}
function edit(slug){{selected=leads.find(x=>x.slug===slug);const f=document.querySelector('#modal form');for(const k of ['nome','email','telefone','status','valor','manutencao','obs'])f.elements[k].value=selected[k]??'';document.querySelector('#modal').showModal()}}window.edit=edit;document.querySelector('#save').onclick=e=>{{e.preventDefault();const f=document.querySelector('#modal form'),d=Object.fromEntries(new FormData(f));patch(selected.slug,d);document.querySelector('#modal').close()}};document.querySelector('#search').oninput=render;document.querySelectorAll('nav button').forEach(b=>b.onclick=()=>{{document.querySelectorAll('nav button').forEach(x=>x.classList.remove('active'));document.querySelectorAll('.mode').forEach(x=>x.classList.remove('active'));b.classList.add('active');document.querySelector('#'+b.dataset.mode).classList.add('active')}});load();
</script></body></html>'''


def snapshot(root: Path) -> None:
    data = rows(root)
    (root / "leads.json").write_text(json.dumps({"atualizado": now_iso(), "leads": data}, ensure_ascii=False, indent=2), encoding="utf-8")
    with (root / "leads.csv").open("w", encoding="utf-8-sig", newline="") as f:
        fields = ["slug", "nome", "nicho", "cidade", "nota", "avaliacoes", "email", "telefone", "whatsapp", "siteAntigo", "motivo", "status", "urlNova", "dataProposta", "followupEm", "valor", "obs"]
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader(); w.writerows(data)
    (root / "dashboard.html").write_text(dashboard_html(data), encoding="utf-8")


EDITOR_BLOCK = r'''<!-- PROSPECTOR-EDITOR-START --><style id="prospector-editor-style">#prospector-editor{position:fixed;inset:0 0 auto;z-index:2147483647;background:#17172a;color:#fff;padding:10px 16px;font:14px system-ui;display:flex;gap:14px;align-items:center}#prospector-editor button{margin-left:auto;background:#6d5ef7;color:#fff;border:0;border-radius:8px;padding:9px 14px}body{padding-top:50px!important}.prospector-editable:hover{outline:2px dashed #6d5ef7;outline-offset:2px}</style><div id="prospector-editor"><b>Modo de edição</b><span>Clique em textos ou imagens</span><button id="prospector-export">Exportar página</button></div><input id="prospector-image" type="file" accept="image/*" hidden><script id="prospector-editor-script">(()=>{const bar=document.querySelector('#prospector-editor'),pick=document.querySelector('#prospector-image');let image=null;document.querySelectorAll('h1,h2,h3,h4,p,li,a,span,button,blockquote').forEach(el=>{if(el.closest('#prospector-editor')||el.children.length)return;el.classList.add('prospector-editable');el.onclick=e=>{if(el.tagName==='A'||el.tagName==='BUTTON')e.preventDefault();el.contentEditable='true';el.focus()};});document.querySelectorAll('img').forEach(el=>{el.classList.add('prospector-editable');el.onclick=e=>{e.preventDefault();image=el;pick.click()}});pick.onchange=()=>{const f=pick.files[0];if(!f||!image)return;const r=new FileReader();r.onload=()=>{image.src=r.result;image.removeAttribute('srcset')};r.readAsDataURL(f)};document.querySelector('#prospector-export').onclick=()=>{const doc=document.documentElement.cloneNode(true);['#prospector-editor','#prospector-image','#prospector-editor-style','#prospector-editor-script'].forEach(s=>doc.querySelector(s)?.remove());doc.querySelectorAll('[contenteditable]').forEach(x=>x.removeAttribute('contenteditable'));doc.querySelectorAll('.prospector-editable').forEach(x=>x.classList.remove('prospector-editable'));const blob=new Blob(['<!doctype html>\n'+doc.outerHTML],{type:'text/html'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='index.html';a.click()}})();</script><!-- PROSPECTOR-EDITOR-END -->'''


def editor(root: Path, slug: str) -> Path:
    source = root / "sites" / slug / "index.html"
    if not source.exists():
        raise FileNotFoundError(source)
    body = source.read_text(encoding="utf-8")
    body = re.sub(r"<!-- PROSPECTOR-EDITOR-START -->.*?<!-- PROSPECTOR-EDITOR-END -->", "", body, flags=re.S)
    if re.search(r"</body\s*>", body, flags=re.I):
        body = re.sub(r"</body\s*>", EDITOR_BLOCK + "</body>", body, count=1, flags=re.I)
    else:
        body += EDITOR_BLOCK
    target = source.with_name("editor.html")
    target.write_text(body, encoding="utf-8")
    return target


def comparar(root: Path) -> Path:
    data = [x for x in rows(root) if (root / "sites" / x["slug"] / "index.html").exists()]
    options = "".join(f'<option value="{html.escape(x["slug"])}">{html.escape(x["nome"])}</option>' for x in data)
    payload = json.dumps({x["slug"]: x for x in data}, ensure_ascii=False).replace("</", "<\\/")
    page = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>Comparador</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#11121b;color:white;font-family:system-ui}}header{{padding:16px 3vw;display:flex;align-items:center;gap:18px}}select{{padding:10px;border-radius:8px}}main{{display:grid;grid-template-columns:1fr 1fr;gap:8px;height:calc(100vh - 74px)}}section{{display:grid;grid-template-rows:auto 1fr;background:white;color:#17172a}}h2{{font-size:14px;margin:0;padding:10px 14px;background:#ececf5}}iframe{{width:100%;height:100%;border:0}}@media(max-width:800px){{main{{grid-template-columns:1fr;height:auto}}section{{height:75vh}}}}</style></head><body><header><b>Antes e depois</b><select id="lead">{options}</select></header><main><section><h2>Site atual</h2><iframe id="old"></iframe></section><section><h2>Nova versão</h2><iframe id="new"></iframe></section></main><script>const data={payload},sel=document.querySelector('#lead');function show(){{const x=data[sel.value];document.querySelector('#old').src=x.siteAntigo||'about:blank';document.querySelector('#new').src='sites/'+x.slug+'/index.html'}}sel.onchange=show;if(sel.options.length){{sel.selectedIndex=0;show()}}</script></body></html>'''
    target = root / "comparar.html"
    target.write_text(page, encoding="utf-8")
    return target


def one_lead(root: Path, slug: str) -> dict:
    matches = [x for x in rows(root) if x["slug"] == slug]
    if not matches:
        raise ValueError(f"Lead não encontrado: {slug}")
    return matches[0]


def cover(root: Path, slug: str) -> Path:
    lead, cfg = one_lead(root, slug), load_config(root)
    signature = cfg.get("assinatura", {})
    current = html.escape(lead.get("siteAntigo") or "about:blank", quote=True)
    new = "index.html"
    diag = html.escape(lead.get("motivo") or "Oportunidades de melhoria identificadas no site atual.")
    page = f'''<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><title>Proposta visual — {html.escape(lead['nome'])}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f4fb;color:#1a1930;font-family:system-ui}}header{{padding:44px 5vw;text-align:center}}h1{{font-size:clamp(28px,5vw,54px);margin:8px}}.tag{{color:#6d5ef7;font-weight:700}}.diag{{max-width:800px;margin:18px auto;color:#5e5b70}}main{{display:grid;grid-template-columns:1fr 1fr;gap:18px;padding:0 3vw 42px}}article{{background:white;border:1px solid #dfdeeb;border-radius:16px;overflow:hidden;box-shadow:0 10px 35px #312a6412}}h2{{font-size:15px;padding:12px 16px;margin:0}}iframe{{width:100%;height:70vh;border:0}}footer{{text-align:center;padding:24px}}@media(max-width:850px){{main{{grid-template-columns:1fr}}iframe{{height:70vh}}}}</style></head><body><header><div class="tag">DEMONSTRAÇÃO PERSONALIZADA</div><h1>{html.escape(lead['nome'])}</h1><p class="diag">{diag}</p><p>Compare as duas versões e abra também pelo celular.</p></header><main><article><h2>Site atual</h2><iframe src="{current}"></iframe></article><article><h2>Nova proposta visual</h2><iframe src="{new}"></iframe></article></main><footer>Preparado por <b>{html.escape(signature.get('nome',''))}</b> · {html.escape(signature.get('apresentacao',''))} · {html.escape(signature.get('whatsapp',''))}</footer></body></html>'''
    target = root / "sites" / slug / "proposta.html"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding="utf-8")
    return target


def queue(root: Path, slugs: list[str]) -> Path:
    cfg = load_config(root); base = str(cfg.get("hostgator", {}).get("pastaBase") or "clientes").strip("/")
    items = []
    for slug in slugs:
        folder = root / "sites" / slug
        for local_name, remote_name in (("index.html", "index.html"), ("proposta.html", "proposta.html")):
            local = folder / local_name
            if not local.exists():
                raise FileNotFoundError(local)
            items.append({"slug": slug, "local": str(local), "remote": f"public_html/{base}/{slug}/{remote_name}"})
    target = root / "fila-publicacao.json"
    target.write_text(json.dumps({"criadaEm": now_iso(), "itens": items}, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description="CRM e artefatos do Prospector de Sites")
    sub = parser.add_subparsers(dest="cmd", required=True)
    for name in ("init", "snapshot", "comparar"):
        p = sub.add_parser(name); p.add_argument("--workspace", required=True)
    p = sub.add_parser("upsert"); p.add_argument("--workspace", required=True); p.add_argument("--input", required=True)
    p = sub.add_parser("status"); p.add_argument("--workspace", required=True); p.add_argument("--slug", required=True); p.add_argument("--status", required=True, choices=STATUSES); p.add_argument("--url", default=""); p.add_argument("--note", default="")
    for name in ("editor", "capa"):
        p = sub.add_parser(name); p.add_argument("--workspace", required=True); p.add_argument("--slug", required=True)
    p = sub.add_parser("fila"); p.add_argument("--workspace", required=True); p.add_argument("--slug", action="append", required=True)
    args = parser.parse_args(); root = workspace(args.workspace)
    if args.cmd == "init": init(root); print(root / "dashboard.html")
    elif args.cmd == "snapshot": snapshot(root); print(root / "dashboard.html")
    elif args.cmd == "upsert": print(f"{upsert(root, Path(args.input).resolve())} lead(s) atualizados"); snapshot(root)
    elif args.cmd == "status": set_status(root, args.slug, args.status, args.url, args.note); snapshot(root); print(args.slug)
    elif args.cmd == "editor": print(editor(root, args.slug))
    elif args.cmd == "comparar": print(comparar(root))
    elif args.cmd == "capa": print(cover(root, args.slug))
    elif args.cmd == "fila": print(queue(root, args.slug))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise SystemExit(1)
