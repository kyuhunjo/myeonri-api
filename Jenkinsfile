pipeline {
    agent any

    environment {
        WORKER_HOST = '192.168.35.14'
        FE_DEV_DIR = '/opt/myeonri-build-dev'
        FE_MAIN_DIR = '/opt/myeonri-build'
        BE_DEV_DIR = '/opt/myeonri-api-build-dev'
        BE_MAIN_DIR = '/opt/myeonri-api-build'
    }

    stages {
        stage('Detect Branch') {
            steps {
                script {
                    def raw = env.GIT_BRANCH ?: env.BRANCH_NAME ?: sh(script: 'git name-rev --name-only HEAD 2>/dev/null || echo dev', returnStdout: true).trim()
                    def branch = raw.replaceAll('^origin/', '').replaceAll('^remotes/origin/', '')
                    echo "Detected branch: ${branch}"
                    env.DEPLOY_BRANCH = branch
                }
            }
        }

        stage('Build & Deploy') {
            steps {
                script {
                    def branch = env.DEPLOY_BRANCH
                    def isMain = branch == 'main'
                    def namespace = isMain ? 'default' : 'dev'
                    def feDir = isMain ? env.FE_MAIN_DIR : env.FE_DEV_DIR
                    def beDir = isMain ? env.BE_MAIN_DIR : env.BE_DEV_DIR
                    def feImage = isMain ? 'myeonri:latest' : 'myeonri:dev'
                    def beImage = 'myeonri-api:latest'
                    def buildMode = isMain ? 'production' : 'dev'
                    def feDeploy = isMain ? 'myeonri' : 'myeonri-dev'
                    def beDeploy = isMain ? 'myeonri-api' : 'myeonri-api-dev'
                    def envPath = isMain ? '/opt/myeonri-build.env' : '/opt/myeonri-build-dev.env'

                    echo "=== Deploying ${branch} → ${namespace} (FE:${feDeploy}, BE:${beDeploy}) ==="

                    sh """
                        ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                            set -e

                            echo '=== [FE] Fetching ${branch} ==='
                            cd ${feDir}
                            git fetch origin
                            git checkout -B ${branch} origin/${branch}

                            echo '=== [FE] Building ==='
                            cp ${envPath} ${feDir}/.env 2>/dev/null || true
                            docker build --no-cache --build-arg VITE_MODE=${buildMode} -t ${feImage} .
                            docker save ${feImage} | ctr -n k8s.io image import -

                            echo '=== [BE] Fetching ${branch} ==='
                            cd ${beDir}
                            git fetch origin
                            git checkout -B ${branch} origin/${branch}

                            echo '=== [BE] Building ==='
                            docker build --no-cache -t ${beImage} .
                            docker save ${beImage} | ctr -n k8s.io image import -

                            echo '=== Deploying to ${namespace} ==='
                            kubectl rollout restart deployment/${feDeploy} -n ${namespace}
                            kubectl rollout status deployment/${feDeploy} -n ${namespace} --timeout=120s || true
                            kubectl rollout restart deployment/${beDeploy} -n ${namespace}
                            kubectl rollout status deployment/${beDeploy} -n ${namespace} --timeout=120s || true

                            echo '=== Done ==='
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
