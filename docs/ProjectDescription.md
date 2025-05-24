# GraphAPIQuery 프로젝트 설명

## 프로젝트 개요
Microsoft Graph API를 활용한 이메일 변경사항 감지 및 외부 API 전송 시스템

### 핵심 기능
- Microsoft Graph API를 통한 이메일 변경사항 실시간 감지
- 다중 Office 365 계정 관리
- 외부 API로 이메일 정보 전송
- CLI 및 REST API 인터페이스 제공

## 아키텍처 설계

### 클린 아키텍처 적용
```
┌─────────────────────────────────────────┐
│              Adapters                   │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │   API   │ │   CLI   │ │   DB    │   │
│  └─────────┘ └─────────┘ └─────────┘   │
└─────────────────┬───────────────────────┘
                  │
┌─────────────────┴───────────────────────┐
│                Core                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │ Domain  │ │Usecases │ │Services │   │
│  └─────────┘ └─────────┘ └─────────┘   │
└─────────────────────────────────────────┘
```

### 폴더 구조
```
GraphAPIQuery_rev2/
├── core/                    # 비즈니스 로직 (외부 의존성 없음)
│   ├── domain/             # 도메인 엔티티
│   ├── usecases/           # 유즈케이스 (비즈니스 규칙)
│   ├── services/           # 복잡한 비즈니스 로직
│   └── utils/              # 공통 유틸리티
├── adapters/               # 외부 연결 구현체
│   ├── api/                # FastAPI 라우터
│   ├── cli/                # CLI 명령어
│   ├── db/                 # 데이터베이스 연동
│   └── worker/             # 백그라운드 작업
├── config/                 # 설정 관리
├── tests/                  # 테스트
│   ├── unit/               # 단위 테스트
│   ├── integration/        # 통합 테스트
│   └── e2e/                # E2E 테스트
├── docs/                   # 문서
└── logs/                   # 로그 파일
```

## 핵심 컴포넌트

### 1. 도메인 엔티티 (core/domain)
- **User**: 사용자 정보 및 계정 관리
- **Email**: 이메일 데이터 및 메타데이터
- **TransmissionRecord**: 전송 이력 및 상태 관리
- **Account**: Office 365 계정 정보

### 2. 유즈케이스 (core/usecases)
- **AccountManagement**: 계정 등록/제거/설정
- **EmailDetection**: 이메일 변경사항 감지
- **EmailTransmission**: 외부 API 전송
- **DataManagement**: 데이터베이스 관리

### 3. 어댑터 (adapters)
- **GraphAPIAdapter**: Microsoft Graph API 연동
- **ExternalAPIAdapter**: 외부 API 전송
- **DatabaseAdapter**: 데이터베이스 연동
- **CLIAdapter**: 명령줄 인터페이스
- **APIAdapter**: REST API 인터페이스

## 기술 스택

### 백엔드
- **FastAPI**: REST API 서버
- **Typer**: CLI 인터페이스
- **Pydantic**: 데이터 검증 및 설정
- **SQLAlchemy**: ORM
- **httpx**: HTTP 클라이언트 (비동기)

### 데이터베이스
- **PostgreSQL**: 메인 데이터베이스 (권장)
- **SQLite**: 개발/테스트용

### 인증 및 보안
- **OAuth 2.0**: Microsoft Graph API 인증
- **JWT**: API 토큰 관리
- **환경변수**: 민감 정보 관리

### 모니터링 및 로깅
- **structlog**: 구조화된 로깅
- **Sentry**: 에러 모니터링 (옵션)

## 주요 특징

### 1. 포트/어댑터 패턴
- Core는 인터페이스(포트)만 의존
- 실제 구현체(어댑터)는 교체 가능
- 테스트 용이성 및 확장성 확보

### 2. 의존성 주입
- FastAPI Depends를 통한 DI
- 설정 기반 어댑터 선택
- Mock 객체를 통한 테스트 지원

### 3. 비동기 처리
- FastAPI의 비동기 지원
- CLI에서는 asyncio.run() 활용
- 동일한 Core 로직 공유

### 4. 환경별 설정
- 개발/스테이징/프로덕션 환경 분리
- .env 파일 기반 설정
- Pydantic Settings 활용

## 확장 계획
- Gmail API 어댑터 추가
- 메시지 큐 연동 (RabbitMQ/Redis)
- 웹 대시보드 구현
- 실시간 알림 시스템

## 최종 업데이트
2025-05-24
