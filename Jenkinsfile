// Notifica o Teams no DEPLOY (build de uma branch). Suporta MÚLTIPLOS AMBIENTES.
//
// O disparo é no BUILD, não a cada commit: você pode ter 10 commits na main, mas a
// notificação só sai quando este pipeline builda/deploya. O script calcula o range
// no git com as variáveis que o Jenkins já expõe:
//   GIT_PREVIOUS_SUCCESSFUL_COMMIT .. GIT_COMMIT
//
// Por padrão o deploy cai no MESMO grupo/canal das PRs (reaproveita o webhook do
// canal). Se quiser o deploy em um GRUPO SEPARADO, descomente TEAMS_DEPLOY_WEBHOOK
// abaixo e crie a credencial por ambiente.
//
// Credenciais "Secret text" no Jenkins:
//   - teams-channel-webhook : URL do fluxo do canal (grupo das PRs) — padrão
//   - github-token          : leitura do repo (API compare)
//   - teams-deploy-webhook-<ambiente> : só se usar grupo separado (opcional)

pipeline {
  agent any

  parameters {
    choice(
      name: 'DEPLOY_ENV',
      choices: ['dev', 'homologacao', 'producao'],
      description: 'Ambiente alvo do deploy'
    )
  }

  environment {
    GITHUB_TOKEN          = credentials('github-token')
    GITHUB_REPOSITORY     = 'HebertyRichards/automacao-teams'  // owner/repo
    NOTIFY_MODE           = 'deploy'
    DEPLOY_PROJECT        = 'automacao-teams'
    DEPLOY_ENV            = "${params.DEPLOY_ENV}"

    // Padrão: deploy no MESMO grupo/canal das PRs (reaproveita este webhook).
    TEAMS_CHANNEL_WEBHOOK = credentials('teams-channel-webhook')

    // GRUPO SEPARADO por ambiente? Descomente — se setado, tem prioridade sobre
    // o canal acima (resolve teams-deploy-webhook-dev/homologacao/producao).
    // TEAMS_DEPLOY_WEBHOOK = credentials("teams-deploy-webhook-${params.DEPLOY_ENV}")
  }

  stages {
    stage('Deploy') {
      steps {
        echo "Deploy no ambiente: ${params.DEPLOY_ENV}"
        // ... seu deploy real aqui ...
      }
    }

    stage('Notificar Teams') {
      steps {
        sh '''
          pip install -r requirements.txt
          python src/main.py
        '''
      }
    }
  }
}
