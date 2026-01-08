from ultralytics import YOLO
import cv2
import numpy as np
import cvzone
import math

import time
import os

global inHole
global color

# function to select the green area that used for region of YOLOv8

def areaSelected(imgArea):
    bbox = []
    rect = []
    lower = np.array([60, 70, 50])
    upper = np.array([86, 255, 255])
    hsv_img = cv2.cvtColor(imgArea, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv_img, lower, upper)
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
    contours, hierarchy = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

    for contour in contours:
        area = cv2.contourArea(contour)
        if area > 500000:
            x, y, w, h = cv2.boundingRect(contour)
            rect.append([x, y, w, h])
            # imgArea = cv2.rectangle(imgArea, (x + 30, y + 30), (x + w - 30, y + h - 30), (0, 255, 0), 4)
            imgArea = cv2.rectangle(imgArea, (x + 30, y + 30), (x + w - 30, y + h - 30), (0, 255, 0), 4)
            holesA = [
                [x + 52, y + 52],
                [x + 52, y + h - 52],
                [x + w - 52, y + 52],
                [x + w - 52, y + h - 52],
                [x + (w - 12) // 2, y + 40],
                [x + (w - 12) // 2, y + h - 40]
            ]

            #  create the points of the holes or pockets
            for hole in holesA:
                center = hole
                radius = 50
                x = int(center[0] - radius)
                y = int(center[1] - radius)
                w = h = int(radius * 2)
                bbox.append([x, y, x + w, y + h])
                # cv2.circle(imgArea, hole, 50, (255, 0, 0), 2)

    return imgArea, bbox, rect

# function to show the results of machine learning (YOLOv8)
# def machinelearning(predict, imgDetect):
#     max_cue = 0
#     max_white = 0
#     max_color = 0
#     whiteBall = []
#     colorBall = []
#     cuePos = []

#     for r in predict:
#         boxes = r.boxes
#         for box in boxes:
#             x1, y1, x2, y2 = box.xyxy[0]
#             x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
#             w, h = (x2 - x1), (y2 - y1)

#             conf = math.ceil(box.conf[0] * 100) / 100
#             for c in box.cls:
#                 namescls = model.names[int(c)]

#                 if namescls == "white-ball" and conf > max_white and not whiteBall:
#                     max_white = conf
#                     center_x, center_y = x1 + w // 2, y1 + h // 2
#                     whiteBall = [x1, y1, w, h]
#                     radius = min(w, h) // 2
#                     cv2.circle(imgDetect, (center_x, center_y), radius + 10, (80, 145, 75), thickness=8)
#                     cvzone.putTextRect(imgDetect, f'{namescls.upper()}', (max(0, x1 + w + 20), max(50, y1 + 20)),
#                                        scale=1.2, thickness=2, colorR=(0, 255, 0), offset=10)

#                 elif namescls == "color-ball" and conf > max_color and not colorBall:
#                     max_color = conf
#                     center_x, center_y = x1 + w // 2, y1 + h // 2
#                     radius = min(w, h) // 2
#                     colorBall = [x1, y1, w, h, radius]
#                     cv2.circle(imgDetect, (center_x, center_y), radius + 10, (80, 145, 75), thickness=8)
#                     cvzone.putTextRect(imgDetect, f'{namescls.upper()}', (max(0, x1 + w + 20), max(50, y1 + 20)),
#                                        scale=1.2, thickness=2, colorR=(0, 255, 0), offset=10)

#                 elif namescls == "cue" and conf > max_cue and not cuePos:
#                     max_cue = conf
#                     center_x, center_y = x1 + w // 2, y1 + h // 2
#                     if y1 > 540:
#                         cuePos = [x1 + 8, y1, w, h]
#                     elif y1 < 600:
#                         cuePos = [x1 + 8, y1, w, h]
#                     cvzone.putTextRect(imgDetect, f'{namescls.upper()}', (max(0, center_x), max(50, center_y)),
#                                        scale=1.2, thickness=2, colorR=(0, 255, 0), offset=10)

#     return imgDetect, whiteBall, colorBall, cuePos

def machinelearning(predict, imgDetect):
    """
    回傳：
      imgDetect,
      whitePrimary  : [x,y,w,h] 或 []
      colorPrimary  : [x,y,w,h,r] 或 []
      cuePos        : [x,y,w,h] 或 []
      whiteBalls    : [[x,y,w,h,conf], ...]  ← 全部白球
      colorBalls    : [[x,y,w,h,r,conf], ...]← 全部彩球
      
    """
    whiteBalls = []
    colorBalls = []
    cuePos = []
    whitePrimary = []
    colorPrimary = []

    # 暫存
    cue_center = None

    # 走訪 YOLO 結果，收集「全部」球
    for r in predict:
        boxes = r.boxes
        for box in boxes:
            x1, y1, x2, y2 = box.xyxy[0]
            x1, y1, x2, y2 = int(x1), int(y1), int(x2), int(y2)
            w, h = (x2 - x1), (y2 - y1)
            conf = float(box.conf[0])

            for c in box.cls:
                namescls = model.names[int(c)]

                if namescls == "white-ball":
                    whiteBalls.append([x1, y1, w, h, conf])

                elif namescls == "color-ball":
                    radius = max(1, min(w, h) // 2)
                    colorBalls.append([x1, y1, w, h, radius, conf])

                elif namescls == "cue" and not cuePos:
                    # 只留一支球桿（你原本邏輯如此）
                    cuePos = [x1, y1, w, h]
                    cx, cy = x1 + w // 2, y1 + h // 2
                    cue_center = (cx, cy)

    # === 視覺化：把畫面上所有球都標註出來 ===
    # 白球
    for (x, y, w, h, conf) in whiteBalls:
        cx, cy = x + w // 2, y + h // 2
        r = max(1, min(w, h) // 2)
        cv2.circle(imgDetect, (cx, cy), r + 10, (80, 145, 75), thickness=4)
        cvzone.putTextRect(
            imgDetect, f'WHITE {conf:.2f}',
            (max(0, x + w + 8), max(24, y + 18)),
            scale=0.8, thickness=1, colorR=(255, 255, 255), offset=6
        )

    # 彩球
    for (x, y, w, h, r, conf) in colorBalls:
        info = classify_ball_number(roi_img, [x, y, w, h])
        num  = info.get("number", None)
        label= info.get("label", "Unknown")
        style= info.get("style", "Unknown")

        # 顯示「#號 + 色名 + 實/條」
        cx, cy = x + w // 2, y + h // 2
        r = max(1, min(w, h) // 2)
        cv2.circle(imgDetect, (cx, cy), r + 10, (80, 145, 75), thickness=4)
        tag = f"{num if num is not None else '?'} | {label} | {style}"
        cv2.putText(roi_img, tag, (x, max(0, y-8)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (255,255,255) if label != "White" else (0,0,0),
                2, cv2.LINE_AA)

    # 球桿
    if cuePos:
        cx, cy = cuePos[0] + cuePos[2] // 2, cuePos[1] + cuePos[3] // 2
        cvzone.putTextRect(
            imgDetect, 'CUE',
            (max(0, cx), max(24, cy)),
            scale=0.9, thickness=2, colorR=(0, 255, 0), offset=8
        )

    # === 挑主球：用於你原本的預測流程（相容舊索引）===
    # 主白球：取 conf 最高（若無白球則空）
    if whiteBalls:
        whiteBalls.sort(key=lambda t: t[4], reverse=True)
        x, y, w, h, _ = whiteBalls[0]
        whitePrimary = [x, y, w, h]

    # 主彩球：
    #   1) 若有球桿，選「距離球桿最近」的彩球
    #   2) 否則取 conf 最高
    if colorBalls:
        if cue_center is not None:
            def d2(ball):
                bx, by, bw, bh, r, conf = ball
                cx, cy = bx + bw // 2, by + bh // 2
                return (cx - cue_center[0])**2 + (cy - cue_center[1])**2
            colorBalls.sort(key=d2)
        else:
            colorBalls.sort(key=lambda t: t[5], reverse=True)

        x, y, w, h, r, _ = colorBalls[0]
        colorPrimary = [x, y, w, h, r]

    # 回傳：前 3 個與你原本一樣（主白、主彩、球桿），後面多了「全部清單」
    return imgDetect, whitePrimary, colorPrimary, cuePos, whiteBalls, colorBalls

# function to calculate the angle
def findAngle(deg):
    theta = math.radians(deg)
    sinus = math.sin(theta)
    cosinus = math.cos(theta)

    if abs(sinus) < 1e-15:
        cosinus = 0
    if abs(cosinus) < 1e-15:
        sinus = 0

    return sinus, cosinus

# function to show the predicted results
def showResult(paths, colorR, predictionR):
    for i, path in enumerate(paths):
        if i == 0:
            pass
        else:
            drawLine(areaSelected[0], (paths[i - 1][0], paths[i - 1][1]), (path[0], path[1]), colorR)
            cv2.circle(areaSelected[0], (path[0], path[1]), 24, colorR, cv2.FILLED)

    if predictionR:
        cvzone.putTextRect(areaSelected[0], "PREDICTION: IN", (300, 80), scale=3, thickness=4, colorR=(0, 255, 0),
                           offset=14)
    else:
        cvzone.putTextRect(areaSelected[0], "PREDICTION: OUT", (300, 80), scale=3, thickness=4, colorR=(200, 97, 64),
                           offset=14)

# function to calculate the point that cue shot the white ball
def findShotPoints(cuePos, whiteBall, radiusMeanR, shotPointsR):
    cuePoints = []
    shotPointR = []
    whiteBallX = whiteBall[0] + whiteBall[2] // 2
    whiteBallY = whiteBall[1] + whiteBall[3] // 2

    radiusMeanR.append((cuePos[2] // 2 + cuePos[3] // 2) // 2)
    radius = 0
    for i in radiusMeanR:
        radius += 1
    radius = radius // (len(radiusMeanR))

    LX = cuePos[0] + cuePos[2] // 2
    LY = cuePos[1] + cuePos[3] // 2
    for the in range(0, 360):
        sinus, cosinus = findAngle(the)
        DX = int(cosinus * radius)
        DY = int(sinus * radius)
        cuePoints.append([LX + DX, LY + DY])

    minGap = 1000000
    for cuePoint in cuePoints:
        gap = math.sqrt(math.pow(whiteBallX - cuePoint[0], 2) + math.pow(whiteBallY - cuePoint[1], 2))
        if gap < minGap:
            minGap = gap
            shotPointR = cuePoint

    shotPointsR.append(shotPointR)
    sumX = 0
    sumY = 0
    for point in shotPointsR:
        sumX += point[0]
        sumY += point[1]
    shotPointR = [sumX // len(shotPointsR), sumY // len(shotPointsR)]

    return shotPointR

# function to draw line of the ball
def drawLine(imgL, pt1, pt2, colorL):
    length = ((pt1[0] - pt2[0]) ** 2 + (pt1[1] - pt2[1]) ** 2) ** .5
    points = []
    for i in np.arange(0, length, 15):
        r = i / length
        x = int((pt1[0] * (1 - r) + pt2[0] * r) + .5)
        y = int((pt1[1] * (1 - r) + pt2[1] * r) + .5)
        p = (x, y)
        points.append(p)
    for p in points:
        for i in points:
            cv2.line(imgL, p, i, colorL, 5)

# function to calculate the line between two points
def findLine(point1, point2):
    x1, y1 = point1[0], point1[1]
    x2, y2 = point2[0], point2[1]
    try:
        m = (y2 - y1) / (x2 - x1)
    except ZeroDivisionError:
        m = (y2 - y1) / (x2 - x1 + 1)
    c = y1 - (m * x1)
    return m, c

# function to detect the collision between white ball and color ball
def collision(whiteBall, colorBall):
    whiteBallList = []
    colorBallList = []

    radius = (whiteBall[2] - whiteBall[0]) // 2
    LX = whiteBall[0] + (whiteBall[2] - whiteBall[0]) // 2
    LY = whiteBall[1] + (whiteBall[3] - whiteBall[1]) // 2
    for the in range(0, 360):
        sinus, cosinus = findAngle(the)
        DX = int(cosinus * radius)
        DY = int(sinus * radius)
        whiteBallList.append([LX + DX, LY + DY])

    radius = colorBall[4]
    LX = colorBall[0] + (colorBall[2] - colorBall[0]) // 2
    LY = colorBall[1] + (colorBall[3] - colorBall[1]) // 2
    for the in range(0, 360):
        sinus, cosinus = findAngle(the)
        DX = int(cosinus * radius)
        DY = int(sinus * radius)
        colorBallList.append([LX + DX, LY + DY])

    collsPoints = []
    for point in whiteBallList:
        if point in colorBallList:
            collsPoints.append(point)

    if len(collsPoints) > 0:
        xPoint = 0
        yPoint = 0
        for point in collsPoints:
            xPoint += point[0]
            yPoint += point[1]
        collsPoint = [xPoint // len(collsPoints), yPoint // len(collsPoints)]
        cv2.circle(areaSelected[0], (collsPoint[0], collsPoint[1]), 16, (80, 145, 75), cv2.FILLED)
        return True, collsPoint
    return False, []

# function to calculate the ball that will go holes or not
def bounceDetection(point, radius, holesD):
    colorD = (80, 145, 75)
    inHoleD = False
    for hole in holesD:
        p = point[0] - radius
        q = point[1] - radius
        r = point[0] + radius
        s = point[1] + radius
        if p >= hole[0] and q >= hole[1] and r <= hole[2] and s <= hole[3]:
            inHoleD = True
            colorD = (80, 145, 75)

    return colorD, inHoleD

# function to predict the direction of color ball
def pathLine(collsPoint, colorBall, paths, holesL):
    global color, inHole
    colorBallCenter = [colorBall[0] + colorBall[2] // 2, colorBall[1] + colorBall[3] // 2]
    m2, c2 = findLine(collsPoint, [colorBallCenter[0], colorBallCenter[1]])

    rectangle = areaSelected(imgArea=img)
    for rects in rectangle[2]:
        print(rects)
        if collsPoint[0] > colorBall[0] + colorBall[2] // 2:
            xLast = rects[0] + 40
        else:
            xLast = rects[2] + 130

        for i in range(0, 2):
            x2 = xLast
            y2 = int((m2 * x2) + c2)

            if y2 >= rects[3] + 60:
                y2 = rects[3] + 60
                x2 = int((y2 - c2) / m2)
            if y2 <= rects[1] + 50:
                y2 = rects[1] + 50
                x2 = int((y2 - c2) / m2)
            if rects[0] + 100 < y2 < rects[3] + 10 and x2 >= rects[2] + 130:
                x2 = rects[2] + 130
                y2 = int((m2 * x2) + c2)
                xLast = rects[0] + 40
            if rects[0] + 100 < y2 < rects[3] + 10 and x2 <= rects[0] + 40:
                x2 = rects[0] + 40
                y2 = int((m2 * x2) + c2)
                xLast = rects[2] + 130

            paths.append([x2, y2])
            color, inHole = bounceDetection(paths[-1], 6, holesL)

            if inHole:
                return paths, color, inHole
            else:
                m2 = -m2
                c2 = y2 - (m2 * x2)

    return paths, color, inHole

# function to controll all calcaulations for prediction

# def poolShotPrediction(shotPointS, whiteBall, colorBall, holesS):
#     try:
#         m1, c1 = findLine([shotPointS[0], shotPointS[1]],
#                           [whiteBall[0] + whiteBall[2] // 2, whiteBall[1] + whiteBall[3] // 2])
#         points = []
#         xLast = (colorBall[0] + colorBall[2] // 2)
#         x1, y1 = xLast, int((m1 * xLast) + c1)
#         if xLast >= whiteBall[0] + whiteBall[2] // 2:
#             section = 1
#         else:
#             section = -1

#         for x in range(whiteBall[0] + whiteBall[2] // 2, xLast, section):
#             y = int((m1 * x) + c1)
#             points.append([x, y])

#         for point in points:
#             p = point[0] - whiteBall[2] // 2
#             q = point[1] - whiteBall[3] // 2
#             r = point[0] + whiteBall[2] // 2
#             s = point[1] + whiteBall[3] // 2
#             box = [p, q, r, s]
#             colorBallPoint = [
#                 colorBall[0],
#                 colorBall[1],
#                 colorBall[0] + colorBall[2],
#                 colorBall[1] + colorBall[3],
#                 colorBall[4]
#             ]
#             colls, collsPoint = collision(box, colorBallPoint)

#             if colls:
#                 x1, y1 = collsPoint[0], collsPoint[1]
#                 paths = [[colorBall[0] + colorBall[2] // 2, colorBall[1] + colorBall[3] // 2]]
#                 paths, colorS, inHoleS = pathLine(collsPoint, colorBall, paths, holesS)
#                 showResult(paths, colorS, inHoleS)

#                 xn = whiteBall[0] + whiteBall[2] // 2
#                 yn = whiteBall[1] + whiteBall[3] // 2
#                 drawLine(areaSelected[0], (xn, yn), (x1, y1), (80, 145, 75))
#                 cv2.circle(areaSelected[0], (x1, y1), 10, (80, 145, 75), cv2.FILLED)

#                 return {"prediction": inHoleS, "paths": paths, "color": colorS}

#     except TypeError:
#         pass

def poolShotPrediction(shotPointS, whiteBall, colorBall, holesS):
    try:
        # 1) 白球擊球線方程
        m1, c1 = findLine(
            [shotPointS[0], shotPointS[1]],
            [whiteBall[0] + whiteBall[2] // 2, whiteBall[1] + whiteBall[3] // 2]
        )

        points = []
        xLast = (colorBall[0] + colorBall[2] // 2)
        x1, y1 = xLast, int((m1 * xLast) + c1)

        # 往哪個 x 方向掃描（正向/反向）
        section = 1 if xLast >= whiteBall[0] + whiteBall[2] // 2 else -1

        for x in range(whiteBall[0] + whiteBall[2] // 2, xLast, section):
            y = int((m1 * x) + c1)
            points.append([x, y])

        # 2) 沿路徑用白球外接框與彩球框做碰撞檢測
        for point in points:
            p = point[0] - whiteBall[2] // 2
            q = point[1] - whiteBall[3] // 2
            r = point[0] + whiteBall[2] // 2
            s = point[1] + whiteBall[3] // 2
            box = [p, q, r, s]

            # colorBallPoint: [x1, y1, x2, y2, ...]
            colorBallPoint = [
                colorBall[0],
                colorBall[1],
                colorBall[0] + colorBall[2],
                colorBall[1] + colorBall[3],
                colorBall[4] if len(colorBall) > 4 else 0   # 避免 index error
            ]

            colls, collsPoint = collision(box, colorBallPoint)

            if colls:
                # 碰撞點（白球打到彩球的接觸點）
                x1, y1 = collsPoint[0], collsPoint[1]

                # 3) 設定路徑起點為彩球中心，並延伸預測
                paths = [[colorBall[0] + colorBall[2] // 2, colorBall[1] + colorBall[3] // 2]]
                paths, colorS, inHoleS = pathLine(collsPoint, colorBall, paths, holesS)

                # 4) 畫出白球擊球線與碰撞點
                xn = whiteBall[0] + whiteBall[2] // 2
                yn = whiteBall[1] + whiteBall[3] // 2
                drawLine(areaSelected[0], (xn, yn), (x1, y1), (80, 145, 75))
                cv2.circle(areaSelected[0], (x1, y1), 10, (80, 145, 75), cv2.FILLED)

                # -----------------------------
                # HSV: 彩球顏色辨識（在 ROI 內對 colorBall 的 bbox 取樣）
                # -----------------------------
                try:
                    bx, by, bw, bh = int(colorBall[0]), int(colorBall[1]), int(colorBall[2]), int(colorBall[3])
                    hsv_info = detect_ball_color_hsv(areaSelected[0], [bx, by, bw, bh])
                    ball_color_label = f"{hsv_info['label']} - {hsv_info['style']}"

                    # 疊上顏色標籤與框線，方便目視確認
                    bgr = color_to_bgr(hsv_info['label'])
                    cv2.rectangle(areaSelected[0], (bx, by), (bx + bw, by + bh), bgr, 2)
                    cv2.putText(
                        areaSelected[0], ball_color_label,
                        (bx, max(0, by - 8)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                        bgr if hsv_info['label'] != "White" else (0, 0, 0),
                        2, cv2.LINE_AA
                    )
                except Exception:
                    hsv_info = {"label": "Unknown", "style": "Unknown"}

                # 5) 即時顯示（維持你原本的行為）
                showResult(paths, colorS, inHoleS)

                # 6) 回傳：保留你原本鍵值，另加上 HSV 顏色資訊
                return {
                    "prediction": inHoleS,     # 入袋預測
                    "paths": paths,            # 彩球路徑點
                    "color": colorS,           # 你原本的 colorS（通常是畫線顏色/樣式）
                    "ball_color": f"{hsv_info.get('label', 'Unknown')} - {hsv_info.get('style','Unknown')}",  # HSV 辨色標籤
                    "ball_color_meta": hsv_info  # hue、white_ratio、black_ratio 等細節
                }

    except TypeError:
        # 某些幀資料不足時直接忽略
        pass

def _safe_crop(img, x, y, w, h):
    H, W = img.shape[:2]
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(W, x + w), min(H, y + h)
    if x1 <= x0 or y1 <= y0:
        return None, (0,0,0,0)
    return img[y0:y1, x0:x1], (x0, y0, x1 - x0, y1 - y0)

def detect_ball_color_hsv(roi_img, bbox):
    """
    以 HSV 色彩空間辨識球色與條紋/實心。
    bbox: [x, y, w, h] (在 roi_img 座標系)
    回傳: {'label', 'style', 'hue', 'white_ratio', 'black_ratio'}
    """
    x, y, w, h = map(int, bbox)
    patch, (x0, y0, w2, h2) = _safe_crop(roi_img, x, y, w, h)
    if patch is None or patch.size == 0:
        return {"label": "Unknown", "style": "Unknown", "hue": None, "white_ratio": 0.0, "black_ratio": 0.0}

    # 建立圓形遮罩（聚焦球面中心，減少背景干擾）
    mask = np.zeros(patch.shape[:2], dtype=np.uint8)
    r = int(0.48 * min(w2, h2))
    cx, cy = w2 // 2, h2 // 2
    cv2.circle(mask, (cx, cy), r, 255, -1)

    # ★ 轉 HSV（OpenCV：H:0-180, S:0-255, V:0-255）
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    Hc, Sc, Vc = cv2.split(hsv)

    # 有效像素：排除太暗(陰影)與過曝(高光)區，降低誤判
    valid = (mask == 255) & (Vc > 30) & (Vc < 250)

    # 白/黑粗篩（用於 Stripe 判斷與白球/黑球）
    white_mask = valid & (Sc < 40) & (Vc > 180)   # 飽和低 + 亮度高
    black_mask = valid & (Vc < 50)               # 亮度極低
    color_core = valid & ~white_mask & ~black_mask

    n_valid = np.count_nonzero(valid)
    if n_valid < 50:
        return {"label": "Unknown", "style": "Unknown", "hue": None, "white_ratio": 0.0, "black_ratio": 0.0}

    white_ratio = np.count_nonzero(white_mask) / n_valid
    black_ratio = np.count_nonzero(black_mask) / n_valid
    color_ratio = np.count_nonzero(color_core) / n_valid

    # 白球（幾乎都是白，且有效色很少）
    if white_ratio > 0.70 and color_ratio < 0.10:
        return {"label": "White", "style": "Cue", "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

    # 全黑（可能是 8 號球或光線不足）
    if black_ratio > 0.60:
        return {"label": "Black", "style": "Solid", "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

    if np.count_nonzero(color_core) < 30:
        label = "White" if white_ratio > 0.4 else ("Black" if black_ratio > 0.4 else "Unknown")
        style = "Cue" if label == "White" else ("Solid" if label == "Black" else "Unknown")
        return {"label": label, "style": style, "hue": None, "white_ratio": float(white_ratio), "black_ratio": float(black_ratio)}

    # ★ 以 S*V 權重求 hue 加權平均，降低暗區/低飽和雜訊
    Hf = Hc[color_core].astype(np.float32)
    Sf = Sc[color_core].astype(np.float32) / 255.0
    Vf = Vc[color_core].astype(np.float32) / 255.0
    wgt = (Sf * Vf) + 1e-6
    hue_mean = float(np.sum(Hf * wgt) / np.sum(wgt))  # 0~180

    # Hue → 顏色名稱（可依場地光調整分界）
    def hue_to_name(h):
        if h < 0 or h > 180:
            return "Unknown"
        # 紅色跨兩端 (0~10) ∪ (160~180)
        if (h <= 10) or (h >= 160):  return "Red"
        if 10 < h <= 25:             # 橘/棕：亮度低偏棕、亮度高偏橘
            return "Brown" if np.median(Vc[color_core]) < 140 else "Orange"
        if 25 < h <= 40:             return "Yellow"
        if 40 < h <= 80:             return "Green"
        if 80 < h <= 130:            return "Blue"     # 含青藍
        if 130 < h <= 155:           return "Purple"
        if 155 < h < 160:            return "Red"
        return "Unknown"

    color_name = hue_to_name(hue_mean)

    # Stripe vs Solid：白面積較大且仍有顏色 → 條紋
    style = "Stripe" if (white_ratio > 0.35 and color_ratio > 0.15 and color_name not in ["White", "Black", "Unknown"]) \
                     else "Solid"

    return {
        "label": color_name,          # 主色名（HSV 決定）
        "style": style,               # 'Solid' / 'Stripe' / 'Cue'
        "hue": hue_mean,              # 供除錯
        "white_ratio": float(white_ratio),
        "black_ratio": float(black_ratio),
    }
_COLOR_TO_NUM = {
    "Yellow":  (1,  9),
    "Blue":    (2, 10),
    "Red":     (3, 11),
    "Purple":  (4, 12),
    "Orange":  (5, 13),
    "Green":   (6, 14),
    "Brown":   (7, 15),   # 常見把 7 視為棕/酒紅
}

def classify_ball_number(roi_img, bbox):
    """
    依 HSV 主色 + Stripe/Solid 判斷「幾號球」。
    參數:
        roi_img: 當前 ROI 影像 (BGR)
        bbox   : [x, y, w, h]
    回傳:
        {
          'number': int 或 None,
          'label':  'Yellow/Blue/Red/Purple/Orange/Green/Brown/Black/White/Unknown',
          'style':  'Solid/Stripe/Cue' 或 'Unknown',
          'white_ratio': float,
          'black_ratio': float,
          'hue': float or None
        }
    """
    info = detect_ball_color_hsv(roi_img, bbox)
    label = info.get('label', 'Unknown')
    style = info.get('style', 'Unknown')

    # 先處理白球 / 黑球
    if label == "White" or style == "Cue":
        info["number"] = 0   # 你也可以改成 None 或 'Cue'
        return info
    if label == "Black":
        # 亮度很低的黑色 → 8 號
        info["number"] = 8
        return info

    # 依顏色表對應 1~7 或 9~15
    if label in _COLOR_TO_NUM:
        solid, stripe = _COLOR_TO_NUM[label]
        if style == "Stripe":
            info["number"] = stripe
        elif style == "Solid":
            info["number"] = solid
        else:
            # 無法確定條紋/實心 → 用白面積比做猜測
            if info.get("white_ratio", 0) > 0.30:
                info["number"] = stripe
            else:
                info["number"] = solid
        return info

    # 其他/未知
    info["number"] = None
    return info

def color_to_bgr(name):
    table = {
        "Yellow": (0, 220, 255),
        "Blue":   (255, 120, 0),
        "Red":    (0, 0, 230),
        "Purple": (180, 0, 180),
        "Orange": (0, 140, 255),
        "Green":  (0, 180, 0),
        "Brown":  (30, 60, 120),
        "Black":  (0, 0, 0),
        "White":  (255, 255, 255),
        "Unknown":(160, 160, 160),
    }
    return table.get(name, (160, 160, 160))

areaSelected_fn = areaSelected
# -----------------------------
#  1. 基本初始化設定
# -----------------------------
shotPoints = []      # 用來儲存擊球點（擊球起始位置）
radiusMean = []      # 用來儲存球的平均半徑，用於幾何運算
lastPoint = []       # 儲存上一幾幀的球中心位置，用於判斷球是否在移動
prediction = True    # 當前是否在進行預測（True：預測中；False：顯示結果）
possibility = []     # 儲存多幀推論結果，用於後續投票
holes = []           # 儲存球桌洞口位置（由 areaSelected() 傳回）

# -----------------------------
#  2. 輸入與輸出設定
# -----------------------------
VIDEO_IN = r"C:\Users\xhuju\Desktop\BallPool\Video\20251110.mp4" 
# 輸入影片
VIDEO_OUT = r"C:\Users\xhuju\Desktop\BallPool\Video\results.mp4"     # 輸出影片
WEIGHT = r"C:\Users\xhuju\Desktop\BallPool\yolo-weight\pool-n.pt"    # YOLO 權重檔路徑



cap = cv2.VideoCapture(VIDEO_IN)    # 開啟影片
if not cap.isOpened():
    raise RuntimeError(f"無法開啟影片: {VIDEO_IN}")

# 先讀取第一幀來取得 ROI 尺寸（避免影片輸出尺寸不符）
ok, first_frame = cap.read()
if not ok or first_frame is None:
    cap.release()
    raise RuntimeError("Cannot read the first frame from the video.")

sa0 = areaSelected_fn(first_frame)         # ← 用備份的函式名呼叫
if not isinstance(sa0, (list, tuple)) or len(sa0) < 2:
    cap.release()
    raise RuntimeError("areaSelected returned invalid structure on first frame")

roi0, holes0 = sa0[0], sa0[1]

# ★ 這一行是關鍵：把全域變數 areaSelected 指向「目前幀的 (roi, holes)」
areaSelected = (roi0, holes0)
if roi0 is None or getattr(roi0, 'size', 0) == 0:
    cap.release()
    raise RuntimeError("areaSelected 回傳的 ROI 影像為空")

# 取得 ROI 尺寸，用於建立輸出影片
H0, W0 = roi0.shape[:2]
fourcc = cv2.VideoWriter_fourcc(*'mp4v')
result = cv2.VideoWriter(VIDEO_OUT, fourcc, 20, (W0, H0))  # 輸出影片以 ROI 尺寸為準

# 載入 YOLO 模型
model = YOLO(WEIGHT)

# 重設影片位置到開頭（因為上面先讀了一幀）
cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

# -----------------------------
#  3. FPS 計算（指示效能）
# -----------------------------
fps = 0.0
alpha = 0.2         # 平滑係數（越小越穩定）
prev_t = time.time() # 前一幀的時間戳記

# -----------------------------
#  4. 主迴圈：逐幀處理影片
# -----------------------------
while True:
    success, img = cap.read()
    if not success or img is None:
        # 若影片播放完或讀取錯誤，結束程式
        break

    # 計算 FPS（採用滑動平均方式）
    now = time.time()
    inst_fps = 1.0 / max(now - prev_t, 1e-6)
    fps = inst_fps if fps == 0 else (alpha * inst_fps + (1 - alpha) * fps)
    prev_t = now

    # === 初始化變數 ===
    color_info = {'label': 'Unknown', 'style': 'Unknown'}
    ball_color_label = 'Unknown'
    bx = by = bw = bh = 0
    
    # 🟡 呼叫 areaSelected() 擷取撞球桌 ROI 與洞口
    sa = areaSelected_fn(img)
    if not isinstance(sa, (list, tuple)) or len(sa) < 2:
        # 若回傳不正確，跳過此幀
        continue
    area = (sa[0], sa[1])  # 封裝成 tuple，與原本程式一致
    roi_img = area[0]       # ROI 影像
    holes = area[1]         # 洞口座標列表

    # -----------------------------
    #  5. 進行 YOLO 偵測
    # -----------------------------
    # 使用 stream=False，避免回傳 generator 造成後續錯誤
    yolo_results = model.predict(roi_img, stream=False, verbose=False)

    # 呼叫自訂的機器學習模組（整合 YOLO 輸出與其他判斷）
    #predicted = machinelearning(yolo_results, roi_img)
    predicted = machinelearning(yolo_results, roi_img)
    whitePrimary, colorPrimary, cuePos = predicted[1], predicted[2], predicted[3]
    whiteAll, colorAll = predicted[4], predicted[5]

    # 顯示球數統計（可選）
    cv2.putText(roi_img, f"White: {len(whiteAll)}  Color: {len(colorAll)}",
            (10, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255,255,255), 2, cv2.LINE_AA)
    # -----------------------------
    #  6. 擊球與移動判斷邏輯
    # -----------------------------
    if predicted[3] and predicted[1] and predicted[2]:
        # 取球框中心位置
        addX = predicted[1][0] + predicted[1][2] // 2
        addY = predicted[1][1] + predicted[1][3] // 2

        # 初始化 lastPoint（至少要有兩個點）
        if not lastPoint:
            lastPoint.append([addX, addY])
            lastPoint.append([addX, addY])
        else:
            lastPoint.append([addX, addY])
            # 僅保留最近 6 點，避免 list 無限制增長
            if len(lastPoint) > 6:
                lastPoint = lastPoint[-6:]

        # 計算兩點距離
        def distance(a, b):
            return math.hypot(a[0] - b[0], a[1] - b[1])

        # ---- A. 若球移動距離大於 4px，代表「正在運動」 ----
        if distance(lastPoint[-1], lastPoint[-2]) >= 4:
            prediction = False
            probability = {}
            count = 0
            # 投票法：統計多幀預測結果，取出出現次數最多的結果
            for output in possibility:
                if output is None:
                    continue
                c = possibility.count(output)
                if c > count:
                    count = c
                    probability = output
            # 顯示最終預測結果
            showResult(
                probability.get('paths', []),
                probability.get('color', []),
                probability.get('prediction', [])
            )

        # ---- B. 若上一幀有動、這幀幾乎靜止，代表「新的擊球開始」 ----
        elif len(lastPoint) > 2:
            if distance(lastPoint[-2], lastPoint[-3]) >= 4 > distance(lastPoint[-1], lastPoint[-2]):
                prediction = True
                shotPoints = []
                possibility = []

        # ---- C. 根據狀態進行對應處理 ----
        if prediction:
            # 尚在預測階段 → 更新擊球點、可能軌跡
            shotPoint = findShotPoints(predicted[3], predicted[1], radiusMean, shotPoints)
            results_obj = poolShotPrediction(shotPoint, predicted[1], predicted[2], holes)
            possibility.append(results_obj)
        elif not prediction:
            # 已擊出球 → 顯示最終結果
            try:
                showResult(
                    probability.get('paths', []),
                    probability.get('color', []),
                    probability.get('prediction', [])
                )
            except NameError:
                pass

    # -----------------------------
    #  7. 顯示畫面與寫入影片
    # -----------------------------
    # 在 ROI 左上角印出 FPS
    cv2.putText(roi_img, f"FPS: {fps:.1f}", (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2, cv2.LINE_AA)

    # 顯示畫面（縮小一半）
    frame = cv2.resize(roi_img, (960, 540))
    cv2.imshow('Pool Shot Predictor', frame)

    bgr = color_to_bgr(color_info['label'])
    cv2.rectangle(roi_img, (bx, by), (bx + bw, by + bh), bgr, 2)
    cv2.putText(roi_img, ball_color_label, (bx, max(0, by - 6)),
            cv2.FONT_HERSHEY_SIMPLEX, 0.6, bgr if color_info['label'] != "White" else (0,0,0), 2, cv2.LINE_AA)

    # 寫入影片（確保與初始尺寸一致）
    h, w = roi_img.shape[:2]
    if (w, h) != (W0, H0):
        frame_to_write = cv2.resize(roi_img, (W0, H0))
    else:
        frame_to_write = roi_img
    result.write(frame_to_write)

    # 按下 Q 可中斷程式
    key = cv2.waitKey(1)
    if key & 0xFF == ord('q'):
        break

# -----------------------------
#  8. 資源釋放與結束
# -----------------------------
cap.release()
result.release()
cv2.destroyAllWindows()
print(f"✅ 分析完成，輸出結果已儲存至：{VIDEO_OUT}")
