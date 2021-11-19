import cv2
import numpy as np
import sys
import datetime
import socket
import os
import PySimpleGUI as sg
import time
from threading import Thread
import copy
import keyboard
import subprocess
import csv
from umodbus import conf
from umodbus.client import tcp

from pillcount.utils import preprocess, Contour, Pill, CommunicationStream, CameraStream, VideoGUI, Counter


def run(args):
    #get the release version
    try:
        f = open("files/version.txt", "r")
        version = str(f.readline())
        version = [int(x) for x in version.split(".")]
        type(version)
        print('Version: ' + str(version))
        f.close()
    except:
        print('ERROR: Version file not found - setting version to 0')
        version = int(0)

    # In case the crop list is sent as a string
    crop = []
    for item in args.Crop:
        crop.append(int(item))

    # Set up logging file
    if args.Logging:
        if not os.path.exists('logs'):
            os.makedirs('logs')
        now = datetime.datetime.now()
        logFileName = 'logs/' + str(len(os.listdir('logs'))) + str(now.strftime(" %m-%d-%Y %H %M %S")) + '.csv'
        logFile = open(logFileName, 'w', newline='')

        with logFile as f:
            # identifying header
            header = ['Number', 'PuckID', 'Registered', 'X', 'Y', 'Area', 'Frame', 'FrameBufferLen']
            writer = csv.writer(f)
            writer.writerow(header)
        lines_written = 0

        # remove logs older than 30 days
        print('Removing logs older than 30 days')
        file_dir = "logs"  # location
        maxDaysToKeep = 30  # n max of days

        maxDaysToKeep_pass = datetime.datetime.now() - datetime.timedelta(maxDaysToKeep)
        for root, dirs, files in os.walk(file_dir):
            for file in files:
                path = os.path.join(file_dir, file)
                filetime = datetime.datetime.fromtimestamp(os.path.getctime(path))
                if filetime < maxDaysToKeep_pass and file.endswith('.csv'):
                    os.remove(path)

    frameStatics = {}
    # frameStatic = []
    if len(args.InputVideo) == 0:
        # Start video stream
        myCameraStream = {}
        for device in args.DeviceNum:
            myCameraStream[device] = CameraStream(device)
            myCameraStream[device].start()
            # slowly grab some initial frames in case the captured images are oversaturated
            for i in range(10):
                time.sleep(0.1)
                frameStatic, _ = myCameraStream[device].get()
            frameStatic = preprocess(frameStatic, crop)
            frameStatics[device] = frameStatic

    # else:
    #     cap = {}
    #     for idx, path in enumerate(args.InputVideo):
    #         cap[idx] = cv2.VideoCapture(path)
    #         cap[idx].set(cv2.CAP_PROP_POS_FRAMES, args.StartFrame)
    #         for i in range(10):
    #             time.sleep(0.1)
    #             ret, frameStatic = cap[idx].read()
    #         if type(frameStatic) == type(None):
    #             print('Video File not Found')
    #             quit()
    #         frameStatic = preprocess(frameStatic, crop)
    #         frameStatics[idx] = frameStatic
    else:
        myCameraStream = {}
        for idx, path in enumerate(args.InputVideo):
            myCameraStream[idx] = CameraStream(InputVideo = path)
            myCameraStream[idx].start()
            # slowly grab some initial frames in case the captured images are oversaturated
            for i in range(10):
                time.sleep(0.1)
                frameStatic, _ = myCameraStream[idx].get()
            if type(frameStatic) == type(None):
                print('Video File not Found')
                quit()
            frameStatic = preprocess(frameStatic, crop)
            frameStatics[idx] = frameStatic

    #Ensure there is a data folder for saving frames
    if not os.path.exists('data'):
        os.makedirs('data')

    # GPIO is currently not used
    if args.GPIO:
        import RPi.GPIO as GPIO
        try:
            # Pin Definitions
            leftBacklight = 24  # BCM pin 18, BOARD pin 12
            rightBacklight = 23

            GPIO.setmode(GPIO.BCM)  # BCM pin-numbering scheme
            # set pin as an output pin with optional initial state of HIGH

            GPIO.setup(leftBacklight, GPIO.OUT, initial=GPIO.HIGH)
            GPIO.setup(rightBacklight, GPIO.OUT, initial=GPIO.HIGH)
            print('Turning ON LED Lights')
        except:
            print('can not control LED')

    #Initialize variables
    allFrames = []
    fps = []
    frameTotal = 0
    frameTime = []
    frameBufferAll = []
    tic = time.time()
    previousPillCount=0

    #initialize counter object
    myCounter = {}
    for key, frameStatic in frameStatics.items():
        myCounter[key] = Counter(args.ModbusCom, [1, 2], args.Crop, args.AreaThresh, 
                                    args.DiffThresh, frameStatic, frameStatic, args.Debug)

    # set the tube clean image - load if it exists
    imageFileName = 'images/CleanTube.jpg'
    if args.ResetCleanTubeImage:
        if os.path.exists(imageFileName):
            os.remove(imageFileName)
    if os.path.exists(imageFileName):
        print('Loading Clean Tube Image')
        try:
            for key in myCounter.keys():
                myCounter[key].tubeCleanImage = cv2.imread(imageFileName)[:, :, 2]

        except:
            print('Tube Image likely corrupt')
            os.remove(imageFileName)
            for key in myCounter.keys():
                myCounter[key].tubeCleanImage = frameStatic
                cv2.imwrite(imageFileName, myCounter[key].frameStatic)

        # cv2.imwrite(imageFileName, myCounter.frameStatic)
    else:
        print('Creating Clean Tube Image - none exists')
        if not os.path.exists('images'): os.makedirs('images')
        for key in myCounter.keys():
            myCounter[key].tubeCleanImage = frameStatic
            cv2.imwrite(imageFileName, myCounter[key].frameStatic)

    #Start the com stream
    if args.ModbusCom:
        comStream = {}
        for key in myCounter.keys():
            comStream[key] = CommunicationStream(myCounter[key],version=version)
            comStream[key].start()
        

    # Start GUI Thread
    if args.DisplayVideo:
        myVideo = VideoGUI('Video', myCounter, frameStatics)
        myVideo.start()
        
    # tr = tracker.SummaryTracker()
    if args.InputVideo == '': 
        for device in args.DeviceNum:
            myCameraStream[device].reset()  # reset frame buffer - this will sometimes max out on init only

    print('Starting Count')
    timeStarted=time.time()

    #Main loop
    while True:
        frametic = time.time()
        frameTotal += 1
        frame = {}
        frame[0] = None
        frame[1] = None

        # Grab the oldest frame from the buffer or video file
        # if args.InputVideo == '':
        #     for device in args.DeviceNum:
        #         frame[device], frameBufferLen = myCameraStream[device].get()
                
        #         if args.DisplayVideo:
        #             for key in myCounter.keys():
        #                 myCounter[key].frameBufferLen = frameBufferLen
        #                 myVideo.frameBufferLen = frameBufferLen
        #                 if myVideo.frameBufferLen > myVideo.maxframeBuffer: 
        #                     myVideo.maxframeBuffer = myVideo.frameBufferLen
        #                 if args.plotResults:
        #                     frameBufferAll.append(frameBufferLen)
        # else:
        #     for idx, path in enumerate(args.InputVideo):
        #         _, frame[idx] = cap[idx].read()
        #         if args.VideoLoop and frame[idx] is None:
        #             print('restarting video')
        #             cap[idx] = cv2.VideoCapture(path)
        #             _, frame[idx] = cap[idx].read()

        for idx in [0, 1]:
            frame[idx], frameBufferLen = myCameraStream[idx].get()
            
            if args.DisplayVideo:
                for key in myCounter.keys():
                    myCounter[key].frameBufferLen = frameBufferLen
                    myVideo.frameBufferLen = frameBufferLen
                    if myVideo.frameBufferLen > myVideo.maxframeBuffer: 
                        myVideo.maxframeBuffer = myVideo.frameBufferLen
                    if args.plotResults:
                        frameBufferAll.append(frameBufferLen)


        # add frame to recent Frame buffer
        for key in myCounter.keys():
            myCounter[key].recentFrames.append(frame[key])
            if len(myCounter[key].recentFrames) > 1000:
                myCounter[key].recentFrames.pop(0)

        # add frame to all frame buffer
        if args.SaveFrames: 
            for key in frame.keys():
                allFrames.append(frame[key])

        # prep frame
        for key, fr in frame.items():
            if fr is not None:
                frame[key] = preprocess(fr, crop)
            else:
                break

        # check if frame is NONE
        skip = False
        for key, fr in frame.items():
            if fr is None:
                skip = True
        if skip:
            continue

        # stop if target pill count reached
        for key in myCounter.keys():
            if args.NumPillsToCount != 0 and len(myCounter[key].pillDataFull) >= args.NumPillsToCount: 
                break

        ## Process frame

        # diff frame
        for key in myCounter.keys():
            myCounter[key].diffFrame(frame[key])

        if args.ModbusCom:
            for key in comStream.keys():
                if comStream[key].comm_FrontDoorClosedValue:

                    # Find Contours
                    myCounter[key].findContours()

                    # Count pills based on contours
                    myCounter[key].countPills(frameTotal)
                
        else:
            for key in myCounter.keys():
                # Find Contours
                myCounter[key].findContours()

                # Count pills based on contours
                myCounter[key].countPills(frameTotal)

        # write to log file
        for key in myCounter.keys():
            if myCounter[key].pillCount > previousPillCount and args.Logging:
                if myCounter[key].pillDataFull == 10:
                    for pill in myCounter[key].pillDataFull[0:8]: #this may cause an issue when pillDataFull is reset at 1000
                        pill.log(logFileName,myCounter[key].puckID)
                if myCounter[key].pillCount >= 20 and myCounter[key].pillCount % 10 == 0:
                    #Modified to write previous 10 pills
                    for pill in myCounter[key].pillDataFull[len(myCounter[key].pillDataFull)-11:len(myCounter[key].pillDataFull) - 1]:
                        pill.log(logFileName,myCounter[key].puckID)
                previousPillCount=myCounter[key].pillCount

        delta_t = time.time() - frametic
        if args.Debug:
            if delta_t != 0:
                fps.append(1 / delta_t)
                frameTime.append(delta_t)
            else:
                frameTime.append(0)

        #Delete this as it is not used
        if args.DisplayVideo:
            if myVideo.stopped:
                if args.InputVideo == '': 
                    for key in myCameraStream.keys():
                        myCameraStream[key].stop()
                # break

        # Slow down display rate
        for key in myCounter.keys():
            if args.DisplayVideo and args.PauseOnPill > 0 and len(myCounter[key].pillDataCurrent) > 0:
                time.sleep(args.PauseOnPill)

        # Clean up
        for key in myCounter.keys():
            if len(myCounter[key].pillDataFull)>1000 and myCounter[key].CountingIdle: #changed to 1000 to prevent excessive memory use TODO: determine if this causes issues with logging or counting
                myCounter[key].reset()

        # if args.Debug:
        if keyboard.is_pressed("q"):
            print("q pressed, ending loop")
            break


    #End of Main Loop

    if args.DisplayVideo: 
        myVideo.stop()

    if args.ModbusCom: 
        for key in comStream.keys():
            comStream[key].stop()

    if args.Debug:
        import statistics
        # pd.set_option("display.max_rows", None, "display.max_columns", None)
        for key in myCounter.keys():
            for pill in myCounter[key].pillDataFull:
                print(pill)
        print('\nFPS Average: ' + str(sum(fps) / len(fps)))
        print('FPS Median: ' + str(statistics.median(fps)))
        print('Min: ' + str(min(fps)) + ' | Max: ' + str(max(fps)))
        res = statistics.pstdev(fps)

        # Printing result
        print("Standard deviation of sample is : " + str(res))

        cv2.destroyAllWindows()

        toc = time.time()
        print('Time Elapsed: ', toc - tic)
        print('Num Frames: ', frameTotal)
        print('Frames per Second: ', frameTotal / (toc - tic))

    if args.SaveFrames:
        fshape = allFrames[0].shape
        fheight, fwidth = fshape[:2]

        now = datetime.datetime.now()
        output_path = 'data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '_partial.avi'
        allFramesVideo = cv2.VideoWriter(output_path, cv2.VideoWriter_fourcc(*"MJPG"), int(30),
                                            (fwidth, fheight))

        print('writing recent frames to video')
        for recentFrameNum, frame in enumerate(allFrames):
            print('writing ' + str(recentFrameNum + 1) + ' of ' + str(len(allFrames)))
            allFramesVideo.write(frame)
        allFramesVideo.release()

    # return len([x for x in myCounter[0].pillDataFull if x.Registered])
    return 


if __name__ == '__main__':
    run(sys.argv)
