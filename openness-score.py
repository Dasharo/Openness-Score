#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path
import subprocess
from coreboot import DasharoCorebootImage
from uefi import UEFIImage
from argparse import ArgumentParser, RawTextHelpFormatter, SUPPRESS

version = 'v0.1.0'


class ObligingArgumentParser(ArgumentParser):

    def error(self, message):
        sys.stderr.write('Error: %s\n' % message)
        self.print_help()
        sys.exit(2)


def check_file(file):
    fw_img = Path(file)

    cbfs_error_string = 'E: Selected image region is not a valid CBFS.'
    uefiextract_error_string = 'parse: not a single Volume Top File ' \
                               'is found, the image may be corrupted'

    if not fw_img.is_file():
        sys.exit('ERROR: \'%s\' file does not exist' % file)

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

    try:
        subprocess.run(['lzma', '-V'],
                       stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        sys.exit('ERROR: lzma not found, please install it first.')

    cbfstool_check = subprocess.run(['cbfstool', file, 'print'],
                                    text=True, capture_output=True)
    fw_is_cbfs = cbfs_error_string not in cbfstool_check.stderr

    uefiextract_check = subprocess.run(['UEFIExtract', file, 'report'],
                                       text=True, capture_output=True)
    fw_is_uefi = uefiextract_error_string not in uefiextract_check.stdout

    if not fw_is_uefi and not fw_is_cbfs:
        sys.exit('ERROR: Could not recognize firmware binary.')

    return fw_is_cbfs, fw_is_uefi


def export_data(args, image):

    output_path = Path.cwd()

    if args.output is not None:
        output_path = Path(args.output)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            sys.exit('You do not have permission to write to %s' % args.output)

    Path(output_path.joinpath('%s_openness_score.md' %
                              Path(args.file).name)).unlink(missing_ok=True)
    Path(output_path.joinpath('%s_openness_score.md' %
                              Path(args.file).name)).touch()
    image.export_markdown(output_path.joinpath(
                          '%s_openness_score.md' % Path(args.file).name))
    image.export_charts(output_path)


def main():

    parser = ObligingArgumentParser(
        description='Calculate Dasharo Openness Score for firmware images\n',
        formatter_class=RawTextHelpFormatter, add_help=False)

    parser.add_argument('file', help='Firmware binary file to be parsed',
                        nargs='?')
    parser.add_argument('-h', '--help', action='help', help=SUPPRESS)
    parser.add_argument('-o', '--output', default='out/', help='\n'.join([
                        'Specifies the directory where to store the results']))
    parser.add_argument('-v', '--verbose', help=SUPPRESS, action='store_true')
    parser.add_argument('-V', '--version', action='version',
                        version='Dasharo Openness Score {}'.format(version))

    args = parser.parse_args()

    if args.verbose:
        print(args)

    if not args.file:
        parser.print_help(sys.stderr)
        sys.exit(0)

    fw_is_cbfs, fw_is_uefi = check_file(args.file)

    if fw_is_cbfs:
        print('\'%s\' detected as Dasharo image' % args.file)
        print('\n\n\'%s\' Dasharo image statistics:' % args.file)
        DasharoCbImg = DasharoCorebootImage(args.file, args.verbose)
        print(DasharoCbImg)
        export_data(args, DasharoCbImg)
    elif fw_is_uefi:
        print('\'%s\' detected as vendor image' % args.file)
        print('\n\n\'%s\' vendor image statistics:' % args.file)
        VendorImg = UEFIImage(args.file, args.verbose)
        print(VendorImg)
        export_data(args, VendorImg)


if __name__ == '__main__':
    main()
