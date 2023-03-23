#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path
import subprocess
from coreboot import DasharoCorebootImage


def usage():
    usage_text = 'Usage:\n' \
                 './openness-score.py <vendor_firmware_image_path>' \
                 ' <dasharo_firmware_image_path>\n' \
                 './openness-score.py <dasharo_firmware_image_path>' \
                 ' <vendor_firmware_image_path>\n'
    print(usage_text)


def check_files():
    fw_img1 = Path(sys.argv[1])
    fw_img2 = Path(sys.argv[2])

    cbfs_error_string = 'E: Selected image region is not a valid CBFS.'
    uefiextract_error_string = 'parse: not a single Volume Top File ' \
                               'is found, the image may be corrupted'

    if not fw_img1.is_file():
        sys.exit('ERROR: \'%s\' file does not exist' % sys.argv[1])

    if not fw_img2.is_file():
        sys.exit('ERROR: \'%s\' file does not exist' % sys.argv[2])

    try:
        subprocess.run(['cbfstool'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit('ERROR: cbfstool not found, please install it first.')

    try:
        subprocess.run(['UEFIExtract'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit('ERROR: UEFIExtract not found, please install it first.')

    cbfstool_check = subprocess.run(['cbfstool', sys.argv[1], 'print'],
                                    text=True, capture_output=True)
    fw1_is_cbfs = cbfs_error_string not in cbfstool_check.stderr

    cbfstool_check = subprocess.run(['cbfstool', sys.argv[2], 'print'],
                                    text=True, capture_output=True)
    fw2_is_cbfs = cbfs_error_string not in cbfstool_check.stderr

    if fw1_is_cbfs and fw2_is_cbfs:
        usage()
        sys.exit('ERROR: Both of the two files seem to be Dasharo images.')
    elif not fw1_is_cbfs and not fw2_is_cbfs:
        usage()
        sys.exit('ERROR: Neither of the two image files are Dasharo images.')

    uefiextract_check = subprocess.run(['UEFIExtract', sys.argv[1], 'report'],
                                       text=True, capture_output=True)
    fw1_is_vendor = uefiextract_error_string not in uefiextract_check.stdout

    uefiextract_check = subprocess.run(['UEFIExtract', sys.argv[2], 'report'],
                                       text=True, capture_output=True)
    fw2_is_vendor = uefiextract_error_string not in uefiextract_check.stdout

    if fw1_is_vendor and fw2_is_vendor:
        usage()
        sys.exit('ERROR: Both of the two files seem to be vendor images.')
    elif not fw1_is_vendor and not fw2_is_vendor:
        usage()
        sys.exit('ERROR: Neither of the two files seem to be vendor images.')

    if fw1_is_cbfs and fw2_is_vendor:
        return sys.argv[1], sys.argv[2]

    if fw1_is_vendor and fw2_is_cbfs:
        return sys.argv[2], sys.argv[1]

    sys.exit('ERROR: Could not recognize vendor or Dasharo firmware binary.')


def main():
    if len(sys.argv) == 1:
        usage()
        sys.exit(0)

    if len(sys.argv) != 3:
        usage()
        sys.exit('ERROR: The utility takes exactly two arguments.')

    dasharo_img_file, vendor_img_file = check_files()

    print('\'%s\' detected as Dasharo image' % dasharo_img_file)
    print('\'%s\' detected as vendor image' % vendor_img_file)

    DasharoCbImg = DasharoCorebootImage(dasharo_img_file)


if __name__ == '__main__':
    main()
