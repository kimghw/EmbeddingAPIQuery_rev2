"""
HTTP 관련 공통 유틸리티
"""
import json
import httpx
from typing import Dict, Any, Optional, Type, Union
from core.exceptions import (
    ExternalServiceError, 
    AuthenticationError, 
    AuthorizationError,
    RateLimitError,
    ValidationError
)


class HTTPErrorHandler:
    """HTTP 응답 에러 처리 유틸리티"""
    
    @staticmethod
    async def handle_response_errors(
        response: httpx.Response,
        service_name: str,
        auth_error_class: Type[Exception] = AuthenticationError,
        rate_limit_error_class: Type[Exception] = RateLimitError
    ) -> None:
        """HTTP 응답 에러 처리"""
        if response.status_code < 400:
            return
        
        # 에러 메시지 추출
        error_message, error_code = HTTPErrorHandler._extract_error_info(response)
        
        # 상태 코드별 예외 처리
        if response.status_code == 401:
            raise auth_error_class(f"Authentication failed: {error_message}", service=service_name)
        elif response.status_code == 403:
            raise AuthorizationError(f"Access forbidden: {error_message}", service=service_name)
        elif response.status_code == 429:
            retry_after = response.headers.get("Retry-After", "60")
            raise rate_limit_error_class(
                f"Rate limit exceeded for {service_name}. Retry after {retry_after} seconds",
                service=service_name,
                retry_after=int(retry_after)
            )
        elif response.status_code >= 500:
            raise ExternalServiceError(
                f"{service_name} server error: {error_message}",
                service=service_name,
                status_code=response.status_code
            )
        elif response.status_code == 400:
            raise ValidationError(f"Bad request to {service_name}: {error_message}")
        else:
            raise ExternalServiceError(
                f"{service_name} error ({response.status_code}): {error_message}",
                service=service_name,
                status_code=response.status_code
            )
    
    @staticmethod
    def _extract_error_info(response: httpx.Response) -> tuple[str, Optional[str]]:
        """응답에서 에러 정보 추출"""
        try:
            error_data = response.json()
            if isinstance(error_data, dict):
                # Graph API 스타일
                if "error" in error_data and isinstance(error_data["error"], dict):
                    message = error_data["error"].get("message", "Unknown error")
                    code = error_data["error"].get("code", "UnknownError")
                # 일반적인 API 스타일
                else:
                    message = error_data.get("message", error_data.get("error", "Unknown error"))
                    code = error_data.get("code", "UnknownError")
            else:
                message = str(error_data)
                code = f"HTTP{response.status_code}"
        except json.JSONDecodeError:
            message = f"HTTP {response.status_code}: {response.text[:200]}"
            code = f"HTTP{response.status_code}"
        
        return message, code


class HTTPClientUtils:
    """HTTP 클라이언트 관련 유틸리티"""
    
    @staticmethod
    def get_default_headers(service_name: str, version: str = "1.0") -> Dict[str, str]:
        """기본 HTTP 헤더 생성"""
        return {
            "User-Agent": f"GraphAPIQuery/{version} ({service_name})",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
    
    @staticmethod
    def add_auth_header(headers: Dict[str, str], token: str, auth_type: str = "Bearer") -> Dict[str, str]:
        """인증 헤더 추가"""
        headers = headers.copy()
        headers["Authorization"] = f"{auth_type} {token}"
        return headers
    
    @staticmethod
    def prepare_json_payload(data: Dict[str, Any]) -> str:
        """JSON 페이로드 준비"""
        return json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    
    @staticmethod
    def is_json_response(response: httpx.Response) -> bool:
        """응답이 JSON 형식인지 확인"""
        content_type = response.headers.get("content-type", "")
        return "application/json" in content_type.lower()
    
    @staticmethod
    def safe_json_decode(response: httpx.Response) -> Optional[Dict[str, Any]]:
        """안전한 JSON 디코딩"""
        if not HTTPClientUtils.is_json_response(response):
            return None
        
        try:
            return response.json()
        except json.JSONDecodeError:
            return None


class RetryUtils:
    """재시도 관련 유틸리티"""
    
    @staticmethod
    def should_retry(response: httpx.Response, attempt: int, max_retries: int) -> bool:
        """재시도 여부 결정"""
        if attempt >= max_retries:
            return False
        
        # 5xx 서버 에러는 재시도
        if response.status_code >= 500:
            return True
        
        # 429 Rate Limit은 재시도
        if response.status_code == 429:
            return True
        
        # 408 Request Timeout은 재시도
        if response.status_code == 408:
            return True
        
        return False
    
    @staticmethod
    def get_retry_delay(response: httpx.Response, attempt: int, base_delay: float = 1.0) -> float:
        """재시도 지연 시간 계산"""
        # Retry-After 헤더가 있으면 사용
        retry_after = response.headers.get("Retry-After")
        if retry_after:
            try:
                return float(retry_after)
            except ValueError:
                pass
        
        # 지수 백오프 적용
        return base_delay * (2 ** attempt)
