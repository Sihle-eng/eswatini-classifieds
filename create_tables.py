import os
from dotenv import load_dotenv
import psycopg2

load_dotenv()
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    print("DATABASE_URL not found")
    exit(1)

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("""
    DROP TABLE IF EXISTS post_media CASCADE;
    DROP TABLE IF EXISTS blog_posts CASCADE;
    
    CREATE TABLE blog_posts (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) NOT NULL,
        content TEXT NOT NULL,
        author_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    
    CREATE TABLE post_media (
        id SERIAL PRIMARY KEY,
        post_id INTEGER NOT NULL REFERENCES blog_posts(id) ON DELETE CASCADE,
        file_url VARCHAR(500) NOT NULL,
        file_type VARCHAR(100) NOT NULL,
        "order" INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cursor.close()
conn.close()
print("Tables recreated with correct names and foreign key!")