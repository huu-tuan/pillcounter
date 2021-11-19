import csv
import pandas as pd
import matplotlib.pyplot as plt
from drawnow import drawnow
import os
import glob
from matplotlib.pyplot import cm
import numpy as np
import math
import itertools


list_of_files = glob.glob('logs/*') # * means all if need specific format then *.csv
latest_file = max(list_of_files, key=os.path.getctime)



data = pd.read_csv(latest_file)
fig=plt.figure()
fig.set_figheight(8)
fig.set_figwidth(3)
# f, ax = plt.subplots(figsize=(12, 6))
plt.ion()
ax = fig.add_subplot(111)
ax.set_xlim([220, 40])
ax.set_ylim([440, 0])


columns=['Number','PuckID','Registered','X','Y','Area','Frame']
pillDataFrame = pd.DataFrame(columns=columns)

#add loop that converts values into lists
#add loop that sorts everything by frame
for index, pill in data.iterrows():
    Number=pill.Number
    PuckID = pill.PuckID
    Registered = bool(pill.Registered)
    X = pill.X.strip("[]").split(",")
    X = [int(x) for x in X]
    Y = pill.Y.strip("[]").split(",")
    Y = [int(y) for y in Y]
    Area = pill.Area.strip("[]").split(",")
    Area = [float(area) for area in Area]
    Frame = pill.Frame.strip("[]").split(",")
    Frame = [int(f) for f in Frame]

    df2 = {'Number': Number,
           'PuckID':PuckID,
           'Registered':Registered,
           'X':X,
           'Y':Y,
           'Area':Area,
           'Frame':Frame}
    pillDataFrame=pillDataFrame.append(df2,ignore_index=True)

startFrame = min([min(x) for x in pillDataFrame.Frame])
endFrame = max([max(x) for x in pillDataFrame.Frame])

frameList = []

for i in range(startFrame,endFrame):
    pillArray = []
    print('processing frame ' + str(i) + ' of ' + str(endFrame))
    # print(len(pillDataFrame))
    if i in list(itertools.chain.from_iterable(pillDataFrame['Frame'].values.tolist())):
        for index, pill in pillDataFrame[[i in list for list in pillDataFrame['Frame'].values]].iterrows():
            if i in pill.Frame:
                subIndex = (pill.Frame.index(i))
                if subIndex == 0:
                    pillArray.append([pill.Number, pill.X[subIndex], pill.Y[subIndex], pill.Area[subIndex], pill.Registered])
                else:
                    pillArray.append([pill.Number, pill.X[0:subIndex+1], pill.Y[0:subIndex+1], pill.Area[0:subIndex+1], pill.Registered])

                # print(subIndex)
                # print(len(pill.X))
                if subIndex + 1 == len(pill.X):
                    pillDataFrame = pillDataFrame.drop(index)
                    # print(len(pillDataFrame))



    frameList.append([i,pillArray])


for frame in frameList:
    print(frame)

x=[]
y=[]
labels=[]

for frame in frameList:
    print(frame)

    for f in frame[1]:
        if len(f) > 0:

            lowThreshx = (0,240)
            lowThreshy = (100,100)
            line2, = ax.plot(lowThreshx, lowThreshy, color='black')
            highThreshx = (0, 240)
            highThreshy = (300, 300)
            line3, = ax.plot(highThreshx, highThreshy, color='black')

            # x.append(frame[1][0][1])
            # y.append(frame[1][0][2])
            x=f[1]
            y=f[2]
            area=f[3]
            registered=f[4]
            label = frame[0]
            labels.append(label)
            color = cm.rainbow(label) #TODO: This needs work
            line1, = ax.plot(x, y)
            # ax.plot.set_ydata(frame[1][0][0][2])
            # ax.plot.set_xdata(frame[1][0][0][1])

            line1.set_xdata(x)
            line1.set_ydata(y)

            if registered:
                circleColor = 'g'
            else:
                circleColor = 'r'

            if type(x) == type([]):
                circle1 = plt.Circle((x[-1], y[-1]),math.sqrt(area[-1]/math.pi),color= circleColor)
            else:
                circle1 = plt.Circle((x, y), math.sqrt(area/math.pi),color = circleColor)


            ax.add_patch(circle1)

            fig.canvas.draw()
            fig.show()
            plt.pause(0.005)
            # line1.pop(0)
            if len(ax.lines) > 10:
                # ax.lines.pop(5)
                l = ax.lines.pop(3)
                # l.remove()
                del l
        else:
            line1, = ax.plot([0], [0], 'b-')
            x=[]
            y=[]
            labels = []

    for obj in ax.findobj(match=type(plt.Circle(1, 1))):
        obj.remove()


#
# #This does not by frame yet
# for index, pill in data.iterrows():
#     X = pill.X.strip("[]").split(",")
#     Y = pill.Y.strip("[]").split(",")
#     AREA = pill.Area.strip("[]").split(",")
#     X = [int(x) for x in X]
#     Y = [-int(y) for y in Y]
#     AREA = [float(area) for area in AREA]
#
#
#
# #This does not by frame yet
# for index, pill in data.iterrows():
#     X = pill.X.strip("[]").split(",")
#     Y = pill.Y.strip("[]").split(",")
#     AREA = pill.Area.strip("[]").split(",")
#     X = [int(x) for x in X]
#     Y = [-int(y) for y in Y]
#     AREA = [float(area) for area in AREA]
#     print(max(AREA))
#     newX=[]
#     newY=[]
#     for i in range(len(X)):
#         circle1 = plt.Circle((X[i], Y[i]), AREA[i]/50)
#
#         newX.append(X[i])
#         newY.append(Y[i])
#         for obj in ax.findobj(match=type(plt.Circle(1, 1))):
#             obj.remove()
#         ax.add_patch(circle1)
#         ax.plot(newX, newY,label=index)
#         fig.canvas.draw()
#         fig.show()
#         plt.pause(0.005)
#
#     # ax.plot(X,Y)
#     # plt.pause(0.05)
# # plt.xlim([0, 300])
# # plt.ylim([0, -400])
# plt.show()
plt.close(fig)