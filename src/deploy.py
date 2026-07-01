"""Lista os commits incluídos num deploy (range base..head) via API do GitHub.

Usado pelo modo `--deploy` (disparado pelo Jenkins no build). O range vem do
próprio build: no Jenkins, `GIT_PREVIOUS_SUCCESSFUL_COMMIT`..`GIT_COMMIT`.
"""

import requests

from models import DeployCommit

API = "https://api.github.com"


def commits_between(repo: str, base: str, head: str, token: str) -> list[DeployCommit]:
    """Commits entre `base` e `head` (exclui `base`, inclui `head`)."""
    if not token:
        raise RuntimeError("GITHUB_TOKEN não definido.")
    if not base or not head:
        raise RuntimeError("Deploy: refs de base/head ausentes.")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    raw: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            f"{API}/repos/{repo}/compare/{base}...{head}",
            headers=headers,
            params={"per_page": 100, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json().get("commits") or []
        raw.extend(batch)
        if len(batch) < 100:      # última página do array de commits
            break
        page += 1

    return [DeployCommit.model_validate(item) for item in raw]


def latest_commit(repo: str, head: str, token: str) -> list[DeployCommit]:
    """Só o commit `head` — fallback pro 1º build (sem baseline anterior)."""
    if not token:
        raise RuntimeError("GITHUB_TOKEN não definido.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(f"{API}/repos/{repo}/commits/{head}", headers=headers,
                        timeout=20)
    resp.raise_for_status()
    return [DeployCommit.model_validate(resp.json())]
