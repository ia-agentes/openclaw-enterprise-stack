# OpenClaw Enterprise Stack

Deploy automatizado para múltiplas instâncias do OpenClaw utilizando Docker Compose + Traefik.

## Recursos

- Deploy multi-instância
- HTTPS automático (Let's Encrypt)
- Traefik
- Templates
- Geração automática de docker-compose
- Backup
- Restore
- Update

## Estrutura

```
bootstrap/
config/
proxy/
templates/
scripts/
instances/
docs/
tests/
```

## Instâncias

- te
- academico
- dp
- adm
- paulo

## Painel administrativo

O stack inclui um painel central para visualizar as instâncias OpenClaw, com
status do gateway, versão, modelo, autenticação OpenAI, Telegram e WhatsApp.
Ele também oferece ações autenticadas para validar uma instância e reiniciar
somente containers declarados em `config/stack.yml`.
Pelo painel também é possível criar uma nova instância: o fluxo valida nome,
domínio e porta, atualiza `config/stack.yml`, gera os arquivos em `instances/`
e inicia o container pelo Docker API.

Configure o domínio e um token forte:

```bash
cp admin/.env.example admin/.env
editor admin/.env
```

Suba o painel:

```bash
bin/oces dashboard
```

Consulte o inventário em JSON, útil para automações e monitoramento:

```bash
bin/oces status --json
```

O painel usa `OCES_ADMIN_TOKEN` via cabeçalho `Authorization: Bearer ...`.
Não exponha o painel sem esse token configurado.
Antes de criar uma instância pelo painel, aponte o DNS do novo subdomínio para
a VPS e mantenha a imagem `openclaw:latest` disponível no host.
