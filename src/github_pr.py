import requests

from models import PullRequest

API = "https://api.github.com"


def list_open_prs(repo: str, token: str) -> list[PullRequest]:
    """Lista PRs abertos do repo (owner/name), excluindo drafts."""
    if not token:
        raise RuntimeError("GITHUB_TOKEN não definido.")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    raw: list[dict] = []
    page = 1
    while True:
        resp = requests.get(
            f"{API}/repos/{repo}/pulls",
            headers=headers,
            params={"state": "open", "per_page": 100, "page": page},
            timeout=20,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        raw.extend(batch)
        page += 1
    prs = [PullRequest.model_validate(item) for item in raw]
    return [pr for pr in prs if not pr.draft]
