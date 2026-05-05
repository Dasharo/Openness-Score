#!/usr/bin/env python3
#
# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import sys
from pathlib import Path
import subprocess
import matplotlib.pyplot as plt
from coreboot import DasharoCorebootImage
from uefi import UEFIImage
from argparse import ArgumentParser, RawTextHelpFormatter, SUPPRESS
from git import Repo

"""The Dasharo Openness Score utility's entrypoint"""

script_path = Path(__file__).resolve()
repo_path = script_path.parent.parent

repo = Repo(repo_path)

try:
    version = repo.git.describe(tags=True, always=True, dirty=True) 
except Exception:
    version = "unknown"
"""The utility's version"""


class ObligingArgumentParser(ArgumentParser):
    """An extension to ArgumentParser class providing better error handling

    :param ArgumentParser: The class to be inherited from.
    :type ArgumentParser: ArgumentParser
    """
    def error(self, message):
        """error Prints an error message if there was an error parsing the
        arguments.

        The function also prints a help section and returns an exit code 2.

        :param message: Message to be printed on error.
        :type message: str
        """
        sys.stderr.write('Error: %s\n' % message)
        self.print_help()
        sys.exit(2)


def check_file(file):
    """The function performs all safety checks and detects the input file
    format

    Function checks if all required external utilities like cbfstool,
    UEFIExtract and lzma are present. It also recognizes whether the input
    file is a coreboot image or UEFI image.

    :param file: The input firmware image path
    :type file: str
    :return: Two booleans indicating the CBFS and UEFI format compliance
    :rtype: bool, bool
    """
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
        subprocess.run(['uefiextract'],
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

    uefiextract_check = subprocess.run(['uefiextract', file, 'report'],
                                       text=True, capture_output=True)
    fw_is_uefi = uefiextract_error_string not in uefiextract_check.stdout

    if not fw_is_uefi and not fw_is_cbfs:
        sys.exit('ERROR: Could not recognize firmware binary.')

    return fw_is_cbfs, fw_is_uefi


def export_data(args, image):
    """Calls the image's class methods to export data to the markdown and pie
    charts

    :param args: Program arguments
    :type args: argparse.Namespace
    :param image: An instance of DasharoCorebootImage or UEFIImage
    :type image: DasharoCorebootImage or UEFIImage
    """
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
                          '%s_openness_score.md' % Path(args.file).name),
                          args.mkdocs, version)
    image.export_charts(output_path)


def compare_scores(dasharo_image, proprietary_image):
    """Compares metrics between Dasharo and proprietary firmware.

    :param dasharo_image: Dasharo image
    :type dasharo_image: DasharoCorebootImage
    :param proprietary_image: Proprietary firmware image
    :type proprietary_image: DasharoCorebootImage

    :return: Three metrics as percentages rounded to 1 decimal: Closed source difference, Data size difference, Empty space size difference
    :rtype: float, float, float
    """
    closed_source_diff = 100 * (dasharo_image.closed_code_size - proprietary_image.closed_code_size) / proprietary_image.closed_code_size
    data_size_diff = 100 * (dasharo_image.data_size - proprietary_image.data_size) / proprietary_image.data_size
    empty_diff = 100 * (dasharo_image.empty_size - proprietary_image.empty_size) / proprietary_image.empty_size
    return round(closed_source_diff, 1), round(data_size_diff, 1), round(empty_diff, 1)


def export_compared_data(args, dasharo_image, proprietary_image):
    """Calls `openness_score.compare_scores` and saves the output to a Markdown file.

    :param args: Program arguments
    :type args: argparse.Namespace
    :param dasharo_image: Dasharo image
    :type dasharo_image: DasharoCorebootImage
    :param proprietary_image: Proprietary firmware image
    :type proprietary_image: DasharoCorebootImage
    """
    output_path = Path.cwd()

    if args.output is not None:
        output_path = Path(args.output)
        try:
            output_path.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            sys.exit('You do not have permission to write to %s' % args.output)

    closed_source_diff, data_size_diff, empty_diff = compare_scores(dasharo_image, proprietary_image)
    dasharo_name = Path(args.file).name
    proprietary_name = Path(args.compare).name
    output_file = output_path.joinpath('compare.md')
    if Path(output_file).is_file():
        with open(output_file, 'a') as md:
            md.write("| %s | %s | %s | %s | %s | %s |\n" % (args.platform, dasharo_name, proprietary_name, closed_source_diff, data_size_diff, empty_diff))
    else:
        with open(output_file, 'w') as md:
            md.write("# Openness score %s comparison table\n\n" % version)
            md.write("|Platform | Dasharo Firmware file | Proprietary Firmware file | closed-source diff [%] | data size diff [%] | empty space diff [%] |\n")
            md.write("| --- | --- | --- | --- | --- | --- |\n")
            md.write("| %s | %s | %s | %s | %s | %s |\n" % (args.platform, dasharo_name, proprietary_name, closed_source_diff, data_size_diff, empty_diff))


def export_liberation_charts(output_path, dasharo_image, proprietary_image,
                              dasharo_name, proprietary_name):
    """Generates two comparison charts: code liberation and TCB reduction.

    Chart 1 shows how many bytes/% of proprietary closed-source code have been
    replaced by open-source in the Dasharo image ('liberated').

    Chart 2 shows how many bytes/% of new empty space the Dasharo image gains
    over the proprietary image (TCB / attack-surface reduction).

    :param output_path: Directory where PNG files are written.
    :type output_path: Path
    :param dasharo_image: Parsed Dasharo firmware image.
    :param proprietary_image: Parsed proprietary firmware image.
    :param dasharo_name: Display name for the Dasharo binary.
    :type dasharo_name: str
    :param proprietary_name: Display name for the proprietary binary.
    :type proprietary_name: str
    """
    def make_autopct(sizes):
        def autopct(pct):
            val = int(round(pct * sum(sizes) / 100.0))
            return '{:.1f}%\n({:,} B)'.format(pct, val)
        return autopct

    subtitle = '%s  vs  %s' % (dasharo_name, proprietary_name)

    # --- Chart 1: Code Liberation ---
    liberated = proprietary_image.closed_code_size - dasharo_image.closed_code_size

    fig, ax = plt.subplots()
    if liberated > 0:
        sizes = [liberated, dasharo_image.closed_code_size]
        labels = ['liberated', 'remaining closed-source']
        colors = ['#38d430', '#f5f5f5']
        explode = (0.1, 0)
    else:
        sizes = [proprietary_image.closed_code_size, -liberated]
        labels = ['closed-source', 'regression (more closed-source)']
        colors = ['#f5f5f5', '#cc0000']
        explode = (0, 0.1)
    ax.pie(sizes, explode=explode, labels=labels,
           autopct=make_autopct(sizes), colors=colors,
           wedgeprops={'edgecolor': '#272727', 'linewidth': 0.5})
    fig.suptitle('Code liberation\n' + subtitle)
    plt.savefig(str(output_path.joinpath('liberation_chart.png')))
    plt.close()

    # --- Chart 2: TCB / Empty Space Reduction ---
    tcb_reduced = dasharo_image.empty_size - proprietary_image.empty_size

    fig, ax = plt.subplots()
    if tcb_reduced > 0:
        sizes = [tcb_reduced, proprietary_image.empty_size]
        labels = ['TCB reduced (newly empty)', 'previously empty']
        colors = ['#38d430', '#f5f5f5']
        explode = (0.1, 0)
    else:
        sizes = [dasharo_image.empty_size, -tcb_reduced]
        labels = ['empty space', 'TCB increase (less empty)']
        colors = ['#f5f5f5', '#cc0000']
        explode = (0, 0.1)
    ax.pie(sizes, explode=explode, labels=labels,
           autopct=make_autopct(sizes), colors=colors,
           wedgeprops={'edgecolor': '#272727', 'linewidth': 0.5})
    fig.suptitle('TCB / empty space reduction\n' + subtitle)
    plt.savefig(str(output_path.joinpath('tcb_reduction_chart.png')))
    plt.close()


def OpennessScore():
    """Utility's entry point responsible for argument parsing and
    creating firmware image class instances based on detected image format.
    Calls functions to create the reports and pie charts.
    """
    parser = ObligingArgumentParser(
        description='Calculate Dasharo Openness Score for firmware images\n',
        formatter_class=RawTextHelpFormatter, add_help=False)

    parser.add_argument('file', help='Firmware binary file to be parsed',
                        nargs='?')
    parser.add_argument('-c', '--compare', metavar='proprietary_file',
                         help='Compare Dasharo and proprietary firmware scores and store result in a Markdown table.' \
                        ' file should be the Dasharo binary and proprietary_file should  be the proprietary firmware binary.')
    parser.add_argument('-l', '--liberation', metavar='proprietary_file',
                        help='Generate liberation and TCB-reduction charts comparing file (Dasharo) against\n'
                             'proprietary_file. Produces liberation_chart.png and tcb_reduction_chart.png.\n'
                             'Without this flag the single-image liberation-factor chart is used instead.')
    parser.add_argument('-p', '--platform', default='-', help='Platform model to provide to the table when --compare is set.')
    parser.add_argument('-h', '--help', action='help', help=SUPPRESS)
    parser.add_argument('-o', '--output', default='out/', help='\n'.join([
                        'Specifies the directory where to store the results']))
    parser.add_argument('-a', '--microarch', default="", help='\n'.join([
                        'CPU michroarchitecture supported by the firmware binary to be passed to ifdtool']))
    parser.add_argument('-v', '--verbose', help='\n'.join([
                        'Print verbose information during the image parsing']),
                        action='store_true')
    parser.add_argument('-m', '--mkdocs', help='\n'.join([
                        'Export the report for Dasharo mkdocs']),
                        action='store_true')
    parser.add_argument('-V', '--version', action='version',
                        version='Dasharo Openness Score {}'.format(version))

    args = parser.parse_args()

    if args.verbose:
        print(args)

    if not args.file:
        parser.print_help(sys.stderr)
        sys.exit(0)

    if args.compare:
        fw_is_cbfs, _ = check_file(args.file)
        if not fw_is_cbfs:
            print("File must be Dasharo!")
            sys.exit(1)
        DasharoImage = DasharoCorebootImage(args.file, args.verbose, args.microarch)
        fw_is_cbfs, fw_is_uefi = check_file(args.compare)
        if fw_is_cbfs:
            ProprietaryImage = DasharoCorebootImage(args.compare, args.verbose, args.microarch)
        elif fw_is_uefi:
            ProprietaryImage = UEFIImage(args.compare, args.verbose)
        export_compared_data(args, DasharoImage, ProprietaryImage)
    elif args.liberation:
        output_path = Path.cwd()
        if args.output is not None:
            output_path = Path(args.output)
            try:
                output_path.mkdir(parents=True, exist_ok=True)
            except PermissionError:
                sys.exit('You do not have permission to write to %s' % args.output)

        fw_is_cbfs, fw_is_uefi = check_file(args.file)
        if fw_is_cbfs:
            DasharoImage = DasharoCorebootImage(args.file, args.verbose, args.microarch)
        else:
            DasharoImage = UEFIImage(args.file, args.verbose)

        fw_is_cbfs, fw_is_uefi = check_file(args.liberation)
        if fw_is_cbfs:
            ProprietaryImage = DasharoCorebootImage(args.liberation, args.verbose, args.microarch)
        else:
            ProprietaryImage = UEFIImage(args.liberation, args.verbose)

        export_liberation_charts(output_path, DasharoImage, ProprietaryImage,
                                  Path(args.file).name, Path(args.liberation).name)
    else:
        fw_is_cbfs, fw_is_uefi = check_file(args.file)

        if fw_is_cbfs:
            print('\'%s\' detected as Dasharo image' % args.file)
            print('\n\n\'%s\' Dasharo image statistics:' % args.file)
            DasharoCbImg = DasharoCorebootImage(args.file, args.verbose, args.microarch)
            print(DasharoCbImg)
            export_data(args, DasharoCbImg)
        elif fw_is_uefi:
            print('\'%s\' detected as vendor image' % args.file)
            print('\n\n\'%s\' vendor image statistics:' % args.file)
            VendorImg = UEFIImage(args.file, args.verbose)
            print(VendorImg)
            export_data(args, VendorImg)


if __name__ == '__main__':
    OpennessScore()
