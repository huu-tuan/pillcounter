from pillcount import count
#from pillcount import count2
import cProfile
import pstats
import io
import datetime

if __name__ == '__main__':
    import argparse

    now = datetime.datetime.now()
    outName = 'data/' + str(now.strftime("%m-%d-%Y %H %M %S")) + '.avi'

    parser = argparse.ArgumentParser(description='counter configuration')
    # parser.add_argument('--DeviceNum', dest='DeviceNum', default=0, type=int, help='device number of the Camera')
    # parser.add_argument('--InputVideo', dest='InputVideo', default = '', type=str, help='filename of the Input Video')
    parser.add_argument('--DeviceNum', dest='DeviceNum', default=[0], type=list, help='device number of the Camera')
    parser.add_argument('--InputVideo', dest='InputVideo', nargs='+', default = [], type=list, help='filename of the Input Video')
    parser.add_argument('--DisplayVideo', dest='DisplayVideo', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Video Display')
    parser.add_argument('--ModbusCom', dest='ModbusCom', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable Modbus Communication')
    parser.add_argument('--GPIO', dest='GPIO', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable GPIO control')
    parser.add_argument('--Debug', dest='Debug', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Debug output')
    parser.add_argument('--Logging', dest='Logging', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable GPIO control')
    parser.add_argument('--StartFrame', dest='StartFrame', default=1, type=int, help='Set the start frame of a video')
    parser.add_argument('--SaveFrames', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable saving of raw input')
    parser.add_argument('--NumPillsToCount', dest='NumPillsToCount', default=0, type=int, help='Set the number of pills to count before completing execution')
    parser.add_argument('--plotResults', dest='plotResults', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable plotting')
    parser.add_argument('--VidFileName', dest='VidFileName', default = outName, type=str, help='destination of the Video')
    parser.add_argument('--Threshold', dest='Threshold', default=100, type=int, help='Low value for threshold ')
    parser.add_argument('--Diff', dest='Diff',default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Difference Thresholding')
    parser.add_argument('--DiffThresh', dest='DiffThresh', default=20, type=int, help='Low value for diff based threshold ')
    parser.add_argument('--AreaThresh', dest='AreaThresh', default=100, type=int, help='Low value for area ')
    parser.add_argument('--Profile', dest='Profile', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Profiling')
    parser.add_argument("--Crop", nargs="+", default=[0, 0, 0, 0], help='Crop [Top, Bottom, Left, Right')
    parser.add_argument('--PauseOnPill', dest='PauseOnPill', default=0, type=float, help='Set length of pause in seconds when pill is present (Only applicable with saved video input)')
    parser.add_argument('--ResetCleanTubeImage', dest='ResetCleanTubeImage', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Delete stored Clean Tube Image and Create New One')
    parser.add_argument('--VideoLoop', dest='VideoLoop', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']),help='Run the video in an infinite loop')

#camera 2 args
    """
    parser.add_argument('--DeviceNum2', dest='DeviceNum2', default=1, type=int, help='device number of the Camera')
    parser.add_argument('--InputVideo2', dest='InputVideo2', default = '', type=str, help='filename of the Input Video')
    parser.add_argument('--DisplayVideo2', dest='DisplayVideo2', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Video Display')
    parser.add_argument('--Debug2', dest='Debug', default=True, type=lambda x: (str(x).lower() in ['true', '1', 'yes']), help='Enable/Disable Debug output')
    parser.add_argument('--Logging2', dest='Logging', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable GPIO control')
    parser.add_argument('--StartFrame2', dest='StartFrame', default=1, type=int, help='Set the start frame of a video')
    parser.add_argument('--SaveFrames2', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable saving of raw input')
    parser.add_argument('--NumPillsToCount2', dest='NumPillsToCount', default=0, type=int, help='Set the number of pills to count before completing execution')
    parser.add_argument('--plotResults2', dest='plotResults', default = False, type=lambda x: (str(x).lower() in ['true','1', 'yes']), help='Enable/Disable plotting')
    parser.add_argument('--VideoLoop2', dest='VideoLoop', default=False, type=lambda x: (str(x).lower() in ['true', '1', 'yes']),help='Run the video in an infinite loop')
    """
    args = parser.parse_args()
    print(args)

    if args.Profile:
        pr = cProfile.Profile()
        pr.enable()
        count.run(args)
        pr.disable()
        s = io.StringIO()
        ps = pstats.Stats(pr, stream=s).sort_stats('tottime')
        ps.print_stats()

        with open('profile.txt', 'w+') as f:
            f.write(s.getvalue())
    else:
        # print('\n>>> ', args.InputVideo)
        args.InputVideo = ["".join(inp) for inp in args.InputVideo]
        print('\n>>> ', args.InputVideo)
        count.run(args)
