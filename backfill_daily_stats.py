"""
과거 posts 데이터를 기반으로 daily_stats 테이블을 백필합니다. (1회성 스크립트)
사전 조건: Supabase SQL Editor에서 daily_stats 테이블 + backfill_daily_stats RPC가 생성되어 있어야 합니다.
"""
from db_manager import DBManager

db = DBManager()
db.client.rpc('backfill_daily_stats').execute()
print("daily_stats 백필 완료!")
