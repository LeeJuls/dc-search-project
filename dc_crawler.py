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
    - MM.DD 또는 MM/DD (올해)
    - YY.MM.DD 또는 YY/MM/DD (과거 연도)
    - YYYY-MM-DD HH:mm:ss (이미 완성된 형식)
    """
    if not date_str: return datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    date_str = date_str.strip()
    now = datetime.now()
    
    # 1. 이미 완성된 형태 (YYYY-MM-DD HH:mm:ss)
    try:
        datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return date_str
    except: pass

    # 2. 오늘 게시글 (HH:mm)
    if ':' in date_str and len(date_str) <= 5:
        return now.strftime('%Y-%m-%d ') + date_str + ':00'

    # 3. 구분자 통일 (. 또는 / 를 - 로 변경)
    clean_date = date_str.replace('.', '-').replace('/', '-')
    parts = clean_date.split('-')
    
    try:
        if len(parts) == 2:
            # MM-DD -> 올해 날짜
            return f"{now.year}-{parts[0].zfill(2)}-{parts[1].zfill(2)} 00:00:00"
        elif len(parts) == 3:
            # YY-MM-DD 또는 YYYY-MM-DD
            year = parts[0]
            if len(year) == 2: year = '20' + year
            return f"{year}-{parts[1].zfill(2)}-{parts[2].zfill(2)} 00:00:00"
    except Exception as e:
        print(f"날짜 처리 중 예외 발생 ({date_str}): {e}")
        
    return date_str

def crawl_dc_gallery(gallery_id, start_page=1, pages=1, is_minor=True):
    """
    특정 갤러리의 게시글 목록을 수집합니다.
    - start_page: 시작 페이지 번호
    - pages: 수집할 페이지 수
    - is_minor: True이면 마이너 갤러리(mgallery), False이면 메이저 갤러리(board) URL을 사용합니다.
    """
    path = "mgallery/board/lists/" if is_minor else "board/lists/"
    base_url = f"https://gall.dcinside.com/{path}"
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Referer': f'https://gall.dcinside.com/{path}/?id={gallery_id}'
    }
    
    posts_data = []

    for page in range(start_page, start_page + pages):
        print(f"현재 {gallery_id} ({'마이너' if is_minor else '메이저'}) {page} 페이지 수집 중...")
        params = {
            'id': gallery_id,
            'page': page
        }
        
        try:
            response = requests.get(base_url, params=params, headers=headers)
            if response.status_code != 200:
                print(f"페이지 요청 실패 (Code: {response.status_code})")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 메이저/마이너 공통으로 사용하는 행 선택 (중복 방지를 위해 find_all 사용)
            rows = soup.find_all('tr', class_=['ub-content', 'us-post'])
            
            if not rows:
                print("게시글 행을 찾을 수 없습니다. (구조 변경 가능성)")
                break

            for row in rows:
                try:
                    # 번호 영역 확인 (공지/광고 제외)
                    num_elem = row.select_one('td.gall_num')
                    if not num_elem: continue
                    
                    num_text = num_elem.text.strip()
                    if num_text.startswith('공지') or not num_text.isdigit():
                        continue # 숫자가 아니면(공지 등) 건너뜁니다.

                    num = num_elem.text.strip()
                    title_elem = row.select_one('td.gall_tit a')
                    if not title_elem: continue
                    
                    title = title_elem.text.strip()
                    reply_elem = row.select_one('span.reply_num')
                    comments = 0
                    if reply_elem:
                        # [5] 형태에서 숫자만 추출
                        comments_text = reply_elem.text.replace('[', '').replace(']', '').strip()
                        if comments_text.isdigit():
                            comments = int(comments_text)
                        # 제목에서 댓글 수 부분 제거하여 순수 제목만 추출
                        title = title.replace(reply_elem.text, "").strip()
                        
                    writer_elem = row.select_one('td.gall_writer')
                    writer = writer_elem.get('data-nick', writer_elem.text.strip()) if writer_elem else '익명'
                    
                    date_elem = row.select_one('td.gall_date')
                    date_raw = date_elem.get('title', date_elem.text.strip()) if date_elem else ''
                    date_standard = get_standard_date(date_raw)
                    
                    views_elem = row.select_one('td.gall_count')
                    views = views_elem.text.strip() if views_elem else '0'
                    if not views.isdigit(): views = '0' # '-' 등으로 표시되는 경우 대비
                    
                    recommend_elem = row.select_one('td.gall_recommend')
                    recommend = recommend_elem.text.strip() if recommend_elem else '0'
                    if not recommend.isdigit(): recommend = '0'
                    
                    posts_data.append({
                        '번호': num,
                        '제목': title,
                        '작성자': writer,
                        '작성일': date_standard,
                        '조회수': int(views),
                        '추천수': int(recommend),
                        '댓글수': comments
                    })
                except Exception as e:
                    continue 
            
            time.sleep(random.uniform(1.0, 2.0))
            
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
