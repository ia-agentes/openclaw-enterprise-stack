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
