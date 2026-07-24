# myeonri-api 배포 가이드 (마스터 빌드/푸시, v2)

## 🚀 빠른 배포

```bash
cd /home/kyuhun/.openclaw/workspace/myeonri-api
./deploy-master.sh [설명]
```

## 📦 워크플로우 (2 hop)

```
[1] 로컬(WSL) ── tar + scp ──→ [2] 마스터(192.168.35.13)
                                       ├─ docker build
                                       ├─ docker push (Docker Hub 자격증명)
                                       └─ k3s JSON patch + rollout
```

## 🔧 스크립트 동작 (4단계)

| 단계 | 명령 | 위치 |
|---|---|---|
| [1/4] 소스 전송 | `tar czf → scp → ssh tar xzf` (python cache, .env, .git 제외) | 로컬 → 마스터 |
| [2/4] Docker 빌드 | `docker build --no-cache` (python:3.12-slim, multi-stage) | 마스터 |
| [3/4] Docker Hub 푸시 | `docker push` | 마스터 |
| [4/4] k3s rollout | `kubectl patch + rollout status` | 마스터 |

## 🎯 k3s Deployment 매핑

| Deployment | namespace | 라우팅 | imagePullPolicy | imagePullSecrets |
|---|---|---|---|---|
| `myeonri-api` | `default` | api.imjoe24.com | `IfNotPresent` | `docker-hub-secret` |

## ⚠️ 런타임 env 주입 (k8s)

- API Dockerfile은 `requirements.txt`만 빌드. **빌드 시 env 불필요**.
- 런타임 env (DB, GOOGLE_CLIENT_ID, API_KEY, GROQ_API_KEY 등)는 k8s deployment spec에서 주입됨.
- `deployment.yaml` 참고: `env:` 블록에 모든 시크릿이 inline되어 있음.
- 빌드/푸시만으로는 env가 변경되지 않으므로, env 변경 시 별도 patch 필요.

## 📜 옛날 워크플로우 (DEPRECATED)

```
로컬 → 워커 빌드/save → 마스터 load + push → k3s
```

## 🛠️ 트러블슈팅

### 빌드 실패 시
- 마스터에서 `/root/build-contexts/myeonri-api/` 확인
- `requirements.txt` 의존성 오류 가능성 (pip install 실패)

### Push 실패 시
- 마스터 `docker login` 확인

### Rollout 실패 시
- k3s `kubectl get pods -n default -l app=myeonri-api`
- `kubectl describe pod ...` 로 상세 확인
- env 주입 누락 시 컨테이너가 시작 시 env 못 읽고 fail. `kubectl logs ...` 확인.

### DB 연결 실패 시
- mysql-service.default.svc.cluster.local ping 확인 (pod 안에서)
- myeonri-api deployment env의 MYSQL_* 확인
