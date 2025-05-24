"""
DateTime 관련 유틸리티 함수들
"""
from datetime import datetime, timezone
from typing import Optional
import re


class DateTimeUtils:
    """DateTime 관련 유틸리티 클래스"""
    
    @staticmethod
    def parse_iso_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        """ISO 형식 datetime 문자열 파싱"""
        if not datetime_str:
            return None
        
        try:
            # Z suffix 처리 (UTC)
            if datetime_str.endswith("Z"):
                return datetime.fromisoformat(datetime_str[:-1]).replace(tzinfo=timezone.utc)
            
            # +00:00 형식 timezone 처리
            elif re.search(r'[+-]\d{2}:\d{2}$', datetime_str):
                return datetime.fromisoformat(datetime_str)
            
            # timezone 정보가 없는 경우 UTC로 가정
            else:
                return datetime.fromisoformat(datetime_str).replace(tzinfo=timezone.utc)
                
        except (ValueError, TypeError) as e:
            # 로깅을 위해 원본 문자열 정보 포함
            return None
    
    @staticmethod
    def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
        """datetime을 ISO 문자열로 변환 (UTC Z 형식)"""
        if not dt:
            return None
        
        # timezone이 없는 경우 UTC로 가정
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        
        # UTC로 변환 후 Z 형식으로 반환
        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat().replace('+00:00', 'Z')
    
    @staticmethod
    def to_utc(dt: Optional[datetime]) -> Optional[datetime]:
        """datetime을 UTC로 변환"""
        if not dt:
            return None
        
        # timezone이 없는 경우 UTC로 가정
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        
        return dt.astimezone(timezone.utc)
    
    @staticmethod
    def now_utc() -> datetime:
        """현재 UTC 시간 반환"""
        return datetime.now(timezone.utc)
    
    @staticmethod
    def is_valid_iso_format(datetime_str: str) -> bool:
        """ISO 형식 datetime 문자열 유효성 검사"""
        if not datetime_str:
            return False
        
        try:
            DateTimeUtils.parse_iso_datetime(datetime_str)
            return True
        except:
            return False
    
    @staticmethod
    def format_for_display(dt: Optional[datetime], format_str: str = "%Y-%m-%d %H:%M:%S UTC") -> str:
        """사용자 표시용 datetime 포맷팅"""
        if not dt:
            return "N/A"
        
        # UTC로 변환
        utc_dt = DateTimeUtils.to_utc(dt)
        return utc_dt.strftime(format_str)
    
    @staticmethod
    def parse_graph_api_datetime(datetime_str: Optional[str]) -> Optional[datetime]:
        """Microsoft Graph API datetime 형식 파싱"""
        if not datetime_str:
            return None
        
        # Graph API는 보통 ISO 8601 형식을 사용
        return DateTimeUtils.parse_iso_datetime(datetime_str)
    
    @staticmethod
    def to_graph_api_format(dt: Optional[datetime]) -> Optional[str]:
        """Microsoft Graph API 형식으로 datetime 변환"""
        if not dt:
            return None
        
        # Graph API는 ISO 8601 Z 형식을 선호
        return DateTimeUtils.to_iso_string(dt)
