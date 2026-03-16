import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import time
import random

def get_standard_date(date_str):
    """
    디시인사이드의 다양한 날짜 형식을 YYYY-MM-DD HH:mm:ss 형식으로 변환합니다.
    - HH:mm (오늘)
    - MM.DD (올해)
    - YY.MM.DD (과거 연도)
    - YYYY-MM-DD HH:mm:ss (이미 완성된 형식)
    """
    now = datetime.now()
    
    # 이미 완성된 형식인지 확인 (title 속성 등에서 가져왔을 경우)
    try:
        datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return date_str
    except:
        pass

    try:
        if ':' in date_str:
            # 오늘 게시글 (HH:mm 형식일 경우)
            if len(date_str) <= 5:
                return now.strftime('%Y-%m-%d ') + date_str + ':00'
            return date_str
        
        parts = date_str.split('.')
        if len(parts) == 2:
            # 올해 게시글 (MM.DD)
            return f"{now.year}-{parts[0]}-{parts[1]} 00:00:00"
        elif len(parts) == 3:
            # 과거 게시글 (YY.MM.DD)
            year = '20' + parts[0] if len(parts[0]) == 2 else parts[0]
            return f"{year}-{parts[1]}-{parts[2]} 00:00:00"
    except Exception as e:
        print(f"날짜 변환 오류 ({date_str}): {e}")
        return date_str

def crawl_dc_gallery(gallery_id, pages=1):
    """
    특정 갤러리의 게시글 목록을 수집합니다.
    """
    base_url = f"https://gall.dcinside.com/mgallery/board/lists/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    posts_data = []

    for page in range(1, pages + 1):
        print(f"현재 {page} 페이지 수집 중...")
        params = {
            'id': gallery_id,
            'page': page
        }
        
        try:
            # 1. 페이지 요청
            response = requests.get(base_url, params=params, headers=headers)
            if response.status_code != 200:
                print(f"페이지 요청 실패 (Code: {response.status_code})")
                break
                
            # 2. HTML 분석
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 게시글 행(row) 찾기
            # us-post 클래스가 일반 유저 게시글입니다.
            rows = soup.select('tr.us-post')
            
            for row in rows:
                # 공지글 제외 (공지글은 제목 옆에 '공지' 배지가 있거나 다른 구조일 수 있음)
                # 여기서는 기본적인 게시글 정보만 추출합니다.
                
                try:
                    num = row.select_one('td.gall_num').text.strip()
                    title_elem = row.select_one('td.gall_tit a')
                    title = title_elem.text.strip()
                    # 댓글 개수 제거 (있을 경우)
                    reply_num = row.select_one('span.reply_num')
                    if reply_num:
                        title = title.replace(reply_num.text, "").strip()
                        
                    writer = row.select_one('td.gall_writer').get('data-nick', '익명')
                    date_raw = row.select_one('td.gall_date').get('title', row.select_one('td.gall_date').text.strip())
                    date_standard = get_standard_date(date_raw)
                    views = row.select_one('td.gall_count').text.strip()
                    recommend = row.select_one('td.gall_recommend').text.strip()
                    
                    posts_data.append({
                        '번호': num,
                        '제목': title,
                        '작성자': writer,
                        '작성일': date_standard,
                        '조회수': views,
                        '추천수': recommend
                    })
                except Exception as e:
                    continue # 한 줄 에러나도 다음 줄 진행
            
            # 3. 차단 방지를 위한 랜덤 휴식
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            print(f"에러 발생: {e}")
            break

    return pd.DataFrame(posts_data)

if __name__ == "__main__":
    # 메인이 실행될 때 전체적인 흐름을 제어합니다.
    # 연결된 파일: requirements.txt (필요 라이브러리 목록)
    
    print("=== 오븐스매시 갤러리 크롤링 시작 ===")
    
    # 1페이지 테스트
    df = crawl_dc_gallery('ovensmash', pages=1)
    
    if not df.empty:
        print(f"\n총 {len(df)}개의 게시글을 수집했습니다.")
        print(df.head())
        # 결과 저장
        df.to_csv('crawl_result_test.csv', index=False, encoding='utf-8-sig')
        print("\n'crawl_result_test.csv'로 저장되었습니다.")
    else:
        print("수집된 데이터가 없습니다.")
