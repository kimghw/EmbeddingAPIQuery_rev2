"""
구조화된 로깅 및 모니터링 유틸리티
"""
import logging
import json
import sys
from typing import Dict, Any, Optional
from datetime import datetime
from contextlib import contextmanager
import structlog
from enum import Enum


class LogLevel(str, Enum):
    """로그 레벨 정의"""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogCategory(str, Enum):
    """로그 카테고리 정의"""
    BUSINESS = "BUSINESS"
    SYSTEM = "SYSTEM"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    EXTERNAL_API = "EXTERNAL_API"
    DATABASE = "DATABASE"
    USER_ACTION = "USER_ACTION"


def setup_structured_logging(
    log_level: str = "INFO",
    enable_json: bool = True,
    enable_console: bool = True
):
    """구조화된 로깅 설정"""
    
    processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if enable_json:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # 표준 로깅 설정
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout if enable_console else None,
        level=getattr(logging, log_level.upper())
    )


class ContextLogger:
    """컨텍스트 정보를 포함한 로거"""
    
    def __init__(self, name: str, category: LogCategory = LogCategory.SYSTEM):
        self.logger = structlog.get_logger(name)
        self.category = category
        self.context: Dict[str, Any] = {
            "category": category.value,
            "logger_name": name
        }
    
    def bind(self, **kwargs) -> 'ContextLogger':
        """컨텍스트 정보 바인딩"""
        new_logger = ContextLogger(self.logger._logger.name, self.category)
        new_logger.context = {**self.context, **kwargs}
        new_logger.logger = self.logger.bind(**kwargs)
        return new_logger
    
    def debug(self, msg: str, **kwargs):
        """디버그 로그"""
        self.logger.debug(msg, **{**self.context, **kwargs})
    
    def info(self, msg: str, **kwargs):
        """정보 로그"""
        self.logger.info(msg, **{**self.context, **kwargs})
    
    def warning(self, msg: str, **kwargs):
        """경고 로그"""
        self.logger.warning(msg, **{**self.context, **kwargs})
    
    def error(self, msg: str, **kwargs):
        """에러 로그"""
        self.logger.error(msg, **{**self.context, **kwargs})
    
    def critical(self, msg: str, **kwargs):
        """치명적 에러 로그"""
        self.logger.critical(msg, **{**self.context, **kwargs})
    
    def log_business_event(
        self, 
        event: str, 
        user_id: Optional[str] = None,
        account_id: Optional[str] = None,
        **kwargs
    ):
        """비즈니스 이벤트 로깅"""
        log_data = {
            "event_type": "business_event",
            "event": event,
            "user_id": user_id,
            "account_id": account_id,
            **kwargs
        }
        self.info(f"Business event: {event}", **log_data)
    
    def log_performance_metric(
        self,
        operation: str,
        duration_ms: float,
        success: bool = True,
        **kwargs
    ):
        """성능 메트릭 로깅"""
        log_data = {
            "event_type": "performance_metric",
            "operation": operation,
            "duration_ms": duration_ms,
            "success": success,
            **kwargs
        }
        self.info(f"Performance: {operation}", **log_data)
    
    def log_external_api_call(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: Optional[int] = None,
        duration_ms: Optional[float] = None,
        **kwargs
    ):
        """외부 API 호출 로깅"""
        log_data = {
            "event_type": "external_api_call",
            "service": service,
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "duration_ms": duration_ms,
            **kwargs
        }
        level = "info" if status_code and 200 <= status_code < 300 else "warning"
        getattr(self, level)(f"External API: {service} {method} {endpoint}", **log_data)
    
    def log_security_event(
        self,
        event: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        severity: str = "medium",
        **kwargs
    ):
        """보안 이벤트 로깅"""
        log_data = {
            "event_type": "security_event",
            "event": event,
            "user_id": user_id,
            "ip_address": ip_address,
            "severity": severity,
            **kwargs
        }
        
        if severity in ["high", "critical"]:
            self.error(f"Security event: {event}", **log_data)
        else:
            self.warning(f"Security event: {event}", **log_data)


class LoggingMixin:
    """로깅 기능을 제공하는 믹스인 클래스"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = None
    
    @property
    def logger(self) -> ContextLogger:
        """로거 인스턴스 반환"""
        if self._logger is None:
            class_name = self.__class__.__name__
            self._logger = ContextLogger(
                f"{self.__class__.__module__}.{class_name}",
                LogCategory.BUSINESS
            )
        return self._logger


@contextmanager
def log_operation(
    logger: ContextLogger,
    operation: str,
    **context
):
    """작업 로깅 컨텍스트 매니저"""
    start_time = datetime.now()
    
    logger.info(
        f"Operation started: {operation}",
        operation=operation,
        **context
    )
    
    try:
        yield logger.bind(operation=operation, **context)
        
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.log_performance_metric(
            operation=operation,
            duration_ms=duration_ms,
            success=True,
            **context
        )
        
    except Exception as e:
        duration_ms = (datetime.now() - start_time).total_seconds() * 1000
        logger.error(
            f"Operation failed: {operation}",
            operation=operation,
            error=str(e),
            error_type=type(e).__name__,
            duration_ms=duration_ms,
            **context
        )
        raise


class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self):
        self.metrics: Dict[str, Any] = {}
        self.logger = ContextLogger("metrics", LogCategory.PERFORMANCE)
    
    def increment_counter(self, name: str, value: int = 1, **tags):
        """카운터 증가"""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in tags.items())}"
        self.metrics[key] = self.metrics.get(key, 0) + value
        
        self.logger.info(
            f"Counter incremented: {name}",
            metric_type="counter",
            metric_name=name,
            value=value,
            tags=tags
        )
    
    def record_gauge(self, name: str, value: float, **tags):
        """게이지 값 기록"""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in tags.items())}"
        self.metrics[key] = value
        
        self.logger.info(
            f"Gauge recorded: {name}",
            metric_type="gauge",
            metric_name=name,
            value=value,
            tags=tags
        )
    
    def record_histogram(self, name: str, value: float, **tags):
        """히스토그램 값 기록"""
        key = f"{name}:{':'.join(f'{k}={v}' for k, v in tags.items())}"
        if key not in self.metrics:
            self.metrics[key] = []
        self.metrics[key].append(value)
        
        self.logger.info(
            f"Histogram recorded: {name}",
            metric_type="histogram",
            metric_name=name,
            value=value,
            tags=tags
        )
    
    def get_metrics(self) -> Dict[str, Any]:
        """수집된 메트릭 반환"""
        return self.metrics.copy()
    
    def reset_metrics(self):
        """메트릭 초기화"""
        self.metrics.clear()


# 전역 메트릭 수집기
_global_metrics = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """전역 메트릭 수집기 반환"""
    return _global_metrics


def create_logger(name: str, category: LogCategory = LogCategory.SYSTEM) -> ContextLogger:
    """로거 생성 팩토리 함수"""
    return ContextLogger(name, category)


# 편의 함수들
def log_user_action(
    user_id: str,
    action: str,
    resource: Optional[str] = None,
    **kwargs
):
    """사용자 액션 로깅"""
    logger = create_logger("user_actions", LogCategory.USER_ACTION)
    logger.log_business_event(
        event=action,
        user_id=user_id,
        resource=resource,
        **kwargs
    )


def log_api_request(
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: Optional[str] = None,
    **kwargs
):
    """API 요청 로깅"""
    logger = create_logger("api_requests", LogCategory.SYSTEM)
    logger.info(
        f"API Request: {method} {path}",
        method=method,
        path=path,
        status_code=status_code,
        duration_ms=duration_ms,
        user_id=user_id,
        **kwargs
    )


def log_database_operation(
    operation: str,
    table: str,
    duration_ms: float,
    affected_rows: Optional[int] = None,
    **kwargs
):
    """데이터베이스 작업 로깅"""
    logger = create_logger("database", LogCategory.DATABASE)
    logger.log_performance_metric(
        operation=f"db_{operation}_{table}",
        duration_ms=duration_ms,
        table=table,
        affected_rows=affected_rows,
        **kwargs
    )
