import sqlite3

try:
    conn = sqlite3.connect('dc_sentiment.db')
    cursor = conn.cursor()
    cursor.execute("ALTER TABLE posts ADD COLUMN comment_count INTEGER DEFAULT 0")
    conn.commit()
    print("Column 'comment_count' added successfully.")
except sqlite3.OperationalError as e:
    print(f"Error or already exists: {e}")
finally:
    conn.close()
