#!/usr/bin/env python3
#
#
# version 2 of the 'convert RWS to wav' script
#
# written by Mark Grandi - Jun 4, 2014
#

import argparse, sys, struct, os, os.path, subprocess
from enum import Enum
from collections import namedtuple

def _read(fileObj, formatStr):
    ''' helper to use struct.unpack() to read data, returns what struct.unpack returns, aka a tuple

    @param fileObj - the file obj to read from
    @param formatStr - the format string passed to unpack()
    '''

    return struct.unpack(formatStr, fileObj.read(struct.calcsize(formatStr)))

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
        self.unknown1 = None
        self.numTracks = -1

        self.unknown2 = None
        self.unknown3 = None # some kind of signature?
        self.streamName1 = ""
        self.unknown4 = None
        self.dataSize = -1
        self.unknown5 = None

        # for each track
        # self.unknown6Array = []

        self.unknown6 = None # some kind of signature?
        self.streamName2 = ""

        self.trackList = []

    def __str__(self):
        ''' tostring override'''

        return "<RWSAudioHeader: headerSize: {}, numTracks: {}, streamName1: {}, streamName2: {}, dataSize: {}, trackList: {} >".format(
            self.headerSize, self.numTracks, self.streamName1, self.streamName2, self.dataSize, self.trackList)

    def __repr__(self):
        return str(self)


    def readHeader(self, fileObj):
        '''reads from a file object and sets the members of this object
        @param fileObj - the file object to read from'''

        self._fileStartPos = fileObj.tell()

        self.headerSize = _read(fileObj, ">I")[0] # RANDOMLY BIG ENDIAN??
        self.unknown1 = fileObj.read(36)
        self.numTracks = _read(fileObj, ">I")[0] # RANDOMLY BIG ENDIAN???
        self.unknown2 = fileObj.read(20)
        self.unknown3 = fileObj.read(16)
        self.streamName1 = _readRwsCString(fileObj)

        self.unknown4 = fileObj.read(24)
        self.dataSize = _read(fileObj, ">I")[0] # RANDOMLY BIG ENDIAN???
        self.unknown5 = fileObj.read(4)

        # now for each track, read 4 bytes of unknown data...
        for i in range(self.numTracks):
            fileObj.read(4)


        self.unknown6 = fileObj.read(16)

        self.streamName2 = _readRwsCString(fileObj)

        # now for each track, create a RWSAudioTrack object for later
        for i in range(self.numTracks):
            self.trackList.append(RWSAudioTrack())

        # now back to parsing the file, for each track
        # create a TrackOrganization object and store it
        for i in range(self.numTracks):

            iterTrack = self.trackList[i]

            _unknown7 = fileObj.read(16)
            _clusterSize = _read(fileObj, ">I")[0]
            _unknown8 = fileObj.read(12)
            _bytesUsedPerCluster = _read(fileObj, ">I")[0]
            _trackStartOffset = _read(fileObj, ">I")[0]

            iterTrack.trackOrganization = TrackOrganization(_unknown7, _clusterSize, 
                _unknown8, _bytesUsedPerCluster, _trackStartOffset)

        # now for each track, create a TrackParameters object
        # and store it
        for i in range(self.numTracks):

            iterTrack = self.trackList[i]

            _sRate = _read(fileObj, ">I")[0]
            _u9 = fileObj.read(4)
            _tDataSize = _read(fileObj, ">I")[0]
            _u10 = fileObj.read(1)
            _nChannels = _read(fileObj, ">B")[0]
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

    @param fileObj - the file object to read from
    '''

    tmpType = _read(fileObj, "<I")

    # see if its a valid chunk type
    chunkType = None
    try:
        chunkType = RWSChunkType(tmpType[0])
    except ValueError as e:
        # not a value we expect....
        sys.exit("Attempted to read RWS Chunk Type at file position {} but got an invalid value: '{}'"
            .format(fileObj.tell() - struct.calcsize("<I"), tmpType[0]))

    # read size and version now
    tmpSize = _read(fileObj, "<I")
    tmpVer = _read(fileObj, "<I")

    return RWSChunkHeader(chunkType, tmpSize[0], tmpVer[0])

def parseAndConvertRws(args):
    '''parses and converts an RWS file into WAV
    @param args - the namespace object we get from argparse.parse_args()
    '''

    # open the file
    with open(args.rwsInputFile, "rb") as f:

        # read the 'container' chunk header
        initalHeader = _readChunkHeader(f)

        print("chunk Container header: {}".format(initalHeader))

        # then read the audio header:
        audioChunkHeader = _readChunkHeader(f)
        print("chunk audio header: {}".format(audioChunkHeader))

        # read the audio header that has stuff like number of tracks, organization, parameters, etc
        audioHeader = RWSAudioHeader()
        audioHeader.readHeader(f)

        # once we are done with that, we still have to read to the rest of the 'chunk' that the 
        # Audio header is placed in. in the RWSAudioHeader object we recorded the file position
        # when we started reading, so we just need to make sure that the file position is
        # audioChunkHeader.chunkSize bytes from the _fileStartPos variable in audioHeader

        needToRead = audioChunkHeader.chunkSize - (f.tell() - audioHeader._fileStartPos)
        f.read(needToRead)

        print("audio header: {}".format(audioHeader))

        # read the audio data chunk header

        audioDataChunkHeader = _readChunkHeader(f)
        print("audio data chunk header: {}".format(audioDataChunkHeader))


        # now read up to audioDataChunkHeader.chunkSize bytes and get the audio data
        # read up to tmpTrack.trackOrganization.bytesUsedPerCluster bytes, then skip over the 'cluster waste'
        # (tmpTrack.clusterSize - tmpTrack.trackOrganization.bytesUsedPerCluster), then start again

        # TODO doesn't handle multiple tracks at the moment!

        tmpTrack = audioHeader.trackList[0]

        realDataSize = tmpTrack.trackOrganization.bytesUsedPerCluster
        wasteSize = tmpTrack.trackOrganization.clusterSize - tmpTrack.trackOrganization.bytesUsedPerCluster

        with open(args.wavOutputFile, "wb") as f2:

            while True:
                # real audio data
                print("reading {} bytes (pos {})".format(realDataSize, f.tell()))
                tmp = f.read(realDataSize)

                if tmp == None or len(tmp) == 0:
                    break

                # write to output file
                print("writing {} bytes to output file, f2 pos: {}\n\n".format(len(tmp), f2.tell()))
                f2.write(tmp)
                
                # skip waste
                print("reading {} waste bytes (pos {})".format(wasteSize, f.tell()))
                f.read(wasteSize)

                

        
        # now run sox
        soxedFilename = os.path.join(os.path.split(args.wavOutputFile)[0], os.path.splitext(os.path.split(args.wavOutputFile)[1])[0] + "_soxed.wav")

        # sox -t raw -r 44100 -e signed-integer -b 16  --endian little -c 2 <input file> <output file>
        subprocess.call(["sox", "-t", "raw", "-r", "48000", "-e", "signed-integer", "-b", "16", 
            "--endian", "little", "-c", "2", args.wavOutputFile, soxedFilename])
        print("finished")


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

if __name__ == "__main__":
    # if we are being run as a real program

    parser = argparse.ArgumentParser(description="parses and converts an RWS file into WAV", 
    epilog="Copyright Jun 4, 2014 Mark Grandi")

    parser.add_argument('rwsInputFile', type=isFileType, help="the input RWS file")

    parser.add_argument("wavOutputFile", help="where to output the .WAV file")
    

    parseAndConvertRws(parser.parse_args())