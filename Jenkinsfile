pipeline {
    agent any

    environment {
        WORKER_HOST = "192.168.35.14"
        MASTER_HOST = "192.168.35.13"
        BE_REPO = "/opt/myeonri-api-build-dev"
        BE_IMAGE_TAG = "myeonri-api:dev"
        BE_DEPLOY_NAME = "myeonri-api-dev"
        NAMESPACE = "dev"
    }

    stages {
        stage("Git Sync") {
            steps {
                sh """
                    ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                        cd ${BE_REPO}
                        git fetch origin
                        git reset --hard origin/dev
                        echo 'BE dev: '\$(git log --oneline -1)
                    "
                """
            }
        }

        stage("Build") {
            steps {
                sh """
                    ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                        cd ${BE_REPO}
                        docker build --no-cache -t ${BE_IMAGE_TAG} .
                        echo 'BE dev build done'
                    "
                """
            }
        }

        stage("Deploy Images") {
            steps {
                sh """
                    ssh -o StrictHostKeyChecking=no root@${WORKER_HOST} "
                        export KUBECONFIG=/root/.kube/config
                        CTR_BIN=\\"\$(ls /var/lib/rancher/k3s/data/current/bin/ctr)\\"

                        docker save ${BE_IMAGE_TAG} | \\\$CTR_BIN --address /run/k3s/containerd/containerd.sock -n k8s.io image import -
                        echo 'Worker ctr import done'

                        docker save ${BE_IMAGE_TAG} | gzip > /tmp/myeonri-api-dev.tar.gz
                        scp -o StrictHostKeyChecking=no /tmp/myeonri-api-dev.tar.gz root@${MASTER_HOST}:/tmp/myeonri-api-dev.tar.gz
                        ssh -o StrictHostKeyChecking=no root@${MASTER_HOST} 'export KUBECONFIG=/root/.kube/config && CTR_BIN=\$(ls /var/lib/rancher/k3s/data/current/bin/ctr) && gunzip -c /tmp/myeonri-api-dev.tar.gz | \$CTR_BIN --address /run/k3s/containerd/containerd.sock -n k8s.io image import -'
                        echo 'Master ctr import done'

                        kubectl rollout restart deployment/${BE_DEPLOY_NAME} -n ${NAMESPACE}
                        kubectl rollout status deployment/${BE_DEPLOY_NAME} -n ${NAMESPACE} --timeout=120s
                        echo 'BE dev rollout done'
                    "
                """
            }
        }
    }

    post {
        success { echo "✅ 개발 BE 배포 성공! dev-api.imjoe24.com" }
        failure { echo "❌ 개발 BE 배포 실패!" }
    }
}
