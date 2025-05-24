"""
보안 관련 유틸리티 함수들
"""
from typing import Dict, Any, List
import re


class SecurityUtils:
    """보안 관련 유틸리티 클래스"""
    
    @staticmethod
    def mask_url(url: str) -> str:
        """URL에서 민감한 정보 마스킹"""
        if not url:
            return url
            
        if "@" in url:
            parts = url.split("@")
            if len(parts) == 2:
                protocol_and_auth = parts[0]
                host_and_db = parts[1]
                if "://" in protocol_and_auth:
                    protocol, auth = protocol_and_auth.split("://", 1)
                    if ":" in auth:
                        user, _ = auth.split(":", 1)
                        return f"{protocol}://{user}:***@{host_and_db}"
        return url
    
    @staticmethod
    def mask_sensitive_dict(
        data: Dict[str, Any], 
        sensitive_keys: List[str], 
        mask_value: str = "***MASKED***"
    ) -> Dict[str, Any]:
        """딕셔너리에서 민감한 키들 마스킹"""
        if not data:
            return data
            
        masked_data = data.copy()
        for key in sensitive_keys:
            if key in masked_data and masked_data[key]:
                masked_data[key] = mask_value
        return masked_data
    
    @staticmethod
    def mask_token(token: str, visible_chars: int = 4) -> str:
        """토큰 마스킹 (앞 4자리만 표시)"""
        if not token or len(token) <= visible_chars:
            return "***"
        return f"{token[:visible_chars]}***"
    
    @staticmethod
    def mask_email(email: str) -> str:
        """이메일 주소 마스킹"""
        if not email or "@" not in email:
            return email
            
        local, domain = email.split("@", 1)
        if len(local) <= 2:
            masked_local = "*" * len(local)
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
        
        return f"{masked_local}@{domain}"
    
    @staticmethod
    def is_sensitive_key(key: str) -> bool:
        """키가 민감한 정보인지 확인"""
        sensitive_patterns = [
            r'.*password.*',
            r'.*secret.*',
            r'.*key.*',
            r'.*token.*',
            r'.*auth.*',
            r'.*credential.*',
            r'.*dsn.*'
        ]
        
        key_lower = key.lower()
        return any(re.match(pattern, key_lower) for pattern in sensitive_patterns)
    
    @staticmethod
    def sanitize_log_data(data: Any) -> Any:
        """로그 데이터에서 민감한 정보 자동 제거"""
        if isinstance(data, dict):
            sanitized = {}
            for key, value in data.items():
                if SecurityUtils.is_sensitive_key(key):
                    sanitized[key] = "***SANITIZED***"
                else:
                    sanitized[key] = SecurityUtils.sanitize_log_data(value)
            return sanitized
        elif isinstance(data, list):
            return [SecurityUtils.sanitize_log_data(item) for item in data]
        elif isinstance(data, str) and len(data) > 50:
            # 긴 문자열은 잠재적으로 민감할 수 있으므로 일부만 표시
            return f"{data[:20]}...{data[-10:]}"
        else:
            return data
