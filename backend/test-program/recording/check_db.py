import sys
sys.path.append('.')
from database.database import Database

db = Database('./data/recordings.db')
recs, total = db.get_recordings(limit=10)
print(f'資料庫中總共有 {total} 筆錄影記錄\n')
for r in recs:
    print(f"{r['game_id']} - {r['start_time']}")
