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

                    def imageTag = "${branch}-${commitSha}"
                    def isMain = (branch == 'main')

                    // 브랜치별 설정
                    def namespace = isMain ? 'default' : 'dev'
                    def deployName = isMain ? 'myeonri-api' : 'myeonri-api-dev'
                    def deployFile = isMain ? 'k8s/deployment.yaml' : 'k8s/dev/myeonri-api-dev.yaml'
                    def redirectCred = isMain ? 'be-google-redirect-prod' : 'be-google-redirect-dev'
                    def mysqlDb = isMain ? 'appdb' : 'appdb_dev'

                    withCredentials([
                        string(credentialsId: 'be-google-client-id', variable: 'BE_GOOGLE_CLIENT_ID'),
                        string(credentialsId: 'be-google-client-secret', variable: 'BE_GOOGLE_CLIENT_SECRET'),
                        string(credentialsId: redirectCred, variable: 'BE_GOOGLE_REDIRECT_URI'),
                        string(credentialsId: 'be-groq-api-key', variable: 'BE_GROQ_API_KEY'),
                        string(credentialsId: 'be-groq-model', variable: 'BE_GROQ_MODEL'),
                        string(credentialsId: 'be-api-key', variable: 'BE_API_KEY'),
                        string(credentialsId: 'be-openweather-key', variable: 'BE_OPENWEATHER_KEY'),
                        string(credentialsId: 'be-sunrise-key', variable: 'BE_SUNRISE_KEY'),
                        string(credentialsId: 'be-mysql-password', variable: 'BE_MYSQL_PASSWORD'),
                    ]) {
                        sh """
                            cd ${BE_WORK_DIR}
                            docker build --no-cache -t myeonri-api:${imageTag} -t myeonri-api:${branch} .
                        """

                        sh """
                            set -e

                            echo "=== 이미지 전송: myeonri-api:${imageTag} ==="
                            echo "=== 이미지 전송: myeonri-api:${imageTag} ==="
                            docker save myeonri-api:${imageTag} | ssh -o StrictHostKeyChecking=no root@192.168.35.14 'ctr --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'

                            echo "=== Deployment YAML 적용 (이미지 태그 치환) ==="
                            sed 's|image: docker.io/library/myeonri-api:.*|image: docker.io/library/myeonri-api:${imageTag}|' \
                                ${BE_WORK_DIR}/${deployFile} | \
                                ssh -o StrictHostKeyChecking=no root@192.168.35.14 'kubectl apply -n ${namespace} -f -'

                            echo "=== Env 주입 (Jenkins credential → k8s env) ==="
                            kubectl set env deployment/${deployName} -n ${namespace} \
                                GOOGLE_CLIENT_ID=${BE_GOOGLE_CLIENT_ID} \
                                GOOGLE_CLIENT_SECRET=${BE_GOOGLE_CLIENT_SECRET} \
                                GOOGLE_REDIRECT_URI=${BE_GOOGLE_REDIRECT_URI} \
                                GROQ_API_KEY=${BE_GROQ_API_KEY} \
                                GROQ_MODEL=${BE_GROQ_MODEL} \
                                API_KEY=${BE_API_KEY} \
                                OPENWEATHER_API_KEY=${BE_OPENWEATHER_KEY} \
                                SUNRISE_API_KEY=${BE_SUNRISE_KEY} \
                                MYSQL_PASSWORD=${BE_MYSQL_PASSWORD}

                            echo "=== Rollout 대기 ==="
                            kubectl rollout status deployment/${deployName} -n ${namespace} --timeout=180s

                            echo "=== 완료: myeonri-api:${imageTag} ==="
                        """
                    }
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
