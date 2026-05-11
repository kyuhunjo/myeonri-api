# Myeonri API Dev Deployment Guide

## Build (dev)
```bash
docker build --no-cache -t myeonri-api:dev .
```

## k8s 매니페스트
프론트엔드 리포지토리(`myeonri/k8s/dev/`)에서 관리:
- `myeonri-api-dev.yaml` — Deployment + Service
- `ingress.yaml` — dev-api.imjoe24.com
- `init-dev-db.sql` — appdb_dev 스키마 생성

## DB 연결 환경변수 (dev)
| 변수 | 값 |
|------|-----|
| MYSQL_DATABASE | appdb_dev |
| CORS_ORIGINS | https://dev.imjoe24.com,https://dev-api.imjoe24.com,http://localhost:5173 |
