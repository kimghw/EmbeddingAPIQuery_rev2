# Microsoft Graph API 이메일 감지 시스템 - 최종 프로젝트 요약

## 프로젝트 개요

Microsoft Graph API를 통해 이메일 변경사항을 실시간으로 감지하고, 외부 API로 전송하는 시스템을 클린 아키텍처 기반으로 구축했습니다.

## 아키텍처 구조

### 클린 아키텍처 적용
```
project_root/
├── core/                    # 비즈니스 로직 (외부 의존성 없음)
│   ├── domain/             # 도메인 엔티티
│   ├── usecases/           # 유즈케이스 (비즈니스 규칙)
│   ├── ports/              # 인터페이스 정의
│   └── utils/              # 핵심 유틸리티
├── adapters/               # 외부 연결 구현체
│   ├── api/                # FastAPI 라우터
│   ├── cli/                # CLI 명령어
│   ├── db/                 # 데이터베이스 연동
│   └── common/             # 공통 어댑터 유틸
├── config/                 # 설정 관리
├── tests/                  # 테스트 코드
└── docs/                   # 문서
```

## 핵심 기능

### 1. 다중 계정 관리
- **계정 등록/제거**: 여러 Office 365 계정 관리
- **인증 상태 관리**: OAuth 2.0 토큰 자동 갱신
- **계정별 설정**: 개별 계정 설정 및 활성화/비활성화

### 2. 이메일 변경사항 감지
- **실시간 감지**: Microsoft Graph API Delta Query 활용
- **변경 유형 분석**: 생성/수정/삭제 이벤트 구분
- **중복 처리 방지**: 이미 처리된 이메일 필터링

### 3. 외부 API 전송
- **안정적 전송**: 재시도 로직 및 서킷 브레이커 패턴
- **전송 이력 관리**: 성공/실패 상태 추적
- **배치 처리**: 대량 이메일 효율적 처리

### 4. 알림 시스템
- **다중 채널**: 이메일, 웹훅, Slack 등 지원
- **템플릿 기반**: 사용자 정의 알림 템플릿
- **조건부 알림**: 규칙 기반 알림 발송

## 기술적 특징

### 1. 복원력 있는 시스템 (Resilience)
```python
# 서킷 브레이커 패턴
@circuit_breaker(failure_threshold=5, recovery_timeout=60)
async def call_external_api():
    pass

# 재시도 로직
@retry(max_attempts=3, strategy=RetryStrategy.EXPONENTIAL)
async def send_notification():
    pass
```

### 2. 캐싱 시스템
```python
# 결과 캐싱
@cache_result(cache_name="graph_api", ttl=3600)
async def get_user_profile(user_id: str):
    pass

# Graph API 전용 캐시
cache = get_graph_api_cache()
await cache.set_access_token(user_id, token, expires_in)
```

### 3. 구조화된 로깅
```python
# 카테고리별 로깅
logger = create_logger("email_detection", LogCategory.BUSINESS)
logger.info("Email detected", email_id=email.id, user_id=user.id)
```

### 4. 트랜잭션 관리
```python
# 분산 트랜잭션
async with create_transaction_context() as tx:
    await tx.add_operation("save_email", save_email_op)
    await tx.add_operation("send_notification", send_notification_op)
    await tx.commit()
```

### 5. 비동기/동기 통합
```python
# CLI에서 비동기 함수 호출
def cli_command():
    result = run_async(async_usecase_function())
    return result
```

## 설정 관리

### 환경별 설정
- **Development**: 개발용 설정 (디버그 모드, 로컬 DB)
- **Staging**: 스테이징 환경 설정
- **Production**: 운영 환경 설정 (보안 강화, 모니터링)

### 설정 검증
```python
# 운영 환경 필수 설정 검증
@field_validator("secret_key")
def validate_secret_key_production(cls, v):
    if len(v) < 32:
        raise ValueError("Secret key must be at least 32 characters")
    return v
```

## 보안 기능

### 1. 데이터 보호
- **민감 정보 마스킹**: 로그 및 응답에서 민감 데이터 숨김
- **암호화**: 중요 데이터 AES 암호화
- **토큰 관리**: 안전한 토큰 저장 및 갱신

### 2. 인증/인가
- **JWT 토큰**: API 인증
- **OAuth 2.0**: Microsoft Graph API 인증
- **역할 기반 접근 제어**: 사용자 권한 관리

## 모니터링 및 관찰성

### 1. 로깅
- **구조화된 로그**: JSON 형태 로그 출력
- **카테고리별 분류**: 비즈니스/시스템/성능/보안 로그
- **로그 레벨 관리**: 환경별 로그 레벨 설정

### 2. 메트릭스
- **성능 지표**: 응답 시간, 처리량 측정
- **에러 추적**: 예외 발생률 모니터링
- **캐시 효율성**: 히트율, 미스율 추적

### 3. 헬스 체크
- **시스템 상태**: 데이터베이스, 외부 API 연결 상태
- **서킷 브레이커 상태**: 각 서비스별 장애 상태
- **리소스 사용량**: 메모리, CPU 사용률

## 테스트 전략

### 1. 단위 테스트
- **Core 로직**: 비즈니스 규칙 테스트
- **유틸리티**: 공통 기능 테스트
- **도메인 엔티티**: 도메인 로직 검증

### 2. 통합 테스트
- **데이터베이스**: Repository 패턴 테스트
- **외부 API**: Mock을 활용한 API 연동 테스트
- **인증**: OAuth 플로우 테스트

### 3. E2E 테스트
- **CLI 시나리오**: 전체 워크플로우 테스트
- **API 시나리오**: REST API 엔드포인트 테스트
- **에러 시나리오**: 장애 상황 대응 테스트

## 배포 및 운영

### 1. 컨테이너화
```dockerfile
# Dockerfile 예시
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "5000"]
```

### 2. 환경 변수 관리
```bash
# .env 파일 예시
ENVIRONMENT=production
DATABASE_URL=postgresql://user:pass@localhost/db
MICROSOFT_CLIENT_ID=your-client-id
MICROSOFT_CLIENT_SECRET=your-client-secret
EXTERNAL_API_URL=https://api.example.com/webhook
```

### 3. 모니터링 설정
- **Sentry**: 에러 추적 및 알림
- **Prometheus**: 메트릭 수집
- **Grafana**: 대시보드 및 시각화

## 성능 최적화

### 1. 캐싱 전략
- **메모리 캐시**: 자주 사용되는 데이터 캐싱
- **분산 캐시**: Redis를 활용한 확장 가능한 캐싱
- **캐시 무효화**: 데이터 변경 시 자동 캐시 갱신

### 2. 비동기 처리
- **비동기 I/O**: 네트워크 요청 병렬 처리
- **백그라운드 작업**: Celery를 활용한 비동기 작업
- **커넥션 풀링**: 데이터베이스 연결 최적화

### 3. 리소스 관리
- **벌크헤드 패턴**: 리소스 격리를 통한 장애 전파 방지
- **타임아웃 설정**: 무한 대기 방지
- **메모리 관리**: 캐시 크기 제한 및 정리

## 확장성 고려사항

### 1. 수평 확장
- **무상태 설계**: 인스턴스 간 상태 공유 없음
- **로드 밸런싱**: 여러 인스턴스 간 부하 분산
- **데이터베이스 샤딩**: 대용량 데이터 처리

### 2. 마이크로서비스 전환 준비
- **도메인 분리**: 각 도메인별 독립적 서비스화 가능
- **API 게이트웨이**: 단일 진입점 제공
- **서비스 디스커버리**: 동적 서비스 발견

## 보안 고려사항

### 1. 데이터 보호
- **전송 중 암호화**: HTTPS/TLS 사용
- **저장 시 암호화**: 민감 데이터 암호화 저장
- **접근 제어**: 최소 권한 원칙 적용

### 2. 인증 보안
- **토큰 만료**: 적절한 토큰 만료 시간 설정
- **리프레시 토큰**: 안전한 토큰 갱신 메커니즘
- **브루트 포스 방지**: 로그인 시도 제한

## 운영 가이드

### 1. 일상 운영
- **로그 모니터링**: 에러 로그 정기 확인
- **성능 모니터링**: 응답 시간 및 처리량 추적
- **용량 관리**: 디스크 및 메모리 사용량 모니터링

### 2. 장애 대응
- **알림 설정**: 임계치 초과 시 자동 알림
- **복구 절차**: 단계별 복구 가이드
- **백업 및 복원**: 정기 백업 및 복원 테스트

### 3. 업데이트 및 배포
- **무중단 배포**: 블루-그린 배포 전략
- **롤백 계획**: 문제 발생 시 즉시 롤백
- **테스트 자동화**: CI/CD 파이프라인 구축

## 결론

이 프로젝트는 클린 아키텍처 원칙을 따라 구축된 견고하고 확장 가능한 시스템입니다. 

### 주요 성과
1. **아키텍처 독립성**: Core 로직이 외부 의존성에서 완전히 분리
2. **높은 테스트 가능성**: 각 계층별 독립적 테스트 가능
3. **확장성**: 새로운 기능 추가 시 기존 코드 영향 최소화
4. **복원력**: 장애 상황에서도 안정적 동작
5. **관찰성**: 충분한 로깅 및 모니터링 기능

### 향후 개선 방향
1. **성능 최적화**: 더 효율적인 캐싱 및 배치 처리
2. **보안 강화**: 추가적인 보안 기능 및 감사 로그
3. **사용자 경험**: 더 직관적인 CLI 및 웹 인터페이스
4. **AI/ML 통합**: 이메일 분류 및 우선순위 자동 결정

이 시스템은 Microsoft Graph API를 활용한 이메일 처리 시스템의 모범 사례로 활용될 수 있으며, 다른 유사한 프로젝트의 참조 아키텍처로 사용할 수 있습니다.
