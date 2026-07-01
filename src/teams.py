"""Envio de mensagens pro Teams via webhooks do Power Automate (app Workflows).

Fluxos com gatilho HTTP ("When a Teams webhook request is received"):
- canal: posta um Adaptive Card no canal dos aprovadores.
- dm: manda um Adaptive Card como DM pra um usuário (recipient por e-mail/UPN).
- lista: mantém UMA mensagem com os PRs abertos, atualizada no lugar (update-in-place).
  Recebe `{card, message_id?}` e RESPONDE com `{message_id}` (o "vars token").
- deploy: posta o card de deploy do Jenkins (cai no canal se não configurado).
"""

import requests


class TeamsClient:
    def __init__(self, channel_webhook: str, dm_webhook: str = "",
                 list_webhook: str = "", deploy_webhook: str = ""):
        self.channel_webhook = channel_webhook
        self.dm_webhook = dm_webhook
        self.list_webhook = list_webhook
        self.deploy_webhook = deploy_webhook

    @staticmethod
    def _post(url: str, payload: dict) -> requests.Response:
        resp = requests.post(url, json=payload, timeout=20)
        if resp.status_code >= 400:
            raise RuntimeError(f"Falha ao postar no Teams: HTTP {resp.status_code}")
        return resp

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

    def post_or_update_list(self, card: dict, message_id: str = "") -> str:
        """Atualiza a mensagem única da lista (ou cria se não houver id).

        Devolve o message-id (novo ou o mesmo), pra ser guardado como vars token.
        """
        if not self.list_webhook:
            raise RuntimeError("TEAMS_LIST_WEBHOOK não configurado.")
        payload: dict = {"card": card}
        if message_id:
            payload["message_id"] = message_id
        resp = self._post(self.list_webhook, payload)
        return self._extract_message_id(resp) or message_id

    def post_deploy(self, card: dict) -> None:
        url = self.deploy_webhook or self.channel_webhook
        if not url:
            raise RuntimeError(
                "Nenhum webhook pra deploy (TEAMS_DEPLOY_WEBHOOK/CHANNEL).")
        self._post(url, {"card": card})

    @staticmethod
    def _extract_message_id(resp: requests.Response) -> str:
        try:
            data = resp.json()
        except ValueError:
            return ""
        if isinstance(data, dict):
            for key in ("message_id", "messageId", "id"):
                if data.get(key):
                    return str(data[key])
        return ""
