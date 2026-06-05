pipeline {
    agent any

    stages {
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
                        string(credentialsId: 'jenkins-token', variable: 'DOCKER_HUB_TOKEN')
                    ]) {
                        sh """
                            echo "$DOCKER_HUB_TOKEN" | docker login -u kyuhunjo --password-stdin
                        """

                        sh """
                            cd ${BE_WORK_DIR}

                            echo "=== Docker build & push ==="
                            docker build --no-cache -t kyuhunjo/${imageName}:latest .
                            docker push kyuhunjo/${imageName}:latest
                        """

                        sh """
                            set -e

                            echo "=== 노드에서 기존 이미지 정리 ==="
                            ssh -o StrictHostKeyChecking=no -i /home/jenkins/.ssh/id_rsa root@192.168.35.14 "k3s ctr -a /run/k3s/containerd/containerd.sock -n k8s.io images rm docker.io/kyuhunjo/${imageName}:latest 2>/dev/null || true"
                            ssh -o StrictHostKeyChecking=no -i /home/jenkins/.ssh/id_rsa root@192.168.35.13 "k3s ctr -a /run/k3s/containerd/containerd.sock -n k8s.io images rm docker.io/kyuhunjo/${imageName}:latest 2>/dev/null || true"

                            echo "=== Docker Hub pull secret 생성 ==="
                            kubectl delete secret docker-hub-secret -n ${namespace} --ignore-not-found
                            kubectl create secret docker-registry docker-hub-secret -n ${namespace} \
                                --docker-server=docker.io \
                                --docker-username=kyuhunjo \
                                --docker-password=${DOCKER_HUB_TOKEN}

                            echo "=== Deployment YAML 적용 ==="
                            kubectl apply -n ${namespace} -f ${deployFile}

                            echo "=== 이미지 롤아웃 강제 재시작 ==="
                            kubectl rollout restart deployment/${deployName} -n ${namespace}

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
