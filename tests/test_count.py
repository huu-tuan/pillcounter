# Unit test used to test functions within 'count.py'
import os,sys,pytest
from pillcount import count
import copy

# Naming convention for test videos:
# <unique number>-<areaThresh>_<Transparent:1,Non-Transparent:0>_<count>
# example: 1-1200_0_26.avi

class Test:
    def __init__(self,fileString):
        self.filepath = fileString
        print(fileString)
        self.testData = fileString.split('\\')[2].split('-')[1].split("_")
        self.areaThresh=int(self.testData[0])
        if self.testData[1] == '1':
            self.diffThresh=15
        else:
            self.diffThresh=50
        self.count=int(self.testData[2].split('.')[0])

    def __str__(self):
        return (self.fileString, self.areaThresh, self.diffThresh)

# @pytest.fixture(autouse=True)
def getTests():
    dirName = '../pillcountertest/data'
    listOfFiles = list()
    testList = []
    for (dirpath, dirnames, filenames) in os.walk(dirName):
        listOfFiles += [os.path.join(dirpath, file) for file in filenames]
    for file in listOfFiles:
        if file.count('_')==2:
            try:
                testList.append(Test(file))
            except:
                print('file invalid: ' + file)
    return testList


class cmdargs:  # Simulated command line data to feed into count program
    DeviceNum = 0
    InputVideo = ''
    DisplayVideo = 0
    ModbusCom = False
    GPIO = False
    Debug = False
    Logging = False
    StartFrame = 0
    SaveFrames = False
    NumPillsToCount = 0
    plotResults = False
    VidFileName = ''
    Diff = True
    DiffThresh = 30
    AreaThresh = 100
    Profile = False
    Crop = [0, 0, 0, 0]
    PauseOnPill = False
    ResetCleanTubeImage = True
    VideoLoop = False

def idfn(val):
    print(val.filepath)
    return val.filepath

@pytest.mark.parametrize("test", getTests(), ids=idfn)
def test_eval(test):
    cmdargs_ = copy.copy(cmdargs)
    cmdargs_.InputVideo = test.filepath
    cmdargs_.AreaThresh = test.areaThresh
    cmdargs_.DiffThresh = test.diffThresh
    print(cmdargs_.InputVideo)
    # imageFileName = 'images\CleanTube.jpg'
    # if os.path.exists(imageFileName):
    #     os.remove(imageFileName)
    resultCount = count.run(cmdargs_)
    print('Expected: ' + str(test.count))
    print('Actual: ' + str(resultCount))
    assert test.count -1 <= resultCount <= test.count

