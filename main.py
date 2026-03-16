from dc_crawler import crawl_dc_gallery
from db_manager import DBManager
from sentiment_analyzer import SentimentAnalyzer
from report_generator import ReportGenerator
from datetime import datetime, timedelta
import pandas as pd
import sqlite3

def run_daily_process(gallery_id='ovensmash', days_ago=7):
    """
    메인 실행 프로세스:
    1. DB 초기화
    2. 데이터 수집
    3. AI 사전 업데이트 (Daily Tutor)
    4. 로컬 감성 분석 (Local Engine)
    5. 프리미엄 리포트 생성 (FE Report)
    """
    db = DBManager()
    analyzer = SentimentAnalyzer(db)
    reporter = ReportGenerator(db.db_name)
    
    print(f"\n--- '{gallery_id}' 갤러리 프로젝트 가동 ---")
    
    # 1. 수집 단계
    target_date = datetime.now() - timedelta(days=days_ago)
    all_new_posts = []
    page = 1
    continue_crawling = True
    
    while continue_crawling:
        df_page = crawl_dc_gallery(gallery_id, pages=1)
        if df_page.empty: break
        df_page['date_dt'] = pd.to_datetime(df_page['작성일'])
        fresh_posts = df_page[df_page['date_dt'] >= target_date]
        if not fresh_posts.empty:
            all_new_posts.append(fresh_posts)
            if len(fresh_posts) < len(df_page): continue_crawling = False
        else: break
        page += 1
        if page > 10: break

    if all_new_posts:
        final_df = pd.concat(all_new_posts).drop(columns=['date_dt'])
        new_added = db.save_posts(final_df)
        print(f">> 수집 완료: 새로운 게시글 {new_added}개 추가")
    
    # 2. AI 학습 단계 (Daily Tutor)
    with sqlite3.connect(db.db_name) as conn:
        sample_df = pd.read_sql("SELECT title FROM posts ORDER BY date_standard DESC LIMIT 30", conn)
        if not sample_df.empty:
            analyzer.update_lexicon_with_llm(sample_df['title'].tolist())

    # 3. 로컬 분석 단계 (Local Engine)
    analyzed_count = analyzer.process_all_unbound_posts(force=True)
    print(f">> 분석 완료: {analyzed_count}개의 게시글 분석됨")

    # 4. 리포트 생성 단계 (FE)
    report_path = reporter.generate_daily_report()
    
    if report_path:
        print(f"\n[최종 보고] 대시보드 리포트가 생성되었습니다.")
        print(f"경로: {os.path.abspath(report_path)}")

if __name__ == "__main__":
    import os
    run_daily_process()
