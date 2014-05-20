#
# parse rws file format
#
#
# written by Mark Grandi - May 9th 2014
#

import argparse, sys, traceback, os, os.path, subprocess, tempfile, shutil


def main(args):
    '''
    @param args - the namespace object given to us by argparse'''

    # recurse and find .rws files
    filesToProcess = list()

    for dirpath, dirnames, filenames in os.walk(args.rwsFolder):

        for iterFileName in filenames:

            if os.path.splitext(iterFileName)[1].lower() == ".rws":
                filesToProcess.append(os.path.join(dirpath, iterFileName))



    # go through each rws file and convert it

    tempdir = tempfile.TemporaryDirectory()

    print("Temporary directory is {}".format(tempdir.name))

    for iterFile in filesToProcess:

        filename = os.path.split(iterFile)[1]

        pcmFilePath = os.path.join(tempdir.name, os.path.splitext(filename)[0] + ".pcm")

        with open(iterFile, "rb") as rwsFile:

            with open(pcmFilePath, "wb") as pcmFile:

                # read the header of the file, 2047 bytes
                rwsFile.read(2047)

                # now loop and read the audio data, and the null bytes
                counter = 0
                while True:
                    counter += 1

                    
                    # test to see if we need to break
                    oldPos = rwsFile.tell()
                    testData = rwsFile.read(10)

                    if testData == b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' or len(testData) == 0:
                        # at the end of the file
                        break

                    # put back at old position
                    rwsFile.seek(oldPos)

                    # read audio data
                    iterAudioData = rwsFile.read(32796)

                    # null bytes
                    rwsFile.read(2020)

                    # write to pcm file
                    pcmFile.write(iterAudioData)

                if args.justDumpRaw:

                    # we are not converting, just dumping the raw pcm file 
                    outputPcm = os.path.join(args.wavFolder, os.path.splitext(filename)[0] + ".pcm")

                    shutil.copyfile(pcmFilePath, outputPcm)
                    print("finished {}: raw pcm copied to {}".format(filename, outputPcm))

                else:
                    # convert as normal
                    outputWav = os.path.join(args.wavFolder, os.path.splitext(filename)[0] + ".wav")

                    # sox -t raw -r 44100 -e signed-integer -b 16 <input file> <output file>
                    subprocess.call(["sox", "-t", "raw", "-r", "44100", "-e", "signed-integer", "-b", "16", 
                        "--endian", "little", "-c", "2", pcmFilePath, outputWav])
                    print("finished {}: converted and saved to {}".format(filename, outputWav))

    # delete temporary directory
    tempdir.cleanup()


def printTraceback():
    '''prints the traceback'''

    # get variables for the method we are about to call
    exc_type, exc_value, exc_traceback = sys.exc_info()

    # print exception
    traceback.print_exception(exc_type, exc_value, exc_traceback)


def isDirectoryType(stringArg):
    ''' helper method for argparse to see if the argument is a directory
    @param stringArg - the argument we get from argparse
    @return the path if it is indeed a directory, or raises ArgumentTypeError if its not.'''

    path = os.path.realpath(os.path.normpath(stringArg))

    if not os.path.isdir(path):

        raise argparse.ArgumentTypeError("{} is not a directory!".format(path))

    return path


if __name__ == "__main__":
    # if we are being run as a real program

    parser = argparse.ArgumentParser(description="parses a rws audio file (xbox 360) and converts it to pcm", 
    epilog="Copyright Mark Grandi, May 9, 2014")

    parser.add_argument("rwsFolder", type=isDirectoryType, help="the folder containing .RWS files")
    parser.add_argument("wavFolder", type=isDirectoryType, help="the folder where we output the .wav files")
    parser.add_argument("--justDumpRaw", action="store_true", help="if set then we will just dump the raw .pcm files to "
        "wavFolder and not run them through sox")

    try:
        main(parser.parse_args())
    except Exception as e: 
        print("Something went wrong...error: {}".format(e))
        print("##################")
        printTraceback()
        print("##################")
        sys.exit(1)