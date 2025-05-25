"""
GraphAPI Query System 표준화된 예외 시스템
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(str, Enum):
    """에러 코드 정의"""
    # 비즈니스 로직 에러
    VALIDATION_ERROR = "VALIDATION_ERROR"
    BUSINESS_RULE_VIOLATION = "BUSINESS_RULE_VIOLATION"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    DUPLICATE_RESOURCE = "DUPLICATE_RESOURCE"
    
    # 외부 서비스 에러
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    AUTHENTICATION_ERROR = "AUTHENTICATION_ERROR"
    AUTHORIZATION_ERROR = "AUTHORIZATION_ERROR"
    RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    
    # 시스템 에러
    DATABASE_ERROR = "DATABASE_ERROR"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class GraphAPIQueryError(Exception):
    """애플리케이션 기본 예외 클래스"""
    
    def __init__(
        self,
        message: str,
        error_code: ErrorCode,
        details: Optional[Dict[str, Any]] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.cause = cause
    
    def to_dict(self) -> Dict[str, Any]:
        """예외를 딕셔너리로 변환"""
        return {
            "error_code": self.error_code.value,
            "message": self.message,
            "details": self.details,
            "cause": str(self.cause) if self.cause else None
        }


class BusinessLogicError(GraphAPIQueryError):
    """비즈니스 로직 에러"""
    pass


class ValidationError(BusinessLogicError):
    """데이터 검증 에러"""
    def __init__(self, message: str, field: Optional[str] = None, **kwargs):
        super().__init__(
            message, 
            ErrorCode.VALIDATION_ERROR, 
            details={"field": field} if field else None,
            **kwargs
        )


class ResourceNotFoundError(BusinessLogicError):
    """리소스 찾을 수 없음 에러"""
    def __init__(self, resource_type: str, resource_id: str, **kwargs):
        super().__init__(
            f"{resource_type} with ID {resource_id} not found",
            ErrorCode.RESOURCE_NOT_FOUND,
            details={"resource_type": resource_type, "resource_id": resource_id},
            **kwargs
        )


class DuplicateResourceError(BusinessLogicError):
    """중복 리소스 에러"""
    def __init__(self, resource_type: str, identifier: str, **kwargs):
        super().__init__(
            f"{resource_type} with identifier {identifier} already exists",
            ErrorCode.DUPLICATE_RESOURCE,
            details={"resource_type": resource_type, "identifier": identifier},
            **kwargs
        )


class ExternalServiceError(GraphAPIQueryError):
    """외부 서비스 에러"""
    def __init__(
        self, 
        message: str, 
        service: str, 
        status_code: Optional[int] = None,
        error_code: ErrorCode = ErrorCode.EXTERNAL_SERVICE_ERROR,
        **kwargs
    ):
        super().__init__(
            message, 
            error_code,
            details={"service": service, "status_code": status_code},
            **kwargs
        )
        self.service = service
        self.status_code = status_code


class AuthenticationError(ExternalServiceError):
    """인증 에러"""
    def __init__(self, message: str, service: str = "Unknown", **kwargs):
        super().__init__(
            message, 
            service, 
            error_code=ErrorCode.AUTHENTICATION_ERROR,
            **kwargs
        )


class AuthorizationError(ExternalServiceError):
    """인가 에러"""
    def __init__(self, message: str, service: str = "Unknown", **kwargs):
        super().__init__(
            message, 
            service,
            error_code=ErrorCode.AUTHORIZATION_ERROR,
            **kwargs
        )


class RateLimitError(ExternalServiceError):
    """Rate Limit 에러"""
    def __init__(
        self, 
        message: str, 
        service: str, 
        retry_after: Optional[int] = None,
        **kwargs
    ):
        super().__init__(
            message, 
            service,
            error_code=ErrorCode.RATE_LIMIT_EXCEEDED,
            **kwargs
        )
        self.retry_after = retry_after
        if retry_after:
            self.details["retry_after"] = retry_after


class DatabaseError(GraphAPIQueryError):
    """데이터베이스 에러"""
    def __init__(self, message: str, operation: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            ErrorCode.DATABASE_ERROR,
            details={"operation": operation} if operation else None,
            **kwargs
        )


class ConfigurationError(GraphAPIQueryError):
    """설정 에러"""
    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            ErrorCode.CONFIGURATION_ERROR,
            details={"config_key": config_key} if config_key else None,
            **kwargs
        )


class InternalError(GraphAPIQueryError):
    """내부 시스템 에러"""
    def __init__(self, message: str, component: Optional[str] = None, **kwargs):
        super().__init__(
            message,
            ErrorCode.INTERNAL_ERROR,
            details={"component": component} if component else None,
            **kwargs
        )


# 하위 호환성을 위한 별칭들
RepositoryError = DatabaseError


# Graph API 관련 특화 예외들
class GraphAPIError(ExternalServiceError):
    """Microsoft Graph API 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="Microsoft Graph API", **kwargs)


class GraphAPIAuthenticationError(AuthenticationError):
    """Microsoft Graph API 인증 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="Microsoft Graph API", **kwargs)


class GraphAPIRateLimitError(RateLimitError):
    """Microsoft Graph API Rate Limit 에러"""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, service="Microsoft Graph API", retry_after=retry_after, **kwargs)


# External API 관련 특화 예외들
class ExternalAPIError(ExternalServiceError):
    """외부 API 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="External API", **kwargs)


class ExternalAPIAuthenticationError(AuthenticationError):
    """외부 API 인증 에러"""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, service="External API", **kwargs)


class ExternalAPIRateLimitError(RateLimitError):
    """외부 API Rate Limit 에러"""
    def __init__(self, message: str, retry_after: Optional[int] = None, **kwargs):
        super().__init__(message, service="External API", retry_after=retry_after, **kwargs)
