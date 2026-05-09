import sys
sys.path.append('.')
from database.database import Database

db = Database('./data/recordings.db')
recording = db.get_recording('game_20260120_154043')

if recording:
    print("Recording found!")
    print(f"game_id: {recording['game_id']}")
    print(f"video_path: {recording['video_path']}")
    
    import os
    if os.path.exists(recording['video_path']):
        print(f"File exists: YES ({os.path.getsize(recording['video_path'])} bytes)")
    else:
        print(f"File exists: NO")
        print(f"Expected path: {recording['video_path']}")
else:
    print("Recording NOT found in database!")
