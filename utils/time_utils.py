from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))

def get_korean_time():
    """현재 한국 시간(timezone 포함) 반환"""
    return datetime.now(KST)

def get_korean_time_for_db():
    """DB 저장용 한국 시간(timezone 미포함) 반환"""
    return datetime.now(KST).replace(tzinfo=None)
