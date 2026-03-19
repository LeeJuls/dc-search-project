from db_manager import DBManager
from sentiment_analyzer import SentimentAnalyzer

db = DBManager()
analyzer = SentimentAnalyzer(db)

# 모든 게시글 재분석 강제 실행
count = analyzer.process_all_unbound_posts(force=True)
print(f"재분석 완료: {count}개의 게시글 스코어 업데이트됨")
