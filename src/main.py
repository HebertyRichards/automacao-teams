import json
import os

import cards
import github_pr
import mapping
from models import (
    IssueCommentEvent,
    PullRequestEvent,
    ReviewCommentEvent,
    ReviewEvent,
)
from settings import Settings
from teams import TeamsClient


def _load_event() -> dict:
    path = os.environ.get("GITHUB_EVENT_PATH")
    if not path or not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def handle_pull_request(event: PullRequestEvent, teams: TeamsClient,
                        user_map: dict, approvers: list[dict],
                        domain: str) -> None:
    pr = event.pull_request

    if event.action in ("opened", "reopened", "ready_for_review"):
        if pr.draft:
            print("PR em draft — ignorando.")
            return
        teams.post_channel(cards.pr_opened(pr, approvers))

    elif event.action == "closed":
        card = cards.pr_merged(pr) if pr.merged else cards.pr_closed(pr)
        teams.post_dm(mapping.email_for(pr.user.login, user_map, domain), card)


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
                         user_map: dict, domain: str) -> None:
    # issue_comment dispara em issues E PRs; só seguimos se for PR.
    if event.action != "created" or not event.issue.pull_request:
        return
    author = event.issue.user.login
    if event.comment.user.login.lower() == author.lower():
        return  # não notifica o autor comentando na própria PR
    card = cards.pr_commented(event.issue.number, event.issue.title,
                              event.comment.user.login, event.comment.html_url,
                              event.comment.body)
    teams.post_dm(mapping.email_for(author, user_map, domain), card)


def handle_review_comment(event: ReviewCommentEvent, teams: TeamsClient,
                          user_map: dict, domain: str) -> None:
    if event.action != "created":
        return
    pr = event.pull_request
    if event.comment.user.login.lower() == pr.user.login.lower():
        return
    card = cards.pr_commented(pr.number, pr.title, event.comment.user.login,
                              event.comment.html_url, event.comment.body)
    teams.post_dm(mapping.email_for(pr.user.login, user_map, domain), card)


def handle_schedule(settings: Settings, teams: TeamsClient) -> None:
    prs = github_pr.list_open_prs(settings.github_repository, settings.github_token)
    teams.post_channel(cards.open_prs_list(settings.github_repository, prs))


def main() -> None:
    settings = Settings()
    teams = TeamsClient(settings.teams_channel_webhook, settings.teams_dm_webhook)
    user_map = mapping.load_map(settings.user_map_path)
    approvers = mapping.load_approvers(settings.user_map_path)
    domain = mapping.load_domain(settings.user_map_path)

    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    raw = _load_event()

    if event_name == "pull_request":
        handle_pull_request(PullRequestEvent.model_validate(raw), teams,
                            user_map, approvers, domain)
    elif event_name == "pull_request_review":
        handle_review(ReviewEvent.model_validate(raw), teams, user_map, domain)
    elif event_name == "issue_comment":
        handle_issue_comment(IssueCommentEvent.model_validate(raw), teams,
                             user_map, domain)
    elif event_name == "pull_request_review_comment":
        handle_review_comment(ReviewCommentEvent.model_validate(raw), teams,
                              user_map, domain)
    elif event_name in ("schedule", "workflow_dispatch"):
        handle_schedule(settings, teams)
    else:
        print(f"Evento '{event_name}' não tratado — nada a fazer.")


if __name__ == "__main__":
    main()

##  vamooo  novamente