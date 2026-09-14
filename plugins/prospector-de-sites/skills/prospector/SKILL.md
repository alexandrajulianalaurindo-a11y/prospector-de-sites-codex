---
name: prospector
description: "Executa o funil Prospector de Sites no Codex: setup, prospecção no Google Maps, qualificação, redesign, editor, comparador, HostGator, propostas Gmail, respostas, follow-up, dashboard e contrato. Use quando a usuária mencionar Prospector de Sites, prospectar empresas para vender sites, ou pedir qualquer etapa desse funil."
---

# Prospector de Sites

Reproduza o fluxo operacional do Prospector de Sites no Codex, alterando apenas integrações exclusivas do Claude Cowork. Preserve a ordem e as regras do funil; não simplifique etapas silenciosamente.

## Comandos equivalentes

O Codex não registra comandos `/...` do Claude. Interprete estes nomes como modos do plugin, aceitando tanto linguagem natural quanto o nome literal:

- `setup`: configuração inicial e teste do ambiente.
- `prospectar`: buscar e qualificar leads.
- `redesenhar`: gerar site premium, editor e comparador.
- `editor`: regenerar a versão editável.
- `publicar`: criar capa e publicar na HostGator.
- `proposta`: preparar rascunhos no Gmail.
- `respostas`: verificar respostas e atualizar o funil.
- `followup`: preparar o único follow-up permitido.
- `contrato`: gerar minuta HTML/DOCX e rascunho de envio.

Se o pedido for “continuar”, leia o banco e retome a próxima etapa válida. Ao terminar cada modo, indique o próximo.

## Roteamento obrigatório

Antes de executar um modo, leia sua referência completa:

- [setup](references/setup.md)
- [prospectar](references/prospectar.md)
- [redesenhar e editor](references/redesenhar.md)
- [publicar na HostGator](references/publicar.md)
- [proposta, respostas e follow-up](references/email.md)
- [contrato](references/contrato.md)

Para qualquer mudança de lead, leia também [dados e dashboard](references/dados-dashboard.md). Para critérios e regras comuns, leia [regras do funil](references/regras.md).

## Adaptações exclusivas do Codex

- Google Maps/site: use pesquisa web primeiro; use navegador controlado somente quando a informação ou interação não puder ser obtida por pesquisa. Se houver CAPTCHA/login, pause para a usuária concluir.
- Arquivos persistentes: use a pasta de operação indicada no config. Não grave dados do cliente dentro da pasta do plugin.
- Gmail: use o conector Gmail para criar rascunhos e pesquisar respostas. Nunca envie automaticamente sem autorização expressa no momento do envio.
- Google Sheets: use Google Drive/Sheets para a planilha acumulada quando conectado.
- Notion: espelhe o status no Pipeline de Sites já criado quando o conector estiver disponível; o SQLite local continua sendo a fonte operacional para compatibilidade com o painel.
- HostGator: prefira SFTP/FTP restrito. Nunca peça nem salve a senha principal do cPanel. Segredos ficam em arquivo local `.prospector-secrets` com permissão restrita ou em variáveis de ambiente, nunca no chat, banco, logs ou Notion.

## Autorizações e travas

- Pesquisa, análise e geração local podem seguir após o briefing.
- Antes de publicar, criar rascunhos, enviar mensagens ou alterar sistemas externos, confirme que a usuária pediu aquela ação neste turno.
- Nunca publicar como oficial, registrar domínio, enviar e-mail, marcar fechamento, inventar preço ou aceitar escopo em nome da usuária.
- Preview usa `noindex,nofollow`, dados públicos verificáveis e aviso discreto de demonstração. Remova quando solicitado.

## Automação local

Use `scripts/prospector.py` para inicializar o workspace, manter SQLite/CSV/JSON, gerar editor, comparador, capa e fila de publicação. Execute `python3 scripts/prospector.py --help` quando precisar confirmar argumentos. Nunca edite o SQLite manualmente se o helper atender à operação.
