# automacao-teams

Notifica o **Microsoft Teams** sobre Pull Requests do GitHub, usando **GitHub Actions** + **Power Automate**. Sem servidor, sem Azure Bot.

## O que faz

- **No grupo/canal** (aprovadores): quando uma PR é **aberta / reaberta / fica pronta** (drafts são ignorados), **@mencionando os aprovadores**; e uma **lista periódica** das PRs abertas.
- **Na DM do autor** (Flow bot): quando a PR é **aprovada**, alguém **pede alterações**, é **fechada** ou é **mergeada** (mostrando a branch `origem → destino`).

```
Evento de PR ─► GitHub Actions ─► POST ─► Power Automate ─► Teams (grupo ou DM)
```

## Eventos cobertos

| Evento do GitHub | Para onde vai | Mensagem |
|---|---|---|
| PR `opened` / `reopened` / `ready_for_review` (não-draft) | grupo | 🆕 Nova PR + @menção dos aprovadores |
| review `approved` | DM autor | ✅ Fulano aprovou sua PR |
| review `changes_requested` | DM autor | 📝 Fulano pediu alterações |
| PR `closed` (sem merge) | DM autor | 🚫 PR fechada sem merge (com branch) |
| PR `closed` (com merge) | DM autor | 🎉 PR mergeada (com branch `origem → destino`) |
| `schedule` / `workflow_dispatch` | grupo | 📋 Lista de PRs abertas |

## Estrutura

```
.github/workflows/notify.yml   # workflow que ESTE repo consome (dispara nos eventos)
src/
  main.py        # roteia por evento
  models.py      # modelos Pydantic do evento do GitHub
  settings.py    # config de ambiente (pydantic-settings)
  teams.py       # POST nos webhooks do Power Automate
  github_pr.py   # lista PRs abertas via API REST
  cards.py       # Adaptive Cards
  mapping.py     # github login -> email / aprovadores
config/user-map.yml            # mapa github↔teams + aprovadores
```

> Modelo **auto-contido**: o próprio repositório consome o `notify.yml`. Para usar em
> outro repo, basta **copiar** `src/`, `requirements.txt`, `config/user-map.yml` e
> `.github/workflows/notify.yml` para lá.

---

## Como implementar (passo a passo)

### 1. Criar os 2 fluxos no Power Automate (`make.powerautomate.com`)

Os dois usam o gatilho **"Quando uma solicitação de webhook do Teams é recebida"** + a ação **"Postar cartão em um chat ou canal"**.

> ⚠️ **PONTO CRÍTICO (causa de erro 401):** no card do **gatilho**, em
> **"Quem pode disparar o fluxo?"**, selecione **"Qualquer pessoa"**.
> Se ficar em "Qualquer usuário no meu locatário", o GitHub recebe **401** e a URL
> sai **sem `sig`**. Só com "Qualquer pessoa" a URL ganha o `&sig=...` e funciona.

**Fluxo do GRUPO** → secret `TEAMS_CHANNEL_WEBHOOK`
- Postar como: **Bot do fluxo**
- Postar em: **Chat em grupo** → selecione o grupo
- Cartão Adaptável: expressão **`triggerBody()?['card']`**

**Fluxo da DM** → secret `TEAMS_DM_WEBHOOK`
- Postar como: **Bot do fluxo**
- Postar em: **Conversar com o bot do Flow**
- Destinatário: expressão **`triggerBody()?['recipient']`** (dinâmico = vai pro autor da PR)
- Cartão Adaptável: expressão **`triggerBody()?['card']`**

Em cada fluxo: **Salvar** → clicar no **gatilho** → copiar a **"URL de POST HTTP"** (confira que termina com `&sig=...`).

### 2. Cadastrar os secrets (no repo, em `Settings → Secrets and variables → Actions`)

| Secret | Obrigatório | Valor |
|---|---|---|
| `TEAMS_CHANNEL_WEBHOOK` | sim | URL do fluxo do grupo |
| `TEAMS_DM_WEBHOOK` | opcional | URL do fluxo da DM |

### 3. Preencher `config/user-map.yml`

```yaml
users:                                   # DM pro autor (login GitHub -> email Teams)
  SeuLoginGitHub: voce@tenant.onmicrosoft.com
approvers:                               # @mencionados no grupo quando abre PR
  - name: Fulano
    email: fulano@tenant.onmicrosoft.com
```

> O e-mail (em `users` e `approvers`) tem que ser o mesmo com que a pessoa entra no
> Teams, e deve ser **usuário nativo do tenant** (convidado não recebe DM do Flow bot).

### 4. Garantir que o `notify.yml` está na branch `main`

Eventos `pull_request` rodam a versão do workflow que está na **branch base**. Então
o `notify.yml` precisa já estar na `main` **antes** de abrir a PR de teste.

### 5. Testar

Crie uma branch a partir da `main` → faça qualquer mudança → **abra uma PR (não-draft)**.
- Acompanhe em **Actions**.
- O card cai no grupo (com @menção). Aprove / feche / faça merge para disparar as DMs.
- Confira a entrega em **Power Automate → Meus fluxos → histórico de execuções**.

---

## Notas

- **Sem Azure / Graph / Bot:** a única "credencial" são as 2 URLs de fluxo (secrets).
- **Segurança:** as URLs contêm `sig=` → são segredos; ficam só nos GitHub Secrets.
- O payload enviado é: grupo `{"card": {...}}` · DM `{"recipient": "email", "card": {...}}`.
