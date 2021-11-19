import cv2

cap = cv2.VideoCapture('v4l2src device=/dev/video0 ! decodebin ! videoconvert ! video/x-raw,format=(string)BGR, width=(int)640, height=(int)480 ! videoconvert ! videoflip method=2 ! appsink name="appsink0"', cv2.CAP_GSTREAMER)


while True:
    ret, frame = cap.read()

    print(frame.shape)