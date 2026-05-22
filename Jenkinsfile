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

        stage('BE: Build & Deploy') {
            steps {
                script {
                    def branch = env.BRANCH_NAME
                    def commitSha = sh(
                        script: "cd ${BE_WORK_DIR} && git rev-parse --short HEAD",
                        returnStdout: true
                    ).trim()

                    echo "Current branch: ${branch}"
                    echo "Commit SHA: ${commitSha}"

                    def namespace = (branch == 'main') ? 'default' : 'dev'
                    def deployName = (branch == 'main') ? 'myeonri-api' : 'myeonri-api-dev'
                    def deployFile = (branch == 'main') ? 'k8s/deployment.yaml' : 'k8s/dev/myeonri-api-dev.yaml'

                    def imageTag = "${branch}-${commitSha}"

                    sh """
                        cd ${BE_WORK_DIR}
                        docker build --no-cache -t myeonri-api:${imageTag} -t myeonri-api:${branch} .
                    """

                    sh """
                        set -e

                        echo "=== 이미지 전송: myeonri-api:${imageTag} ==="
                        docker save myeonri-api:${imageTag} | ssh -o StrictHostKeyChecking=no root@192.168.35.14 'ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'

                        echo "=== Deployment YAML 적용 ==="
                        sed 's|image: docker.io/library/myeonri-api:.*|image: docker.io/library/myeonri-api:${imageTag}|' \\
                            ${BE_WORK_DIR}/${deployFile} | \\
                            ssh -o StrictHostKeyChecking=no root@192.168.35.14 'kubectl apply -n ${namespace} -f -'

                        echo "=== Rollout 대기 ==="
                        kubectl rollout status deployment/${deployName} -n ${namespace} --timeout=180s

                        echo "=== 완료: myeonri-api:${imageTag} ==="
                    """
                }
            }
        }
    }

    post {
        success {
            script {
                def branch = env.BRANCH_NAME
                def commitSha = sh(
                    script: "cd ${BE_WORK_DIR} && git rev-parse --short HEAD",
                    returnStdout: true
                ).trim()

                if (branch == 'main') {
                    echo "✅ 운영 BE 배포 성공! api.imjoe24.com (${commitSha})"
                } else {
                    echo "✅ 개발 BE 배포 성공! dev-api.imjoe24.com (${commitSha})"
                }
            }
        }
        failure {
            echo '❌ BE 배포 실패!'
        }
    }
}
