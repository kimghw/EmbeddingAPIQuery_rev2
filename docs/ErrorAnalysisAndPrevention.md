# 에러 분석 및 사후 방지 지침

## 📋 개요
본 문서는 Microsoft Graph API 이메일 감지 시스템 개발 과정에서 발생한 에러들을 분석하고, 향후 유사한 문제를 방지하기 위한 지침을 제공합니다.

---

## 🚨 발생한 주요 에러 분석

### 1. SQLAlchemy 경고: "fully NULL primary key identity cannot load any object"

**에러 내용:**
```
SAWarning: fully NULL primary key identity cannot load any object. This condition may raise an error in a future release.
```

**원인 분석:**
- SQLAlchemy ORM에서 Primary Key가 None인 객체를 로드하려고 할 때 발생
- 새로운 엔티티 생성 시 ID가 아직 할당되지 않은 상태에서 관계 조회 시도

**해결 방법:**
- 엔티티 생성 후 즉시 flush() 또는 commit() 호출하여 ID 할당
- 관계 조회 전 객체가 완전히 저장되었는지 확인

**예방 지침:**
```python
# 잘못된 방법
user = User(username="test")
session.add(user)
# user.id는 아직 None 상태
accounts = user.accounts  # 경고 발생

# 올바른 방법
user = User(username="test")
session.add(user)
session.flush()  # ID 할당
accounts = user.accounts  # 안전
```

### 2. 포트 충돌 에러: "Address already in use"

**에러 내용:**
```
ERROR: [Errno 98] Address already in use
```

**원인 분석:**
- 이전에 실행된 서버 프로세스가 완전히 종료되지 않음
- 동일한 포트를 사용하는 다른 프로세스가 실행 중

**해결 방법:**
```bash
# 포트 사용 프로세스 확인
netstat -tlnp | grep :5000
lsof -ti:5000

# 프로세스 강제 종료
sudo kill -9 $(lsof -ti:5000)
```

**예방 지침:**
- 서버 종료 시 Ctrl+C로 정상 종료
- 개발 환경에서는 서로 다른 포트 사용
- 스크립트에 포트 체크 로직 추가

### 3. favicon.ico 404 에러

**에러 내용:**
```
INFO: 127.0.0.1:51730 - "GET /favicon.ico HTTP/1.1" 404 Not Found
```

**원인 분석:**
- 브라우저가 자동으로 요청하는 favicon 파일이 없음
- FastAPI에서 정적 파일 서빙 설정 누락

**해결 방법:**
```python
# main.py에 추가
from fastapi.staticfiles import StaticFiles

app.mount("/static", StaticFiles(directory="static"), name="static")

# 또는 favicon 라우트 추가
@app.get("/favicon.ico")
async def favicon():
    return FileResponse("static/favicon.ico")
```

**예방 지침:**
- 프로젝트 초기 설정 시 정적 파일 디렉토리 구성
- favicon.ico 파일 기본 제공
- 404 에러가 기능에 영향 없음을 문서화

---

## 🛡️ 사후 방지 지침

### 1. 개발 환경 설정 체크리스트

#### 1.1 프로젝트 초기화
- [ ] 가상환경 생성 및 활성화 확인
- [ ] requirements.txt 의존성 설치 완료
- [ ] .env 파일 설정 및 민감정보 확인
- [ ] .gitignore 설정 (가상환경, .env, __pycache__ 등)

#### 1.2 데이터베이스 설정
- [ ] SQLAlchemy 모델 정의 완료
- [ ] 관계 설정 시 lazy loading 고려
- [ ] Primary Key 자동 생성 설정 확인
- [ ] 테이블 생성 스크립트 테스트

#### 1.3 서버 실행 전 체크
- [ ] 포트 사용 여부 확인 (`netstat -tlnp | grep :PORT`)
- [ ] 이전 프로세스 정리
- [ ] 로그 레벨 설정 확인

### 2. 코딩 표준 및 베스트 프랙티스

#### 2.1 SQLAlchemy 사용 시
```python
# 1. 엔티티 생성 후 즉시 flush
def create_entity(session, data):
    entity = Entity(**data)
    session.add(entity)
    session.flush()  # ID 할당
    return entity

# 2. 관계 조회 전 존재 확인
def get_related_entities(entity):
    if entity.id is None:
        raise ValueError("Entity must be saved before accessing relations")
    return entity.related_entities

# 3. 트랜잭션 관리
def safe_operation(session):
    try:
        # 작업 수행
        session.commit()
    except Exception as e:
        session.rollback()
        raise e
```

#### 2.2 서버 관리
```python
# 1. 포트 체크 함수
def check_port_available(port):
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(('localhost', port)) != 0

# 2. 서버 시작 전 체크
if not check_port_available(5000):
    print("Port 5000 is already in use")
    exit(1)
```

#### 2.3 에러 핸들링
```python
# 1. 구체적인 예외 처리
try:
    result = risky_operation()
except SpecificException as e:
    logger.error(f"Specific error occurred: {e}")
    # 구체적인 복구 로직
except Exception as e:
    logger.error(f"Unexpected error: {e}")
    # 일반적인 에러 처리

# 2. 로깅 표준화
import logging
logger = logging.getLogger(__name__)

def log_operation(operation_name):
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.info(f"Starting {operation_name}")
            try:
                result = func(*args, **kwargs)
                logger.info(f"Completed {operation_name}")
                return result
            except Exception as e:
                logger.error(f"Failed {operation_name}: {e}")
                raise
        return wrapper
    return decorator
```

### 3. 테스트 및 검증 절차

#### 3.1 단위 테스트 필수 항목
- [ ] 모든 유즈케이스 테스트
- [ ] 데이터베이스 CRUD 작업 테스트
- [ ] 에러 케이스 테스트
- [ ] 경계값 테스트

#### 3.2 통합 테스트 체크리스트
- [ ] API 엔드포인트 전체 테스트
- [ ] 데이터베이스 연동 테스트
- [ ] 외부 API 모킹 테스트
- [ ] 인증/인가 플로우 테스트

#### 3.3 배포 전 검증
- [ ] 모든 테스트 통과
- [ ] 로그 레벨 프로덕션 설정
- [ ] 환경변수 검증
- [ ] 성능 테스트 수행

### 4. 모니터링 및 알림 설정

#### 4.1 로그 모니터링
```python
# 구조화된 로깅
import structlog

logger = structlog.get_logger()

def log_with_context(operation, **context):
    logger.info(
        "Operation completed",
        operation=operation,
        **context
    )
```

#### 4.2 에러 추적
```python
# Sentry 연동 (선택사항)
import sentry_sdk

sentry_sdk.init(
    dsn="YOUR_SENTRY_DSN",
    traces_sample_rate=1.0,
)
```

### 5. 문서화 요구사항

#### 5.1 필수 문서
- [ ] API 문서 (Swagger/OpenAPI)
- [ ] 설치 및 실행 가이드
- [ ] 환경 설정 가이드
- [ ] 트러블슈팅 가이드
- [ ] 에러 코드 정의서

#### 5.2 코드 문서화
```python
# 1. 함수 문서화
def process_email_changes(account_id: str) -> List[EmailChange]:
    """
    계정의 이메일 변경사항을 감지하고 처리합니다.
    
    Args:
        account_id: 처리할 계정 ID
        
    Returns:
        감지된 이메일 변경사항 목록
        
    Raises:
        AccountNotFoundError: 계정을 찾을 수 없는 경우
        GraphAPIError: Graph API 호출 실패 시
    """
    pass

# 2. 클래스 문서화
class EmailDetectionUseCase:
    """
    이메일 변경사항 감지를 담당하는 유즈케이스.
    
    Microsoft Graph API의 DeltaLink를 사용하여
    효율적으로 변경사항을 감지합니다.
    """
    pass
```

---

## 🔄 지속적 개선 프로세스

### 1. 에러 발생 시 대응 절차
1. **즉시 대응**: 에러 로그 수집 및 분석
2. **임시 조치**: 서비스 복구를 위한 임시 해결책 적용
3. **근본 원인 분석**: 에러 발생 원인 심층 분석
4. **영구 해결책**: 근본 원인 제거를 위한 코드 수정
5. **문서 업데이트**: 본 문서에 새로운 에러 케이스 추가
6. **테스트 추가**: 동일한 에러 방지를 위한 테스트 케이스 작성

### 2. 정기 점검 항목
- **주간**: 로그 분석 및 성능 모니터링
- **월간**: 의존성 업데이트 및 보안 점검
- **분기**: 아키텍처 리뷰 및 리팩토링 계획

### 3. 팀 공유 및 학습
- 에러 케이스 공유 세션
- 베스트 프랙티스 문서 업데이트
- 코드 리뷰 체크리스트 개선

---

## 📚 참고 자료

### 공식 문서
- [SQLAlchemy ORM Tutorial](https://docs.sqlalchemy.org/en/14/orm/tutorial.html)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Microsoft Graph API](https://docs.microsoft.com/en-us/graph/)

### 에러 해결 가이드
- [SQLAlchemy Common Issues](https://docs.sqlalchemy.org/en/14/errors.html)
- [FastAPI Troubleshooting](https://fastapi.tiangolo.com/tutorial/debugging/)
- [Python Logging Best Practices](https://docs.python.org/3/howto/logging.html)

---

**최종 업데이트**: 2025-05-25  
**작성자**: GraphAPI Query System Development Team  
**버전**: 1.0
