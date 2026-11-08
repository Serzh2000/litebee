"""Печатные листы A4 с меткой tag36h11 заданного номера (как apriltag_36h11_id0_A4.png).

Использование: python -I tools/gen_apriltag_print.py <выходная папка> <id> [<id> ...]
Нужен opencv-python (модуль aruco). Для каждого номера создаётся файл apriltag_36h11_id<N>_A4.png, 300 dpi, A4.
На листе: чёрный квадрат 160 мм (с рамкой, весь тег целиком) и два малых, 70 и 85 мм. Печатать в 100 % масштабе.
После создания каждый лист проверяется детектором OpenCV (должен вернуть тот же номер).
"""
import os
import sys

import cv2
import numpy as np

DPI = 300
W, H = 2480, 3508  # A4 при 300 dpi


def mm(v):
    return int(round(v * DPI / 25.4))


def tag(dic, ident, side_px):
    # 8 модулей: 6 данных + рамка по 1 модулю; side_px кратно 8 для чётких границ
    side = (side_px // 8) * 8
    return cv2.aruco.generateImageMarker(dic, ident, side, borderBits=1), side


def sheet(dic, ident):
    img = np.full((H, W), 255, np.uint8)
    big, bs = tag(dic, ident, mm(160))
    x0, y0 = mm(14.3), mm(8.5)
    img[y0:y0 + bs, x0:x0 + bs] = big
    cv2.putText(img, "tag36h11  id %d  -  black square 160 mm" % ident, (x0, y0 + bs + 85), cv2.FONT_HERSHEY_SIMPLEX, 2.0, 0, 4, cv2.LINE_AA)
    s70, a = tag(dic, ident, mm(70))
    y1 = y0 + bs + 140
    xs1 = mm(8.5)
    img[y1:y1 + a, xs1:xs1 + a] = s70
    cv2.putText(img, "70 mm", (xs1, y1 + a + 85), cv2.FONT_HERSHEY_SIMPLEX, 2.0, 0, 4, cv2.LINE_AA)
    s85, b = tag(dic, ident, mm(85))
    xs2 = W - mm(8.5) - b - mm(2)
    img[y1:y1 + b, xs2:xs2 + b] = s85
    cv2.putText(img, "85 mm", (xs2, y1 + b + 85), cv2.FONT_HERSHEY_SIMPLEX, 2.0, 0, 4, cv2.LINE_AA)
    cv2.putText(img, "Print at 100% (Actual size), no 'fit to page'. Measure the black square.", (mm(5), H - 60), cv2.FONT_HERSHEY_SIMPLEX, 1.6, 0, 3, cv2.LINE_AA)
    return img


def main():
    out = sys.argv[1]
    ids = [int(x) for x in sys.argv[2:]]
    os.makedirs(out, exist_ok=True)
    dic = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    det = cv2.aruco.ArucoDetector(dic, cv2.aruco.DetectorParameters())
    for i in ids:
        img = sheet(dic, i)
        path = os.path.join(out, "apriltag_36h11_id%d_A4.png" % i)
        cv2.imwrite(path, img, [cv2.IMWRITE_PNG_COMPRESSION, 9])
        # проверка: найдёт ли детектор номер на напечатанном листе (с белым полем вокруг)
        corners, found, _ = det.detectMarkers(cv2.copyMakeBorder(img, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255))
        got = sorted(int(x) for x in (found.flatten() if found is not None else []))
        print(path, "decoded ids:", got)


if __name__ == "__main__":
    main()
