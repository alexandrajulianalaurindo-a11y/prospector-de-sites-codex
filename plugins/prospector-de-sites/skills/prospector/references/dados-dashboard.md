# Dados, CRM e dashboard

## Arquitetura do workspace

```text
prospector-config.json
.prospector-secrets
prospector.db
leads.csv
leads.json
dashboard.html
comparar.html
sites/<slug>/index.html
sites/<slug>/editor.html
sites/<slug>/proposta.html
sites/<slug>/contrato.html
fila-publicacao.json
```

`prospector.db` é a fonte operacional. `leads.csv`, `leads.json` e `dashboard.html` são snapshots regeneráveis. A planilha Google e o Notion espelham o banco; falha no espelho não apaga dados locais.

## Status

`novo | redesenhado | publicado | proposta | respondeu | fechado | descartado | frio`

Nunca rebaixe status avançado durante novo upsert. `fechado`, valor, pagamento e contrato assinado só mudam após confirmação da usuária.

## Config sem segredos

```json
{
  "workspace": "CAMINHO",
  "assinatura": {"nome":"", "apresentacao":"", "whatsapp":""},
  "contratante": {"nome":"", "documento":"", "endereco":""},
  "prospeccao": {"nichos":[], "cidade":"", "leadsPorBusca":10, "maxAvaliados":25},
  "envio": {"modo":"rascunho", "followupDias":3},
  "hostgator": {"dominio":"", "servidor":"", "porta":22, "usuario":"", "pastaBase":"clientes", "protocolo":"sftp"},
  "integracoes": {"googleSheetUrl":"", "notionDatabaseId":""}
}
```

Segredos usam variáveis `PROSPECTOR_HOST`, `PROSPECTOR_PORT`, `PROSPECTOR_USER`, `PROSPECTOR_PASSWORD` ou o arquivo local `.prospector-secrets`, nunca `prospector-config.json`.

## Helper

Inicializar:

```bash
python3 scripts/prospector.py init --workspace CAMINHO
```

Importar/upsert de JSON:

```bash
python3 scripts/prospector.py upsert --workspace CAMINHO --input leads-novos.json
```

Atualizar status:

```bash
python3 scripts/prospector.py status --workspace CAMINHO --slug cliente-x --status redesenhado
```

Regenerar snapshots:

```bash
python3 scripts/prospector.py snapshot --workspace CAMINHO
```

Após qualquer mutação, execute `snapshot`. Depois espelhe apenas os registros mudados no Notion e regenere/atualize a planilha acumulada.
