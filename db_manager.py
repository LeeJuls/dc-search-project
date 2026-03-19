import os
import pandas as pd
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

class DBManager:
    """
    데이터베이스 연결 및 테이블 관리를 담당하는 클래스입니다. (Supabase 버전)
    """
    def __init__(self):
        self.client = None
        url: str = os.environ.get("SUPABASE_URL", "")
        key: str = os.environ.get("SUPABASE_KEY", "")
        if not url or not key:
            print("경고: SUPABASE_URL 또는 SUPABASE_KEY가 설정되지 않았습니다. .env 파일을 확인하세요.")
        else:
            self.client: Client = create_client(url, key)

    def init_db(self):
        """
        Supabase 클라우드에서는 SQL Editor를 통해 테이블을 생성하는 것을 권장합니다.
        로컬 SQLite와 달리 코드 레벨에서의 CREATE TABLE 자동화 로직은 제외합니다.
        """
        pass

    def save_posts(self, df, gallery_id):
        """
        Pandas 데이터프레임을 Supabase DB에 저장(UPSERT)합니다.
        """
        if df.empty:
            return 0

        # DataFrame to list of dicts
        records = df[['번호', '제목', '작성자', '작성일', '조회수', '추천수']].copy()
        records['댓글수'] = df.get('댓글수', 0)
        
        # Rename columns to match Supabase table 'posts'
        records.rename(columns={
            '번호': 'post_num',
            '제목': 'title',
            '작성자': 'writer',
            '작성일': 'date_standard',
            '조회수': 'views',
            '추천수': 'recommend',
            '댓글수': 'comment_count'
        }, inplace=True)
        
        # 추가 컬럼 세팅
        records['gallery_id'] = gallery_id
        
        # NaN 처리 (Supabase JSON 직렬화 오류 방지)
        records = records.fillna(0)
        
        data = records.to_dict(orient='records')
        
        try:
            # Supabase upsert requires unique constraints on (gallery_id, post_num)
            response = self.client.table('posts').upsert(data, on_conflict='gallery_id,post_num').execute()
            if hasattr(response, 'data') and response.data:
                return len(response.data)
            return len(data)
        except Exception as e:
            print(f"Supabase 저장 오류: {e}")
            return 0

    def get_latest_post_num(self, gallery_id='ovensmash'):
        """
        현재 DB에 저장된 가장 최근 게시글 번호를 가져옵니다.
        """
        try:
            response = self.client.table('posts').select('post_num').eq('gallery_id', gallery_id).order('post_num', desc=True).limit(1).execute()
            if response.data and len(response.data) > 0:
                return int(response.data[0]['post_num'])
        except Exception as e:
            print(f"최신 글 번호 조회 오류: {e}")
            
        return 0

if __name__ == "__main__":
    db = DBManager()
    print("Supabase 연결 테스트 완료.")
