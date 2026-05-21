pipeline {
    agent any

    environment {
        BE_WORK_DIR = "${WORKSPACE}/myeonri-be"
        BRANCH_NAME = "${env.BRANCH_NAME}"
        IMAGE_TAG = "${env.BRANCH_NAME == 'main' ? 'latest' : 'dev'}"
        NAMESPACE = "${env.BRANCH_NAME == 'main' ? 'default' : 'dev'}"
        DEPLOY_NAME = "${env.BRANCH_NAME == 'main' ? 'myeonri-api' : 'myeonri-api-dev'}"
    }

    stages {
        stage('BE: Git Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: "*/${env.BRANCH_NAME}"]],
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [
                        [$class: 'RelativeTargetDirectory', relativeTargetDir: 'myeonri-be'],
                        [$class: 'CleanBeforeCheckout']
                    ],
                    submoduleCfg: [],
                    userRemoteConfigs: [[
                        url: 'https://github.com/kyuhunjo/myeonri-api.git',
                        credentialsId: 'github-token'
                    ]]
                ])
            }
        }

        stage('BE: Build') {
            steps {
                script {
                    sh """
                        cd ${BE_WORK_DIR}
                        docker build --no-cache -t myeonri-api:${IMAGE_TAG} .
                    """
                }
            }
        }

        stage('BE: Deploy') {
            steps {
                script {
                    sh """
                        ssh -o StrictHostKeyChecking=no root@192.168.35.14 'echo SSH_OK'
                        docker save myeonri-api:${IMAGE_TAG} | ssh -o StrictHostKeyChecking=no root@192.168.35.14 'ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'
                        kubectl rollout restart deployment/${DEPLOY_NAME} -n ${NAMESPACE}
                        kubectl rollout status deployment/${DEPLOY_NAME} -n ${NAMESPACE} --timeout=120s
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                if (env.BRANCH_NAME == 'main') {
                    echo '✅ 운영 BE 배포 성공! api.imjoe24.com'
                } else {
                    echo '✅ 개발 BE 배포 성공! dev-api.imjoe24.com'
                }
            }
        }
        failure {
            echo '❌ BE 배포 실패!'
        }
    }
}
