import sqlite3
import pandas as pd
from datetime import datetime
import os

class ReportGenerator:
    """
    분석된 데이터를 바탕으로 프리미엄 HTML 리포트와 마크다운 요약을 생성하는 클래스입니다.
    연결된 파일: db_manager.py, main.py
    """
    def __init__(self, db_name="dc_sentiment.db", output_dir="reports"):
        self.db_name = db_name
        self.output_dir = output_dir
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_daily_report(self):
        """
        최근 7일간의 여론 지표를 시각화한 HTML 및 MD 리포트를 생성합니다.
        """
        with sqlite3.connect(self.db_name) as conn:
            # 1. 데이터 로드
            df = pd.read_sql("""
                SELECT title, date_standard, sentiment_score, writer, views, recommend 
                FROM posts 
                WHERE date_standard >= date('now', '-7 days')
                ORDER BY date_standard DESC
            """, conn)
            
            if df.empty:
                print("리포트를 생성할 데이터가 없습니다.")
                return None

            # 2. 통계 계산
            total_count = len(df)
            avg_score = df['sentiment_score'].mean()
            pos_count = len(df[df['sentiment_score'] > 0.1])
            neg_count = len(df[df['sentiment_score'] < -0.1])
            neu_count = total_count - pos_count - neg_count
            
            # 3. HTML 리포트 생성 (Rich UI 스타일)
            now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            html_content = f"""
            <!DOCTYPE html>
            <html lang="ko">
            <head>
                <meta charset="UTF-8">
                <title>오븐스매시 여론 리포트 - {datetime.now().strftime('%Y%m%d')}</title>
                <style>
                    :root {{
                        --primary: #6366f1;
                        --positive: #22c55e;
                        --negative: #ef4444;
                        --neutral: #94a3b8;
                        --bg: #f8fafc;
                        --card: #ffffff;
                    }}
                    body {{ font-family: 'Pretendard', sans-serif; background: var(--bg); color: #1e293b; margin: 0; padding: 20px; }}
                    .container {{ max-width: 1000px; margin: 0 auto; }}
                    header {{ text-align: center; margin-bottom: 40px; }}
                    h1 {{ color: #0f172a; font-size: 2.5rem; margin-bottom: 10px; }}
                    .timestamp {{ color: #64748b; font-size: 0.9rem; }}
                    
                    .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 40px; }}
                    .stat-card {{ background: var(--card); padding: 25px; border-radius: 16px; box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1); text-align: center; }}
                    .stat-card h3 {{ font-size: 0.9rem; color: #64748b; margin: 0 0 10px 0; }}
                    .stat-card .value {{ font-size: 2rem; font-weight: 700; }}
                    .value.pos {{ color: var(--positive); }}
                    .value.neg {{ color: var(--negative); }}
                    
                    .section {{ background: var(--card); padding: 30px; border-radius: 20px; box-shadow: 0 10px 15px -3px rgb(0 0 0 / 0.1); margin-bottom: 40px; }}
                    .section-title {{ font-size: 1.5rem; font-weight: 700; margin-bottom: 25px; border-left: 5px solid var(--primary); padding-left: 15px; }}
                    
                    table {{ width: 100%; border-collapse: collapse; }}
                    th {{ text-align: left; padding: 12px; border-bottom: 2px solid #e2e8f0; color: #64748b; font-weight: 600; }}
                    td {{ padding: 15px 12px; border-bottom: 1px solid #f1f5f9; }}
                    .score-tag {{ padding: 4px 8px; border-radius: 6px; font-size: 0.8rem; font-weight: 600; }}
                    .score-pos {{ background: #dcfce7; color: #166534; }}
                    .score-neg {{ background: #fee2e2; color: #991b1b; }}
                    .score-neu {{ background: #f1f5f9; color: #475569; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <header>
                        <h1>CookieRun Ovensmash Insight</h1>
                        <p class="timestamp">분석 일시: {now_str}</p>
                    </header>
                    
                    <div class="stats-grid">
                        <div class="stat-card">
                            <h3>총 분석 데이터</h3>
                            <div class="value">{total_count}</div>
                        </div>
                        <div class="stat-card">
                            <h3>평균 여론</h3>
                            <div class="value {'pos' if avg_score > 0 else 'neg'}">{avg_score:.2f}</div>
                        </div>
                        <div class="stat-card">
                            <h3>긍정 비율</h3>
                            <div class="value pos">{pos_count/total_count*100:.1f}%</div>
                        </div>
                        <div class="stat-card">
                            <h3>부정 비율</h3>
                            <div class="value neg">{neg_count/total_count*100:.1f}%</div>
                        </div>
                    </div>
                    
                    <div class="section">
                        <div class="section-title">최신 분석 게시글 Top 20</div>
                        <table>
                            <thead>
                                <tr>
                                    <th>제목</th>
                                    <th>작성일</th>
                                    <th>작성자</th>
                                    <th>점수</th>
                                </tr>
                            </thead>
                            <tbody>
            """
            
            for _, row in df.head(20).iterrows():
                tag_class = "score-pos" if row['sentiment_score'] > 0.1 else "score-neg" if row['sentiment_score'] < -0.1 else "score-neu"
                html_content += f"""
                                <tr>
                                    <td>{row['title']}</td>
                                    <td>{row['date_standard']}</td>
                                    <td>{row['writer']}</td>
                                    <td><span class="score-tag {tag_class}">{row['sentiment_score']:.2f}</span></td>
                                </tr>
                """
            
            html_content += """
                            </tbody>
                        </table>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # 파일 저장
            file_name = f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
            file_path = os.path.join(self.output_dir, file_name)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            print(f">> 리포트 생성 완료: {file_path}")
            return file_path

if __name__ == "__main__":
    rg = ReportGenerator()
    rg.generate_daily_report()
