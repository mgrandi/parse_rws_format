#!/usr/bin/env python3
#
#
# version 2 of the 'convert RWS to FLAC' script
#
# written by Mark Grandi - Jun 4, 2014
#

import argparse, sys, struct, os, os.path, subprocess, tempfile, shutil, logging, pprint
from enum import Enum
from collections import namedtuple

ENDIANNESS = ">" # big endian to start out with

def _read(fileObj, formatStr, overrideEndian=None):
    ''' helper to use struct.unpack() to read data, returns what struct.unpack returns, aka a tuple

    @param fileObj - the file obj to read from
    @param formatStr - the format string passed to unpack()
    @param overrideEndian - by default we use the ENDIANNESS global variable to tell what endian we use
        but if overrideEndian is use, we use that instead of the ENDIANNESS variable
    '''

    tmpstr = ""
    if not overrideEndian:
        tmpstr = "{}{}".format(ENDIANNESS,formatStr)
    else:
        tmpstr = "{}{}".format(overrideEndian,formatStr)

    return struct.unpack(tmpstr, fileObj.read(struct.calcsize(tmpstr)))

def _readRwsCString(fileObj):
    ''' this reads a null terminated string , but for some reason these
    are padded to 16 bytes with 0xAB characters.... so this advances the file's
    pointer to the correct spot

    @return a string'''

    startPos = fileObj.tell()
    # need to read bytes until we get null byte cause this is a null
    # terminated c string
    stringBuffer = bytearray()
    while True:

        tmp = fileObj.read(1)
        if tmp is not None and len(tmp) != 0:

            if tmp != b'\x00':
                stringBuffer += tmp
            else:
                # found the null terminator

                # but we need to read up to a 16 byte padding boundary
                endPos = fileObj.tell()
                remainingChars = 16 - ((endPos - startPos) % 16)
                fileObj.read(remainingChars)

                # now we can return the string 
                return stringBuffer.decode("utf-8")

        else:
            # end of file?
            sys.exit("unexpected end of file in _readRwsCString(), file position is at {}".format(fileObj.tell()))
            #return stringBuffer.decode("utf-8")

class RWSChunkType(Enum):
    ''' enum that describes the different chunk types'''
    AudioContainer = 0x0000080d
    AudioHeader = 0x0000080e
    AudioData = 0x0000080f

'''
namedtuple that holds the information for a track's 'organization', used in RWSAudioTrack
'''
TrackOrganization = namedtuple("TrackOrganization", 
    ["unknown7", "clusterSize", "unknown8", "bytesUsedPerCluster", "trackStartOffset" ])

''' named tuple that holds the information for a track's "parameters", used in RWSAudioTrack
'''
TrackParameters = namedtuple("TrackParameters", 
    ["sampleRate", "unknown9", "trackDataSize", "unknown10", "numChannels", "unknown11",
    "unknown12", "unknown13", "unknown14"])

'''
named tuple that just holds the information in a RWS Chunk Header
@param chunkType - a RWSChunkType instance
@param chunkSize - number
@param chunkVersion - number

'''
RWSChunkHeader = namedtuple("RWSChunkheader", ["chunkType", "chunkSize", "chunkVersion"])



class RWSAudioHeaderSegment:

    # # 24 bytes, 4 bytes, 4 bytes, 4 bytes, 16 bytes, C String padded to 16 bytes

    def __init__(self):
        self.unknown15 = None
        self.dataSize = -1
        self.unknown16 = None
        self.unknown17 = None
        self.unknown18 = None
        self.segmentName = ""


    def __str__(self):

        return "<RWSAudioHeaderSegment:  dataSize: {}, segmentName: {} >".format(self.dataSize, self.segmentName)


    def __repr__(self):
        return str(self)

class RWSAudioTrack:
    ''' class that holds track specific information'''

    def __init__(self):
        ''' constructor'''

        self.trackOrganization = None # a TrackOrganization object
        self.trackParameters = None # a TrackParameters object
        self.trackName = ""

    def __str__(self):
        ''' tostring override'''

        return "<RWSAudioTrack: trackOrganization: {}, trackParameters: {}, trackName: {} >".format(
            self.trackOrganization, self.trackParameters, self.trackName)

    def __repr__(self):
        return str(self)

class RWSAudioHeader:
    ''' class that describes the AudioHeader data'''


    def __init__(self):
        '''constructor'''

        self._fileStartPos = -1

        self.headerSize = -1
        self.unknown1 = None # this used to be 36 bytes but now is 28 bytes
        self.numSegments = -1 # this used to be bytes 28-32 of the old unknown1
        self.unknown1Point5 = None # this used to be bytes 32-36 of the old unknown1
        self.numTracks = -1

        self.unknown2 = None
        self.unknown3 = None # some kind of signature?
        self.streamName1 = ""

        # REMOVED BECAUSE we now have a list of these, RWSAudioHeaderSegments
        self.segments = []

        # self.unknown4 = None
        # self.dataSize = -1
        # self.unknown5 = None

        # # for each track
        # # self.unknown6Array = []

        # self.unknown6 = None # some kind of signature?
        # self.streamName2 = ""

        self.trackList = []

    def __str__(self):
        ''' tostring override'''

        return "<RWSAudioHeader: headerSize: {}, numTracks: {}, streamName1: {}, segments: {}, trackList: {} >".format(
            self.headerSize, self.numTracks, self.streamName1, self.segments, self.trackList)

    def __repr__(self):
        return str(self)


    def readHeader(self, fileObj):
        '''reads from a file object and sets the members of this object
        @param fileObj - the file object to read from'''

        self._fileStartPos = fileObj.tell()

        fileSizeInBytes = os.stat(fileObj.fileno()).st_size

        self.headerSize = _read(fileObj, "I")[0] # RANDOMLY BIG ENDIAN??

        logging.debug("Do we switch to little endian? headerSize: {} , fileSize: {}".format(self.headerSize, fileSizeInBytes))
        if self.headerSize > fileSizeInBytes:
            # the endianness is wrong, switch
            # we start out as big endianness so here we switch to little
            logging.debug("\tyes! self.headerSize ({}) > fileSizeInBytes ({}) so its probably not big endian, switching to little endian!".format(self.headerSize, fileSizeInBytes))
            global ENDIANNESS
            ENDIANNESS = "<"
            fileObj.seek(self._fileStartPos)
            self.headerSize = _read(fileObj, "I")[0]
        else:
            logging.debug("\tno, keeping big endian")


        # this is to support multiple segments 
        self.unknown1 = fileObj.read(28)
        self.numSegments = _read(fileObj, "I")[0]
        self.unknown1Point5 = fileObj.read(4)
        ######################################

        self.numTracks = _read(fileObj, "I")[0] # RANDOMLY BIG ENDIAN???
        self.unknown2 = fileObj.read(20)
        self.unknown3 = fileObj.read(16)
        self.streamName1 = _readRwsCString(fileObj)

        ###################
        # NOW WE GO THROUGH EVERY SEGMENT WE HAVE AND CREATE A RWSAudioHeaderSegment
        ###################

        for i in range(self.numSegments):

            tmpSegment = RWSAudioHeaderSegment()


            # TESTING: to see what the first two bytes of these '32' bytes mean
            tmpOne = _read(fileObj, "I")[0]
            tmpTwo = _read(fileObj, "I")[0]
            fileObj.read(16)


            #logging.debug("TESTING: {} - {} = {}".format(tmpTwo, tmpOne, tmpTwo - tmpOne))
            #tmpSegment.unknown15 = fileObj.read(24)


            ###################

            tmpSegment.dataSize = _read(fileObj, "I")[0]
            tmpSegment.unknown16 = fileObj.read(4)
            #tmpSegment.unknown17 = fileObj.read(4) # THESE ARE NO LONGER NEEDED ???
            #tmpSegment.unknown18 = fileObj.read(16) # THESE ARE NO LONGER NEEDED?
            #tmpSegment.segmentName = ""

            self.segments.append(tmpSegment)


        for i in range(self.numSegments):

            tmpSegment = self.segments[i]

            tmpSegment.unknown18 = fileObj.read(20)

        for i in range(self.numSegments):

            tmpSegment = self.segments[i]

            tmpSegment.segmentName = _readRwsCString(fileObj)

        ###################

        logging.debug("segments: {}".format(pprint.pformat(self.segments)))

        # self.unknown4 = fileObj.read(24)
        # self.dataSize = _read(fileObj, ">I")[0] # RANDOMLY BIG ENDIAN???
        # self.unknown5 = fileObj.read(4)

        # # now for each track, read 4 bytes of unknown data...
        # for i in range(self.numTracks):
        #     fileObj.read(4)


        # self.unknown6 = fileObj.read(16)

        # self.streamName2 = _readRwsCString(fileObj)

        # now for each track, create a RWSAudioTrack object for later
        for i in range(self.numTracks):
            self.trackList.append(RWSAudioTrack())

        # now back to parsing the file, for each track
        # create a TrackOrganization object and store it
        for i in range(self.numTracks):

            iterTrack = self.trackList[i]

            _unknown7 = fileObj.read(16)
            _clusterSize = _read(fileObj, "I")[0]
            _unknown8 = fileObj.read(12)
            _bytesUsedPerCluster = _read(fileObj, "I")[0]
            _trackStartOffset = _read(fileObj, "I")[0]

            iterTrack.trackOrganization = TrackOrganization(_unknown7, _clusterSize, 
                _unknown8, _bytesUsedPerCluster, _trackStartOffset)

        # now for each track, create a TrackParameters object
        # and store it
        for i in range(self.numTracks):

            iterTrack = self.trackList[i]

            _sRate = _read(fileObj, "I")[0]
            _u9 = fileObj.read(4)
            _tDataSize = _read(fileObj, "I")[0]
            _u10 = fileObj.read(1)
            _nChannels = _read(fileObj, "B")[0]
            _u11 = fileObj.read(2)
            _u12 = fileObj.read(12)
            _u13 = fileObj.read(16)
            _u14 = fileObj.read(4)

            iterTrack.trackParameters = TrackParameters(_sRate, _u9, _tDataSize, _u10,
                _nChannels, _u11, _u12, _u13, _u14)

        # for each track, read 16 bytes of unknown data (some kind of signature?)
        for i in range(self.numTracks):
            fileObj.read(16)

        # for each track, read the track names
        for i in range(self.numTracks):

            iterTrack = self.trackList[i]

            iterTrack.trackName = _readRwsCString(fileObj)


def _readChunkHeader(fileObj):
    ''' reads the chunk header and returns a RWSChunkHeader object

    these are always little endian

    @param fileObj - the file object to read from
    '''

    tmpType = _read(fileObj, "I", "<")

    # see if its a valid chunk type
    chunkType = None
    try:
        chunkType = RWSChunkType(tmpType[0])
    except ValueError as e:
        # not a value we expect....
        sys.exit("Attempted to read RWS Chunk Type at file position {} but got an invalid value: '{}'"
            .format(fileObj.tell() - struct.calcsize("<I"), tmpType[0]))

    # read size and version now
    tmpSize = _read(fileObj, "I", "<")
    tmpVer = _read(fileObj, "I", "<")

    return RWSChunkHeader(chunkType, tmpSize[0], tmpVer[0])

def parseAndConvertRws(args):
    '''parses and converts an RWS file into WAV
    @param args - the namespace object we get from argparse.parse_args()
    '''

    level = logging.INFO
    if args.verbose:
        level = logging.DEBUG

    logging.basicConfig(level=level)

    # recurse and find .rws files
    filesToProcess = list()
    for dirpath, dirnames, filenames in os.walk(args.rwsFolder):
        for iterFileName in filenames:

            if os.path.splitext(iterFileName)[1].lower() == ".rws":
                filesToProcess.append(os.path.join(dirpath, iterFileName))


    logging.debug("List of files to process: {}".format(pprint.pformat(filesToProcess)))

    # go through each rws file and convert it

    tempdir = tempfile.TemporaryDirectory()
    logging.debug("Temporary directory is {}".format(tempdir.name))

    counter = 1
    for iterFile in filesToProcess:

        logging.info("{}/{} - Processing file '{}'".format(counter, len(filesToProcess), iterFile))

        # open the file
        with open(iterFile, "rb") as f:            

            # read the 'container' chunk header
            initalHeader = _readChunkHeader(f)
            logging.debug("chunk Container header: {}".format(initalHeader))

            # then read the audio header:
            audioChunkHeader = _readChunkHeader(f)
            logging.debug("chunk audio header: {}".format(audioChunkHeader))

            # read the audio header that has stuff like number of tracks, organization, parameters, etc
            audioHeader = RWSAudioHeader()
            audioHeader.readHeader(f)

            # once we are done with that, we still have to read to the rest of the 'chunk' that the 
            # Audio header is placed in. in the RWSAudioHeader object we recorded the file position
            # when we started reading, so we just need to make sure that the file position is
            # audioChunkHeader.chunkSize bytes from the _fileStartPos variable in audioHeader
            needToRead = audioChunkHeader.chunkSize - (f.tell() - audioHeader._fileStartPos)
            f.read(needToRead)

            logging.debug("audio header: {}".format(pprint.pformat(audioHeader)))

            # read the audio data chunk header
            audioDataChunkHeader = _readChunkHeader(f)
            logging.debug("audio data chunk header: {}".format(pprint.pformat(audioDataChunkHeader)))


            # now read up to audioDataChunkHeader.chunkSize bytes and get the audio data
            # read up to tmpTrack.trackOrganization.bytesUsedPerCluster bytes, then skip over the 'cluster waste'
            # (tmpTrack.clusterSize - tmpTrack.trackOrganization.bytesUsedPerCluster), then start again

            # TODO doesn't handle multiple tracks at the moment!

            tmpTrack = audioHeader.trackList[0]

            realDataSize = tmpTrack.trackOrganization.bytesUsedPerCluster
            wasteSize = tmpTrack.trackOrganization.clusterSize - tmpTrack.trackOrganization.bytesUsedPerCluster


            logging.debug("###################")
            logging.debug("realDataSize: {}".format(realDataSize))
            logging.debug("wasteSize: {}".format(wasteSize))
            logging.debug("starting at file pos: {}".format(f.tell()))
            logging.debug("###################")


            # tmpStart = 0
            # tmplimit = 205

            segmentCounter = 1
            logging.info("\tThis track has {} segments".format(len(audioHeader.segments)))

            for iterSegment in audioHeader.segments:

                logging.info("\t\t{}/{} Processing segment: '{}'".format(segmentCounter, len(audioHeader.segments), iterSegment.segmentName))

                # get the path to the temporary file we will be saving the pcm as
                filename = os.path.splitext(os.path.split(iterFile)[1])[0] + "_{}".format(iterSegment.segmentName)
                pcmFilePath = os.path.join(tempdir.name, filename  + ".pcm")

                # limit = 6719488 + 348160 + 69632 + 174080 + 348160
                # tmpcounter = 0
                dataCounter = 0
                #shouldDie = False
                with open(pcmFilePath, "wb") as f2:

                    # loop and write data to the pcm file, skipping over the waste in the clusters
                    while True:
                        # if shouldDie:
                        #     break
                        # #logging.debug("Counter is at: {}".format(tmpcounter))


                        # real audio data
                        #print("reading {} bytes (pos {})".format(realDataSize, f.tell()))
                        tmp = f.read(realDataSize)


                        if tmp == None or len(tmp) == 0:
                            logging.error("Unexpected end of file!, got None or 0 bytes at file pos {}".format(f.tell()))
                            break

                        logging.debug("\t\t\tRead {} bytes (real data), now at {}".format(len(tmp), f.tell()))
                        dataCounter += len(tmp)
                        logging.debug("\t\t\tData read so far: {}".format(dataCounter))


                            

                        # write to output file
                        #print("writing {} bytes to output file, f2 pos: {}\n\n".format(len(tmp), f2.tell()))
                        # if tmpcounter > tmpStart and tmpcounter <= tmplimit:
                        #     f2.write(tmp)


                        # skip waste
                        #print("reading {} waste bytes (pos {})".format(wasteSize, f.tell()))
                        f.read(wasteSize)
                        dataCounter += wasteSize
                        logging.debug("\t\t\tRead {} bytes (waste), dataCounter: {}, filepos now at {}".format(wasteSize, dataCounter, f.tell()))

                        if dataCounter <= iterSegment.dataSize:
                            f2.write(tmp)

                            if dataCounter == iterSegment.dataSize:
                                logging.debug("\t\t\tENDED ON EVEN")
                                break

                        else:
                            onlyWrite = dataCounter - iterSegment.dataSize
                            logging.error("\t\t\tDIDN'T END ON EVEN: onlyWrite: {}".format(onlyWrite))
                            f2.write(tmp[:onlyWrite])
                            shouldDie = True

                    # write a dummmy null byte?
                    f2.write(b'\x00')

                    if args.justDumpRaw:

                            # we are not converting, just dumping the raw pcm file 
                            outputPcm = os.path.join(args.outputFolder, filename + ".pcm")

                            shutil.copyfile(pcmFilePath, outputPcm)
                            logging.info("\t\t\tfinished {}: raw pcm copied to {}".format(filename, outputPcm))

                    else:
                        # convert as normal
                        outputFile = os.path.join(args.outputFolder, filename + ".flac")

                        argList = ["ffmpeg", "-f", "s16be", "-ar", str(tmpTrack.trackParameters.sampleRate), "-ac", 
                            str(tmpTrack.trackParameters.numChannels), "-i", pcmFilePath, "-codec", "flac", 
                            "-compression_level", "8", "-y", outputFile]

                        logging.debug("ffmpeg arguments: {}".format(pprint.pformat(argList)))

                        # TODO manually coding in 48000 sample rate, 2 channels, etc instead of using data from file format
                        try:
                            subprocess.check_output(argList, stderr=subprocess.STDOUT, universal_newlines=True)
                        except subprocess.CalledProcessError as e:
                            sys.exit('''Error calling ffmpeg on file {} !\n\nGot return code {}, while running command: \n'{}'\n\noutput:\n################\n{}\n################'''
                                .format(filename, e.returncode, " ".join(e.cmd), e.output))
                        logging.info("\t\t\t{}: converted and saved to {}".format(filename, outputFile))  

                segmentCounter += 1
        counter += 1

    logging.info("finished")
    # make sure to cleanup the temporary directory
    tempdir.cleanup()



def isFileType(filePath):
    ''' see if the file path given to us by argparse is a file
    @param filePath - the filepath we get from argparse
    @return the filepath if it is a file, else we raise a ArgumentTypeError'''

    from os.path import isfile

    # make sure this is a file
    if not isfile(filePath):
        raise argparse.ArgumentTypeError("{} is not a file!".format(filePath))

    return filePath

def isDirectoryType(stringArg):
    ''' helper method for argparse to see if the argument is a directory
    @param stringArg - the argument we get from argparse
    @return the path if it is indeed a directory, or raises ArgumentTypeError if its not.'''

    path = os.path.realpath(os.path.normpath(stringArg))

    if not os.path.isdir(path):

        raise argparse.ArgumentTypeError("{} is not a directory!".format(path))

    return path

def printTraceback():
    '''prints the traceback'''

    import traceback

    # get variables for the method we are about to call
    exc_type, exc_value, exc_traceback = sys.exc_info()

    # print exception
    traceback.print_exception(exc_type, exc_value, exc_traceback)

if __name__ == "__main__":
    # if we are being run as a real program

    parser = argparse.ArgumentParser(description="parses and converts an RWS file into FLAC", 
    epilog="Copyright Jun 4, 2014 Mark Grandi")

    parser.add_argument('rwsFolder', type=isDirectoryType, help="the folder containing .RWS files")

    parser.add_argument("outputFolder", help="the folder where we output the flac files")
    parser.add_argument("--justDumpRaw", action="store_true", help="if set then we will just dump the raw .pcm files to "
        "outputFolder and not run them through ffmpeg")
    parser.add_argument("--verbose", action="store_true", help="increase verbosity")


    try:
        parseAndConvertRws(parser.parse_args())
    except Exception as e: 
        print("Something went wrong...error: {}".format(e))
        print("##################")
        printTraceback()
        print("##################")
        sys.exit(1)