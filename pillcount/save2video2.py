import numpy as np
import cv2
import time
import datetime
import sys


width = 424
height = 240
# scale = .5

cap1 = cv2.VideoCapture(0)
cap1.set(3, width)
cap1.set(4,height)
cap2 = cv2.VideoCapture(1)
cap2.set(3, width)
cap2.set(4,height)

# cap.set(cv2.CAP_PROP_FPS,10)
fps = cap1.get(cv2.CAP_PROP_FPS)
print(fps)
ret, frame1 = cap1.read()
ret, frame2 = cap2.read()

fshape = frame1.shape
fheight = fshape[0]
fwidth = fshape[1]

print(fheight)
print(fwidth)

now = datetime.datetime.now()
outName1 = '../data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '1.avi'
outName2 = '../data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '2.avi'
print(outName1)
print(outName2)
out1 = cv2.VideoWriter(outName1, cv2.VideoWriter_fourcc(*"MJPG"), fps, (fwidth,fheight))
out2 = cv2.VideoWriter(outName2, cv2.VideoWriter_fourcc(*"MJPG"), fps, (fwidth,fheight))

print(sys.argv[1])
frameTarget = sys.argv[1]
showVid = sys.argv[2]

#while(cap.isOpened()):
allFrames1=[]
allFrames2=[]
fps=[]
for i in range(int(frameTarget)):
    tic=time.time()
    ret, frame1 = cap1.read()
    ret, frame2 = cap2.read()
    if ret==True:

        # write the flipped frame

        allFrames1.append(frame1)
        allFrames2.append(frame2)

        if int(showVid) == 1:
            cv2.imshow('frame1',frame1)
            cv2.imshow('frame2', frame2)
            print([frame1.shape[1],frame1.shape[0]])
        cv2.waitKey(1)
        toc = time.time()
        if (toc-tic) !=0: fps.append(1 / (toc - tic))
        # out.write(frame)
    else:
        break


print(sum(fps)/len(fps))

i=0
for frame in allFrames1:
    i=i+1
    print(i/len(allFrames1))
    out1.write(frame)

i=0
for frame in allFrames2:
    i=i+1
    print(i/len(allFrames2))
    out2.write(frame)

# Release everything if job is finished
cap1.release()
out1.release()
cap2.release()
out2.release()
cv2.destroyAllWindows()
