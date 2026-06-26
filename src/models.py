from pydantic import BaseModel


class GitHubUser(BaseModel):
    login: str


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


class ReviewEvent(BaseModel):
    action: str
    pull_request: PullRequest
    review: Review
