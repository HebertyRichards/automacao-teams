import re

from models import DeployCommit, PullRequest

# Adaptive Card estoura por volta de ~28KB; limitamos os itens listados.
_MAX_ITEMS = 100

_MD_SPECIAL = re.compile(r"([\\`*_~\[\]()])")


def _md(text: str) -> str:
    return _MD_SPECIAL.sub(r"\\\1", text or "")


def _card(title: str, facts: list[tuple[str, str]], link: str | None,
          subtitle: str | None = None, link_label: str = "Abrir PR") -> dict:
    body: list[dict] = [
        {"type": "TextBlock", "size": "Large", "weight": "Bolder",
         "text": title, "wrap": True},
    ]
    if subtitle:
        body.append({"type": "TextBlock", "text": subtitle, "wrap": True,
                     "spacing": "None", "isSubtle": True})
    if facts:
        body.append({"type": "FactSet",
                     "facts": [{"title": k, "value": v} for k, v in facts]})

    actions = []
    if link:
        actions.append({"type": "Action.OpenUrl", "title": link_label, "url": link})

    return {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.4",
        "body": body,
        "actions": actions,
    }


# --- Canal -------------------------------------------------------------------

def _mentions(approvers: list[dict[str, str]]) -> tuple[str, list[dict]]:
    """Monta o texto com <at>...</at> e as entidades de menção do Teams."""
    tags: list[str] = []
    entities: list[dict] = []
    for a in approvers:
        tag = f"<at>{a['name']}</at>"
        tags.append(tag)
        entities.append({
            "type": "mention",
            "text": tag,
            "mentioned": {"id": a["email"], "name": a["name"]},
        })
    return " ".join(tags), entities


def pr_opened(pr: PullRequest, mentions: list[dict[str, str]] | None = None) -> dict:
    """PR criada/pronta — notificação no canal @mencionando aprovadores + times."""
    card = _card(
        title="🆕 Nova PR aguardando revisão",
        subtitle=_md(pr.title),
        facts=[
            ("Autor", pr.user.login),
            ("Repositório", pr.base.repo.full_name),
            ("Branch", f"{pr.head.ref} → {pr.base.ref}"),
        ],
        link=pr.html_url,
        link_label="Revisar PR",
    )
    if mentions:
        text, entities = _mentions(mentions)
        card["body"].insert(1, {
            "type": "TextBlock", "wrap": True, "spacing": "Small",
            "text": f"{text} — revisem por favor 👀",
        })
        card["msteams"] = {"entities": entities}
    return card


def open_prs_list(repo: str, prs: list[PullRequest]) -> dict:
    """Resumo de todas as PRs abertas (não-draft)."""
    if not prs:
        body = [
            {"type": "TextBlock", "size": "Large", "weight": "Bolder",
             "text": "✅ Nenhuma PR aberta", "wrap": True},
            {"type": "TextBlock", "text": repo, "isSubtle": True, "wrap": True},
        ]
    else:
        body = [
            {"type": "TextBlock", "size": "Large", "weight": "Bolder",
             "text": f"📋 PRs abertas ({len(prs)})", "wrap": True},
            {"type": "TextBlock", "text": repo, "isSubtle": True, "wrap": True,
             "spacing": "None"},
        ]
        for pr in prs[:_MAX_ITEMS]:
            # link (nome do PR) + autor
            body.append({
                "type": "TextBlock", "wrap": True, "spacing": "Small",
                "text": f"[#{pr.number} {_md(pr.title)}]({pr.html_url}) — "
                        f"_{pr.user.login}_",
            })
        hidden = len(prs) - _MAX_ITEMS
        if hidden > 0:
            body.append({"type": "TextBlock", "wrap": True, "spacing": "Small",
                         "isSubtle": True, "text": f"… e mais {hidden} PR(s)"})

    return {"type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": body, "actions": []}


# --- Deploy (Jenkins) --------------------------------------------------------

def deploy_card(repo: str, project: str, base: str, head: str,
                commits: list[DeployCommit], environment: str = "") -> dict:
    """Card de deploy: projeto X foi deployado com os commits a seguir."""
    facts: list[tuple[str, str]] = []
    if environment:
        facts.append(("Ambiente", environment))
    facts += [
        ("Repositório", repo),
        ("Range", f"{base[:7]} → {head[:7]}"),
        ("Commits", str(len(commits))),
    ]

    body: list[dict] = [
        {"type": "TextBlock", "size": "Large", "weight": "Bolder",
         "text": f"🚀 Deploy — {_md(project or repo)}", "wrap": True},
        {"type": "FactSet",
         "facts": [{"title": k, "value": v} for k, v in facts]},
    ]

    for c in commits[:_MAX_ITEMS]:
        subject = (c.commit.message or c.sha).splitlines()[0]
        line = f"[`{c.sha[:7]}`]({c.html_url}) {_md(subject)}"
        if c.author:
            line += f" — _{c.author.login}_"
        body.append({"type": "TextBlock", "wrap": True, "spacing": "Small",
                     "text": line})

    hidden = len(commits) - _MAX_ITEMS
    if hidden > 0:
        body.append({"type": "TextBlock", "wrap": True, "spacing": "Small",
                     "isSubtle": True, "text": f"… e mais {hidden} commit(s)"})

    return {"type": "AdaptiveCard",
            "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
            "version": "1.4", "body": body, "actions": []}


# --- DM pro autor ------------------------------------------------------------

def pr_merged(pr: PullRequest) -> dict:
    facts = _author_facts(pr) + [("Mergeada", f"{pr.head.ref} → {pr.base.ref}")]
    return _card("🎉 Sua PR foi mergeada!", facts, pr.html_url)


def pr_closed(pr: PullRequest) -> dict:
    facts = _author_facts(pr) + [("Branch", f"{pr.head.ref} → {pr.base.ref}")]
    return _card("🚫 Sua PR foi fechada sem merge", facts, pr.html_url)


def pr_approved(pr: PullRequest, reviewer: str) -> dict:
    return _card(f"✅ {reviewer} aprovou sua PR", _author_facts(pr), pr.html_url)


def pr_changes_requested(pr: PullRequest, reviewer: str) -> dict:
    return _card(f"📝 {reviewer} pediu alterações na sua PR",
                 _author_facts(pr), pr.html_url, link_label="Ver comentários")


def pr_review_requested(pr: PullRequest, requester: str) -> dict:
    return _card(f"🔍 {requester} pediu sua revisão na PR",
                 _author_facts(pr), pr.html_url, link_label="Revisar PR")


def pr_commented(number: int, title: str, commenter: str,
                 comment_url: str, body: str = "") -> dict:
    card = _card(f"💬 {commenter} comentou na sua PR",
                 [("PR", f"#{number} — {_md(title)}")], comment_url,
                 link_label="Ver comentário")
    if body:
        snippet = body if len(body) <= 200 else body[:200] + "…"
        card["body"].insert(1, {"type": "TextBlock", "wrap": True,
                                "text": _md(snippet), "isSubtle": True})
    return card


def _author_facts(pr: PullRequest) -> list[tuple[str, str]]:
    return [
        ("PR", f"#{pr.number} — {_md(pr.title)}"),
        ("Repositório", pr.base.repo.full_name),
    ]
