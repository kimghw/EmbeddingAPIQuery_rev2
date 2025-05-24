```yaml
project_workflow:
  name: "Email Integration & Management System (with Clean Architecture & Thin Adapter)"
  description: "Graph API를 통한 이메일 변경사항 감지/분석/외부 API 전송 시스템을, Clean Architecture 기반으로 FastAPI + 에이전트(Worker) 환경에서 개발하기 위한 전체 워크플로우"

  phases:

    - phase: "1. 디렉토리 구조 및 초기 설계"
      steps:
        - name: "프로젝트 기본 구조 생성"
          description: >
            - 클린 아키텍처와 얇은 어댑터 구조를 적용하기 위해 아래 폴더 구조를 초기 생성합니다.
            - 프로젝트 루트에 main.py (FastAPI 엔트리포인트) 생성
            - core/ 아래에 domain, usecases, services, utils (필요 시) 디렉토리를 생성
            - adapters/ 아래에 api, cli, db, worker 등 외부 연결 어댑터 디렉토리를 생성
            - tests/ 아래에 단위 및 통합 테스트를 작성할 폴더 생성
            - config/ (또는 settings/) 폴더를 두어 환경 설정(Pydantic Settings) 파일을 관리
        - name: "핵심 로직(비즈니스 코어)와 어댑터 레이어 분리"
          description: >
            - core/* 폴더에는 도메인 엔티티, 유즈케이스, 서비스 로직만 위치시킵니다.
            - adapters/* 폴더에는 DB, 외부 API, CLI, FastAPI 라우터 등 실제 구현체(어댑터)만 위치시킵니다.
            - 핵심 로직은 외부 의존(라이브러리, DB 세부 구현 등)을 갖지 않도록 주의합니다.
        - name: "포트(Ports)/어댑터(Adapters) 인터페이스 작성"
          description: >
            - 유즈케이스나 서비스에서 필요한 DB, 외부 API, 메시지 큐 등은 core.usecases 또는 core.services에 인터페이스(추상 클래스) 형태로 정의합니다.
            - adapters.db, adapters.api, adapters.worker 등에서 해당 인터페이스를 실제 구현(Concrete Class)하여 의존성을 주입받습니다.

    - phase: "2. 도메인 모델(엔티티) 및 유즈케이스 정의"
      steps:
        - name: "도메인 엔티티 정의"
          description: >
            - core/domain 디렉토리에 이메일, 사용자, 전송이력 등과 관련된 Entity(예: Email, User, TransmissionRecord 등)를 정의합니다.
            - 도메인 엔티티는 Pydantic에 의존하지 않고(필요 시 dataclass 또는 간단한 Python 클래스 사용), 비즈니스 로직/속성만 포함합니다.
        - name: "유즈케이스(Atomic / Composite) 정의"
          description: >
            - core/usecases/ 에서 Atomic 유즈케이스(예: 다중 계정 및 설정관리, 사용자 인증, Graph API 인증, 이메일 변경사항 감지 등)와
              Composite 유즈케이스(예: 인증 및 이메일 변경사항 확인, 갱신 이메일 메시지 API로 보내기)를 정의합니다.
            - 각 유즈케이스는 필요한 입력/출력을 명확히 선언하고, 결과를 반환할 때는 Pydantic 모델(또는 DTO)로 매핑하도록 합니다.
            - 예) detect_email_changes.py, send_email_changes.py 등으로 분리
        - name: "서비스(비즈니스 규칙 구현) 작성"
          description: >
            - 유즈케이스 수행 중 복잡한 비즈니스 로직(조건 판단, 특정 알고리즘 적용, 통계 처리 등)은 core/services/로 분리할 수 있습니다.
            - 서비스 레이어에서 도메인 엔티티를 조작하거나, 인터페이스(포트)를 통해 외부 어댑터로부터 데이터를 가져옵니다.

    - phase: "3. FastAPI 진입점(라우터) 및 CLI 어댑터 구현"
      steps:
        - name: "FastAPI 라우터(Adapters)"
          description: >
            - adapters/api/ 에 라우터 모듈을 생성합니다. 예: adapters/api/v1/mail_router.py
            - 라우터는 core의 유즈케이스를 호출하기 전후로 Request/Response 변환만 담당합니다.
            - API 요청 바디나 응답은 Pydantic 모델을 사용하여 데이터 검증, 스웨거(OpenAPI) 문서 자동화에 활용합니다.
            - 예) POST /api/v1/mail/detect → detect_email_changes 유즈케이스 실행 → 결과를 Pydantic ResponseModel로 변환하여 반환
        - name: "CLI 어댑터"
          description: >
            - adapters/cli/ 아래에 CLI 명령어별 모듈을 작성합니다. (예: detect_mail_changes_cli.py)
            - Python의 argparse/typer/click 등을 활용하여 CLI 파라미터 파싱
            - 파싱된 파라미터로 core.usecases 내의 함수(메서드)를 호출
            - 최종 결과를 JSON이나 텍스트 포맷으로 변환하여 출력
        - name: "main.py에서 FastAPI 앱 구성"
          description: >
            - main.py에서 FastAPI 앱 인스턴스를 생성하고, adapters/api/ 아래 정의된 라우터를 include_router로 등록
            - DB 세션, Config, 기타 의존성은 FastAPI의 Depends(또는 AsyncDepends)로 주입
            - core/usecases나 services는 포트(인터페이스)에 의존, 실제 구현체는 adapters/db/xxxRepository 등을 통해 주입

    - phase: "4. DB, 외부 API, 에이전트(Worker) 등 어댑터 구현"
      steps:
        - name: "DB 어댑터 작성 (Repository 패턴)"
          description: >
            - adapters/db/ 에 Repository 인터페이스의 실제 구현체를 작성합니다(예: SqlAlchemy, async ORM 등).
            - 예) EmailRepository, UserRepository, TransmissionRecordRepository 등
            - CORE(usecases)에서는 Repository 인터페이스를 주입받아 DB 접근 로직을 호출합니다.
        - name: "Graph API 인증 어댑터 작성"
          description: >
            - adapters/api/graph_adapter.py 등을 생성하여, Graph API 호출 로직을 구현합니다.
            - OAuth2.0 인증 토큰 발급, 갱신, 에러 처리 로직이 포함됩니다.
            - CORE(usecases)에서는 GraphApiPort(추상화된 포트)만 바라보고, 실제 구현은 graph_adapter에서 처리합니다.
        - name: "외부 API 전송 어댑터 작성"
          description: >
            - adapters/api/external_api_adapter.py 등을 생성하여, 외부 API 호출(HTTP) 로직을 구현합니다.
            - 재시도, 응답 유효성 검증, 인증(토큰) 등을 처리합니다.
            - CORE에서 ExternalApiPort(인터페이스)에 의존 -> 이 어댑터가 구현체가 됨
        - name: "Worker(에이전트) 어댑터 작성 (선택)"
          description: >
            - 이메일 변경 이벤트나 특정 작업을 비동기로 처리할 필요가 있다면 Celery, RQ 등의 메시지 큐 사용
            - adapters/worker/ 디렉토리에 task_queue_adapter.py 등을 두고, CORE가 넘겨주는 DTO(또는 Pydantic 모델)를 메시지 큐에 적재
            - Worker 측에서 이를 consume하여 외부 API 전송 등 장기 작업을 처리

    - phase: "5. 설정 관리"
      steps:
        - name: "Pydantic Settings + ConfigPort 구현"
          description: >
            - core/ports/config_port.py (또는 유사 경로)에 설정 정보를 얻기 위한 추상화(Interface) 정의
            - adapters/config/config_adapter.py 등에 실제 Pydantic Settings를 적용하여 환경 변수를 로드
            - DB 접속정보, API Key, OAuth 클라이언트 ID/Secret 등을 .env 파일이나 시스템 환경변수에서 불러옵니다.
        - name: "환경별 설정(개발/스테이징/운영) 분리"
          description: >
            - config/ 아래에 dev.py, staging.py, prod.py 등 환경별 설정파일을 둘 수도 있고, 하나의 Pydantic BaseSettings를 상속하여 분리
            - ENVIRONMENT 변수에 따라 적절히 Factory 패턴이나 if 분기를 활용하여 설정 인스턴스를 생성

    - phase: "6. 유즈케이스(코어) 내부에서 Pydantic 모델로 반환 & API 응답 매핑"
      steps:
        - name: "유즈케이스 반환 타입을 Pydantic 모델(또는 DTO)"
          description: >
            - core/usecases/* 내의 함수들이 최종적으로 반환할 데이터를 표현할 전용 Pydantic 모델(예: EmailChangeOutput, UserProfileOutput 등)을 정의
            - 도메인 엔티티(Email, User 등)을 usecase 결과로 바로 반환하지 않고, 필요한 정보만 담은 DTO나 Pydantic 모델로 변환 후 반환
        - name: "API 라우터에서 ResponseModel로 사용"
          description: >
            - FastAPI 라우터 함수의 response_model 파라미터에 유즈케이스 반환 모델을 지정
            - 자동으로 OpenAPI 문서가 생성되며, 응답 스키마가 명확해집니다.
            - CLI 어댑터에서도 동일한 모델을 활용하여 JSON 직렬화 후 콘솔 출력할 수 있습니다.

    - phase: "7. 로깅 및 예외 처리"
      steps:
        - name: "공통 로깅 설정"
          description: >
            - Python 로깅(logging) 모듈 또는 structlog 등을 사용하여, CORE/CLI/API 모두에서 공통 포맷(LogFormatter) 적용
            - main.py에 logging 설정을 두거나, 별도 log_config.py에서 설정
        - name: "비즈니스 예외 처리"
          description: >
            - CORE에서 발생 가능한 예외를 의미 있는 도메인 예외 클래스로 정의(예: InvalidUserException)
            - 어댑터(예: FastAPI 라우터)에서는 이 예외를 잡아 HTTPException 등으로 변환해 클라이언트에 반환
            - CLI 어댑터에서는 적절한 에러 코드 또는 메시지를 출력
        - name: "에러 모니터링(옵션)"
          description: >
            - Sentry 등 APM 툴 연동 시 FastAPI 미들웨어나 CLI 예외 핸들러에서 에러 추적 이벤트 전송

    - phase: "8. 테스트 전략 수립"
      steps:
        - name: "단위 테스트(Unit Test)"
          description: >
            - tests/unit/ 하위에 core(domain, usecases, services)별로 테스트 작성
            - 도메인 엔티티와 유즈케이스가 의도대로 동작하는지 Mock(포트) 기반 테스트
        - name: "통합 테스트(Integration Test)"
          description: >
            - tests/integration/에서 실제 DB, 실제 Graph API(Staging), 외부 API(Mock or 실서버)와 연동 테스트
            - FastAPI TestClient를 활용해 라우터 엔드포인트 테스트
        - name: "E2E 테스트(End-to-End)"
          description: >
            - 전체 흐름: (로그인 → 이메일 변경 사항 감지 → 외부API 전송 → DB 기록) 시나리오 테스트
            - CLI와 API 양쪽 경로 모두를 시뮬레이션 가능하다면 각각 실행

    
  additional_notes:
    - "위 단계들은 기간이나 일정 순서에 구애받지 않고, Clean Architecture와 FastAPI Thin Adapter 구조를 체계적으로 적용하기 위한 지침입니다."
    - "요구사항(이메일 감지, 전송, DB 관리, Composite/Atomic 유즈케이스 등)은 코어 영역에서 명확히 정의 후, 어댑터에서 이를 최소한으로 변환만 수행하도록 원칙을 지킵니다."
    - "에이전트(Worker) 활용 시, 코어에서 Worker Port를 정의하고 adapters/worker 등에서 메시지 큐 연동 로직 구현하여 독립성 유지합니다."
    - "유즈케이스(또는 서비스) 반환 타입은 반드시 Pydantic 모델(또는 DTO)을 사용하여 타입 안정성과 문서화를 동시에 달성합니다."
```
