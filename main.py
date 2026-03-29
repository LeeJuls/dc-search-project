from dc_crawler import crawl_dc_gallery
from db_manager import DBManager
from sentiment_analyzer import SentimentAnalyzer
from report_generator import ReportGenerator
from config import TARGET_GALLERIES
from datetime import datetime, timedelta, timezone
import pandas as pd
import os

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

def run_daily_process(gallery_id='ovensmash', days_ago=7, is_minor=True,
                      skip_llm=False, llm_only=False):
    """
    메인 실행 프로세스:
    1. DB 초기화
    2. 데이터 수집           (llm_only=True 이면 건너뜀)
    3. AI 사전 업데이트      (skip_llm=True 이면 건너뜀)
    4. 로컬 감성 분석        (항상 실행)
    5. 1일/7일 리포트 자동 생성 (항상 실행)
    """
    db = DBManager()
    analyzer = SentimentAnalyzer(db)
    reporter = ReportGenerator()
    
    print(f"\n--- '{gallery_id}' ({'마이너' if is_minor else '메이저'}) 갤러리 프로젝트 가동 ---")
    if skip_llm:
        print("   [모드: 크롤링 전용 -LLM 사전 업데이트 건너뜀]")
    if llm_only:
        print("   [모드: LLM 전용 -크롤링 건너뜀]")

    # 1. 수집 단계 (llm_only 시 건너뜀)
    if llm_only:
        print(">> [크롤링 건너뜀] llm_only 모드")
    else:
        target_date = (datetime.now(KST) - timedelta(days=days_ago)).replace(tzinfo=None)
        all_new_posts = []
        page = 1
        continue_crawling = True

        while continue_crawling:
            # 특정 페이지(page) 딱 한 페이지만 가져오도록 호출
            df_page = crawl_dc_gallery(gallery_id, start_page=page, pages=1, is_minor=is_minor)
            if df_page is None or df_page.empty: break

            # 현재 수집된 데이터의 날짜 확인
            df_page['date_dt'] = pd.to_datetime(df_page['작성일'])
            min_date = df_page['date_dt'].min()
            max_date = df_page['date_dt'].max()

            # 목표 기간 내의 게시글만 필터링
            fresh_posts = df_page[df_page['date_dt'] >= target_date]

            if not fresh_posts.empty:
                all_new_posts.append(fresh_posts)
                print(f"   - {page}페이지 분석 중... (날짜 범위: {min_date} ~ {max_date})")

                # 페이지 내의 모든 글이 목표 기간을 벗어났다면 (가장 최신글조차 과거라면) 중단
                if max_date < target_date:
                    print(f"   - 목표 기간({days_ago}일) 데이터 수집 완료.")
                    continue_crawling = False
            else:
                # 이 페이지에 최신글이 하나도 없다면 중단 (이미 과거 데이터로 넘어감)
                print(f"   - {page}페이지 이후로는 목표 기간을 벗어남. 수집을 종료합니다.")
                break

            page += 1
            # 대형 갤러리를 위해 제한을 상향 (게시글이 너무 많으므로 적정선인 100페이지로 조정)
            if page > 100:
                print(f"   - 최대 수집 제한(100페이지)에 도달하여 안전을 위해 중단합니다.")
                break

        if all_new_posts:
            final_df = pd.concat(all_new_posts).drop(columns=['date_dt'])
            new_added = db.save_posts(final_df, gallery_id)
            print(f">> [{gallery_id}] 수집 완료: 새로운 게시글 {new_added}개 추가")
        else:
            print(f">> [{gallery_id}] 새로 수집된 게시글이 없습니다.")

    # 2. AI 학습 단계 (skip_llm 시 건너뜀)
    lexicon_changed = False
    if skip_llm:
        print(">> [LLM 건너뜀] skip_llm 모드")
    else:
        try:
            response = db.client.table('posts').select('title').eq('gallery_id', gallery_id).order('date_standard', desc=True).limit(30).execute()
            if hasattr(response, 'data') and response.data:
                sample_df = pd.DataFrame(response.data)
                if not sample_df.empty:
                    gallery_info = next((g for g in TARGET_GALLERIES if g['id'] == gallery_id), None)
                    gallery_name = gallery_info['name'] if gallery_info else gallery_id
                    lexicon_changed = analyzer.update_lexicon_with_llm(sample_df['title'].tolist(), gallery_name=gallery_name) or False
        except Exception as e:
            print(f"Supabase 샘플 데이터 호출 에러: {e}")

    # 3. 로컬 분석 단계 (lexicon 변경 또는 llm_only 모드일 때만 전체 재분석)
    force_reanalyze = lexicon_changed or llm_only
    analyzed_count = analyzer.process_all_unbound_posts(force=force_reanalyze)
    print(f">> 분석 완료: {analyzed_count}개의 게시글 분석됨")

    # 4. 당일 통계 집계 저장 (daily_stats)
    today_str = datetime.now(KST).strftime('%Y-%m-%d')
    today_start = today_str + ' 00:00:00'
    tomorrow_start = (datetime.now(KST).replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)).strftime('%Y-%m-%d %H:%M:%S')

    try:
        response = db.client.table('posts').select('sentiment_score') \
            .eq('gallery_id', gallery_id) \
            .gte('date_standard', today_start) \
            .lt('date_standard', tomorrow_start) \
            .execute()

        if response.data:
            scores = [r['sentiment_score'] or 0 for r in response.data]
            total = len(scores)
            pos = sum(1 for s in scores if s > 0.1)
            neg = sum(1 for s in scores if s < -0.1)
            neu = total - pos - neg
            avg = sum(scores) / total
            db.upsert_daily_stats(gallery_id, today_str, total, pos, neg, neu, avg)
            print(f">> [{gallery_id}] 당일({today_str}) 통계 저장: {total}건")
    except Exception as e:
        print(f"당일 통계 집계 오류: {e}")

    # 5. 리포트 생성 단계
    reporter.generate_daily_report(gallery_id, days=1)
    reporter.generate_daily_report(gallery_id, days=7)
    
    return True

if __name__ == "__main__":
    import sys
    input_target = sys.argv[1] if len(sys.argv) > 1 else 'ovensmash'
    
    # URL 분석을 통한 갤러리 ID 및 타입(메이저/마이너) 판별
    is_minor = True # 기본값
    gallery_id = input_target
    
    if 'gall.dcinside.com' in input_target:
        is_minor = '/mgallery/' in input_target or '/mini/' in input_target
        if 'id=' in input_target:
            gallery_id = input_target.split('id=')[-1].split('&')[0]
        
    run_daily_process(gallery_id, is_minor=is_minor)
