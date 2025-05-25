# 에러 분석 및 재발 방지 지침

## 프로젝트 개발 과정에서 발생한 주요 에러 분석

### 1. 도메인 모델 타입 불일치 에러

#### 발생한 에러
```
ValidationError: 1 validation error for User
id
  Input should be a valid string [type=string_type, input_value=UUID('39dd6508-5a53-4e9d-8a98-cd6a4265a8d6'), input_type=UUID]
```

#### 원인 분석
- **근본 원인**: Pydantic 도메인 모델에서 `id` 필드를 `str` 타입으로 정의했으나, 테스트 코드에서 `uuid.uuid4()` 객체를 직접 전달
- **설계 불일치**: 도메인 모델의 타입 정의와 실제 사용 코드 간의 불일치
- **타입 검증 부족**: 개발 단계에서 타입 검증이 충분히 이루어지지 않음

#### 해결 방법
```python
# 잘못된 방법
test_user = User(
    id=uuid.uuid4(),  # UUID 객체 직접 사용
    username="test_user",
    email="test@example.com"
)

# 올바른 방법
test_user = User(
    id=str(uuid.uuid4()),  # 문자열로 변환
    username="test_user", 
    email="test@example.com"
)
```

### 2. 데이터베이스 UNIQUE 제약 조건 위반

#### 발생한 에러
```
IntegrityError: (sqlite3.IntegrityError) UNIQUE constraint failed: users.email
```

#### 원인 분석
- **근본 원인**: 이전 테스트 실행에서 생성된 데이터가 데이터베이스에 남아있어 동일한 이메일로 사용자 생성 시도
- **테스트 격리 부족**: 테스트 간 데이터 격리가 제대로 이루어지지 않음
- **테스트 데이터 관리 미흡**: 고정된 테스트 데이터 사용으로 인한 충돌

#### 해결 방법
```python
# 고유한 테스트 데이터 생성
unique_id = str(uuid.uuid4())[:8]
test_user = User(
    id=str(uuid.uuid4()),
    username=f"test_user_{unique_id}",
    email=f"test_{unique_id}@example.com",
    created_at=datetime.now()
)
```

### 3. Repository 메서드명 불일치

#### 발생한 에러
```
AttributeError: 'SQLUserRepository' object has no attribute 'create'
```

#### 원인 분석
- **근본 원인**: Repository 인터페이스와 구현체 간의 메서드명 불일치
- **인터페이스 설계 불일치**: 포트(인터페이스)와 어댑터(구현체) 간의 계약 불일치
- **문서화 부족**: 실제 구현된 메서드명에 대한 문서화 부족

#### 해결 방법
```python
# 잘못된 방법
created_user = await user_repo.create(test_user)

# 올바른 방법 (실제 구현된 메서드 사용)
created_user = await user_repo.save(test_user)
```

### 4. Deprecated 함수 사용 경고

#### 발생한 경고
```
DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version.
```

#### 원인 분석
- **근본 원인**: Python 3.12에서 `datetime.utcnow()` 함수가 deprecated됨
- **라이브러리 버전 변경**: Python 버전 업그레이드에 따른 API 변경사항 미반영
- **최신 표준 미적용**: timezone-aware datetime 사용 권장사항 미적용

#### 해결 방법
```python
# Deprecated 방법
created_at=datetime.utcnow()

# 권장 방법
created_at=datetime.now()
# 또는 timezone-aware 방법
created_at=datetime.now(datetime.UTC)
```

## 재발 방지 지침

### 1. 개발 단계별 검증 체크리스트

#### 설계 단계
- [ ] 도메인 모델의 타입 정의 명확화
- [ ] 포트/어댑터 인터페이스 계약 명시
- [ ] 데이터베이스 스키마와 도메인 모델 일치성 확인

#### 구현 단계
- [ ] Pydantic 모델 타입 검증 테스트 작성
- [ ] Repository 인터페이스와 구현체 메서드명 일치 확인
- [ ] 최신 Python 버전 호환성 검토

#### 테스트 단계
- [ ] 테스트 데이터 격리 전략 수립
- [ ] 고유한 테스트 데이터 생성 로직 구현
- [ ] 데이터베이스 초기화/정리 자동화

### 2. 코드 품질 관리 도구 도입

#### 정적 분석 도구
```bash
# 타입 검사
pip install mypy
mypy core/ adapters/

# 코드 품질 검사
pip install pylint
pylint core/ adapters/

# 포맷팅
pip install black
black core/ adapters/
```

#### pre-commit 훅 설정
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    rev: 23.1.0
    hooks:
      - id: black
  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.0.1
    hooks:
      - id: mypy
```

### 3. 테스트 전략 개선

#### 테스트 격리 패턴
```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

@pytest.fixture
def clean_database():
    """각 테스트마다 깨끗한 데이터베이스 제공"""
    engine = create_engine("sqlite:///:memory:")
    # 테이블 생성
    Base.metadata.create_all(engine)
    
    Session = sessionmaker(bind=engine)
    session = Session()
    
    yield session
    
    session.close()
```

#### 테스트 데이터 팩토리
```python
class TestDataFactory:
    @staticmethod
    def create_unique_user():
        unique_id = str(uuid.uuid4())[:8]
        return User(
            id=str(uuid.uuid4()),
            username=f"test_user_{unique_id}",
            email=f"test_{unique_id}@example.com",
            created_at=datetime.now()
        )
```

### 4. 문서화 및 가이드라인

#### API 문서화
- 모든 Repository 메서드의 시그니처와 동작 명세
- 도메인 모델의 필드 타입과 제약사항 문서화
- 에러 처리 가이드라인 작성

#### 개발 가이드라인
```markdown
## 도메인 모델 작성 규칙
1. 모든 ID 필드는 str 타입으로 정의
2. datetime 필드는 timezone-aware 사용 권장
3. Optional 필드는 명시적으로 Optional[] 타입 사용

## 테스트 작성 규칙
1. 각 테스트는 독립적으로 실행 가능해야 함
2. 테스트 데이터는 고유성을 보장해야 함
3. 테스트 후 리소스 정리 필수
```

### 5. CI/CD 파이프라인 개선

#### GitHub Actions 워크플로우
```yaml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install pytest mypy black
      
      - name: Run type checking
        run: mypy core/ adapters/
      
      - name: Run code formatting check
        run: black --check core/ adapters/
      
      - name: Run tests
        run: pytest tests/ -v
```

### 6. 모니터링 및 알림

#### 에러 추적
- Sentry 등 에러 모니터링 도구 연동
- 구조화된 로깅으로 에러 컨텍스트 수집
- 에러 발생 시 자동 알림 설정

#### 성능 모니터링
- 데이터베이스 쿼리 성능 모니터링
- API 응답 시간 추적
- 메모리 사용량 모니터링

## 결론

이번 프로젝트에서 발생한 에러들은 대부분 다음과 같은 공통 원인을 가지고 있었습니다:

1. **타입 안정성 부족**: 정적 타입 검사 도구 미사용
2. **테스트 격리 부족**: 테스트 간 데이터 공유로 인한 충돌
3. **인터페이스 불일치**: 설계와 구현 간의 계약 불일치
4. **최신 표준 미적용**: 라이브러리 버전 변경사항 미반영

이러한 문제들을 해결하기 위해 위에서 제시한 지침들을 따르면, 향후 유사한 에러의 재발을 크게 줄일 수 있을 것입니다.

**핵심 원칙**: 
- 타입 안정성 확보
- 테스트 격리 보장  
- 인터페이스 계약 준수
- 지속적인 코드 품질 관리
