pipeline {
    agent any

    environment {
        WORKER_HOST = '192.168.35.14'
    }

    stages {
        stage('Build & Deploy') {
            steps {
                script {
                    def branch = sh(script: 'git name-rev --name-only HEAD 2>/dev/null || echo dev', returnStdout: true).trim()
                    branch = branch.replaceAll('^origin/', '').replaceAll('^remotes/origin/', '')
                    echo "Deploying branch: ${branch}"

                    def scriptName = (branch == 'main') ? '/opt/myeonri-build-main.sh' : '/opt/myeonri-build-dev.sh'

                    sh """
                        ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                            bash ${scriptName}
                        "
                    """
                }
            }
        }
    }

    post {
        success {
            echo '✅ 배포 성공!'
        }
        failure {
            echo '❌ 배포 실패!'
        }
    }
}
