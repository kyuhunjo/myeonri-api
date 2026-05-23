pipeline {
    agent any

    environment {
        BE_WORK_DIR = "${WORKSPACE}/myeonri-be"
    }

    stages {
        stage('BE: Git Checkout') {
            steps {
                checkout([
                    branches: [[name: '**']],
                    $class: 'GitSCM',
                    doGenerateSubmoduleConfigurations: false,
                    extensions: [
                        [$class: 'RelativeTargetDirectory', relativeTargetDir: 'myeonri-be'],
                        [$class: 'CleanBeforeCheckout'],
                        [$class: 'CloneOption', noTags: true, honorRefspec: true],
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
                    def isMain = (branch == 'main')
                    def imageName = isMain ? 'myeonri-api-main' : 'myeonri-api-dev'
                    def namespace = isMain ? 'default' : 'dev'
                    def deployName = isMain ? 'myeonri-api' : 'myeonri-api-dev'
                    def deployFile = isMain ? 'k8s/deployment.yaml' : 'k8s/dev/myeonri-api-dev.yaml'
                    def redirectCred = isMain ? 'be-google-redirect-prod' : 'be-google-redirect-dev'

                    echo "Current branch: ${branch}"
                    echo "Image: ${imageName}"

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
                            docker build --no-cache -t ${imageName}:latest .

                            echo "=== Registry push ==="
                            REG_IP=10.43.19.223
                            skopeo copy --dest-tls-verify=false docker-daemon:${imageName}:latest docker://$REG_IP:5000/${imageName}:latest
                        """

                        sh """
                            set -e

                            echo "=== Deployment YAML 적용 ==="
                            kubectl apply -n ${namespace} -f ${BE_WORK_DIR}/${deployFile}

                            echo "=== Env 주입 (Jenkins credential → k8s env) ==="
                            kubectl set env deployment/${deployName} -n ${namespace} \\
                                GOOGLE_CLIENT_ID=${BE_GOOGLE_CLIENT_ID} \\
                                GOOGLE_CLIENT_SECRET=${BE_GOOGLE_CLIENT_SECRET} \\
                                GOOGLE_REDIRECT_URI=${BE_GOOGLE_REDIRECT_URI} \\
                                GROQ_API_KEY=${BE_GROQ_API_KEY} \\
                                GROQ_MODEL=${BE_GROQ_MODEL} \\
                                API_KEY=${BE_API_KEY} \\
                                OPENWEATHER_API_KEY=${BE_OPENWEATHER_KEY} \\
                                SUNRISE_API_KEY=${BE_SUNRISE_KEY} \\
                                MYSQL_PASSWORD=${BE_MYSQL_PASSWORD}

                            echo "=== Rollout 대기 ==="
                            kubectl rollout status deployment/${deployName} -n ${namespace} --timeout=180s

                            echo "=== 완료: ${imageName} ==="
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
                if (branch == 'main') {
                    echo "✅ 운영 BE 배포 성공! api.imjoe24.com"
                } else {
                    echo "✅ 개발 BE 배포 성공! dev-api.imjoe24.com"
                }
            }
        }
        failure {
            echo '❌ BE 배포 실패!'
        }
    }
}
