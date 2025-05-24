에이전트를 사용하여 fastapi를 개발 시 적용 규칙

1. 소프트웨어 아키텍쳐(클린 아키텍쳐, 얇은 어댑터 구조)
 1.1 핵심 로직을 한 곳에 두고 여러 진입점을 얇은 래퍼로만 감싸서 외부(DB, API, UI 등)와의 입출력 파트를 "포트/어댑터'로 얇게 구성
     - 인터페이스를 구성
 1.2 폴더구조
     - 프로젝트는 core, adapters(infras), tests, main.py 구조를 반드시 준수
     - core 하위에 domain, usecases, services를 둔다. 필요시 core/utils 도 둠
     - adapters 하위에는 api, cli, db등의 외부 연결을 둠(api, db 는 인터페이스/어댑터 적용)
     - 설정관리 전용 디렉토리 설정
 1.3 핵심로직(비즈니스 코어:도메인, 유즈케이스, 서비스)의 독립성 확보
     - 비즈니스 규칙(도메인 로직), 엔티티, 유즈케이스는 Core 에만 위치
     - 엔티티와 유즈케이스에 대한 설명과 유즈케이스가 어떻게 구성되어 있는지 문서화
     - Core의 엔티티는 외부 구현(예:라이브러리, db, 외부 API)에 전혀 의존하지 않음
     - 유즈케이스와 서비스는 필요한 경우 "포트/인터페이스' 형식의 추상 클래스로 정의하고, 어댑터 구현 고려
 1.4 엔트리 포인트
     - CLI, API, 기타 UI 등 다양한 진입점(Entry Point)에서는 공통된 단일 책임  로직을 적용한 어답터 적용
     - 해당 진입점들은 정의된 유즈케이스나 서비스 반환하고, 단순히 입력 파싱 및 출력 형식 변환만 담당하는 형태만 추가하여 얇게 만듬
 1.5 포트/어댑터(Ports/Adapters) 개념 적용
     - 유즈케이스나 서비스가 필요로 하는 외부 자원(DB, API, 파일, 메시지 큐 등)을 '포트'로 정의하고, 실제 의존 모듈은 얇은 '어댑터' 레이어에서 구현
     - FastAPI 라우터는 CORE 호출 전후에 Request/Response 데이터 변환을 담당하는 어댑터로 됨
     - CLI는 입력(터미널 arguments)과 출력(json 변환 등)을 변환하고 단일 유즈케이스나 서비스를 반환하는 얇은 어댑터가 됨
     - 어댑터 교체 시스템 구현하고 교체를 위한 사용자 인터페이스(설정파일 수정등) 구현
 1.6 동기/비동기 이슈 통일
     - 코어 로직이 동기/비동기 모두에서 호환 가능하도록 구조를 설계
     -- Python에서는 asyn/await 를 적극 활용하되, CLI에서 동기적으로만 동작해야 한다면 asyncio.run() 등의 방법으로 CORE 메서드를 호출하는 식으로 일관성 있게 가져감

2. 디자인 패턴 및 의존성 관리
2.1 의존성 주입
   - DB 세션, 설정(config), 외부 API Client 등은 FastAPI의 Depends(비동기 라면 AsyncDepends), 혹은 별도의 DI 컨테이너를 활용하여 주입
   - CORE는 세션이나 클라이언트 등 '구현 상세'에 직접 의존하지 않게 하고, '포트/인터페이스'만 의존하도록 설계
2.2 Repository 패턴/Service 레이어
   - 도메인 엔티티와 영속성(DB)을 분리하기 위해 Repository 패턴 적용 가능
   - CORE의 엔티티는 DB dmlwhs djqtdl qlwmsltm fhwlraks ekarh, DB 접근은 어댑터 측에서 Repositiory 인터페이스 구현 해 CORE 주입
2.3 Factory/Builder
   - 복잡한 객체(예: 특정 옵션이 적용된 DB 세션, 외부 API 클라이언트등)을 생성해야 한다면, Factory나 Builder 를 사용해 CORE 내에서 직접 생성 로직이 노출되지 않도록 구현
2.4 에이전트/Worker 처리가 필요한 경우
   - 메시지 큐, 별도 Task Queue(RQ, Celery 등) 또는 백그라운드 Worker가 필요하다면, CORE의 유스케이스에서 Worker로 전달해야 할 ‘데이터 형태(=DTO나 Pydantic 모델)를 정의’하고, 실제 메시지 큐에 적재하는 로직은 어댑터(Worker Adapter)로 분리합니다.

3. 데이터 모델 / 스키마
3.1 입출력 데이터의 일원화
   - CORE → CLI/Router로 반환되는 값은 반드시 Pydantic 모델 등 스키마를 통해 정의
   - CLI 쪽에서는 내부적으로 JSON으로 직렬화하여 출력하고, API 쪽에서는 FastAPI ResponseModel과 OpenAPI 문서화에 활용
3.2 DTO와 도메인 엔티티 구분
   - CORE 내부 로직을 위해 사용하는 ‘도메인 엔티티’와 외부 전송을 위한 ‘DTO(Data Transfer Object) / Pydantic 모델’을 분리 가능
   - 다만, 규모가 작다면 Pydantic 모델을 곧바로 도메인 엔티티처럼 사용 가능
3.3 OpenAPI 문서화
   - FastAPI를 사용한다면 자동으로 문서가 생성되므로, 라우터별로 response_model과 적절한 docstring, 설명 등을 붙여 문서화
   - CLI용으로는 Swagger/OpenAPI가 필요 없지만, 동일한 데이터 구조(시그니처)라는 점은 지켜야 합니다.

4. 로깅(Logging) 및 예외 처리(Exception Handling)
4.1 공통 로깅 구조
   - CORE, CLI, API 전부 공통 로깅 포맷을 사용하도록 설계합니다.
   - Python 표준 로깅(logging) 모듈 혹은 structlog 등을 사용해 구조화된 로그를 남기고, 레벨별(INFO, WARNING, ERROR, CRITICAL)로 분류합니다.
4.2 예외 처리
   - CORE에서는 비즈니스 로직 상의 예외를 ‘의미 있는 예외 클래스로’ 정의해서 throw합니다(예: NotEnoughBalanceError, InvalidUserInputError 등).
   - CLI나 API 어댑터에서는 이 예외를 받아서 사용자에게 맞는 포맷으로 변환합니다. (CLI면 에러 코드/메시지, API면 HTTP status code + JSON 응답 등)
4.3 Tracing / Error Monitoring
   - 필요하다면 Sentry와 같은 에러 트래킹 도구를 연동하여 예외 발생 시 추적할 수 있도록 합니다.
   - FastAPI의 미들웨어나 이벤트 훅을 활용해 에러 발생 시 공통 핸들러를 태워 로깅 및 모니터링할 수 있도록 합니다.

5. 네이밍 컨벤션
5.1 CORE 메서드, CLI 커맨드, API 엔드포인트
   - 동일하거나 유사한 기능의 경우 같은 이름(혹은 유사한 명칭)을 사용하여 유지보수를 쉽게 합니다.
   - 예: CORE의 create_user() → CLI command: create-user, API endpoint: POST /users.
5.2 Pydantic 스키마 명명
   - Request/Response 모델은 xxxRequest, xxxResponse, 혹은 CreateUserInput, UserOutput 등 직관적으로 구분될 수 있는 이름을 사용합니다.
5.3 모듈/패키지 구조
   - core/ 아래에 entities, usecases, services 등 도메인 로직을 분리하여 명명합니다.
   - adapters/ 아래에 api, cli, db, worker 등을 두어 어댑터별로 분리합니다.

6. 설정 관리
6.1 기본구조
   - Core 독립성: Core는 구체적인 설정 구현에 의존하지 않고, ConfigPort 인터페이스에만 의존
   - 설정 기반 의존성 선택
6.2 설정 포트/어댑터 패턴
   - 포트 정의: Core에서 필요한 설정 인터페이스를 ConfigPort로 추상화
   - 어댑터 구현: ConfigAdapter에서 실제 Pydantic Settings와 연동
   - 의존성 주입: FastAPI Depends와 CLI에서 동일한 설정 인스턴스 주입
6.3 환경별 설정 관리
   - Factory 패턴: 환경변수 ENVIRONMENT에 따라 적절한 설정 클래스 자동 선택
   - 환경변수 우선순위: .env 파일 < 시스템 환경변수 < 코드 기본값
   - 검증 로직: Pydantic validator를 통해 운영환경에서 필수값 검증
   - 설정값이 잘 반영되었는지 설정이 적용된 결과를 로그
6.4 어댑터 선택 
   - 어댑터 선택 및 세부 설정을 위한 사용자 인터페이스 구현(환경파일 기반)



-------------------추가 ----------------------
- __유즈케이스 반환 타입을 Pydantic 모델로 변경__

- __API 응답에서 Pydantic 스키마 활용__

- __타입 안정성 및 문서화 개선__
