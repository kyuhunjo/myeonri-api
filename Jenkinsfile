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
                    // Jenkins 멀티브랜치 파이프라인의 브랜치명 사용
                    def branch = env.BRANCH_NAME

                    def commitSha = sh(
                        script: "cd ${BE_WORK_DIR} && git rev-parse --short HEAD",
                        returnStdout: true
                    ).trim()

                    echo "Current branch: ${branch}"
                    echo "Commit SHA: ${commitSha}"

                    def namespace = (branch == 'main') ? 'default' : 'dev'
                    def deployName = (branch == 'main') ? 'myeonri-api' : 'myeonri-api-dev'
                    def containerName = (branch == 'main') ? 'myeonri-api' : 'myeonri-api-dev'

                    // 유니크 이미지 태그: 브랜치-커밋SHA
                    def imageTag = "${branch}-${commitSha}"

                    sh """
                        cd ${BE_WORK_DIR}
                        docker build --no-cache -t myeonri-api:${imageTag} -t myeonri-api:${branch} .
                    """

                    sh """
                        set -e

                        echo "=== 이미지 전송: myeonri-api:${imageTag} ==="
                        docker save myeonri-api:${imageTag} | ssh -o StrictHostKeyChecking=no root@192.168.35.14 'ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'

                        echo "=== Deployment 이미지 업데이트 ==="
                        kubectl set image deployment/${deployName} -n ${namespace} ${containerName}=docker.io/library/myeonri-api:${imageTag}

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
