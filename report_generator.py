import pandas as pd
from datetime import datetime, timedelta, timezone
import os
from db_manager import DBManager

# 한국 시간대 (UTC+9)
KST = timezone(timedelta(hours=9))

class ReportGenerator:
    """
    분석된 데이터를 바탕으로 프리미엄 HTML 리포트와 마크다운 요약을 생성하는 클래스입니다.
    연결된 파일: db_manager.py, main.py
    """
    def __init__(self, output_dir="reports"):
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_daily_report(self, gallery_id='ovensmash', days=7):
        """
        특정 기간(days)의 여론 지표 리포트를 생성합니다.
        """
        db = DBManager()
        target_date = (datetime.now(KST) - timedelta(days=days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        ).strftime('%Y-%m-%d %H:%M:%S')
        
        try:
            response = db.client.table('posts').select('title, date_standard, sentiment_score, writer, views, recommend') \
                .eq('gallery_id', gallery_id) \
                .gte('date_standard', target_date) \
                .order('date_standard', desc=True).limit(5000).execute()
                
            if hasattr(response, 'data') and response.data:
                df = pd.DataFrame(response.data)
            else:
                df = pd.DataFrame()
        except Exception as e:
            print(f"리포트용 DB 로드 오류: {e}")
            return None

        if df.empty:
            print(f"[{gallery_id}] {days}일간 분석할 데이터가 없습니다.")
            return None

        # 2. 통계 계산
        total_count = len(df)
        avg_score = df['sentiment_score'].mean()
        pos_df = df[df['sentiment_score'] > 0.1].sort_values(by='sentiment_score', ascending=False)
        neg_df = df[df['sentiment_score'] < -0.1].sort_values(by='sentiment_score', ascending=True)

        pos_count = len(pos_df)
        neg_count = len(neg_df)
        neu_count = total_count - pos_count - neg_count

        # 3. HTML 리포트 생성
        now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
        html_content = f"""
        <!DOCTYPE html>
        <html lang="ko">
        <head>
            <meta charset="UTF-8">
            <title>{gallery_id} 여론 리포트 ({days}일)</title>
            <style>
                :root {{
                    --primary: #6366f1;
                    --positive: #10b981;
                    --negative: #ef4444;
                    --neutral: #64748b;
                    --bg: #f1f5f9;
                    --card: #ffffff;
                }}
                body {{ font-family: 'Pretendard', sans-serif; background: var(--bg); color: #1e293b; margin: 0; padding: 40px; }}
                .container {{ max-width: 1000px; margin: 0 auto; }}
                header {{ text-align: center; margin-bottom: 50px; }}
                h1 {{ color: #0f172a; font-size: 2.8rem; margin-bottom: 10px; }}
                .tag {{ background: var(--primary); color: white; padding: 5px 15px; border-radius: 20px; font-size: 0.9rem; font-weight: 600; }}

                .stats-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 40px; }}
                .stat-card {{ background: var(--card); padding: 30px; border-radius: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); text-align: center; }}
                .stat-card h3 {{ color: #64748b; font-size: 1rem; margin-bottom: 15px; }}
                .stat-card .value {{ font-size: 2.5rem; font-weight: 800; }}

                .ratio-section {{ background: var(--card); padding: 40px; border-radius: 24px; margin-bottom: 40px; box-shadow: 0 4px 20px rgba(0,0,0,0.05); }}
                .ratio-title {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 30px; text-align: center; }}
                .ratio-bar {{ display: flex; height: 60px; border-radius: 30px; overflow: hidden; margin-bottom: 20px; }}
                .ratio-part {{ display: flex; flex-direction: column; justify-content: center; align-items: center; color: white; font-weight: 700; font-size: 1rem; }}
                .ratio-pos {{ background: var(--positive); }}
                .ratio-neu {{ background: var(--neutral); }}
                .ratio-neg {{ background: var(--negative); }}

                .detail-section {{ margin-bottom: 50px; }}
                .detail-title {{ font-size: 1.8rem; font-weight: 800; margin-bottom: 25px; padding-bottom: 10px; border-bottom: 4px solid; }}
                .pos-title {{ color: var(--positive); border-color: var(--positive); }}
                .neg-title {{ color: var(--negative); border-color: var(--negative); }}

                .post-card {{ background: var(--card); padding: 20px; border-radius: 16px; margin-bottom: 15px; display: flex; justify-content: space-between; align-items: center; transition: transform 0.2s; }}
                .post-card:hover {{ transform: scale(1.02); }}
                .post-info {{ font-size: 1.1rem; font-weight: 600; color: #334155; }}
                .post-score {{ padding: 6px 12px; border-radius: 10px; font-weight: 700; }}
                .score-pos {{ background: #dcfce7; color: #065f46; }}
                .score-neg {{ background: #fee2e2; color: #991b1b; }}

                .nav-links {{ text-align: center; margin-top: 40px; }}
                .nav-links a {{ color: var(--primary); text-decoration: none; font-weight: 600; margin: 0 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <header>
                    <span class="tag">{gallery_id} 갤러리</span>
                    <h1>Trend Analysis Report</h1>
                    <p>분석 기간: 최근 {days}일 | 분석 일시: {now_str}</p>
                </header>

                <div class="stats-grid">
                    <div class="stat-card">
                        <h3>총 수집 게시글</h3>
                        <div class="value">{total_count}</div>
                    </div>
                    <div class="stat-card">
                        <h3>종합 여론 점수</h3>
                        <div class="value" style="color: {'var(--positive)' if avg_score > 0 else 'var(--negative)'}">{avg_score:.2f}</div>
                    </div>
                </div>

                <div class="ratio-section">
                    <div class="ratio-title">여론 분포도</div>
                    <div class="ratio-bar">
                        <div class="ratio-part ratio-pos" style="width: {pos_count/total_count*100}%">긍정 {pos_count/total_count*100:.1f}%</div>
                        <div class="ratio-part ratio-neu" style="width: {neu_count/total_count*100}%">중립 {neu_count/total_count*100:.1f}%</div>
                        <div class="ratio-part ratio-neg" style="width: {neg_count/total_count*100}%">부정 {neg_count/total_count*100:.1f}%</div>
                    </div>
                </div>

                <div class="detail-section">
                    <div class="detail-title pos-title">👍 긍정 여론 주요 키워드/글 Top 10</div>
        """

        for _, row in pos_df.head(10).iterrows():
            html_content += f"""
                    <div class="post-card">
                        <div class="post-info">{row['title']}</div>
                        <div class="post-score score-pos">+{row['sentiment_score']:.2f}</div>
                    </div>
            """

        html_content += """
                </div>

                <div class="detail-section">
                    <div class="detail-title neg-title">👎 부정 여론 주요 키워드/글 Top 10</div>
        """

        for _, row in neg_df.head(10).iterrows():
            html_content += f"""
                    <div class="post-card">
                        <div class="post-info">{row['title']}</div>
                        <div class="post-score score-neg">{row['sentiment_score']:.2f}</div>
                    </div>
            """

        html_content += """
                </div>

                <div class="nav-links">
                    <a href="#">상단으로 이동</a>
                </div>
            </div>
        </body>
        </html>
        """

        # 파일명에 갤러리ID와 기간 포함
        file_name = f"report_{gallery_id}_{days}d_{datetime.now(KST).strftime('%Y%m%d_%H%M%S')}.html"
        file_path = os.path.join(self.output_dir, file_name)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        return file_path

if __name__ == "__main__":
    rg = ReportGenerator()
    rg.generate_daily_report()
