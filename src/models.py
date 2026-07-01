from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str
    type: str = ""   # "User" ou "Bot" — usado pra não notificar sobre bots


class Repo(BaseModel):
    full_name: str


class Base(BaseModel):
    ref: str
    repo: Repo


class Head(BaseModel):
    ref: str


class PullRequest(BaseModel):
    number: int
    title: str
    html_url: str
    draft: bool = False
    merged: bool = False
    user: GitHubUser
    head: Head
    base: Base


class Review(BaseModel):
    state: str = ""
    user: GitHubUser


class PullRequestEvent(BaseModel):
    action: str
    pull_request: PullRequest
    requested_reviewer: GitHubUser | None = None  # presente em review_requested
    sender: GitHubUser | None = None              # quem disparou o evento


class ReviewEvent(BaseModel):
    action: str
    pull_request: PullRequest
    review: Review


class Comment(BaseModel):
    html_url: str
    body: str = ""
    user: GitHubUser


class IssueRef(BaseModel):
    number: int
    title: str
    html_url: str
    user: GitHubUser
    pull_request: dict | None = None


class IssueCommentEvent(BaseModel):
    action: str
    issue: IssueRef
    comment: Comment


class ReviewCommentEvent(BaseModel):
    action: str
    pull_request: PullRequest
    comment: Comment


class CommitDetail(BaseModel):
    message: str = ""


class DeployCommit(BaseModel):
    """Item de commit retornado pela API `compare` do GitHub."""
    sha: str
    html_url: str = ""
    commit: CommitDetail = CommitDetail()
    author: GitHubUser | None = None  # pode ser null (autor sem conta no GitHub)
