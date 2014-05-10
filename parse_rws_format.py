#
# parse rws file format
#
#
# written by Mark Grandi - May 9th 2014
#

import argparse, sys, traceback


def main(args):
    '''
    @param args - the namespace object given to us by argparse'''


    # read the header of the file, 2047 bytes
    args.rwsFile.read(2047)
    print("reading 2047")

    # now loop and read the audio data, and the null bytes
    counter = 0
    while True:
        counter += 1

        if counter == 10000:
            import pdb;pdb.set_trace()
        print("\tpos is {}".format(args.rwsFile.tell()))
        # test to see if we need to break
        oldPos = args.rwsFile.tell()
        testData = args.rwsFile.read(10)
        print("reading 10")

        if testData == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' or len(testData) == 0:
            # at the end of the file
            print("reached 10 null bytes after reading null bytes..probably at end of file (position {})".format(oldPos))
            break

        # put back at old position
        args.rwsFile.seek(oldPos)

        # read audio data
        iterAudioData = args.rwsFile.read(32796)
        print("reading 32796")

        # null bytes
        args.rwsFile.read(2020)
        print("reading 2020")

        # write to pcm file
        args.pcmFile.write(iterAudioData)

    print("finished")


def printTraceback():
    '''prints the traceback'''

    # get variables for the method we are about to call
    exc_type, exc_value, exc_traceback = sys.exc_info()

    # print exception
    traceback.print_exception(exc_type, exc_value, exc_traceback)

if __name__ == "__main__":
    # if we are being run as a real program

    parser = argparse.ArgumentParser(description="parses a rws audio file (xbox 360) and converts it to pcm", 
    epilog="Copyright Mark Grandi, May 9, 2014")

    parser.add_argument("rwsFile", type=argparse.FileType("rb"), help="the input RWS file")
    parser.add_argument("pcmFile", type=argparse.FileType("wb"), help="the output PCM file")

    try:
        main(parser.parse_args())
    except Exception as e: 
        print("Something went wrong...error: {}".format(e))
        print("##################")
        printTraceback()
        print("##################")
        sys.exit(1)