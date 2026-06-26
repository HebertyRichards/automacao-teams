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
| PR `review_requested` (pedir review / re-request) | DM revisor | 🔍 Fulano pediu sua revisão na PR |
| review `approved` | DM autor | ✅ Fulano aprovou sua PR |
| review `changes_requested` | DM autor | 📝 Fulano pediu alterações |
| `issue_comment` (comentário na conversa) | DM autor | 💬 Fulano comentou na sua PR |
| `pull_request_review_comment` (comentário em código) | DM autor | 💬 Fulano comentou na sua PR |
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

**Formas de preencher o `users:`** (login do GitHub → e-mail do Teams):

| Forma | Como | Quando usar |
|---|---|---|
| **Mapa explícito** | listar `login: email` | confiável; ideal quando login ≠ e-mail |
| **Convenção `email_domain`** | `email_domain: geeknine.onmicrosoft.com` → deriva `{login}@dominio` | só se o **login == prefixo do e-mail** |
| **SSO (GitHub Enterprise)** | busca o e-mail real pela API | automático; ver seção SSO abaixo |

### 4. Garantir que o `notify.yml` está na branch `main`

Eventos `pull_request` rodam a versão do workflow que está na **branch base**. Então
o `notify.yml` precisa já estar na `main` **antes** de abrir a PR de teste.

### 5. Testar

Crie uma branch a partir da `main` → faça qualquer mudança → **abra uma PR (não-draft)**.
- Acompanhe em **Actions**.
- O card cai no grupo (com @menção). Aprove / feche / faça merge para disparar as DMs.
- Confira a entrega em **Power Automate → Meus fluxos → histórico de execuções**.

---

## Quando a mensagem é enviada (e o que pode faltar)

### Mensagens de GRUPO (PR aberta, lista de PRs)
São enviadas se:
- ✅ `TEAMS_CHANNEL_WEBHOOK` cadastrado **e** o fluxo do grupo com **"Qualquer pessoa"**.
- ✅ a PR **não é draft** (drafts são ignorados de propósito).
- A **@menção** só "pinga" se os e-mails de `approvers` forem **usuários do tenant** que estão **no grupo**.
- **Não depende** do `users:` — a notificação no grupo sai mesmo sem mapeamento.

### Mensagens de DM (aprovada, alteração, comentário, fechada, mergeada)
Só chegam se **TODAS** estas forem verdade:
1. ✅ `TEAMS_DM_WEBHOOK` cadastrado **e** o fluxo da DM com **"Qualquer pessoa"**.
2. ✅ o **login do GitHub do autor** resolve um e-mail (está em `users:`, ou via `email_domain`).
3. ✅ esse e-mail é **usuário NATIVO do tenant** (convidado/gmail **não** recebe DM).
4. ✅ (para review/comentário) quem agiu **não é o próprio autor** (auto-ação é ignorada).

### Por que "não chegou nada" — diagnóstico rápido

| Sintoma | Onde ver | Causa provável |
|---|---|---|
| `TEAMS_DM_WEBHOOK não configurado — DM ignorada.` | log do Actions | secret da DM não existe |
| `Sem e-mail do destinatário — DM ignorada.` | log do Actions | login não está em `users` (nem `email_domain`) |
| `401 Unauthorized` | log do Actions | fluxo sem **"Qualquer pessoa"** ou URL sem `sig` |
| Actions **verde**, mas DM não chega | **Power Automate → histórico** | e-mail não é usuário nativo do tenant (Flow não acha a pessoa) |
| Nenhum run apareceu | aba Actions | `notify.yml` não está na `main` / evento não habilitado |

> ⚠️ Atenção ao 4º caso: o GitHub recebe **202 (sucesso)** ao chamar o fluxo, então o
> Actions fica **verde** mesmo quando o Power Automate **falha** internamente em achar a
> pessoa. Se o Actions passou mas a DM não veio, **confira o histórico do fluxo no Power Automate**.

---

## SSO (GitHub Enterprise) — mapeamento automático

Se a empresa usa **GitHub Enterprise Cloud com SAML/SSO ligado ao Azure AD**, dá pra
descobrir o e-mail real de cada pessoa **automaticamente** — sem mapa manual nem convenção.

**Como funciona:** no SSO, cada usuário do GitHub fica vinculado a uma identidade externa
(o e-mail/UPN do Azure AD). Esse vínculo é consultável pela **API GraphQL** do GitHub:

```graphql
query($org: String!) {
  organization(login: $org) {
    samlIdentityProvider {
      externalIdentities(first: 100) {
        nodes {
          user { login }                 # login do GitHub
          samlIdentity { nameId }        # e-mail/UPN do Azure AD (Teams)
        }
      }
    }
  }
}
```

Com isso o código montaria o mapa `login → e-mail` em tempo de execução, **zero manutenção**.

**Requisitos:** GitHub Enterprise Cloud, SAML SSO configurado, e um **token (PAT) com escopo
`admin:org`** (ou `read:org` conforme a política), guardado como secret. Não está
implementado neste repo — é o caminho recomendado se/quando a empresa tiver Enterprise+SSO.

---

## Notas

- **Sem Azure / Graph / Bot:** a única "credencial" são as 2 URLs de fluxo (secrets).
- O payload enviado é: grupo `{"card": {...}}` · DM `{"recipient": "email", "card": {...}}`.
