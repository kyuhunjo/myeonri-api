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
        stage('Build & Deploy') {
            steps {
                script {
                    def branch = env.BRANCH_NAME
                    def isMain = branch == 'main'
                    def namespace = isMain ? 'default' : 'dev'
                    def feDir = isMain ? env.FE_MAIN_DIR : env.FE_DEV_DIR
                    def beDir = isMain ? env.BE_MAIN_DIR : env.BE_DEV_DIR
                    def feImage = isMain ? 'myeonri:latest' : 'myeonri:dev'
                    def beImage = 'myeonri-api:latest'
                    def buildMode = isMain ? 'production' : 'dev'
                    def envFile = isMain ? '/opt/myeonri-build.env' : '/opt/myeonri-build-dev.env'

                    echo "=== Deploying ${branch} → ${namespace} ==="

                    sh """
                        ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                            set -e

                            echo '=== [FE] Fetching ${branch} ==='
                            cd ${feDir}
                            git fetch origin
                            git checkout -B ${branch} origin/${branch}

                            echo '=== [FE] Building ==='
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
                            kubectl rollout restart deployment/myeonri -n ${namespace}
                            kubectl rollout status deployment/myeonri -n ${namespace} --timeout=120s || true
                            kubectl rollout restart deployment/myeonri-api -n ${namespace}
                            kubectl rollout status deployment/myeonri-api -n ${namespace} --timeout=120s || true

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
