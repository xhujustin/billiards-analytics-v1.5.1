import sys
sys.path.append('.')
from database.database import Database
import os

db = Database('./data/recordings.db')
recording = db.get_recording('game_20260119_225848')

if recording:
    print("錄影記錄找到！")
    print(f"game_id: {recording['game_id']}")
    print(f"video_path: {recording['video_path']}")
    
    if os.path.exists(recording['video_path']):
        size = os.path.getsize(recording['video_path'])
        print(f"影片檔案: 存在 ({size} bytes = {size/1024/1024:.2f} MB)")
    else:
        print(f"影片檔案: 不存在！")
        print(f"預期路徑: {recording['video_path']}")
else:
    print("資料庫中找不到錄影記錄！")
