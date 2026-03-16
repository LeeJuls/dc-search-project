import sqlite3
import os

class DBManager:
    """
    데이터베이스 연결 및 테이블 관리를 담당하는 클래스입니다.
    연결된 파일: dc_crawler.py (수집된 데이터를 처리함)
    """
    def __init__(self, db_name="dc_sentiment.db"):
        self.db_name = db_name
        self.init_db()

    def init_db(self):
        """
        필요한 테이블(posts, lexicon, summary)을 생성합니다.
        """
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            
            # 1. 게시글 저장 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS posts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    post_num TEXT UNIQUE, -- 디시인사이드 글 번호 (중복 방지 키)
                    title TEXT,
                    writer TEXT,
                    date_standard DATETIME,
                    views INTEGER,
                    recommend INTEGER,
                    sentiment_score REAL DEFAULT 0.0, -- 감성 분석 점수
                    analyzed_at DATETIME
                )
            ''')
            
            # 2. 감성 사전 테이블 (나중에 API가 알려줄 신조어 등 저장)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS lexicon (
                    word TEXT PRIMARY KEY,
                    score REAL,
                    updated_at DATETIME
                )
            ''')
            
            # 3. 일별 요약 통계 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_summary (
                    date DATE PRIMARY KEY,
                    avg_score REAL,
                    post_count INTEGER,
                    positive_count INTEGER,
                    negative_count INTEGER,
                    top_keywords TEXT
                )
            ''')
            conn.commit()

    def save_posts(self, df):
        """
        Pandas DataFrame에 담긴 게시글 데이터를 DB에 저장합니다.
        중복된 번호(post_num)가 있으면 건너뜁니다 (INSERT OR IGNORE).
        """
        if df.empty:
            return 0

        new_count = 0
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            for _, row in df.iterrows():
                try:
                    cursor.execute('''
                        INSERT OR IGNORE INTO posts (post_num, title, writer, date_standard, views, recommend)
                        VALUES (?, ?, ?, ?, ?, ?)
                    ''', (row['번호'], row['제목'], row['작성자'], row['작성일'], row['조회수'], row['추천수']))
                    if cursor.rowcount > 0:
                        new_count += 1
                except Exception as e:
                    print(f"DB 저장 오류: {e}")
            conn.commit()
        return new_count

    def get_latest_post_num(self):
        """
        현재 DB에 저장된 가장 최근 게시글 번호를 가져옵니다.
        """
        with sqlite3.connect(self.db_name) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(CAST(post_num AS INTEGER)) FROM posts")
            result = cursor.fetchone()
            return result[0] if result[0] else 0

if __name__ == "__main__":
    # 로컬 테스트용
    db = DBManager()
    print("데이터베이스 초기화 완료.")
