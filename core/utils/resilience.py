"""
재시도 및 서킷 브레이커 패턴 구현
"""
import asyncio
import time
import random
from typing import TypeVar, Callable, Any, Optional, Dict, List
from datetime import datetime, timedelta
from enum import Enum
import functools

from .logging import create_logger, LogCategory
from ..exceptions import ExternalServiceError, InternalError

logger = create_logger("resilience", LogCategory.SYSTEM)

T = TypeVar('T')


class CircuitState(str, Enum):
    """서킷 브레이커 상태"""
    CLOSED = "CLOSED"      # 정상 상태
    OPEN = "OPEN"          # 차단 상태
    HALF_OPEN = "HALF_OPEN"  # 반개방 상태


class RetryStrategy(str, Enum):
    """재시도 전략"""
    FIXED = "FIXED"              # 고정 간격
    EXPONENTIAL = "EXPONENTIAL"  # 지수 백오프
    LINEAR = "LINEAR"            # 선형 증가
    RANDOM = "RANDOM"            # 랜덤 지터


class CircuitBreaker:
    """서킷 브레이커 패턴 구현"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = CircuitState.CLOSED
        self.success_count = 0
        
        logger.info(
            f"Circuit breaker initialized: {name}",
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout
        )
    
    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """서킷 브레이커를 통한 함수 호출"""
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker {self.name} moved to HALF_OPEN")
            else:
                raise ExternalServiceError(
                    f"Circuit breaker {self.name} is OPEN",
                    service=self.name
                )
        
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure()
            raise e
    
    def _should_attempt_reset(self) -> bool:
        """리셋을 시도해야 하는지 확인"""
        if self.last_failure_time is None:
            return True
        
        return (datetime.now() - self.last_failure_time).total_seconds() >= self.recovery_timeout
    
    def _on_success(self):
        """성공 시 호출"""
        self.failure_count = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:  # 3번 성공하면 CLOSED로 전환
                self.state = CircuitState.CLOSED
                self.success_count = 0
                logger.info(f"Circuit breaker {self.name} moved to CLOSED")
    
    def _on_failure(self):
        """실패 시 호출"""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            logger.warning(f"Circuit breaker {self.name} moved back to OPEN")
        elif self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            logger.warning(
                f"Circuit breaker {self.name} moved to OPEN",
                failure_count=self.failure_count,
                threshold=self.failure_threshold
            )
    
    def get_state(self) -> Dict[str, Any]:
        """현재 상태 반환"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }


class RetryConfig:
    """재시도 설정"""
    
    def __init__(
        self,
        max_attempts: int = 3,
        strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        multiplier: float = 2.0,
        jitter: bool = True,
        exceptions: tuple = (Exception,)
    ):
        self.max_attempts = max_attempts
        self.strategy = strategy
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.multiplier = multiplier
        self.jitter = jitter
        self.exceptions = exceptions
    
    def calculate_delay(self, attempt: int) -> float:
        """재시도 지연 시간 계산"""
        if self.strategy == RetryStrategy.FIXED:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.EXPONENTIAL:
            delay = self.base_delay * (self.multiplier ** (attempt - 1))
        elif self.strategy == RetryStrategy.LINEAR:
            delay = self.base_delay * attempt
        elif self.strategy == RetryStrategy.RANDOM:
            delay = random.uniform(self.base_delay, self.max_delay)
        else:
            delay = self.base_delay
        
        # 최대 지연 시간 제한
        delay = min(delay, self.max_delay)
        
        # 지터 추가
        if self.jitter and self.strategy != RetryStrategy.RANDOM:
            jitter_range = delay * 0.1
            delay += random.uniform(-jitter_range, jitter_range)
        
        return max(0, delay)


class RetryExecutor:
    """재시도 실행기"""
    
    def __init__(self, config: RetryConfig):
        self.config = config
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """재시도 로직으로 함수 실행"""
        last_exception = None
        
        for attempt in range(1, self.config.max_attempts + 1):
            try:
                logger.debug(
                    f"Executing function (attempt {attempt}/{self.config.max_attempts})",
                    function=func.__name__,
                    attempt=attempt
                )
                
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except self.config.exceptions as e:
                last_exception = e
                
                if attempt == self.config.max_attempts:
                    logger.error(
                        f"All retry attempts failed for {func.__name__}",
                        attempts=attempt,
                        final_error=str(e)
                    )
                    break
                
                delay = self.config.calculate_delay(attempt)
                logger.warning(
                    f"Attempt {attempt} failed for {func.__name__}, retrying in {delay:.2f}s",
                    error=str(e),
                    delay=delay
                )
                
                await asyncio.sleep(delay)
        
        raise last_exception


class ResilientExecutor:
    """서킷 브레이커와 재시도를 결합한 실행기"""
    
    def __init__(
        self,
        circuit_breaker: CircuitBreaker,
        retry_config: RetryConfig,
        name: str = "resilient_executor"
    ):
        self.circuit_breaker = circuit_breaker
        self.retry_executor = RetryExecutor(retry_config)
        self.name = name
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """복원력 있는 실행"""
        logger.info(f"Executing with resilience: {func.__name__}")
        
        async def resilient_call():
            return await self.circuit_breaker.call(func, *args, **kwargs)
        
        try:
            return await self.retry_executor.execute(resilient_call)
        except Exception as e:
            logger.error(
                f"Resilient execution failed for {func.__name__}",
                error=str(e),
                circuit_state=self.circuit_breaker.state.value
            )
            raise


class BulkheadExecutor:
    """벌크헤드 패턴 구현 (리소스 격리)"""
    
    def __init__(self, max_concurrent: int = 10, name: str = "bulkhead"):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.max_concurrent = max_concurrent
        self.name = name
        self.active_count = 0
        
        logger.info(
            f"Bulkhead executor initialized: {name}",
            max_concurrent=max_concurrent
        )
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """벌크헤드 패턴으로 함수 실행"""
        async with self.semaphore:
            self.active_count += 1
            try:
                logger.debug(
                    f"Executing in bulkhead: {func.__name__}",
                    active_count=self.active_count,
                    max_concurrent=self.max_concurrent
                )
                
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            finally:
                self.active_count -= 1
    
    def get_stats(self) -> Dict[str, Any]:
        """벌크헤드 통계 반환"""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "available_slots": self.max_concurrent - self.active_count
        }


class TimeoutExecutor:
    """타임아웃 실행기"""
    
    def __init__(self, timeout_seconds: float, name: str = "timeout"):
        self.timeout_seconds = timeout_seconds
        self.name = name
    
    async def execute(self, func: Callable[..., T], *args, **kwargs) -> T:
        """타임아웃과 함께 함수 실행"""
        try:
            if asyncio.iscoroutinefunction(func):
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.timeout_seconds
                )
            else:
                # 동기 함수를 비동기로 실행
                loop = asyncio.get_event_loop()
                return await asyncio.wait_for(
                    loop.run_in_executor(None, func, *args, **kwargs),
                    timeout=self.timeout_seconds
                )
        except asyncio.TimeoutError:
            logger.error(
                f"Function {func.__name__} timed out after {self.timeout_seconds}s"
            )
            raise InternalError(
                f"Operation timed out after {self.timeout_seconds} seconds",
                component=self.name
            )


# 데코레이터들
def circuit_breaker(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    expected_exception: type = Exception,
    name: Optional[str] = None
):
    """서킷 브레이커 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker_name = name or f"{func.__module__}.{func.__name__}"
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            expected_exception=expected_exception,
            name=breaker_name
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await breaker.call(func, *args, **kwargs)
        
        # 서킷 브레이커 상태 확인 메서드 추가
        wrapper.get_circuit_state = breaker.get_state
        return wrapper
    
    return decorator


def retry(
    max_attempts: int = 3,
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exceptions: tuple = (Exception,)
):
    """재시도 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        config = RetryConfig(
            max_attempts=max_attempts,
            strategy=strategy,
            base_delay=base_delay,
            max_delay=max_delay,
            exceptions=exceptions
        )
        executor = RetryExecutor(config)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await executor.execute(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


def resilient(
    failure_threshold: int = 5,
    recovery_timeout: int = 60,
    max_attempts: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple = (Exception,)
):
    """복원력 있는 실행 데코레이터 (서킷 브레이커 + 재시도)"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        breaker = CircuitBreaker(
            failure_threshold=failure_threshold,
            recovery_timeout=recovery_timeout,
            name=f"{func.__module__}.{func.__name__}"
        )
        
        retry_config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            exceptions=exceptions
        )
        
        executor = ResilientExecutor(breaker, retry_config)
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await executor.execute(func, *args, **kwargs)
        
        wrapper.get_circuit_state = breaker.get_state
        return wrapper
    
    return decorator


def bulkhead(max_concurrent: int = 10):
    """벌크헤드 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        executor = BulkheadExecutor(
            max_concurrent=max_concurrent,
            name=f"{func.__module__}.{func.__name__}"
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await executor.execute(func, *args, **kwargs)
        
        wrapper.get_bulkhead_stats = executor.get_stats
        return wrapper
    
    return decorator


def timeout(seconds: float):
    """타임아웃 데코레이터"""
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        executor = TimeoutExecutor(
            timeout_seconds=seconds,
            name=f"{func.__module__}.{func.__name__}"
        )
        
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            return await executor.execute(func, *args, **kwargs)
        
        return wrapper
    
    return decorator


# 전역 서킷 브레이커 관리자
class CircuitBreakerManager:
    """서킷 브레이커 관리자"""
    
    def __init__(self):
        self.breakers: Dict[str, CircuitBreaker] = {}
    
    def get_breaker(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ) -> CircuitBreaker:
        """서킷 브레이커 가져오기 또는 생성"""
        if name not in self.breakers:
            self.breakers[name] = CircuitBreaker(
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                expected_exception=expected_exception,
                name=name
            )
        return self.breakers[name]
    
    def get_all_states(self) -> Dict[str, Dict[str, Any]]:
        """모든 서킷 브레이커 상태 반환"""
        return {name: breaker.get_state() for name, breaker in self.breakers.items()}
    
    def reset_breaker(self, name: str):
        """서킷 브레이커 리셋"""
        if name in self.breakers:
            breaker = self.breakers[name]
            breaker.state = CircuitState.CLOSED
            breaker.failure_count = 0
            breaker.success_count = 0
            breaker.last_failure_time = None
            logger.info(f"Circuit breaker {name} has been reset")


# 전역 인스턴스
_circuit_breaker_manager = CircuitBreakerManager()

def get_circuit_breaker_manager() -> CircuitBreakerManager:
    """전역 서킷 브레이커 매니저 반환"""
    return _circuit_breaker_manager
