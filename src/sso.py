"""Resolve login do GitHub -> e-mail via SAML SSO (GitHub Enterprise).

No SSO, cada usuário do GitHub fica vinculado a uma identidade externa (o e-mail/UPN
do IdP). Esse vínculo é consultável pela API GraphQL do GitHub em
`organization.samlIdentityProvider.externalIdentities`.

Requer um token (PAT ou GitHub App) com escopo `admin:org` (ou `read:org` conforme a
política) na organização. O `GITHUB_TOKEN` padrão do Actions NÃO tem esse acesso.
"""

import requests

GRAPHQL = "https://api.github.com/graphql"

_QUERY = """
query($org: String!, $cursor: String) {
  organization(login: $org) {
    samlIdentityProvider {
      externalIdentities(first: 100, after: $cursor) {
        pageInfo { hasNextPage endCursor }
        nodes {
          user { login }
          samlIdentity { nameId }
        }
      }
    }
  }
}
"""


def resolve_emails(org: str, token: str) -> dict[str, str]:
    """Monta `{login: email}` a partir do SSO. Vazio se faltar org/token/IdP."""
    if not org or not token:
        return {}

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
    }
    emails: dict[str, str] = {}
    cursor: str | None = None

    while True:
        resp = requests.post(
            GRAPHQL,
            headers=headers,
            json={"query": _QUERY, "variables": {"org": org, "cursor": cursor}},
            timeout=20,
        )
        resp.raise_for_status()
        payload = resp.json()

        if payload.get("errors"):
            msgs = "; ".join(e.get("message", "") for e in payload["errors"])
            raise RuntimeError(f"Consulta SSO (GraphQL) falhou: {msgs}")

        org_data = (payload.get("data") or {}).get("organization") or {}
        idp = org_data.get("samlIdentityProvider")
        if not idp:
            print(f"Org '{org}' sem SAML IdP configurado — mapa SSO vazio.")
            return {}

        conn = idp.get("externalIdentities") or {}
        for node in conn.get("nodes") or []:
            login = ((node.get("user") or {}).get("login") or "").lower()
            name_id = (node.get("samlIdentity") or {}).get("nameId") or ""
            if login and name_id:
                emails[login] = name_id

        page = conn.get("pageInfo") or {}
        if not page.get("hasNextPage"):
            break
        cursor = page.get("endCursor")

    return emails
