"""Mapeamento login do GitHub -> e-mail/UPN do Teams.

O arquivo (YAML) fica no repo que usa a automação, no formato:

    users:
      octocat: octocat@empresa.com
      fulano-dev: fulano@empresa.com
"""

import os

import yaml


def load_map(path: str) -> dict[str, str]:
    if not path or not os.path.exists(path):
        print(f"Mapeamento não encontrado em '{path}' — DMs ficarão sem destinatário.")
        return {}
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    users = data.get("users") or {}
    return {str(login).lower(): email for login, email in users.items()}


def load_domain(path: str) -> str:
    """Domínio opcional p/ derivar e-mail automaticamente: {login}@dominio."""
    if not path or not os.path.exists(path):
        return ""
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return str(data.get("email_domain") or "")


def email_for(login: str, mapping: dict[str, str], domain: str = "") -> str:
    login = (login or "").lower()
    if login in mapping:          # exceção explícita tem prioridade
        return mapping[login]
    if domain and login:          # convenção: {login}@dominio
        return f"{login}@{domain}"
    return ""


def load_approvers(path: str) -> list[dict[str, str]]:
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    approvers = data.get("approvers") or []
    return [
        {"name": str(a["name"]), "email": str(a["email"])}
        for a in approvers
        if isinstance(a, dict) and a.get("name") and a.get("email")
    ]
