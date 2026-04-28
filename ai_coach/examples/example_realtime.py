"""
Example 2: Real-time Video Stream Processing

This example demonstrates AI Coach with video stream.
Shows: continuous processing, real-time updates.
"""

import sys
import numpy as np
import cv2
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ai_coach import (
    StabilityDetector,
    AICoachManager,
    draw_coach_panel,
)


def simulate_ball_detection(frame_num):
    """Simulate ball detection (in real use, use YOLO)"""
    # Simple sine wave motion for balls
    base_x = 200 + 100 * np.sin(frame_num * 0.05)
    base_y = 150 + 50 * np.cos(frame_num * 0.03)
    
    return [
        (int(base_x), int(base_y)),
        (int(base_x + 50), int(base_y + 50)),
        (int(base_x + 100), int(base_y - 50)),
    ]


def main():
    print("Real-time AI Coach Example")
    print("-" * 40)
    print("Press 'q' to quit, 's' to save frame, 'a' to toggle advice")
    print()
    
    # Initialize
    detector = StabilityDetector()
    manager = AICoachManager(
        api_url="http://localhost:8000/api/analyze",
        confidence_threshold=0.5,
    )
    
    show_advice = True
    frame_count = 0
    
    # Create window
    cv2.namedWindow("AI Coach - Real-time", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("AI Coach - Real-time", 1200, 700)
    
    while True:
        # Create frame
        frame = np.ones((600, 1000, 3), dtype=np.uint8) * 240
        
        # Add grid
        for i in range(0, 1000, 100):
            cv2.line(frame, (i, 0), (i, 600), (200, 200, 200), 1)
        for i in range(0, 600, 100):
            cv2.line(frame, (0, i), (1000, i), (200, 200, 200), 1)
        
        # Simulate ball detection
        balls = simulate_ball_detection(frame_count)
        
        # Draw balls
        for x, y in balls:
            if 0 <= x < 1000 and 0 <= y < 600:
                cv2.circle(frame, (x, y), 10, (0, 100, 255), -1)
                cv2.circle(frame, (x, y), 10, (0, 0, 255), 2)
        
        # Detect stability
        is_stable = detector.is_stable(balls)
        
        # Add info text
        status_text = f"Frame: {frame_count} | Stable: {is_stable}"
        cv2.putText(frame, status_text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 0), 2)
        
        # For demonstration only (real use requires API server)
        advice_json = {
            "title": "AI Coach",
            "sections": {
                "Status": "Processing...",
                "Suggestion": "Observe ball position",
                "Stability": "STABLE" if is_stable else "MOVING",
            }
        }
        
        # Render panel if enabled
        if show_advice:
            frame = draw_coach_panel(frame, advice_json, alpha=0.6, position="right")
        
        # Display
        cv2.imshow("AI Coach - Real-time", frame)
        
        # Handle keyboard
        key = cv2.waitKey(30) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            cv2.imwrite(f"frame_{frame_count}.jpg", frame)
            print(f"Saved frame_{frame_count}.jpg")
        elif key == ord('a'):
            show_advice = not show_advice
            print(f"Advice: {'ON' if show_advice else 'OFF'}")
        
        frame_count += 1
    
    cv2.destroyAllWindows()
    print("Example finished!")


if __name__ == "__main__":
    main()
