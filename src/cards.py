from models import PullRequest


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


def pr_opened(pr: PullRequest, approvers: list[dict[str, str]] | None = None) -> dict:
    """PR criada/pronta — notificação pros aprovadores no canal (com @menção)."""
    card = _card(
        title="🆕 Nova PR aguardando revisão",
        subtitle=pr.title,
        facts=[
            ("Autor", pr.user.login),
            ("Repositório", pr.base.repo.full_name),
            ("Branch", f"{pr.head.ref} → {pr.base.ref}"),
        ],
        link=pr.html_url,
        link_label="Revisar PR",
    )
    if approvers:
        text, entities = _mentions(approvers)
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
        for pr in prs:
            body.append({
                "type": "TextBlock", "wrap": True, "spacing": "Small",
                "text": f"[#{pr.number} {pr.title}]({pr.html_url}) — "
                        f"_{pr.user.login}_",
            })

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


def pr_commented(number: int, title: str, commenter: str,
                 comment_url: str, body: str = "") -> dict:
    card = _card(f"💬 {commenter} comentou na sua PR",
                 [("PR", f"#{number} — {title}")], comment_url,
                 link_label="Ver comentário")
    if body:
        snippet = body if len(body) <= 200 else body[:200] + "…"
        card["body"].insert(1, {"type": "TextBlock", "wrap": True,
                                "text": snippet, "isSubtle": True})
    return card


def _author_facts(pr: PullRequest) -> list[tuple[str, str]]:
    return [
        ("PR", f"#{pr.number} — {pr.title}"),
        ("Repositório", pr.base.repo.full_name),
    ]
