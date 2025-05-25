"""
표준화된 에러 핸들링 및 로깅 유틸리티
"""
import logging
import traceback
import functools
from typing import Any, Callable, Dict, Optional, Type, TypeVar, Union
from datetime import datetime
import asyncio
import json

from ..exceptions import (
    GraphAPIQueryError, 
    ErrorCode, 
    ExternalServiceError,
    DatabaseError,
    ConfigurationError,
    InternalError
)

logger = logging.getLogger(__name__)

T = TypeVar('T')

class ErrorContext:
    """에러 컨텍스트 정보를 담는 클래스"""
    
    def __init__(
        self,
        operation: str,
        user_id: Optional[str] = None,
        account_id: Optional[str] = None,
        request_id: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ):
        self.operation = operation
        self.user_id = user_id
        self.account_id = account_id
        self.request_id = request_id
        self.additional_context = additional_context or {}
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """컨텍스트를 딕셔너리로 변환"""
        return {
            "operation": self.operation,
            "user_id": self.user_id,
            "account_id": self.account_id,
            "request_id": self.request_id,
            "timestamp": self.timestamp.isoformat(),
            "additional_context": self.additional_context
        }

class StandardizedErrorHandler:
    """표준화된 에러 핸들러"""
    
    def __init__(self, logger_name: Optional[str] = None):
        self.logger = logging.getLogger(logger_name or __name__)
    
    def handle_error(
        self,
        error: Exception,
        context: Optional[ErrorContext] = None,
        reraise: bool = True
    ) -> Optional[GraphAPIQueryError]:
        """에러를 표준화된 방식으로 처리"""
        
        # 이미 표준화된 에러인 경우
        if isinstance(error, GraphAPIQueryError):
            self._log_standardized_error(error, context)
            if reraise:
                raise error
            return error
        
        # 표준화되지 않은 에러를 변환
        standardized_error = self._standardize_error(error, context)
        self._log_standardized_error(standardized_error, context)
        
        if reraise:
            raise standardized_error
        return standardized_error
    
    def _standardize_error(
        self, 
        error: Exception, 
        context: Optional[ErrorContext] = None
    ) -> GraphAPIQueryError:
        """에러를 표준화된 형태로 변환"""
        
        error_message = str(error)
        error_details = {}
        
        if context:
            error_details.update(context.to_dict())
        
        # 에러 타입별 분류
        if isinstance(error, (ConnectionError, TimeoutError)):
            return ExternalServiceError(
                message=f"Connection error: {error_message}",
                service="Unknown",
                details=error_details,
                cause=error
            )
        
        elif isinstance(error, ValueError):
            return GraphAPIQueryError(
                message=f"Validation error: {error_message}",
                error_code=ErrorCode.VALIDATION_ERROR,
                details=error_details,
                cause=error
            )
        
        elif "database" in error_message.lower() or "sql" in error_message.lower():
            return DatabaseError(
                message=f"Database error: {error_message}",
                details=error_details,
                cause=error
            )
        
        elif "config" in error_message.lower():
            return ConfigurationError(
                message=f"Configuration error: {error_message}",
                details=error_details,
                cause=error
            )
        
        else:
            # 기본적으로 내부 에러로 처리
            return GraphAPIQueryError(
                message=f"Internal error: {error_message}",
                error_code=ErrorCode.INTERNAL_ERROR,
                details=error_details,
                cause=error
            )
    
    def _log_standardized_error(
        self, 
        error: GraphAPIQueryError, 
        context: Optional[ErrorContext] = None
    ):
        """표준화된 에러를 로깅"""
        
        log_data = {
            "error_code": error.error_code.value,
            "error_message": error.message,
            "error_details": error.details,
            "traceback": traceback.format_exc() if error.cause else None
        }
        
        if context:
            log_data["context"] = context.to_dict()
        
        # 에러 심각도에 따른 로그 레벨 결정
        if error.error_code in [ErrorCode.INTERNAL_ERROR, ErrorCode.DATABASE_ERROR]:
            self.logger.error(
                f"Critical error occurred: {error.error_code.value}",
                extra={"error_data": log_data}
            )
        elif error.error_code in [ErrorCode.EXTERNAL_SERVICE_ERROR, ErrorCode.CONFIGURATION_ERROR]:
            self.logger.warning(
                f"Service error occurred: {error.error_code.value}",
                extra={"error_data": log_data}
            )
        else:
            self.logger.info(
                f"Business error occurred: {error.error_code.value}",
                extra={"error_data": log_data}
            )

# 전역 에러 핸들러 인스턴스
_global_error_handler = StandardizedErrorHandler()

def handle_errors(
    operation: str,
    reraise: bool = True,
    context_factory: Optional[Callable[..., ErrorContext]] = None
):
    """에러 핸들링 데코레이터"""
    
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs) -> T:
                context = None
                if context_factory:
                    try:
                        context = context_factory(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"Failed to create error context: {e}")
                        context = ErrorContext(operation=operation)
                else:
                    context = ErrorContext(operation=operation)
                
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    return _global_error_handler.handle_error(e, context, reraise)
            
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs) -> T:
                context = None
                if context_factory:
                    try:
                        context = context_factory(*args, **kwargs)
                    except Exception as e:
                        logger.warning(f"Failed to create error context: {e}")
                        context = ErrorContext(operation=operation)
                else:
                    context = ErrorContext(operation=operation)
                
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    return _global_error_handler.handle_error(e, context, reraise)
            
            return sync_wrapper
    
    return decorator

def log_operation_start(operation: str, context: Optional[Dict[str, Any]] = None):
    """작업 시작 로깅"""
    logger.info(
        f"Operation started: {operation}",
        extra={
            "operation": operation,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }
    )

def log_operation_success(
    operation: str, 
    duration_ms: Optional[float] = None,
    result_summary: Optional[Dict[str, Any]] = None
):
    """작업 성공 로깅"""
    log_data = {
        "operation": operation,
        "status": "success",
        "timestamp": datetime.now().isoformat()
    }
    
    if duration_ms is not None:
        log_data["duration_ms"] = duration_ms
    
    if result_summary:
        log_data["result_summary"] = result_summary
    
    logger.info(f"Operation completed successfully: {operation}", extra=log_data)

def log_operation_failure(
    operation: str,
    error: Exception,
    duration_ms: Optional[float] = None,
    context: Optional[Dict[str, Any]] = None
):
    """작업 실패 로깅"""
    log_data = {
        "operation": operation,
        "status": "failure",
        "error": str(error),
        "error_type": type(error).__name__,
        "timestamp": datetime.now().isoformat()
    }
    
    if duration_ms is not None:
        log_data["duration_ms"] = duration_ms
    
    if context:
        log_data["context"] = context
    
    logger.error(f"Operation failed: {operation}", extra=log_data)

class OperationTimer:
    """작업 시간 측정 컨텍스트 매니저"""
    
    def __init__(self, operation: str, auto_log: bool = True):
        self.operation = operation
        self.auto_log = auto_log
        self.start_time = None
        self.end_time = None
        self.duration_ms = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        if self.auto_log:
            log_operation_start(self.operation)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        self.duration_ms = (self.end_time - self.start_time).total_seconds() * 1000
        
        if self.auto_log:
            if exc_type is None:
                log_operation_success(self.operation, self.duration_ms)
            else:
                log_operation_failure(self.operation, exc_val, self.duration_ms)
    
    async def __aenter__(self):
        return self.__enter__()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return self.__exit__(exc_type, exc_val, exc_tb)

def create_error_response(error: GraphAPIQueryError) -> Dict[str, Any]:
    """API 응답용 에러 딕셔너리 생성"""
    return {
        "success": False,
        "error": {
            "code": error.error_code.value,
            "message": error.message,
            "details": error.details,
            "timestamp": datetime.now().isoformat()
        }
    }

def create_success_response(data: Any, message: Optional[str] = None) -> Dict[str, Any]:
    """API 응답용 성공 딕셔너리 생성"""
    response = {
        "success": True,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    if message:
        response["message"] = message
    
    return response

# 편의 함수들
def safe_execute(func: Callable[..., T], *args, **kwargs) -> Optional[T]:
    """안전하게 함수를 실행하고 에러 발생 시 None 반환"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        _global_error_handler.handle_error(e, reraise=False)
        return None

async def safe_execute_async(func: Callable[..., T], *args, **kwargs) -> Optional[T]:
    """안전하게 비동기 함수를 실행하고 에러 발생 시 None 반환"""
    try:
        if asyncio.iscoroutinefunction(func):
            return await func(*args, **kwargs)
        else:
            return func(*args, **kwargs)
    except Exception as e:
        _global_error_handler.handle_error(e, reraise=False)
        return None
