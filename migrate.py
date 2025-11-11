"""
Run this once: python migrate.py
"""
import sqlite3

conn = sqlite3.connect('terminology_rag.db')
cursor = conn.cursor()

# Add column
try:
    cursor.execute("ALTER TABLE documents ADD COLUMN source_url TEXT")
    print("✓ Added source_url column")
except:
    print("✓ Column already exists")

# Extract sources from chunk text and save
cursor.execute("SELECT id, chunk_text FROM documents")
rows = cursor.fetchall()

for row_id, chunk_text in rows:
    source = "Unknown"
    if "SOURCE:" in chunk_text:
        for line in chunk_text.split('\n'):
            if line.startswith('SOURCE:'):
                source = line.replace('SOURCE:', '').strip()
                break
    
    cursor.execute("UPDATE documents SET source_url = ? WHERE id = ?", (source, row_id))

conn.commit()
conn.close()

print(f"✅ Migrated {len(rows)} chunks")
print("Now restart your app!")