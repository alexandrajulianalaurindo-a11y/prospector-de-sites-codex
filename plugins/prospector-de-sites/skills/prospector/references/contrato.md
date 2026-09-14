# Modo contrato

## Pré-condições

Use somente lead confirmado como `fechado` pela usuária. Reúna do banco/config o que já existe antes de perguntar. Faltantes possíveis: documento e endereço do cliente, preço, forma de pagamento, prazo, manutenção e dados completos da prestadora. Nunca invente.

## Arquivos

Gere:

- `sites/<slug>/contrato.html`, A4 e pronto para impressão/PDF;
- `sites/<slug>/contrato.docx`, quando o gerador DOCX estiver disponível;
- `sites/<slug>/dados-contrato.json`, sem segredos.

Após confirmar todos os dados, execute:

```bash
python3 scripts/gerar_contrato.py --dados DADOS.json --workspace CAMINHO --slug SLUG
```

A minuta cobre partes, objeto, escopo, prazo, preço/pagamento, responsabilidades, alterações fora do escopo, domínio/hospedagem, manutenção opcional, rescisão, proteção de dados compatível com site institucional e foro definido pela usuária. Preserve aviso de minuta-base e recomendação de revisão jurídica.

O contrato não pode prometer validade jurídica automática. Para assinatura forte, a usuária escolhe uma plataforma própria. Não acrescente login, pagamentos, banco de dados ou suporte ilimitado ao escopo.

## Gmail e status

Crie rascunho cordial, resumindo escopo, valor e prazo, e solicite leitura/assinatura. Anexe apenas se o conector permitir; caso contrário, indique claramente o arquivo que a usuária deve anexar. O envio exige autorização.

Após confirmação de envio, registre `contratoStatus=enviado` e data. `assinado` e `pago` somente após confirmação da usuária. Regenere os espelhos.
