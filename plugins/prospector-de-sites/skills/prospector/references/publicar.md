# Modo publicar

## Pré-condições

Leia config, banco e arquivos do lead. Exija domínio apresentável, acesso restrito SFTP/FTP, `index.html` validado e autorização da usuária neste turno. Não aceite senha principal do cPanel.

## Capa

Gere `sites/<slug>/proposta.html` com:

- nome do negócio;
- diagnóstico objetivo;
- original e redesign lado a lado;
- instrução para abrir no celular;
- assinatura da prestadora;
- nenhum formulário ou coleta de dados.

Use:

```bash
python3 scripts/prospector.py capa --workspace CAMINHO --slug SLUG
```

## Publicação

Monte a fila:

```bash
python3 scripts/prospector.py fila --workspace CAMINHO --slug SLUG
```

O destino é `public_html/<pastaBase>/<slug>/`, com `index.html` e `proposta.html`. Execute o publicador com segredos locais:

```bash
python3 scripts/publicar.py --workspace CAMINHO
```

O script aceita SFTP via comando `sftp` ou FTP/FTPS pela biblioteca padrão, conforme config. Se a rede do Codex não alcançar o servidor, não repita indefinidamente: deixe a fila pronta e oriente a execução local. Navegador/cPanel é último recurso e o login é feito pela usuária.

## Verificação bloqueante

Abra `https://<dominio>/<pastaBase>/<slug>/` e `.../proposta.html`. Confirme conteúdo correto e certificado válido. Link HTTP não vai para o lead. Em falha de SSL, peça AutoSSL no cPanel e valide novamente.

Somente após o teste altere status para `publicado`, grave URL, regenere snapshots e espelhe o pipeline. Próximo modo: `proposta`.
