import json
import os
import sys

import cards
import deploy
import github_pr
import mapping
import sso
from models import (
    IssueCommentEvent,
    PullRequestEvent,
    ReviewCommentEvent,
    ReviewEvent,
)
from settings import Settings
from teams import TeamsClient

# Ações de PR que mexem no conjunto de PRs abertas -> atualizam a lista única.
_LIST_ACTIONS = {"opened", "reopened", "ready_for_review", "closed"}


def _load_event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _emit_message_id(message_id: str) -> None:
    """Expõe o message-id da lista pro workflow (persistir como vars token)."""
    if not message_id:
        return
    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as fh:
            fh.write(f"message_id={message_id}\n")
    print(f"message_id={message_id}")


def refresh_pr_list(settings: Settings, teams: TeamsClient) -> None:
    """Remonta a lista de PRs abertas e atualiza a mensagem única no Teams."""
    if not teams.list_webhook:
        return
    prs = github_pr.list_open_prs(settings.github_repository, settings.github_token)
    card = cards.open_prs_list(settings.github_repository, prs)
    new_id = teams.post_or_update_list(card, settings.teams_pr_message_id)
    _emit_message_id(new_id)


def handle_pull_request(event: PullRequestEvent, teams: TeamsClient,
                        user_map: dict, mentions: list[dict],
                        domain: str) -> None:
    pr = event.pull_request

    if event.action in ("opened", "reopened", "ready_for_review"):
        if pr.draft:
            print("PR em draft — ignorando.")
            return
        teams.post_channel(cards.pr_opened(pr, mentions))

    elif event.action == "closed":
        card = cards.pr_merged(pr) if pr.merged else cards.pr_closed(pr)
        teams.post_dm(mapping.email_for(pr.user.login, user_map, domain), card)

    elif event.action == "review_requested" and event.requested_reviewer:
        # cobre tanto pedir review quanto "re-request review" (avaliar de novo).
        requester = event.sender.login if event.sender else pr.user.login
        reviewer_login = event.requested_reviewer.login
        card = cards.pr_review_requested(pr, requester)
        teams.post_dm(mapping.email_for(reviewer_login, user_map, domain), card)


def handle_review(event: ReviewEvent, teams: TeamsClient, user_map: dict,
                  domain: str) -> None:
    if event.action != "submitted":
        return
    pr = event.pull_request
    reviewer = event.review.user.login
    state = event.review.state.lower()

    if state == "approved":
        card = cards.pr_approved(pr, reviewer)
    elif state == "changes_requested":
        card = cards.pr_changes_requested(pr, reviewer)
    else:
        return
    teams.post_dm(mapping.email_for(pr.user.login, user_map, domain), card)


def handle_issue_comment(event: IssueCommentEvent, teams: TeamsClient,
                         settings: Settings) -> None:
    # issue_comment só serve pro comando "/github" (refresh da lista).
    # Comentário na CONVERSA da PR NÃO gera DM — só comentário em código faz.
    if event.action != "created" or not event.issue.pull_request:
        return
    if (event.comment.body or "").strip().lower() in ("/github", "github"):
        refresh_pr_list(settings, teams)


def handle_review_comment(event: ReviewCommentEvent, teams: TeamsClient,
                          user_map: dict, domain: str) -> None:
    # DM só pra comentário em CÓDIGO (review comment).
    if event.action != "created":
        return
    pr = event.pull_request
    commenter = event.comment.user
    if commenter.login.lower() == pr.user.login.lower():
        return  # autor comentando no próprio código
    if _is_bot(commenter):
        return  # bots não geram DM
    card = cards.pr_commented(pr.number, pr.title, commenter.login,
                              event.comment.html_url, event.comment.body)
    teams.post_dm(mapping.email_for(pr.user.login, user_map, domain), card)


def handle_deploy(settings: Settings, teams: TeamsClient) -> None:
    """Card de deploy (Jenkins): projeto deployado com os commits do range."""
    base = settings.deploy_base or os.environ.get("GIT_PREVIOUS_SUCCESSFUL_COMMIT", "")
    head = settings.deploy_head or os.environ.get("GIT_COMMIT", "")
    if not head:
        raise RuntimeError("Deploy: defina DEPLOY_HEAD (ou rode no Jenkins com GIT_COMMIT).")

    if base:
        commits = deploy.commits_between(settings.github_repository, base, head,
                                         settings.github_token)
    else:
        # 1º build: sem build bem-sucedido anterior -> sem baseline p/ o range.
        print("Deploy: sem baseline (1º build) — mostrando só o último commit.")
        commits = deploy.latest_commit(settings.github_repository, head,
                                       settings.github_token)

    card = cards.deploy_card(settings.github_repository, settings.deploy_project,
                             base or head, head, commits, settings.deploy_env)
    teams.post_deploy(card)


def _build_user_map(settings: Settings) -> dict[str, str]:
    """Merge dos mapas login->email. SSO é a fonte PRINCIPAL; o user-map.yml é
    o FALLBACK (só entra pros logins que o SSO não resolveu)."""
    explicit = mapping.load_map(settings.user_map_path)
    try:
        sso_map = sso.resolve_emails(settings.github_org, settings.sso_token)
    except Exception as exc:  # SSO é best-effort: não derruba as notificações
        print(f"SSO indisponível ({exc}) — seguindo só com o mapa manual.")
        sso_map = {}
    # {**explicit, **sso_map}: SSO sobrescreve; o yml preenche o que faltar.
    return {**explicit, **sso_map}


def _is_bot(user) -> bool:
    return user.type.lower() == "bot" or user.login.lower().endswith("[bot]")


def main() -> None:
    settings = Settings()
    teams = TeamsClient(settings.teams_channel_webhook, settings.teams_dm_webhook,
                        settings.teams_list_webhook, settings.teams_deploy_webhook)

    mode = (settings.notify_mode or os.environ.get("NOTIFY_MODE", "")).lower()
    if mode == "deploy" or "--deploy" in sys.argv:
        handle_deploy(settings, teams)
        return

    user_map = _build_user_map(settings)
    # @menções no canal: aprovadores (individuais) + reviewers (times, ex.: QA).
    mentions = (mapping.load_approvers(settings.user_map_path)
                + mapping.load_reviewers(settings.user_map_path))
    domain = mapping.load_domain(settings.user_map_path)

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    raw = _load_event()

    if event_name == "pull_request":
        event = PullRequestEvent.model_validate(raw)
        handle_pull_request(event, teams, user_map, mentions, domain)
        if event.action in _LIST_ACTIONS:
            refresh_pr_list(settings, teams)
    elif event_name == "pull_request_review":
        handle_review(ReviewEvent.model_validate(raw), teams, user_map, domain)
    elif event_name == "issue_comment":
        handle_issue_comment(IssueCommentEvent.model_validate(raw), teams, settings)
    elif event_name == "pull_request_review_comment":
        handle_review_comment(ReviewCommentEvent.model_validate(raw), teams,
                              user_map, domain)
    elif event_name in ("schedule", "workflow_dispatch"):
        refresh_pr_list(settings, teams)
    else:
        print(f"Evento '{event_name}' não tratado — nada a fazer.")


if __name__ == "__main__":
    main()
