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


def _load_mentions(path: str, key: str) -> list[dict[str, str]]:
    """@menções no formato de mapa `Nome: email` (igual ao `users:`). O nome é o
    texto exibido na @menção no Teams. Usada por approvers e reviewers."""
    if not path or not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    items = data.get(key) or {}
    return [
        {"name": str(name), "email": str(email)}
        for name, email in items.items()
        if name and email
    ]


def load_approvers(path: str) -> list[dict[str, str]]:
    """Aprovadores individuais @mencionados no canal (nome do Teams + e-mail)."""
    return _load_mentions(path, "approvers")


def load_reviewers(path: str) -> list[dict[str, str]]:
    """Time(s) revisor(es) @mencionado(s) junto — ex.: QA (nome + e-mail do time)."""
    return _load_mentions(path, "reviewers")
