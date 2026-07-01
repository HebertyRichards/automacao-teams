from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore",
                                      case_sensitive=False)

    github_token: str = ""
    github_repository: str = ""
    github_org: str = ""

    # SSO/SAML (GitHub Enterprise): token com escopo admin:org/read:org.
    # O GITHUB_TOKEN padrão do Actions NÃO consegue ler o samlIdentityProvider.
    sso_token: str = ""

    teams_channel_webhook: str = ""
    teams_dm_webhook: str = ""
    teams_list_webhook: str = ""       # lista única de PRs (update-in-place)
    teams_deploy_webhook: str = ""     # deploy (Jenkins); cai no canal se vazio

    # "vars token": message-id da lista guardado como variável do repositório.
    teams_pr_message_id: str = ""

    user_map_path: str = ""

    # Deploy (Jenkins). Base/head caem nas envs do Jenkins se não vierem aqui.
    notify_mode: str = ""
    deploy_project: str = ""
    deploy_env: str = ""
    deploy_base: str = ""
    deploy_head: str = ""
