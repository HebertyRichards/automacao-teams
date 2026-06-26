"""Envio de mensagens pro Teams via webhooks do Power Automate (app Workflows).

São dois fluxos com gatilho HTTP ("When a Teams webhook request is received"):
- canal: posta um Adaptive Card no canal dos aprovadores.
- dm: manda um Adaptive Card como DM pra um usuário (recipient por e-mail/UPN).
"""

import requests


class TeamsClient:
    def __init__(self, channel_webhook: str, dm_webhook: str = ""):
        self.channel_webhook = channel_webhook
        self.dm_webhook = dm_webhook

    @staticmethod
    def _post(url: str, payload: dict) -> None:
        resp = requests.post(url, json=payload, timeout=20)
        resp.raise_for_status()

    def post_channel(self, card: dict) -> None:
        if not self.channel_webhook:
            raise RuntimeError("TEAMS_CHANNEL_WEBHOOK não configurado.")
        self._post(self.channel_webhook, {"card": card})

    def post_dm(self, recipient_email: str, card: dict) -> None:
        if not self.dm_webhook:
            print("TEAMS_DM_WEBHOOK não configurado — DM ignorada.")
            return
        if not recipient_email:
            print("Sem e-mail do destinatário (mapeamento ausente) — DM ignorada.")
            return
        self._post(self.dm_webhook, {"recipient": recipient_email, "card": card})
