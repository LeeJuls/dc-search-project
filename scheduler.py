import time
from datetime import datetime
from config import TARGET_GALLERIES
from main import run_daily_process
import traceback

def process_galleries():
    """정의된 모든 갤러리를 순회하며 수집 및 분석을 실행합니다."""
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 스케줄러 데이터 수집 사이클 시작")
    
    for gallery in TARGET_GALLERIES:
        try:
            print(f"\n=======================================================")
            print(f"타겟 갤러리 수집 시작: {gallery['name']} ({gallery['id']})")
            print(f"=======================================================")
            
            # 메인 분석 프로세스 호출
            run_daily_process(gallery_id=gallery['id'], days_ago=7, is_minor=gallery['is_minor'])
            
            print(f"--> 타겟 갤러리 완료: {gallery['name']}")
        except Exception as e:
            print(f"--> [오류] {gallery['name']} 갤러리 처리 중 예외 발생:")
            traceback.print_exc()
            
        # IP 차단 등을 방지하기 위해 갤러리와 갤러리 처리 사이에 약간의 딜레이 부여 (10초)
        print("\n--> 서버 및 타겟 사이트 안정화를 위해 10초 대기합니다...")
        time.sleep(10)
        
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 사이클 수집 및 분석 작업 모두 완료")

def run_scheduler(interval_minutes=30):
    """지정된 분 간격으로 스케줄러를 무한 구동합니다."""
    print(f"\n=======================================================")
    print(f"   DC Search 백그라운드 스케줄러 구동 시작 (주기: {interval_minutes}분)  ")
    print(f"=======================================================")
    
    while True:
        try:
            process_galleries()
        except Exception as e:
            print("스케줄러 메인 루프 작동 중 치명적 오류 발생:")
            traceback.print_exc()
            
        # 다음 실행 시간 계산 및 대기
        next_run = datetime.now().timestamp() + (interval_minutes * 60)
        print(f"\n=> 🔄 다음 전체 수집 예정 시간: {datetime.fromtimestamp(next_run).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"=> {interval_minutes}분 동안 대기합니다...\n")
        
        time.sleep(interval_minutes * 60)

if __name__ == "__main__":
    # 라이브러리 추가 설치 없이 파이썬 기본 time 만으로 구현
    # 주기 30분
    run_scheduler(interval_minutes=30)
