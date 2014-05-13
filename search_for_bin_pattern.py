#!/usr/bin/env python3
#
# script to look for the DDS magic number in the KXE files
#

# searching for 
# 44 44 53 20 = 'DDS ' (magic number)
with open("/Users/markgrandi/Code/bzr_new/parse_rws_format/LVL000_decompressed.KXE", "rb") as f:

    while True:
        byte = f.read(1)

        if not byte:
            break

        if byte == "D".encode("utf-8"):

            moreData = f.read(3)
            if not moreData or len(moreData) < 3:
                break

            if moreData == "DS ".encode("utf-8"):
                print("DDS signature found at {}".format(f.tell()-4))
                continue