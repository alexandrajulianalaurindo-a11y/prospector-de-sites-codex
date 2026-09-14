# Modo prospectar

## Preparação

Leia config e banco. Se faltarem nicho ou cidade, pergunte. Use a meta configurada, padrão 10, e teto de 25 estabelecimentos avaliados. Exclua todos os slugs/domínios já registrados.

## Busca e qualificação

1. Pesquise `[nicho] em [cidade]` no Google Maps.
2. Para cada resultado, capture nome, URL do perfil, nota, avaliações, telefone e site.
3. Aplique em ordem: nota ≥4,7; avaliações ≥40; site próprio ativo; site com dois problemas objetivos; e-mail público confirmado.
4. Abra o site e verifique desktop/mobile. Registre os problemas com evidências curtas e URLs-fonte.
5. Procure WhatsApp em `wa.me`, `api.whatsapp.com` ou telefone celular. Normalize para `55DDDNÚMERO`.
6. Procure o e-mail no site, contato, `mailto:` e busca pública pelo nome. Nunca adivinhe padrão de e-mail.
7. Registre aprovados e descartados, inclusive o motivo. Pare na meta ou no 25º avaliado.

Use pesquisa web primeiro. Se resultados públicos não trouxerem dados suficientes, use o navegador controlado no Maps. CAPTCHA ou login é ponto de pausa para a usuária, não algo a contornar.

## Persistência

Monte um JSON com todos os avaliados e execute:

```bash
python3 scripts/prospector.py upsert --workspace CAMINHO --input ARQUIVO.json
python3 scripts/prospector.py snapshot --workspace CAMINHO
```

Crie/atualize a planilha acumulada `Leads Prospector — [nicho] [cidade]` no Google Sheets e espelhe os leads no Pipeline de Sites do Notion. Não crie duplicatas.

## Saída

Entregue tabela ranqueada, contagem de qualificados/descartados, links da planilha/painel e a frase `Dashboard atualizado: N leads`. Próximo modo: `redesenhar` para cinco ou mais leads; se houver menos, use todos e avise.
