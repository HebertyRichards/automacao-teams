# automacao-teams

Notifica o **Microsoft Teams** sobre Pull Requests do GitHub, usando **GitHub Actions** + **Power Automate**. Sem servidor, sem Azure Bot.

## O que faz

- **No grupo/canal** (aprovadores): quando uma PR é **aberta / reaberta / fica pronta** (drafts são ignorados), **@mencionando os aprovadores**.
- **Na DM do autor** (Flow bot): quando a PR é **aprovada**, alguém **pede alterações**, é **fechada** ou é **mergeada** (mostrando a branch `origem → destino`).
- **Lista única de PRs abertas** (opcional): **UMA** mensagem que é **atualizada no lugar** (não reposta, sem flood), referenciada pelo message-id guardado como variável do repo (o **"vars token"**).
- **Deploy** (opcional, via **Jenkins**): card *"projeto deployado com os commits a seguir"* — disparado no **build**, não a cada commit.
- **E-mail via SSO/SAML** (opcional): resolve `login do GitHub → e-mail do Teams` **automaticamente** pela API do GitHub, sem mapa manual.

```
Evento de PR ─► GitHub Actions ─► POST ─► Power Automate ─► Teams (grupo / DM / lista)
Deploy       ─► Jenkins        ─► POST ─► Power Automate ─► Teams (deploy)
```

## Eventos cobertos

| Evento do GitHub | Para onde vai | Mensagem |
|---|---|---|
| PR `opened` / `reopened` / `ready_for_review` (não-draft) | grupo | 🆕 Nova PR + @menção de aprovadores + times (ex.: QA) |
| PR `review_requested` (pedir review / re-request) | DM revisor | 🔍 Fulano pediu sua revisão na PR |
| review `approved` | DM autor | ✅ Fulano aprovou sua PR |
| review `changes_requested` | DM autor | 📝 Fulano pediu alterações |
| `pull_request_review_comment` (comentário em **código**) | DM autor | 💬 Fulano comentou na sua PR (bots **não** notificam) |
| PR `closed` (sem merge) | DM autor | 🚫 PR fechada sem merge (com branch) |
| PR `closed` (com merge) | DM autor | 🎉 PR mergeada (com branch `origem → destino`) |
| PR `opened`/`reopened`/`ready`/`closed` | lista | 🔄 atualiza a mensagem única de PRs abertas |
| `schedule` / `workflow_dispatch` | lista | 🔄 atualiza a mensagem única de PRs abertas |
| comentário **`/github`** numa PR | lista | 🔄 força o refresh da mensagem única |
| deploy (Jenkins) | deploy | 🚀 projeto deployado + commits do range |

## Estrutura

```
.github/workflows/notify.yml   # workflow que ESTE repo consome (dispara nos eventos)
src/
  main.py        # roteia por evento / modo deploy
  models.py      # modelos Pydantic do evento do GitHub
  settings.py    # config de ambiente (pydantic-settings)
  teams.py       # POST nos webhooks do Power Automate (canal/dm/lista/deploy)
  github_pr.py   # lista PRs abertas via API REST
  deploy.py      # commits do range (API compare) p/ o card de deploy
  sso.py         # login -> email via SAML SSO (GraphQL)
  cards.py       # Adaptive Cards
  mapping.py     # github login -> email / aprovadores
config/user-map.yml            # mapa github↔teams + aprovadores
ci/Jenkinsfile.deploy          # exemplo de pipeline p/ o card de deploy
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

| Secret / Variable | Tipo | Obrigatório | Valor |
|---|---|---|---|
| `TEAMS_CHANNEL_WEBHOOK` | secret | sim | URL do fluxo do grupo |
| `TEAMS_DM_WEBHOOK` | secret | opcional | URL do fluxo da DM |
| `TEAMS_LIST_WEBHOOK` | secret | opcional | URL do fluxo da **lista única** (update-in-place) |
| `SSO_TOKEN` | secret | opcional | PAT/GitHub App com `admin:org` — **só** pro SSO |
| `GH_VARS_TOKEN` | secret | opcional | PAT/GitHub App com escopo p/ gravar variables — **só** pro vars token |
| `TEAMS_PR_MESSAGE_ID` | **variable** | auto | o **"vars token"** — gravado pelo próprio workflow |

> **Deploy (Jenkins)** usa credenciais no próprio Jenkins (`teams-deploy-webhook`,
> `github-token`), **não** secrets do GitHub. Veja a seção Jenkins abaixo.

> ⚠️ O `TEAMS_PR_MESSAGE_ID` é uma **variable** (não secret), criada/atualizada
> **automaticamente** pelo workflow após a primeira postagem da lista. Para gravá-la o
> workflow usa o `GH_VARS_TOKEN` (**separado** do `SSO_TOKEN`): PAT com `repo` ou
> GitHub App com permissão *Variables: write*.

### 3. Preencher `config/user-map.yml`

Todos no mesmo formato de mapa `Nome/Login: email`:

```yaml
users:                                   # DM pro autor (login GitHub -> email Teams)
  SeuLoginGitHub: voce@tenant.onmicrosoft.com
approvers:                               # @mencionados no canal quando abre PR
  Fulano: fulano@tenant.onmicrosoft.com
  Beltrano: beltrano@tenant.onmicrosoft.com
reviewers:                               # time(s) @mencionado(s) junto (ex.: QA)
  QA: qa@tenant.onmicrosoft.com
  DevOps: devops@tenant.onmicrosoft.com
```

> O e-mail (em `users`, `approvers` e `reviewers`) tem que ser o mesmo com que a pessoa
> entra no Teams, e deve ser **usuário nativo do tenant** (convidado não recebe DM do Flow bot).

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

### Mensagens de GRUPO (PR aberta)
São enviadas se:
- ✅ `TEAMS_CHANNEL_WEBHOOK` cadastrado **e** o fluxo do grupo com **"Qualquer pessoa"**.
- ✅ a PR **não é draft** (drafts são ignorados de propósito).
- A **@menção** só "pinga" se os e-mails de `approvers` forem **usuários do tenant** que estão **no grupo**.
- **Não depende** do `users:` — a notificação no grupo sai mesmo sem mapeamento.

> A **lista única de PRs** (📋) é um fluxo separado (`TEAMS_LIST_WEBHOOK`); se o secret
> não existir, o refresh é ignorado silenciosamente. Veja a seção *"Lista única"*.

### Mensagens de DM (aprovada, alteração, comentário em código, fechada, mergeada)
Só chegam se **TODAS** estas forem verdade:
1. ✅ `TEAMS_DM_WEBHOOK` cadastrado **e** o fluxo da DM com **"Qualquer pessoa"**.
2. ✅ o **login do GitHub do autor** resolve um e-mail (SSO, `users:` ou `email_domain`).
3. ✅ esse e-mail é **usuário NATIVO do tenant** (convidado/gmail **não** recebe DM).
4. ✅ (para review/comentário) quem agiu **não é o próprio autor** (auto-ação é ignorada).

> **Comentários:** só **comentário em código** (`pull_request_review_comment`) gera DM.
> Comentário na **conversa** da PR **não** notifica, e **bots não geram DM**.

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

Isso está **implementado** em `src/sso.py`: o mapa `login → e-mail` é montado em tempo
de execução, **zero manutenção**. O **SSO é a fonte principal**; o `user-map.yml` é só
fallback. Precedência:

**SSO (principal) → `users:` (fallback) → convenção `email_domain`**.

Vale também pros **aprovadores**: liste-os por `login` que o e-mail da @menção vem do
SSO; o `email` no yml só entra se o SSO não resolver aquele login.

**Como ligar:**
1. Crie um **PAT** (ou GitHub App) com escopo **`admin:org`** (ou `read:org`).
2. Cadastre como secret **`SSO_TOKEN`** (o workflow já injeta `GITHUB_ORG`).
3. Pronto — o SSO passa a resolver os e-mails. Se o token faltar ou a org não tiver
   IdP, o código cai de volta no mapa manual (best-effort, não quebra).

> ⚠️ O `GITHUB_TOKEN` padrão do Actions **não** consegue ler o `samlIdentityProvider`
> — por isso o SSO exige um token próprio (`SSO_TOKEN`).

---

## Lista única de PRs ("vars token") — sem flood

Em vez de postar a lista a cada evento (o que **floodaria** o chat), mantemos **UMA**
mensagem que é **atualizada no lugar**. O message-id dessa mensagem é o **"vars token"**:
guardado como **variável do repositório** (`TEAMS_PR_MESSAGE_ID`) pelo próprio workflow.

**Fluxo `lista` no Power Automate** → secret `TEAMS_LIST_WEBHOOK`. Diferente dos outros,
ele precisa **editar** e **responder com o id**:
- Recebe `triggerBody()?['card']` e `triggerBody()?['message_id']`.
- **Condição:** se `message_id` estiver **vazio** → ação **"Postar cartão"** (captura o id
  gerado); senão → ação **"Atualizar um cartão adaptável em um chat ou canal"** usando o
  `message_id`.
- No fim, **"Responder à solicitação de webhook do Teams"** com corpo
  `{"message_id": "<id da mensagem>"}` (o `id` que a ação de postar retornou).

O workflow lê `vars.TEAMS_PR_MESSAGE_ID`, chama o fluxo, e **grava de volta** o id
retornado (passo *"Persistir message-id"* — usa o `SSO_TOKEN`). Assim a próxima execução
**atualiza a mesma mensagem** em vez de criar outra.

- **Refresh manual:** rode o workflow por **`workflow_dispatch`** ou comente **`/github`**
  numa PR.
- **Sem apagar/repostar:** por segurança, o fluxo só **posta/atualiza** — nunca apaga.
- **Concurrency:** o workflow serializa os runs (`group: teams-notify-<repo>`,
  `cancel-in-progress: false`) pra 2 PRs simultâneas não brigarem pelo vars token
  nem duplicarem a mensagem.

> **Limite de card:** listas (PRs e commits de deploy) são cortadas em **100 itens**
> (com "… e mais N") — Adaptive Card estoura por volta de ~28KB.

---

## Deploy via Jenkins — card com os commits

O disparo é no **build/deploy**, não a cada commit. O script calcula o **range no git**
(`GIT_PREVIOUS_SUCCESSFUL_COMMIT`..`GIT_COMMIT`, que o Jenkins expõe) e lista os commits
via **API `compare`** do GitHub, montando o card 🚀 *"projeto deployado com os commits"*.

**Grupo do deploy:** por **padrão o deploy cai no MESMO grupo/canal das PRs** —
reaproveita o webhook `teams-channel-webhook` (credencial do Jenkins). Se quiser o
deploy em um **grupo SEPARADO**, descomente `TEAMS_DEPLOY_WEBHOOK` no
[`Jenkinsfile`](Jenkinsfile) e crie a credencial por ambiente
(`teams-deploy-webhook-<ambiente>`); quando setado, ele tem prioridade sobre o canal.

**Multi-ambiente:** o parâmetro `DEPLOY_ENV` (`dev`/`homologacao`/`producao`) rotula o
card e, se você usar grupo separado, seleciona a credencial certa — adicione ambientes
na lista `choices` conforme precisar. Variáveis:

| Env | Uso |
|---|---|
| `NOTIFY_MODE=deploy` | ativa o modo deploy |
| `TEAMS_CHANNEL_WEBHOOK` | webhook do grupo das PRs — usado por padrão pelo deploy |
| `TEAMS_DEPLOY_WEBHOOK` | opcional — webhook de um **grupo separado** por ambiente (tem prioridade) |
| `GITHUB_TOKEN` | leitura do repo (API compare) |
| `GITHUB_REPOSITORY` | `owner/repo` |
| `DEPLOY_PROJECT` / `DEPLOY_ENV` | nome do projeto e ambiente (rótulos do card) |
| `DEPLOY_BASE` / `DEPLOY_HEAD` | opcional — sobrepõe o range (senão usa as vars do Jenkins) |

---

## Notas

- **Sem Azure / Graph / Bot:** a única "credencial" são as 2 URLs de fluxo (secrets).
- O payload enviado é: grupo `{"card": {...}}` · DM `{"recipient": "email", "card": {...}}`.
