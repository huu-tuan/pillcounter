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
import subprocess
import csv
from umodbus import conf
from umodbus.client import tcp



def prep(image, crop=[0, 0, 0, 0], pad=True):
    # frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    image = np.array(image, copy=True)
    # TODO: find cleaner way to update frame Static so that it is not preprocessed each time
    if len(image.shape) == 3: image = image[:, :, 2]  # input image is the same for each layer so grabbing one is more efficient than conversion
    height = image.shape[1]
    width = image.shape[0]

    # Cropping out based on args
    if sum(crop) != 0:
        rightCrop = int(crop[3])
        leftCrop = int(crop[2])
        topcrop = int(crop[0])
        bottomcrop = int(crop[1])
        image = image[rightCrop:width - leftCrop, topcrop:height - bottomcrop]

    if pad: image = np.pad(image, pad_width=5, mode='constant', constant_values=255)
    return image


class Contour:
    
    def __init__(self, points):
        # approximate the contour, where epsilon is the distance to the original contour
        cnt = cv2.convexHull(points)
        # add the first point as the last point, to ensure it is closed
        lenCnt = len(cnt)
        cnt = np.append(cnt, [[cnt[0][0][0], cnt[0][0][1]]])
        cnt = np.reshape(cnt, (lenCnt + 1, 1, 2))

        # find the area
        self.area = cv2.contourArea(cnt)

        # grab the approximate centerpoint of the contour
        self.yloc = int(round(cnt.mean(axis=0)[0][0]))
        self.xloc = int(round(cnt.mean(axis=0)[0][1]))
        self.points = cnt
        cnt=None #cleanup?

        allY = self.points[:, 0][:, 0]
        allX = self.points[:, 0][:, 1]
        self.yMax = max(allY)
        self.yMin = min(allY)
        self.xMax = max(allX)
        self.xMin = min(allX)

    
    def __str__(self):
        return ('Xmin: ' + str(self.xMin) + ' X: ' + str(self.xloc) + ' Xmax: ' + str(self.xMax) + ' Ymin: ' + str(self.yMin) + ' Y: ' + str(self.yloc) + ' Ymax: ' + str(self.yMax) + " Area: " + str(self.area) + " Num Points: " + str(len(self.points)))


class Pill:
    
    def __init__(self, X, Y, Area, Frame, Time, num, cnt, frameBufferLen):
        self.num = num
        self.X = [X]
        self.Y = [Y]
        self.Area = [Area]
        self.Frame = [Frame]
        self.Time = [Time]
        self.Registered = False
        self.currentContour = cnt
        self.frameBufferLen = frameBufferLen
    
    def update(self, X, Y, Area, Frame, Time, cnt, frameBufferLen):
        self.X.append(X)
        self.Y.append(Y)
        self.Area.append(Area)
        self.Frame.append(Frame)
        self.Time.append(Time)
        self.Registered = True #Pill is registed when 2 frames
        self.currentContour = cnt
        self.frameBufferLen = frameBufferLen

        return len(self.Frame) #returns number of frames pill has appeared in

    
    def printLatest(self):
        print(str(self.num) + ': X: ' + str(self.X[-1]) + " Y : " + str(self.Y[-1]) + " Area " + str(
            self.Area[-1]) + " Frame " + str(self.Frame[-1]) + " Time: " + str(self.Time[-1]))

    
    def log(self, logFileName, puckID):
        logFile = open(logFileName, 'a', newline='')
        with logFile as f:
            # identifying header
            row = ['Number', 'PuckID', 'Registered', 'X', 'Y', 'Area', 'Frame', 'FrameBufferLen']
            row = [self.num, puckID, self.Registered, self.X, self.Y, self.Area, self.Frame, self.frameBufferLen]
            writer = csv.writer(f)
            writer.writerow(row)

    
    def __str__(self):
        return (str(self.num) + ' ' + str(self.Registered) + ': X: ' + str(self.X) + " Y : " + str(self.Y) + " Area " + str(
            self.Area) + " Frame " + str(self.Frame) + " Time: " + str(self.Time))


class communicationStream():
    """
    Class that continuously communicates with the PLC.
    """

    
    def __init__(self, myCounter, version, IPAddress='10.13.1.250', Port=502, DEBUG=False):
        self.IPAddress = IPAddress
        self.Port = Port
        self.stopped = False

        self.myCounter = myCounter

        self.version = version

        self.comm_CountingIdleCoil = 0
        self.comm_CountingIdleValue = 0
        self.comm_PillDetectedSignal1Coil = 0
        self.comm_PillDetectedSignal1Coil = 1
        self.comm_PillDetectedSignal1Value = 0
        self.comm_PillDetectedSignal2Coil = 2
        self.comm_PillDetectedSignal2Value = 0
        self.comm_FrontDoorClosedCoil = 3
        self.comm_FrontDoorClosedValue = 1
        # removed camera 2 signals
        self.comm_TranslucentPillsCoil = 5
        self.comm_TranslucentPillsValue = 0
        self.comm_HeartBeatCoil = 6
        self.comm_HeartBeatValue = 0
        self.comm_CameraViewCoil = 7
        self.comm_CameraViewValue = 0
        self.comm_ConfirmTubeCleanCoil = 8
        self.comm_ConfirmTubeCleanValue = 0
        self.comm_TuningActiveCoil = 9
        self.comm_TuningActiveValue = 0
        self.comm_TubeMissingCoil = 10
        self.comm_TubeMissingValue = 0
        self.comm_SystemInitializedCoil = 11
        self.comm_SystemInitializedValue = 0

        self.slave_id = 255

        self.comm_PillSizeRegister = 0
        self.comm_PillSizeValue = 1
        self.comm_TubeDustLevelRegister = 1
        self.comm_TubeDustLevelValue = 0
        self.comm_DiffThreshRegister = 2
        self.comm_DiffThreshValue = 0
        self.comm_PuckIDRegister = 3
        self.comm_PuckIDValue = 0

        self.comm_VersionMajorRegister = 4
        self.comm_VersionMajorValue = version[0]
        self.comm_VersionMinorRegister = 5
        self.comm_VersionMinorValue = version[1]
        self.comm_VersionPatchRegister = 6
        self.comm_VersionPatchValue = version[2]

        self.DEBUG = DEBUG

        self.connectSocket()

    
    def connectSocket(self):
        ConnectionComplete = False
        while not ConnectionComplete:
            try:
                conf.SIGNED_VALUES = True
                self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.sock.connect((str(self.IPAddress), self.Port))
                ConnectionComplete = True
            except:
                print('can not open socket')
                time.sleep(3)

    
    def start(self):
        # Read initial pill data registers once on startup
        ReadComplete = False
        while not ReadComplete:
            try:
                print('Sending Version # to PLC: ' + str(self.version))
                # Write Version Number on Startup
                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_VersionMajorRegister,
                                                    value=int(self.comm_VersionMajorValue))
                response = tcp.send_message(message, self.sock)
                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_VersionMinorRegister,
                                                    value=int(self.comm_VersionMinorValue))
                response = tcp.send_message(message, self.sock)
                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_VersionPatchRegister,
                                                    value=int(self.comm_VersionPatchValue))
                response = tcp.send_message(message, self.sock)


                message = tcp.read_holding_registers(slave_id=self.slave_id,
                                                     starting_address=self.comm_PillSizeRegister,
                                                     quantity=1)
                response = tcp.send_message(message, self.sock)
                self.comm_PillSizeValue = response[0]
                self.myCounter.AreaThresh = self.comm_PillSizeValue

                message = tcp.read_holding_registers(slave_id=self.slave_id,
                                                     starting_address=self.comm_DiffThreshRegister,
                                                     quantity=1)
                response = tcp.send_message(message, self.sock)
                self.comm_DiffThreshValue = response[0]
                self.myCounter.DiffThresh = self.comm_DiffThreshValue
                ReadComplete = True
            except:
                print('retrying connection')
                time.sleep(1)

        # Start background thread
        Thread(target=self.receive, args=()).start()
        return self

    
    def reset(self):
        self.something = 0
        self.connectSocket()

    
    def receive(self):
        while not self.stopped:
            try:
                time.sleep(.25)

                # Get coil values
                coilVal = tcp.read_coils(slave_id=self.slave_id, starting_address=0, quantity=12)
                response = tcp.send_message(coilVal, self.sock)
                self.comm_CountingIdleValue = response[self.comm_CountingIdleCoil]
                self.comm_TranslucentPillsValue = response[self.comm_TranslucentPillsCoil]
                self.comm_HeartBeatValue = response[self.comm_HeartBeatCoil]
                self.comm_CameraViewValue = response[self.comm_CameraViewCoil]
                self.comm_ConfirmTubeCleanValue = response[self.comm_ConfirmTubeCleanCoil]
                self.comm_TuningActiveValue = response[self.comm_TuningActiveCoil]
                self.comm_SystemInitializedValue = response[self.comm_SystemInitializedCoil]
                self.comm_TubeMissingValue = response[self.comm_TubeMissingCoil]
                self.comm_FrontDoorClosedValue = response[self.comm_FrontDoorClosedCoil]

                # Save pic of clean Tube:
                # print('comm_ConfirmTubeCleanValue: ' + str(self.comm_ConfirmTubeCleanValue))
                if self.comm_ConfirmTubeCleanValue == 1:
                    if not os.path.exists('images'):
                        os.makedirs('images')
                    imageFileName = 'images/CleanTube.jpg'
                    cv2.imwrite(imageFileName, self.myCounter.frameStatic)
                    self.myCounter.tubeCleanImage = self.myCounter.frameStatic
                    self.comm_ConfirmTubeCleanValue = 0
                    print('Reset Tube Image')
                    # self.comm_CameraViewValue = response[self.comm_CameraViewCoil]
                    message = tcp.write_single_coil(slave_id=self.slave_id, address=self.comm_ConfirmTubeCleanCoil, value=0)
                    response = tcp.send_message(message, self.sock)

                # Write Pill Size Value
                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_PillSizeRegister,
                                                    value=int(self.myCounter.AreaThresh))
                response = tcp.send_message(message, self.sock)

                # Write DiffThresh Value
                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_DiffThreshRegister,
                                                    value=int(self.myCounter.DiffThresh))
                response = tcp.send_message(message, self.sock)

                # Write MissingTube Value
                message = tcp.write_single_coil(slave_id=self.slave_id, address=self.comm_TubeMissingCoil,
                                                    value=int(self.myCounter.missingTube))
                # print(int(self.myCounter.missingTube))
                response = tcp.send_message(message, self.sock)
                # print(response)

                # Read Puck ID
                message = tcp.read_holding_registers(slave_id=self.slave_id,
                                                     starting_address=self.comm_PuckIDRegister,
                                                     quantity=1)
                response = tcp.send_message(message, self.sock)
                self.comm_PuckIDValue = response[0]
                self.myCounter.puckID = self.comm_PuckIDValue

                # Write Tube Dust Level
                message = tcp.read_holding_registers(slave_id=self.slave_id,
                                                     starting_address=self.comm_TubeDustLevelRegister,
                                                     quantity=1)
                response = tcp.send_message(message, self.sock)
                self.comm_TubeDustLevelValue = response[0]

                message = tcp.write_single_register(slave_id=self.slave_id, address=self.comm_TubeDustLevelRegister,
                                                    value=int(self.myCounter.tubeCleanLevel))
                response = tcp.send_message(message, self.sock)

                # Write heartbeat value
                message = tcp.write_single_coil(slave_id=self.slave_id, address=self.comm_HeartBeatCoil, value=1)
                response = tcp.send_message(message, self.sock)

                # Front Door state
                if self.comm_FrontDoorClosedValue == 1:
                    self.comm_FrontDoorClosedValue = True
                else:
                    self.comm_FrontDoorClosedValue = False

                # System Init state
                if self.comm_SystemInitializedValue == 1:
                    self.myCounter.systemInitialized = True
                else:
                    self.myCounter.SystemInitialized = False

                # Counting Idle state
                if self.comm_CountingIdleValue == 1:
                    self.myCounter.CountingIdle = True
                else:
                    self.myCounter.CountingIdle = False

                # Set tuning state
                if self.comm_TuningActiveValue == 1:
                    self.myCounter.TuningActive = True
                else:
                    self.myCounter.TuningActive = False

                if self.comm_CameraViewValue == 1:
                    response = os.system('wmctrl -a DrugSettings')
                    # print(response)
                    # if response != 0:
                    #     os.system('remmina ~/pillcount/files/Unitronics.remmina')
                    #     print('starting VNC')
                    self.comm_CameraViewValue == 0
                    print('switched view')
                    # self.comm_CameraViewValue = response[self.comm_CameraViewCoil]
                    message = tcp.write_single_coil(slave_id=self.slave_id, address=self.comm_CameraViewCoil, value=0)
                    response = tcp.send_message(message, self.sock)

            except:
                print('Com Stream lost connection - reconnecting')
                self.connectSocket()

            # print("CountingIdleValue:     " + str(self.comm_CountingIdleValue))
            # print("TranslucentPillsValue: " + str(self.comm_TranslucentPillsValue))
            # print("HeartBeatValue:        " + str(self.comm_HeartBeatValue))
            # print("CameraViewValue:       " + str(self.comm_CameraViewValue))
            # print("CameraViewValue:       " + str(self.comm_PillSizeValue))

    # def get(self):
    #     return self.something
    
    def stop(self):
        self.stopped = True


class cameraStream:
    """
    Class that continuously gets frames from a VideoCapture object
    with a dedicated thread.
    """

    
    def __init__(self, DeviceNum):

        # DeviceNum = 0
        width = 424
        height = 240

        if os.name == 'nt':
            cap = cv2.VideoCapture(DeviceNum + cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(DeviceNum, cv2.CAP_V4L2)
        while cap is None or not cap.isOpened():
            print('Warning: unable to connect to USB camera - REBOOT REQUIRED')
            cap = cv2.VideoCapture(DeviceNum, cv2.CAP_V4L2)
            time.sleep(5)
        cap.set(3, int(width))
        cap.set(4, int(height))
        cap.set(8, 16.0)  # Format
        cap.set(9, 0.0)  # Mode
        cap.set(10, 0.0)  # brightness
        cap.set(11, 50.0)  # contrast
        cap.set(12, 50.0)  # saturation
        cap.set(13, 0.0)  # hue
        cap.set(16, 1.0)  # Convert RGB
        cap.set(20, 50.0)  # Sharpness
        cap.set(22, 300.0)  # Gamma
        cap.set(23, 4600.0)  # Temperature
        cap.set(32, 0.0)  # Backlight
        cap.set(38, 10.0)  # Buffersize
        cap.set(39, 0.0)  # Autofocus

        self.stream = cap
        self.frame = []
        (self.grabbed, frame) = self.stream.read()
        self.frame.append(frame)
        self.stopped = False
        self.frameNum = 0

    
    def start(self):
        Thread(target=self.capture, args=()).start()
        return self

    
    def reset(self):
        self.frame = []
        (self.grabbed, frame) = self.stream.read()
        self.frame.append(frame)
        self.stopped = False

    
    def capture(self):
        while not self.stopped:
            if not self.grabbed:
                self.stop()
            else:
                if len(self.frame) > 100:
                    self.frame.pop(0)
                (self.grabbed, frame) = self.stream.read()
                self.frame.append(frame)
                self.frameNum += 1

    
    def get(self):
        # If the frame buffer is empty, wait until a frame arrives
        while len(self.frame) < 1:
            time.sleep(.001)
        return [self.frame.pop(0), len(self.frame)]

    
    def stop(self):
        self.stopped = True


class video():
    
    def __init__(self, windowName, myCounter, frame):
        self.windowName = windowName
        self.screenWidth = 640
        self.screenHeight = 480
        self.stopped = False
        self.frame = frame
        self.contours = []
        self.myCounter = myCounter
        self.showImage = True
        self.frameBufferLen = 0
        self.maxframeBuffer = 0
        self.lastAreaMinString=""
        self.lastAreaString=""
        img = cv2.imread('pillcount/images/Header.png')

        self.current_index = 0
        self.video_ids = list(self.myCounter.keys())

        # Define the window layout
        sg.theme("DarkBlack1")

        colHeader = sg.Column([[sg.Image(key='-HEADER-', data=cv2.imencode(".png", img)[1].tobytes(), enable_events=True, pad=None)]], size=(480, 84), pad=(0, 0))
        colActions = sg.Column([[sg.Button("Reset Count", font=("Helvetica", 12), size=(8, 1)),
                                 sg.Button("Reset Ref", font=("Helvetica", 12), size=(8, 1)),
                                 sg.Button("Save Frames", font=("Helvetica", 12), size=(10, 1)), 
                                 sg.Button("Switch Stream", font=("Helvetica", 12), size=(10, 1)), 
                                 ]], size=(480, 45),
                               pad=(0, 0))

        colVideo = sg.Column([[sg.Image(filename="", key="-IMAGE-")]], pad=(0, 0))
        colData = sg.Column([[sg.Text('COUNT:', font=("Helvetica", 20),size=(10,1))],
                             [sg.Text('', font=("Helvetica", 30),size=(10,1), key='-COUNT-')],
                             [sg.Text('', font=("Helvetica", 10),size=(10,1))], #BLANK SPACE
                             [sg.Text('SIZE AVG:', font=("Helvetica", 13),size=(10,1))],
                             [sg.Text('of last 5 pills:', font=("Helvetica", 8), size=(10, 1))],
                             [sg.Text('', font=("Helvetica", 25),size=(10,1), key='-SIZE_AVERAGE-')],
                             [sg.Text('', font=("Helvetica", 10), size=(10, 1))], #BLANK SPACE
                             [sg.Text('SIZE MIN:', font=("Helvetica", 13), size=(10, 1))],
                             [sg.Text('of last 5 pills:', font=("Helvetica", 8), size=(10, 1))],
                             [sg.Text('', font=("Helvetica", 25), size=(10, 1), key='-SIZE_MIN-')]],
                            pad=(0, 0))

        colFrameData = sg.Column([[sg.Text("Frame Buffer = ", size=(10, 1), justification="left"),
             sg.Text('', font=("Helvetica", 10), size=(5, 1), key='-FRAMEBUFFER-'),
             sg.Text("Buffer Max   = ", size=(10, 1), justification="left"),
             sg.Text('', font=("Helvetica", 10), size=(5, 1), key='-MAXFRAMEBUFFER-')]], size=(450, 45), pad=(0, 0))
        colThresholdSlider = sg.Column([[
                sg.Text("Threshold", size=(10, 1), justification="left"),
                sg.Slider(
                    (15, 100),
                    self.myCounter[self.current_index].DiffThresh,
                    1,
                    orientation="h",
                    size=(50, 50),
                    key="-THRESH SLIDER-",
                ),
            ]], pad=(0, 0))
        colAreaSlider = sg.Column([[
                sg.Text("Size Thresh", size=(10, 1), justification="left"),
                sg.Slider(
                    (50, 5000),
                    self.myCounter[self.current_index].AreaThresh,
                    1,
                    orientation="h",
                    size=(50, 50),
                    key="-SIZE SLIDER-",
                )
            ]], pad=(0, 0))
        self.layout = [[colHeader],
                       [colActions],
                       [colVideo,colData],
                       [colFrameData],
                       [colThresholdSlider],
                       [colAreaSlider]]

        # Create the window and show it
        # self.window = sg.Window("DrugSettings", self.layout, location=(100, 100), size=(480, 800), margins=(0, 0),
        #                         border_depth=None, no_titlebar=True)
        self.window = sg.Window("DrugSettings", self.layout, location=(100, 100), size=(1280, 800), margins=(0, 0),
                                border_depth=None, no_titlebar=True)


    
    def start(self):
        Thread(target=self.show, args=()).start()
        self.maxframeBuffer = 0
        return self

    
    def update(self):
        self.frame[self.current_index] = self.myCounter[self.current_index].frame
        self.contours = []
        #if not self.myCounter[self.current_index].CountingIdle: #TODO: re add this later
        if len(self.myCounter[self.current_index].thresh) !=0:
            contours, hierarchy = cv2.findContours(self.myCounter[self.current_index].thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            if len(hierarchy) > 0:
                for cnt, heir in zip(contours, hierarchy[0]):
                    # for cnt in contours:
                    if len(cnt) > 4 and heir[3] == 0:  self.contours.append(cnt)

    
    def stop(self):
        self.stopped = True

    
    def saveRecentFrames(self):
        recentFrames = copy.deepcopy(self.myCounter[self.current_index].recentFrames)
        fshape = recentFrames[0].shape
        fheight = fshape[0]
        fwidth = fshape[1]

        now = datetime.datetime.now()

        # for partial video saves
        recentFramesVideoName = 'data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '_partial.avi'
        # for full video saves
        recentFramesVideo = cv2.VideoWriter(recentFramesVideoName, cv2.VideoWriter_fourcc(*"MJPG"), int(30),
                                            (fwidth, fheight))

        print('writing recent frames to video')
        recentFrameNum = 0
        for frame in recentFrames:
            recentFrameNum += 1
            print('writing ' + str(recentFrameNum) + ' of ' + str(len(recentFrames)))
            recentFramesVideo.write(frame)
        recentFramesVideo.release()

    
    def show(self):
        while not self.stopped:
            self.update() #TODO:moved this from main loop
            displayFrame = np.array(self.frame[self.current_index], copy=True)  # make a copy so that we don't modify the raw frame
            contours = self.contours
            myCounter = self.myCounter[self.current_index]
            count = len([x for x in myCounter.pillDataFull if x.Registered])#len(myCounter.pillDataFull)

            scale = True

            # draw contours on the frame
            displayFrame = cv2.drawContours(displayFrame, contours, -1, (0, 0, 0),
                                            thickness=2)  # thickness=3 for outline

            # draw pill number on pill and trace path on frame - this will draw on top of contours
            for pill in myCounter.pillDataCurrent:  # .tail(5).iterrows():
                font = cv2.FONT_HERSHEY_SIMPLEX
                font_size = int(1)
                # if len(pill.X) >= 2:
                if pill.Registered:
                    pillColor = (0, 0, 0)

                    # cv2.putText(displayFrame, label, (pill.Y[-1], pill.X[-1]), font, font_size, (0, 255, 0), 2,
                    #             cv2.LINE_AA)

                    path = [pill.X, pill.Y]
                    for i in range(len(path[0]) - 1):
                        cv2.line(displayFrame, (path[1][i], path[0][i]), (path[1][i + 1], path[0][i + 1]), (255, 0, 0), 5)

                    displayFrame = cv2.drawContours(displayFrame, [pill.currentContour.points], -1, pillColor, thickness=cv2.FILLED)
                    #displayFrame = cv2.fillPoly(displayFrame, pts=pill.currentContour.points, color=(0, 255, 0))


            # draw a horizontal line to show the threshold for new pill registry
            displayFrame = cv2.line(displayFrame, (myCounter.yMaxthresh, 0),
                                    (myCounter.yMaxthresh, displayFrame.shape[1]), (255, 0, 0), 5)
            displayFrame = cv2.line(displayFrame, (myCounter.yMinThresh, 0),
                                    (myCounter.yMinThresh, displayFrame.shape[1]), (255, 0, 0), 5)

            if scale:
                # Scale up the image to fill more of the screen
                width = displayFrame.shape[1]
                height = displayFrame.shape[0]
                scaleFactor = 1.0
                scaledWidth = int(width * scaleFactor)
                scaledHeight = int(height * scaleFactor)
                dim = (scaledWidth, scaledHeight)
                # displayFrame = displayFrame[rightCrop:width - leftCrop, topcrop:height - bottomcrop]
                displayFrame = cv2.resize(displayFrame, dim, interpolation=cv2.INTER_AREA)

            # displayFrame = cv2.rotate(displayFrame, cv2.ROTATE_90_CLOCKWISE)
            h, w = displayFrame.shape[:2]
            if h > w:
                displayFrame = cv2.rotate(displayFrame, cv2.ROTATE_90_CLOCKWISE)

            ### resize at all
            h, w = displayFrame.shape[:2]
            ratio = [h/max(w, h), w/max(w, h)]
            nh, nw = int(ratio[0] * 720), int(ratio[1] * 720)
            print('>>>> ', nw, nh)
            displayFrame = cv2.resize(displayFrame, (nw, nh))

            # Gui actions and responses
            event, values = self.window.read(timeout=1)

            # Process events and values
            if event == "Save Frames":
                self.saveRecentFrames()
            if event == "BACK" or event == "-HEADER-" and self.myCounter[self.current_index].systemInitialized:
                response = os.system('wmctrl -a Unitronics')
                print(response)
                if response != 0:
                    print('Starting GUI')
                    time.sleep(2)
                    subprocess.Popen(['remmina', '/home/jetson/pillcounter/files/Unitronics.remmina'])
            if event == "Exit" or event == sg.WIN_CLOSED:
                self.stop()
            if event == "Reset Count":
                myCounter.reset()
                self.maxframeBuffer = 0
            if event == "Reset Ref":
                myCounter.frameStatic = myCounter.frame
                print('frameReset')
                self.maxframeBuffer = 0
            if event == "Switch Stream":
                if (self.current_index + 1) < len(self.video_ids):
                    self.current_index = self.video_ids[self.current_index + 1]
                else:
                    self.current_index = 0

            myCounter.DiffThresh = values["-THRESH SLIDER-"] #TODO: reimplement tuning
            # print(myCounter.DiffThresh)
            # if myCounter.TuningActive:
            #     self.layout[5][1].update(myCounter.AreaThresh)
            # else:
            myCounter.AreaThresh = values["-SIZE SLIDER-"]

            self.window["-IMAGE-"].update(data=cv2.imencode(".png", displayFrame)[1].tobytes())
            if not os.name == 'nt': self.window.Maximize()

            countString = str(int(len([x for x in myCounter.pillDataFull if x.Registered])))
            if len([x for x in myCounter.pillDataFull if x.Registered])>=6:
            # if len(myCounter.pillDataFull)>=6:

                lastFiveAreaList = [x.Area[1:4] for x in myCounter.pillDataFull if x.Registered] #This is inneficcient / but grabs only first 4 registered area
                lastFiveAreaList = lastFiveAreaList[-5:-1] #need to only show averages of pills in frame

                lastFiveAreaList = sum(lastFiveAreaList, [])

                areaString = str(int(np.mean(lastFiveAreaList)))
                areaMinString = str(int(min(lastFiveAreaList)))
                self.lastAreaString = areaString
                self.lastAreaMinString = areaMinString
            else:
                areaString = self.lastAreaString
                areaMinString = self.lastAreaMinString

            self.window['-COUNT-'].update(value=countString)
            self.window['-SIZE_AVERAGE-'].update(value=areaString)
            self.window['-SIZE_MIN-'].update(value=areaMinString)
            self.window['-FRAMEBUFFER-'].update(value=self.frameBufferLen)
            self.window['-MAXFRAMEBUFFER-'].update(value=self.maxframeBuffer)


class counter():
    
    def __init__(self, useModBus, coils, crop, areaThresh, diffThresh, frame, frameStatic, DEBUG=True):
        self.pillDataFull = []  # pd.DataFrame(columns=['X', 'Y','Area', 'Frame', 'Time'])
        self.pillDataCurrent = []  # pd.DataFrame(columns=['X', 'Y','Area', 'Frame', 'Time'])
        self.pillCount = 0
        self.registeredPillCount = 0
        self.useModBus = useModBus
        self.DEBUG = DEBUG
        # self.pillTimes = [time.time()]
        self.AreaDivider = 50

        self.frameBufferLen = 0

        self.TuningActive = False
        self.maxPillArea = 0
        self.minPillArea = 0
        self.maxPillWidth = 0
        self.maxPillHeight = 0
        self.pillAreaArray = []

        self.CountingIdle = False

        self.DiffThresh = diffThresh
        self.AreaThresh = areaThresh

        self.yDiffMax = 175
        self.yDiffMin = -12  # This should be a factor of areaThresh - for larger pills that are rotating, the center can actually go up a few  pix up
        # This usually becomes an issue if the min y thresh is set too low
        self.xDiffMax = 50
        self.framesWithNoContours = 0
        self.framesWithNoContoursThresh = 30 #Reduced from 60 to prevent tracking unnecessary contours
        self.Signal = 1
        self.frame = frame
        self.recentFrames = []
        self.frameStatic = frameStatic
        self.frameWidth = frameStatic.shape[0]
        self.frameHeight = frameStatic.shape[1]
        self.crop = crop
        self.thresh = []
        self.slave_id = 255
        self.tubeCleanImage = frameStatic
        self.tubeCleanLevel=0
        self.systemInitialized=False

        self.yMinThresh = 100  # max(100,int(self.AreaThresh / self.AreaDivider))
        self.yMaxthresh = 300  # self.frameHeight - self.yMinThresh - 20

        self.missingTube = False

        self.puckID=0

        self.tuning_MaxArea = 0
        self.tuning_MaxWidth = 0
        self.tuning_MaxHeight = 0

        self.staticFrameBuffer = []

        self.contours = []

        if useModBus:
            connected = False
            print('Trying to Connect to PLC')

            while True:#self.connectSocket() == False:
                # print('Trying to Connect to PLC')
                self.closedLoop = True
                connected = self.connectSocket()
                self.Signal1 = tcp.write_single_coil(slave_id=self.slave_id, address=coils[0], value=1) #this may need to be one to avoid stray count
                # print(self.Signal1)
                # print(coils[0])
                self.Signal2 = tcp.write_single_coil(slave_id=self.slave_id, address=coils[1], value=1)
                # print(self.Signal2)
                # print(coils[1])
                if connected: break
                print('Waiting for PLC')
                time.sleep(1)

    
    def printContours(self):
        for cnt in self.contours:
            print(cnt)

    
    def reset(self):
        self.pillDataFull = []
        self.pillDataCurrent = []
        self.pillCount = 0

    
    def connectSocket(self):
        try:
            conf.SIGNED_VALUES = True
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect(('10.13.1.250', 502))
            print('PLC Connection Established')
            return True
        except:
            print('can not open socket with PLC')
            return False

    
    def diffFrame(self, frame):

        # determine if the static frame should be updated
        self.staticFrameBuffer.append(frame)
        if len(self.staticFrameBuffer) > 40:
            diff = cv2.absdiff(self.staticFrameBuffer[-1], self.staticFrameBuffer[0])
            super_threshold_indices = diff < min(self.DiffThresh,15) #to prevent 0 values
            diff[super_threshold_indices] = 0
            super_threshold_indices = diff >= min(self.DiffThresh,15) #to prevent 0 values
            diff[super_threshold_indices] = 255
            self.staticFrameBuffer.pop(0)
            #Set static frame if virtually unchanged after 40 frames
            if np.sum(diff) < 10000: #arbitrary number that seems to work well
                self.frameStatic = frame
                self.staticFrameBuffer = []
                # Check the tube dust level
                crop = [40, 40, 40, 40] #ignore tube walls
                subdiff = cv2.subtract(prep(self.tubeCleanImage, crop, False), prep(self.frameStatic, crop, False))

                self.tubeCleanLevel = min(100, int(100 * subdiff.mean()/50)) #50 is the fully dirty value
                # print(self.frameStatic.mean())
                if self.frameStatic.mean() > 160: #The sum of an image with a missing tube is ~170+ / normal image is ~135
                    if not self.missingTube: print('Tube Missing')
                    self.missingTube = True
                else:
                    self.missingTube=False

        self.frame = frame

        diff = cv2.absdiff(self.frameStatic, self.frame)
        super_threshold_indices = diff < self.DiffThresh
        diff[super_threshold_indices] = 0
        super_threshold_indices = diff >= self.DiffThresh
        diff[super_threshold_indices] = 255
        self.thresh = (255 - diff)

    
    def findContours(self):
        # contours, hierarchy = cv2.findContours(self.thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        self.contours = []  # reset contours

        if len(self.thresh) !=0:
            contours, hierarchy = cv2.findContours(self.thresh, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
            if len(hierarchy) >=1:
                for cnt, heir in zip(contours, hierarchy[0]):
                    # for cnt in contours:
                    if heir[3] == 0:
                        newContour = Contour(cnt)
                        self.addContour(newContour)
                        newContour=None

        # sort them so that the lowest contour first
        self.contours.sort(key=lambda x: x.yloc, reverse=True)

    
    def addContour(self, contour):
        # this method checks the contour characteristics before adding
        # Filter out contour for entire frame and small artifacts
        # if self.AreaThresh <= cnt.area < 50000 and len(cnt.points)>4:
        # TODO: this should be combined with the findContours function

        #Sort contours by Area
        # self.contours.sort(key=lambda x: x.area, reverse=False) #This is not needed

        # This should prevent any contours that are below the area threshold from being processed - removed for now
        if contour.area < 50000 and len(contour.points) > 7 and contour.area > self.AreaThresh:
            self.contours.append(contour)

    
    def printCurrentPills(self, latest=False):
        if latest:
            for pill in self.pillDataCurrent:
                pill.printLatest()
        else:
            for pill in self.pillDataCurrent:
                print(pill)

    
    def printAllPills(self):
        for pill in self.pillDataFull:
            print(pill)

    
    def printContours(self):
        for cnt in self.contours:
            print(cnt)

    
    def countPills(self, frameTotal):

        # Cleanup stale pills
        pillIndex = 0
        indexToRemove=[]
        for pill in self.pillDataCurrent:
            if frameTotal - pill.Frame[-1] > 10:
                indexToRemove.append(pillIndex)
            pillIndex += 1
        for index in sorted(indexToRemove, reverse=True): #delete in reverse to avoid dynamic index issues
            del self.pillDataCurrent[index]

        # Sort by lowest pill first
        self.pillDataCurrent.sort(key=lambda x: x.Y[-1], reverse=True)

        # Loop through contours starting with the highest
        for cnt in self.contours:

            EXISTINGPILLFOUND = False
            NEWPILLFOUND = False
            _, pillTime = divmod(time.time(), 1)
            pillTime = round(pillTime, 3)

            # if self.TuningActive == 1:
            if cnt.yloc < self.yMaxthresh and cnt.yloc > self.yMinThresh and 50 <= cnt.area and self.TuningActive:
                self.pillAreaArray.append(cnt.area)
                if len(self.pillAreaArray) > 100:
                    min = np.mean(self.pillAreaArray) - np.std(self.pillAreaArray)
                    print(np.mean(self.pillAreaArray) - np.std(self.pillAreaArray))
                    self.AreaThresh = min

            if not self.TuningActive:
                self.maxPillWidth = 0
                self.maxPillHeigh = 0
                self.maxPillArea = 0
                self.minPillArea = 0
                self.pillAreaArray = []

            # Search through Active Pill table to find a match
            if True:#self.AreaThresh <= cnt.area:
                # TODO: need to just search for the closest pill?

                for pill in self.pillDataCurrent:  # looping through current currentPills from the highest first

                    if pill.Y[-1] + self.yDiffMin <= cnt.yloc <= pill.Y[-1] + self.yDiffMax * (
                            frameTotal - pill.Frame[-1]) and \
                            abs(cnt.xloc - pill.X[-1]) < self.xDiffMax * (frameTotal - pill.Frame[-1]) and \
                            2 >= frameTotal - pill.Frame[-1] > 0:
                        EXISTINGPILLFOUND = True
                        if self.DEBUG: print('Processing: ', end='')
                        if self.DEBUG: print([cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime])
                        if self.DEBUG: print(' Registering as existing currentPill: ' + str(pill.num))
                        if self.DEBUG: print('  X    : ' + str(pill.X) + '->' + str(cnt.xloc))
                        if self.DEBUG: print('  Y    : ' + str(pill.Y) + '->' + str(cnt.yloc))
                        if self.DEBUG: print('  Area : ' + str(pill.Area) + '->' + str(
                            cnt.area))
                        if self.DEBUG: print('  Frame: ' + str(pill.Frame) + '->' + str(
                            frameTotal))
                        if self.DEBUG: print('  Time : ' + str(pill.Time) + '->' + str(
                            pillTime))

                        numFramesForPill = pill.update(cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime, cnt, self.frameBufferLen)
                        if numFramesForPill == 2:
                            self.registeredPillCount += 1
                            if self.useModBus:
                                try:
                                    if self.Signal == 1:
                                        response = tcp.send_message(self.Signal1, self.sock)
                                        self.Signal = 2
                                    else:
                                        response = tcp.send_message(self.Signal2, self.sock)
                                        self.Signal = 1
                                    if self.DEBUG: print('New pill signal sent successfuly')
                                except:
                                    print('Counter lost connection - can not send counting signal - reconnecting')
                                    self.connectSocket()

                        break  # no need to look through other currentPills since match was made

                # If no match is found and pill is in registration area, register as a new pill
                if not EXISTINGPILLFOUND and cnt.yloc < self.yMaxthresh and cnt.yloc > self.yMinThresh:
                    NEWPILLFOUND = True
                    if self.DEBUG: print('-----------------------------')
                    if self.DEBUG: print('Processing: ', end='')
                    if self.DEBUG: print([cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime], end='')
                    if self.DEBUG: print(' Registering as NEW PILL: ' + str(self.pillCount))

                    newpill = Pill(cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime, self.pillCount, cnt, self.frameBufferLen)
                    self.pillCount += 1
                    self.pillDataCurrent.append(newpill)
                    self.pillDataFull.append(newpill)

                # Otherwise log issue
                if not EXISTINGPILLFOUND and not NEWPILLFOUND and cnt.yloc > self.yMinThresh:
                    if self.DEBUG: print('Processing: ', end='')
                    if self.DEBUG: print([cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime], end='')
                    if self.DEBUG: print(' UNREGISTERED')

            else:
                if self.DEBUG: print('Processing: ', end='')
                if self.DEBUG: print([cnt.xloc, cnt.yloc, cnt.area, frameTotal, pillTime], end='')
                if self.DEBUG: print(' TOO SMALL')
        return

def run(args):

    #Import keyboard module for quitting with "q" keypress
    # if args.Debug:
    import keyboard

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
            myCameraStream[device] = cameraStream(device)
            myCameraStream[device].start()
            # slowly grab some initial frames in case the captured images are oversaturated
            for i in range(10):
                time.sleep(0.1)
                frameStatic, _ = myCameraStream[device].get()
            frameStatic = prep(frameStatic, crop)
            frameStatics[device] = frameStatic

    else:
        cap = {}
        for idx, path in enumerate(args.InputVideo):
            cap[idx] = cv2.VideoCapture(path)
            cap[idx].set(cv2.CAP_PROP_POS_FRAMES, args.StartFrame)
            for i in range(10):
                time.sleep(0.1)
                ret, frameStatic = cap[idx].read()
            if type(frameStatic) == type(None):
                print('Video File not Found')
                quit()
            frameStatic = prep(frameStatic, crop)
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
        myCounter[key] = counter(args.ModbusCom, [1, 2], args.Crop, args.AreaThresh, args.DiffThresh, frameStatic, frameStatic,
                            args.Debug)

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
            comStream[key] = communicationStream(myCounter[key],version=version)
            comStream[key].start()
        

    # Start GUI Thread
    if args.DisplayVideo:
        myVideo = video('Video', myCounter, frameStatics)
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
        frameTotal = frameTotal + 1
        frame = {}
        frame[0] = None
        frame[1] = None

        # Grab the oldest frame from the buffer or video file
        if args.InputVideo == '':
            for device in args.DeviceNum:
                frame[device], frameBufferLen = myCameraStream[device].get()
                
                if args.DisplayVideo:
                    for key in myCounter.keys():
                        myCounter[key].frameBufferLen = frameBufferLen
                        myVideo.frameBufferLen = frameBufferLen
                        if myVideo.frameBufferLen > myVideo.maxframeBuffer: myVideo.maxframeBuffer = myVideo.frameBufferLen
                        if args.plotResults:frameBufferAll.append(frameBufferLen)

        else:
            for idx, path in enumerate(args.InputVideo):
                _, frame[idx] = cap[idx].read()
                if args.VideoLoop and frame[idx] is None:
                    print('restarting video')
                    cap[idx] = cv2.VideoCapture(path)
                    _, frame[idx] = cap[idx].read()


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
                frame[key] = prep(fr, crop)
            else:
                break

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

        frametoc = time.time()
        if args.Debug:
            if (frametoc - frametic) != 0:
                fps.append(1 / (frametoc - frametic))
                frameTime.append(frametoc - frametic)
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
        print()
        print('FPS Average: ' + str(sum(fps) / len(fps)))
        print('FPS Median: ' + str(statistics.median(fps)))
        print('Min: ' + str(min(fps)) + ' | Max: ' + str(max(fps)))
        res = statistics.pstdev(fps)

        # Printing result
        print("Standard deviation of sample is : " + str(res))

        cv2.destroyAllWindows()

        toc = time.time()
        print('Time Elapsed: ')
        print(toc - tic)
        print('Num Frames: ')
        print(frameTotal)
        print(frameTotal)
        print('Frames per Second: ')
        print(frameTotal / (toc - tic))

    if args.SaveFrames:

        fshape = allFrames[0].shape
        fheight = fshape[0]
        fwidth = fshape[1]

        now = datetime.datetime.now()

        # for partial video saves
        allFramesVideoName = 'data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '_partial.avi'
        # for full video saves
        allFramesVideo = cv2.VideoWriter(allFramesVideoName, cv2.VideoWriter_fourcc(*"MJPG"), int(30),
                                            (fwidth, fheight))

        print('writing recent frames to video')
        recentFrameNum = 0
        for frame in allFrames:
            recentFrameNum += 1
            print('writing ' + str(recentFrameNum) + ' of ' + str(len(allFrames)))
            allFramesVideo.write(frame)
        allFramesVideo.release()


    return len([x for x in myCounter[0].pillDataFull if x.Registered])

if __name__ == '__main__':
    run(sys.argv)
