# Modo setup

## Objetivo

Deixar workspace, identidade, filtros, integrações, CRM e publicação preparados uma vez.

## Ordem

1. Localize `prospector-config.json`. Se existir, mostre somente campos não sensíveis e pergunte o que atualizar. Caso contrário, colete em um único formulário:
   - pasta de trabalho;
   - nome, apresentação e WhatsApp da assinatura;
   - nichos e cidade padrão;
   - meta de leads, padrão 10;
   - rascunho ou envio direto, usando rascunho como padrão;
   - dados do prestador para contrato, se a usuária quiser configurá-los agora.
2. Pergunte se a HostGator já foi contratada. Se não, salve configuração parcial; o restante do funil pode ser testado localmente.
3. Se contratada, colete apenas domínio, servidor, porta, usuário SFTP restrito e pasta base. A senha não passa pelo chat. Oriente a criar `.prospector-secrets` local ou variáveis de ambiente.
4. Execute `prospector.py init`, atualize o JSON de configuração e gere os snapshots.
5. Confirme acesso aos conectores necessários: Google Drive/Sheets, Gmail e Notion. Se algum estiver ausente, registre como pendência sem apagar a configuração.
6. Para HostGator configurada, crie `teste.html`, peça autorização de publicação, publique e valide `https://.../clientes/teste/`.

## Encerramento

Informe o que ficou pronto, o que depende de conexão e o próximo modo `prospectar`. Nunca diga que Gmail ou HostGator está conectado sem um teste confirmado.
