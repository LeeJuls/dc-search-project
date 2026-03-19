import requests
from bs4 import BeautifulSoup

def check_structure(url):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    r = requests.get(url, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    print(f"URL: {url}")
    print(f"us-post count: {len(soup.select('tr.us-post'))}")
    print(f"ub-content count: {len(soup.select('tr.ub-content'))}")
    
    # Check first row
    rows = soup.select('tr.us-post') + soup.select('tr.ub-content')
    if rows:
        print("\n--- First Row Example ---")
        row = rows[0]
        print(f"Classes: {row.get('class')}")
        title = row.select_one('td.gall_tit a')
        print(f"Title present: {title is not None}")
        if title:
            print(f"Title text: {title.text.strip()}")
        num = row.select_one('td.gall_num')
        print(f"Number present: {num is not None}")
        if num:
            print(f"Number text: {num.text.strip()}")

check_structure('https://gall.dcinside.com/mgallery/board/lists/?id=maplerpg')
check_structure('https://gall.dcinside.com/board/lists/?id=maplestory_new')
