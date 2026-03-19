from flask import Flask, render_template, request, redirect, url_for
from config import TARGET_GALLERIES
from db_manager import DBManager
import pandas as pd
from datetime import datetime, timedelta
import os

app = Flask(__name__)

def get_sentiment_data(gallery_id, days):
    """DB에서 데이터를 가져와 분석에 필요한 형태로 반환합니다."""
    db = DBManager()
    target_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d %H:%M:%S')
    
    try:
        if not db.client:
            return 'ERROR: DBManager의 client가 None입니다. (환경변수 SUPABASE_URL, SUPABASE_KEY 명칭 오타 또는 누락 의심)'
            
        response = db.client.table('posts').select('gallery_id, post_num, title, sentiment_score, views, recommend, comment_count') \
            .eq('gallery_id', gallery_id) \
            .gte('date_standard', target_date) \
            .order('date_standard', desc=True) \
            .execute()
            
        if hasattr(response, 'data') and response.data:
            df = pd.DataFrame(response.data)
        else:
            return f'ERROR: Supabase와 100% 정상 통신되었습니다!! 하지만 반환된 데이터가 0건입니다. (요청한 날짜: {target_date}, 대상: {gallery_id})'
    except Exception as e:
        return f'ERROR: Supabase 쿼리 중 예외 발생 - {str(e)}'
        
    if df.empty:
        return 'ERROR: 데이터프레임 변환 후 비어있습니다.'

        # 공감 포인트 계산 (조회수 + 추천수 + 댓글수)
        df['engagement_score'] = df['views'] + df['recommend'] + df['comment_count']

        total = len(df)
        # 긍정/부정 필터링 후 공감 포인트 높은 순으로 정렬
        pos_df = df[df['sentiment_score'] > 0.1].sort_values(by='engagement_score', ascending=False)
        neg_df = df[df['sentiment_score'] < -0.1].sort_values(by='engagement_score', ascending=False)
        
        return {
            'gallery_id': gallery_id,
            'days': days,
            'total_count': total,
            'avg_score': df['sentiment_score'].mean(),
            'pos_count': len(pos_df),
            'neg_count': len(neg_df),
            'neu_count': total - len(pos_df) - len(neg_df),
            'pos_posts': pos_df.head(10).to_dict('records'),
            'neg_posts': neg_df.head(10).to_dict('records')
        }

@app.route('/')
def index():
    # 기본값은 config.py에 정의된 첫 번째 갤러리
    default_gallery = TARGET_GALLERIES[0]['id']
    gallery_id = request.args.get('gallery', default_gallery)
    days = int(request.args.get('days', 7))
    
    # 쿼리 파라미터 유효성 검사
    is_valid = any(g['id'] == gallery_id for g in TARGET_GALLERIES)
    if not is_valid:
        gallery_id = default_gallery
        
    data = get_sentiment_data(gallery_id, days)
    
    # 디버깅 문자열인 경우 바로 화면에 에러를 띄웁니다.
    if isinstance(data, str) and data.startswith('ERROR'):
        return f"<h1>렌더 서버 에러 추적 모드</h1><h3 style='color:red;'>{data}</h3>"

    return render_template('dashboard.html', data=data, gallery_id=gallery_id, days=days, target_galleries=TARGET_GALLERIES)

if __name__ == '__main__':
    # 템플릿 폴더가 없으면 생성
    if not os.path.exists('templates'):
        os.makedirs('templates')
    app.run(port=8000, debug=True)
