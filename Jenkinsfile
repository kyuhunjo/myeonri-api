pipeline {
    agent any

    environment {
        BE_WORK_DIR = "${WORKSPACE}/myeonri-be"
        BE_IMAGE_TAG = "myeonri-api:dev"
        BE_DEPLOY_NAME = "myeonri-api-dev"
        NAMESPACE = "dev"
    }

    stages {
        stage('BE: Git Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '*/dev']],
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
                        docker build --no-cache -t ${BE_IMAGE_TAG} .
                    """
                }
            }
        }

        stage('BE: Deploy') {
            steps {
                script {
                    sh """
                        docker save ${BE_IMAGE_TAG} -o /tmp/myeonri-api-dev.tar
                        k3s ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import /tmp/myeonri-api-dev.tar
                        rm -f /tmp/myeonri-api-dev.tar
                        kubectl rollout restart deployment/${BE_DEPLOY_NAME} -n ${NAMESPACE}
                        kubectl rollout status deployment/${BE_DEPLOY_NAME} -n ${NAMESPACE} --timeout=120s
                    """
                }
            }
        }
    }

    post {
        success { echo "✅ 개발 BE 배포 성공! dev-api.imjoe24.com" }
        failure { echo "❌ 개발 BE 배포 실패!" }
    }
}
