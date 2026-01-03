# 구현 계획 (Implementation Plan)

## 1. 환경 설정 (Docker Compose)
- [x] **프로젝트 디렉토리 구조 생성**
    - `README.md`에 정의된 구조에 따라 폴더 생성 (`apps/`, `database/`, `pgbouncer/`, `locust/`, `results/`).
    - `requirements.txt` 생성 (벤치마크 러너 및 공통 의존성).

- [x] **Docker Compose 구성 (`docker-compose.yml`)**
    - 서비스 정의: `postgres`, `pgbouncer`.
    - 애플리케이션 서비스 정의:
        - `fastapi-app`: `Dockerfile` 작성 (Base: `python:3.11-slim`).
        - `django-app`: `Dockerfile` 작성.
        - `flask-app`: `Dockerfile` 작성.
    - **리소스 제한 설정**:
        - Postgres: `cpus: '0.5'`, `mem_limit: '512m'` (DB 병목 유도를 위한 제한).
        - Apps: `cpus: '1.0'`, `mem_limit: '512m'`.
    - **Volume & Network**:
        - `pg_data` 볼륨 마운트 (데이터 영속성).
        - 내부 네트워크 `benchmark-net` 구성.

## 2. 데이터베이스 및 시딩
- [x] **스키마 설계**
    - 단순 조회가 아닌 부하를 줄 수 있는 관계형 스키마.
    - 예시: `Users` (사용자), `Posts` (게시글), `Comments` (댓글) - 1:N 관계 활용.
- [x] **시딩 스크립트 작성 (`database/seed.py`)**
    - `faker` 라이브러리 활용하여 리얼한 데이터 생성.
    - 데이터 규모: 사용자 1만 명, 게시글 5만 개, 댓글 10만 개 (조인 부하 유발용).
    - `sqlalchemy`를 사용하여 고속 삽입 (Bulk Insert) 구현.
    - 실행 방식: 로컬 또는 별도 컨테이너에서 실행하여 DB 초기화.

## 3. 애플리케이션 구현
모든 프레임워크는 동일한 로직의 API 엔드포인트를 구현합니다: `GET /benchmark/db-test`.
로직: 랜덤한 게시글을 조회하고, 해당 게시글의 작성자 정보와 댓글 일부를 조인하여 가져오는 쿼리 실행.

- [x] **공통 쿼리 로직 정의**
    - 프레임워크 간 공정한 비교를 위해 실행되는 쿼리의 복잡도를 동일하게 유지.

- [x] **FastAPI + SQLAlchemy (Async)**
    - 드라이버: `asyncpg`
    - SQLAlchemy `AsyncEngine` 설정.
    - **중요**: `pool_mode = transaction` 호환성을 위해 `asyncpg` 연결 시 `statement_cache_size=0` 또는 `prepare_threshold=None` 설정 필수 (Prepared Statement 비활성화).
    - 비동기 엔드포인트 구현.

- [x] **Flask + SQLAlchemy (Sync)**
    - 드라이버: `psycopg` (v3) 또는 `psycopg2`.
    - SQLAlchemy 동기 엔진 설정.
    - 동기 엔드포인트 구현.

- [x] **Django**
    - 드라이버: `psycopg`
    - `models.py` 정의 (공통 스키마와 일치).
    - 뷰(View) 구현.

## 4. PgBouncer 상세 설계 및 설정 (Best Practices 적용)
공식 문서 및 고성능 튜닝 가이드를 기반으로 한 설정입니다.

### 4.1 핵심 설정값 및 선정 이유
- [x] **`pgbouncer.ini` [databases] 설정**
    - `* = host=postgres port=5432` (모든 DB 요청을 내부 postgres 컨테이너로 전달)

- [x] **`pgbouncer.ini` [pgbouncer] 설정**
    - **`pool_mode = transaction`**
        - **이유**: 높은 동시성 환경에서 가장 효율적입니다. 세션 모드 대비 연결 재사용률이 압도적으로 높습니다.
    - **`max_client_conn = 10000`**
        - **이유**: 웹 서버(Locust/App)로부터 들어오는 연결 요청을 거절하지 않고 최대한 받아주기 위해 넉넉하게 설정합니다 (OS `ulimit` 고려 필요).
    - **`default_pool_size = 20`**
        - **이유**: `(Core Count * 2) + Spindle Count` 공식을 참고. 제한된 DB 리소스(0.5 vCPU)를 고려하여, 너무 많은 연결이 경합하지 않도록 20으로 제한합니다. 이는 DB가 컨텍스트 스위칭 없이 쿼리 처리에 집중하게 돕습니다.
    - **`min_pool_size = 5`**
        - **이유**: 유휴 상태에서도 최소한의 연결을 유지하여, 초기 트래픽 유입 시 연결 맺는 비용(3-way handshake)을 제거합니다.
    - **`reserve_pool_size = 5`**
        - **이유**: `default_pool_size`가 꽉 찼을 때 일시적인 스파이크를 처리하기 위한 예비 풀입니다.
    - **`so_reuseport = 1`**
        - **이유**: 리눅스 커널 기능을 사용하여 들어오는 연결 처리를 여러 프로세스/스레드에 분산시켜 네트워크 성능을 최적화합니다 (가능한 경우).
    - **`ignore_startup_parameters = extra_float_digits`**
        - **이유**: 일부 Python 드라이버(구버전 psycopg2 등)가 보내는 파라미터로 인한 에러 방지.

### 4.2 Logging 및 모니터링 (성능 영향 최소화)
- [x] **로깅 설정**
    - `log_connections = 0`: 연결/해제 로그 비활성화 (I/O 부하 감소로 벤치마크 정확도 향상).
    - `log_disconnections = 0`: 상동.
    - `log_stats = 1`: 통계 로그 활성화.
    - `stats_period = 60`: 1분 단위 통계 기록 (벤치마크 분석용).
    - `verbose = 0`: 디버그 로그 비활성화.

### 4.3 타임아웃 및 큐 관리 (Fail-fast)
- [x] **Timeout 설정**
    - `query_wait_timeout = 15`: 연결 풀 고갈 시 15초 대기 후 에러 발생 (무한 대기 방지 및 벤치마크 실패 시점 명확화).
    - `client_idle_timeout = 0`: 클라이언트 유휴 연결 끊지 않음 (벤치마크 도구의 연결 유지 보장).
    - `server_idle_timeout = 600`: 불필요한 서버 연결 정리.

### 4.4 네트워크 및 시스템 튜닝
- [x] **Network 설정**
    - `listen_backlog = 4096`: 대량의 동시 접속 요청(Thundering Herd) 처리를 위한 백로그 증설.
    - `auth_type = md5`: 표준 인증 방식 사용.

- [x] **userlist.txt 생성**
    - `md5` 기반 인증 정보 생성.

## 5. 부하 테스트 설정 (Locust)
- [x] **Locustfile 작성**
    - `User` 행동 정의: 해당 API 엔드포인트를 지속적으로 호출.
    - 동시성(Concurrency) 제어를 위한 파라미터화.
- [x] **자동화 스크립트 작성 (`run_benchmark.py`)**
    - `subprocess` 모듈을 사용하여 Docker Compose 제어.
    - **실행 로직**:
        1. `docker-compose up -d postgres` (DB 초기화).
        2. `seed.py` 실행 유무 확인 (데이터 없으면 실행).
        3. Loop: [FastAPI, Django, Flask] x [Direct, PgBouncer]:
            - 해당 앱 컨테이너 실행 (`--scale app=1`).
            - PgBouncer 필요 시 함께 실행.
            - `Locust` Headless 실행 (`--users`, `--spawn-rate`, `--run-time` 동적 전달).
            - 결과 CSV 파일 저장 및 파싱.
            - 컨테이너 종료 (`down`).
    - 결과 요약 리포트(`summary_report.md` or CSV) 자동 생성.

## 6. 실행 및 결과 정리
- [x] **벤치마크 수행**
    - 3개 프레임워크 x 2개 연결 방식(Direct, PgBouncer) = 총 6가지 케이스 테스트.
    - 사용자 수(Concurrency)를 늘려가며 한계점 확인.
- [x] **데이터 시각화**
    - 수집된 데이터를 바탕으로 비교 그래프 생성.
- [x] **README 업데이트**
    - 결과 테이블 채우기 및 분석 내용 작성.
