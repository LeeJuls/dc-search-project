from dc_crawler import crawl_dc_gallery
from db_manager import DBManager
from datetime import datetime, timedelta
import pandas as pd

def run_daily_process(gallery_id='ovensmash', days_ago=7):
    """
    메인 실행 프로세스:
    1. DB 초기화
    2. 데이터 수집 (지정된 날짜까지)
    3. DB 저장 및 결과 보고
    """
    # 1. DB 매니저 초기화
    db = DBManager()
    
    print(f"--- '{gallery_id}' 갤러리 데이터 업데이트 시작 ---")
    
    # 2. 수집 대상 날짜 기준 설정 (현재로부터 7일 전까지)
    target_date = datetime.now() - timedelta(days=days_ago)
    print(f"수집 기준일: {target_date.strftime('%Y-%m-%d')} 이후 게시글")
    
    all_new_posts = []
    page = 1
    continue_crawling = True
    
    while continue_crawling:
        # 페이지 단위로 수집
        df_page = crawl_dc_gallery(gallery_id, pages=1) # 1페이지씩 수집
        if df_page.empty:
            break
            
        # 날짜 필터링
        df_page['date_dt'] = pd.to_datetime(df_page['작성일'])
        
        # 현재 페이지 글 중 기준일보다 최신인 글만 필터링
        fresh_posts = df_page[df_page['date_dt'] >= target_date]
        
        if not fresh_posts.empty:
            all_new_posts.append(fresh_posts)
            
            # 페이지에 기준일보다 오래된 글이 섞여 있다면 중단
            if len(fresh_posts) < len(df_page):
                print(f"{page}페이지에서 기준일 이전 게시글 발견. 수집을 마칩니다.")
                continue_crawling = False
        else:
            # 현재 페이지 모든 글이 기준일 이전인 경우
            print(f"{page}페이지의 모든 글이 기준일 데이터가 아닙니다. 중단합니다.")
            break
            
        page += 1
        # 무한 루프 방지 (최대 30페이지까지만)
        if page > 30:
            break

    # 3. 통합 및 DB 저장
    if all_new_posts:
        final_df = pd.concat(all_new_posts).drop(columns=['date_dt'])
        new_added = db.save_posts(final_df)
        print(f"\n[업데이트 결과] 총 {len(final_df)}개 수집 시도 중, 새로운 게시글 {new_added}개가 DB에 반영되었습니다.")
    else:
        print("\n새로 수집된 게시글이 없습니다.")

if __name__ == "__main__":
    # 이 파일은 전체 시스템을 연결하는 메인 브레인 역할을 합니다.
    # 연결된 파일: dc_crawler.py, db_manager.py
    run_daily_process()
