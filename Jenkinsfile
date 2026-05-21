pipeline {
    agent any

    environment {
        BE_WORK_DIR = "${WORKSPACE}/myeonri-be"
    }

    stages {
        stage('BE: Git Checkout') {
            steps {
                checkout([
                    $class: 'GitSCM',
                    branches: [[name: '**']],
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
                    def branch = sh(
                        script: "cd ${BE_WORK_DIR} && git name-rev --name-only HEAD | sed 's/remotes/origin//' | sed 's/^\\///'",
                        returnStdout: true
                    ).trim()

                    echo "Current branch: ${branch}"

                    def imageTag = (branch == 'main') ? 'latest' : 'dev'
                    def namespace = (branch == 'main') ? 'default' : 'dev'
                    def deployName = (branch == 'main') ? 'myeonri-api' : 'myeonri-api-dev'

                    sh """
                        cd ${BE_WORK_DIR}
                        docker build --no-cache -t myeonri-api:${imageTag} .
                    """

                    sh """
                        ssh -o StrictHostKeyChecking=no root@192.168.35.14 'echo SSH_OK'
                        docker save myeonri-api:${imageTag} | ssh -o StrictHostKeyChecking=no root@192.168.35.14 'ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'
                        kubectl rollout restart deployment/${deployName} -n ${namespace}
                        kubectl rollout status deployment/${deployName} -n ${namespace} --timeout=120s
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                def branch = sh(
                    script: "cd ${BE_WORK_DIR} && git name-rev --name-only HEAD | sed 's/remotes/origin//' | sed 's/^\\///'",
                    returnStdout: true
                ).trim()

                if (branch == 'main') {
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
