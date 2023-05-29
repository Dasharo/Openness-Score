# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import re
import os
import sys
import subprocess
from typing import List
from pathlib import Path
import matplotlib.pyplot as plt

"""This module is responsible for parsing UEFI images"""


class UEFIImage:
    """UEFIImage class

    The main class representing an UEFI firmware image
    """

    debug = False

    # Format: Type, Subtype, Name
    EMPTY_REGION_PADDING = [
        # First level padding present between IFD regions
        ['Padding', 'Empty (0xFF)', '- Padding'],
        ['Padding', 'Empty (0x00)', '- Padding']
    ]
    """A list of entries known to be top-level empty paddings"""

    EMPTY_BIOS_PADDING = [
        # Second level padding between volumes (ME firmware can also contain
        # such padding thus in separate array)
        ['Padding', 'Empty (0xFF)', '-- Padding'],
        ['Padding', 'Empty (0x00)', '-- Padding']
    ]
    """A list of entries known to be second-level empty paddings"""

    NON_EMPTY_REGION_PADDING = [
        # First level padding present between IFD regions
        ['Padding', 'Non-empty', '- Padding']
    ]
    """A list of entries known to be top-level non-empty paddings"""

    NON_EMPTY_BIOS_PADDING = [
        # Second level padding between volumes (ME firmware can also contain
        # such padding thus in separate array)
        ['Padding', 'Non-empty', '-- Padding']
    ]
    """A list of entries known to be second-level non-empty paddings"""

    # TODO: Ensure Reserved1, Reserved2, PTT, DevExp1 and DevExp2 are
    # indeed closed-source.
    CLOSED_SOURCE_REGIONS = ['ME', 'DevExp1', 'DevExp2', 'Microcode', 'EC',
                             'IE', 'PTT', 'Reserved1', 'Reserved2']
    """A list of regions known to be closed-source"""

    DATA_REGIONS = ['Descriptor', 'GbE', 'PDR', '10GbE1', '10GbE2']
    """A list of regions known to contain data only"""

    item_patterns = [
        r"^\s(?P<type>.*?)\s+\|",
        r"\s(?P<subtype>.*?)\s+\|",
        r"\s+(?P<base>[A-FN\/0-9]+?)\s+\|",
        r"\s(?P<size>[A-F0-9]+?)\s\|",
        r"\s(?P<crc32>[A-Z0-9]+?)\s\|",
        r"\s(?P<name>.*?)$"
    ]

    report_regexp = re.compile(''.join(item_patterns), re.MULTILINE)
    bios_region_started = False

    def __init__(self, image_path, verbose=False):
        """UEFIImage class init method

        Initializes the class fields for storing the firmware image components
        classified to specific groups. Also calls
        :meth:`~coreboot.UEFIImage._parse_uefi_image` and
        :meth:`~coreboot.UEFIImage._calculate_metrics` methods to parse the
        image and calculate the metrics.

        :param image_path: Path the the firmware image file being parsed.
        :type image_path: str
        :param verbose: Optional parameter to turn on debug information during
                        the image parsing, defaults to False
        :type verbose: bool, optional
        """
        self.image_path = image_path
        """Path to the image represented by UEFIImage class"""
        self.image_size = os.path.getsize(image_path)
        """Image size in bytes"""
        self.uefi_entries = {}
        """Dictionary holding the UEFI image entries"""
        self.volumes = []
        """List holding the UEFI Firmware Volumes"""
        self.regions = []
        """List holding the Intel firmware image regions"""
        self.bios_region = {}
        """Dictionary holding the UEFI image entries inside BIOS region"""
        self.num_regions = 0
        """Total number of Intel firmare image regions"""
        self.num_volumes = 0
        """Total number of the UEFI Firmware Volumes"""
        self.num_entries = 0
        """Total number of all UEFI image entries"""
        self.open_code_size = 0
        """Total number of bytes classified as open-source code"""
        self.closed_code_size = 0
        """Total number of bytes classified as closed-source code"""
        self.data_size = 0
        """Total number of bytes classified as data"""
        self.empty_size = 0
        """Total number of bytes classified as empty"""
        self.closed_code_regions = []
        """List holding image regions filled with closed-source code"""
        self.data_regions = []
        """List holding image regions filled with data"""
        self.empty_spaces = []
        """List holding empty image regions"""

        self.debug = verbose
        """Used to enable verbose debug output from the parsing process"""

        self._parse_uefi_image()
        self._calculate_metrics()

    def __len__(self):
        """Returns the length of the UEFI firmware image

        :return: Length of the firmware binary file
        :rtype: int
        """
        return self.image_size

    def __repr__(self):
        """UEFIImage class representation

        :return: class representation
        :rtype: str
        """
        return "UEFIImage()"

    def __str__(self):
        """Returns string representation of the firmware image

        Prints the firmware image statistics.

        :return: UEFIImage string representation
        :rtype: str
        """
        return 'Vendor UEFI image %s:\n' \
               '\tImage size: %d\n' \
               '\tNumber of entries: %d\n' \
               '\tNumber of regions: %d\n' \
               '\tNumber of volumes: %d\n' \
               '\tTotal open-source files size: %d\n' \
               '\tTotal closed-source files size: %d\n' \
               '\tTotal data size: %d\n' \
               '\tTotal empty size: %d' % (
                    self.image_path,
                    self.image_size,
                    self.num_entries,
                    self.num_regions,
                    self.num_volumes,
                    self.open_code_size,
                    self.closed_code_size,
                    self.data_size,
                    self.empty_size)

    def _parse_uefi_image(self):
        """Parses the UEFI image with UEFIExtract and extracts information
        about its components

        Parses the output of 'UEFIExtract self.image_path report' and extract
        the UEFI image components to a self.uefi_entries dictionary using the
        :const:`uefi.UEFIImage.report_regexp` regular expression.

        UEFI regions are saved in the :attr:`uefi.UEFIImage.regions`. If the
        region is a BIOS region, it is also saved to
        :attr:`uefi.UEFIImage.bios_region` for later use.

        If self.debug is True, all UEFI entries and regions with their
        attributes are printed on the console at the end.
        """
        cmd = ['UEFIExtract', self.image_path, 'report']
        uefi_extract = subprocess.run(cmd, text=True, capture_output=True)

        if uefi_extract.returncode != 0:
            sys.exit('ERROR: UEFIExtarct returned an error')

        file = open(''.join([self.image_path, '.report.txt']), mode='r')
        uefi_report = file.read()
        file.close()

        for match in re.finditer(self.report_regexp, uefi_report):
            # Update the size if we dealing with capsule images.
            # There should be only one entry with type Image
            if match.group('type') == 'Image':
                if int(match.group('size'), 16) != self.image_size:
                    self.image_size = int(match.group('size'), 16)
            # Compressed sections have no base. Avoid integer casting errors to
            # by setting base to -1.
            if match.group('base') == 'N/A':
                self.uefi_entries[self.num_entries] = {
                    'type': match.group('type'),
                    'subtype':  match.group('subtype'),
                    'base': -1,
                    'size':  int(match.group('size'), 16),
                    'name':  match.group('name'),
                }
            else:
                self.uefi_entries[self.num_entries] = {
                    'type': match.group('type'),
                    'subtype':  match.group('subtype'),
                    'base': int(match.group('base'), 16),
                    'size': int(match.group('size'), 16),
                    'name': match.group('name'),
                }

            if self._entry_is_region(self.uefi_entries[self.num_entries]):
                self.regions.append(self.uefi_entries[self.num_entries])
                self.num_regions += 1
                if match.group('subtype') == 'BIOS':
                    self.bios_region = self.uefi_entries[self.num_entries]

            self.num_entries += 1

        if self.debug:
            print("UEFI image entries:")
            [print(self.uefi_entries[i]) for i in range(self.num_entries)]
            print("UEFI image regions:")
            [print(region) for region in self.regions]

    def _entry_is_volume(self, entry):
        """Helper function to check if UEFI entry is an UEFI Firmware Volume

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is a Firmware Volume, False otherwise.
        :rtype: bool
        """
        # Take only the top level volumes. Volumes that are nested/compressed
        # will have size of -1 (N/A).
        if entry['type'] == 'Volume' and entry['size'] != -1:
            return True
        else:
            return False

    def _is_entry_nested_volume(self, entry):
        """Helper function to check if UEFI entry is an UEFI Firmware Volume
        nested in another already detected UEFI Firmware Volume

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is a Firmware Volume is nested, False
                 otherwise.
        :rtype: bool
        """
        # Ignore nested uncompressed volumes, they will be handled inside
        # UEFIVolume class. FSP-S is an example where multiple uncompressed
        # volumes exist.
        for i in range(self.num_volumes):
            volume_start = self.volumes[i].volume_base
            volume_end = (self.volumes[i].volume_base +
                          self.volumes[i].volume_size)
            if (entry['base'] >= volume_start) and \
               (entry['base'] + entry['size'] <= volume_end):
                return True

        return False

    def _entry_is_region(self, entry):
        """Helper function to check if UEFI entry is a region

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is a region, False otherwise.
        :rtype: bool
        """
        if entry['type'] == 'Region':
            return True
        else:
            return False

    def _is_entry_inside_bios_region(self, entry):
        """Helper function to check if UEFI entry resides inside the BIOS
        region

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is inside the BIOS region, False otherwise.
        :rtype: bool
        """
        # We ignore nested/compressed entries. We only care about padding that
        # have a base and size which are inside BIOS region. We handle regions
        # separately.
        bios_start = self.bios_region['base']
        bios_end = self.bios_region['base'] + self.bios_region['size']
        if entry['base'] == -1:
            return False
        elif self._entry_is_region(entry):
            return False
        elif (entry['base'] < bios_start) or (entry['base'] >= bios_end):
            return False
        elif (entry['base'] >= bios_start) and \
             (entry['base'] + entry['size'] <= bios_end):
            return True
        else:
            print('ERROR: Could not determine if entry is in BIOS region')
            print(entry)
            return False

    def _classify_entries(self):
        """Classifies the UEFI entries and regions into basic categories

        Each detected UEFI region is being classified into 2 basic categories
        (utility assumes there is no open-source code in vendor images and
        empty spaces are counted separately - nto as regions) and appended to
        respective lists. UEFI Firmware Volumes inside the BIOS region are
        processed separately and not included here.

        :attr:`uefi.UEFIImage.closed_code_regions` are appended with UEFI
        regions which type is found in
        :const:`uefi.UEFIImage.CLOSED_SOURCE_REGIONS`

        :attr:`uefi.UEFIImage.data_regions` are appended with UEFI regions
        which type is found in :const:`uefi.UEFIImage.DATA_REGIONS`. Every
        other regions which did not fall into these categories are classified
        as closed-source code and appended to
        :attr:`uefi.UEFIImage.closed_code_regions`.

        Next, the entries are being processed. For simplicity we only classify
        entries that do not belong to Firmware Volumes, so they are either
        data (non-empty pads) or empty (empty padding). If an entry is a
        Firmware Volume and resides inside the BISO region, a new instance of
        :class:`uefi.UEFIVolume` is created and appended to
        :attr:`uefi.UEFIImage.volumes` list.

        Entries are counted as data if their names are found in
        :const:`uefi.UEFIImage.NON_EMPTY_REGION_PADDING` or are inside BIOS
        region and their names are found in
        :const:`uefi.UEFIImage.NON_EMPTY_BIOS_PADDING`. Entries are counted as
        empty if their names are found in
        :const:`uefi.UEFIImage.EMPTY_REGION_PADDING` or are inside BIOS region
        and their names are found in
        :const:`uefi.UEFIImage.EMPTY_BIOS_PADDING`.

        If self.debug is True, all so far classified regions with their
        attributes are printed on the console at the end.
        """
        # Regions first
        for i in range(self.num_regions):
            if self.regions[i]['subtype'] in self.CLOSED_SOURCE_REGIONS:
                self.closed_code_regions.append(self.regions[i])
            elif self.regions[i]['subtype'] in self.DATA_REGIONS:
                self.data_regions.append(self.regions[i])
            elif self.regions[i]['subtype'] == 'BIOS':
                # Do nothing. BIOS region is comprised of FVs which are parsed
                # in next loop.
                continue
            else:
                print('WARNING: Found unclassified region %s.\n'
                      'Counting it as closed-source.' %
                      self.regions[i]['subtype'])
                self.closed_code_regions.append(self.regions[i])

        for i in range(self.num_entries):
            if self._entry_is_volume(self.uefi_entries[i]) and \
               self._is_entry_inside_bios_region(self.uefi_entries[i]):
                if not self._is_entry_nested_volume(self.uefi_entries[i]):
                    volume = UEFIVolume(self.uefi_entries, i, self.debug)
                    self.volumes.append(volume)
                    self.num_volumes += 1
                    print(volume)

            entry_type = [self.uefi_entries[i]['type'],
                          self.uefi_entries[i]['subtype'],
                          self.uefi_entries[i]['name']]
            # Detect the empty and non-empty paddings between volumes and
            # regions only.
            if entry_type in self.EMPTY_BIOS_PADDING and \
               self._is_entry_inside_bios_region(self.uefi_entries[i]):
                self.empty_spaces.append(self.uefi_entries[i])
            elif (entry_type in self.NON_EMPTY_BIOS_PADDING) and \
                 (self._is_entry_inside_bios_region(self.uefi_entries[i])):
                self.data_regions.append(self.uefi_entries[i])
            elif entry_type in self.EMPTY_REGION_PADDING:
                self.empty_spaces.append(self.uefi_entries[i])
            elif entry_type in self.NON_EMPTY_REGION_PADDING:
                self.data_regions.append(self.uefi_entries[i])

        if self.debug:
            print("UEFI image empty entries:")
            for i in range(len(self.empty_spaces)):
                print(self.empty_spaces[i])
            print("UEFI image data entries:")
            for i in range(len(self.data_regions)):
                print(self.data_regions[i])
            print("UEFI image closed-code entries:")
            for i in range(len(self.closed_code_regions)):
                print(self.closed_code_regions[i])

    def _sum_sizes(self, regions):
        """Sums the size of the regions

        :param regions: Dictionary of regions to sum
        :type regions: dict
        :return: Sum of the region sizes
        :rtype: int
        """
        return sum(list(r['size'] for r in regions))

    def _calculate_metrics(self):
        """Calculates the sizes of the four basic firmware components
        categories

        The function calls the :meth:`uefi.UEFIImage._classify_entries` and
        then sums up the classified regions sizes.

        :attr:`uefi.UEFIImage.closed_code_regions` sizes sum is added to
        :attr:`uefi.UEFIImage.closed_code_size`

        :attr:`uefi.UEFIImage.data_regions` sizes sum is added to
        :attr:`uefi.UEFIImage.data_size`

        :attr:`uefi.UEFIImage.empty_spaces` sizes sum is added to
        :attr:`uefi.UEFIImage.empty_size`

        Additionally for each detected UEFI Firmware Volume region their four
        basic component's categories are also added to the total metrics.

        :attr:`uefi.UEFIVolume.open_code_size` is added to
        :attr:`uefi.UEFIImage.open_code_size` (although it is expected to be
        0).

        :attr:`uefi.UEFIVolume.closed_code_size` is added to
        :attr:`uefi.UEFIImage.closed_code_size`

        :attr:`uefi.UEFIVolume.data_size` is added to
        :attr:`uefi.UEFIImage.data_size`

        :attr:`uefi.UEFIVolume.empty_size` is added to
        :attr:`uefi.UEFIImage.empty_size`

        At the end the method calls :meth:`uefi.UEFIImage._normalize_sizes`
        """
        self._classify_entries()
        # We do not calculate any open-source code. Let's be honest, there
        # isn't any truly open-source code in vendor images.
        self.closed_code_size = self._sum_sizes(self.closed_code_regions)
        self.data_size = self._sum_sizes(self.data_regions)
        self.empty_size = self._sum_sizes(self.empty_spaces)

        for i in range(self.num_volumes):
            self.open_code_size += self.volumes[i].open_code_size
            self.closed_code_size += self.volumes[i].closed_code_size
            self.data_size += self.volumes[i].data_size
            self.empty_size += self.volumes[i].empty_size

        self._normalize_sizes()

    def _normalize_sizes(self):
        """Checks if all firmware image components sizes sum up to whole image
        size

        This method acts as a safety check if there was no error during
        parsing and classification. It may happen that the total size of
        classified entries does not sum up to full image size. In such case
        the size difference are counted as data (possibly some metadata) and
        added to :attr:`uefi.UEFIImage.closed_code_size`. Additionally and
        error is printed.
        """
        # Final check if all sizes are summing up to whole image size
        full_size = sum([self.open_code_size, self.empty_size,
                         self.closed_code_size, self.data_size])

        self.data_size += (self.image_size - full_size)

        if full_size != self.image_size:
            print('ERROR: Something went wrong.\n'
                  'The component sizes do not sum up to the image size. '
                  '%d != %d' % (full_size, self.image_size))

    def _get_percentage(self, metric):
        """Helper function to generate code share percentage

        :param metric: The size of open-source or closed-source code
        :type metric: int
        :return: Percentage share of given metric compared to the sum of
                 open-source and closed-source code size.
        :rtype: int
        """
        return metric * 100 / (self.open_code_size + self.closed_code_size)

    def _export_regions_md(self, file, regions, category):
        """Write the regions for given category to the markdown file

        :param file: Markdown file handle to write the regions's info to
        :type file: file
        :param regions: Dictionary containing regions to be written to the
                        markdown file.
        :type regions: dict
        :param category: Category of the regions to be written to the markdown
                         file. Should be one of: open-source, closed-source,
                         data, empty.
        :type category: str
        """
        for region in regions:
            file.write('| {} | {} | {} | {} |\n'.format(
                        region['subtype'], hex(region['base']),
                        hex(region['size']), category))

    def export_markdown(self, file):
        """Opens a file and saves the openness report in markdown format

        Saves the parsed information and classified image components into a
        markdown file. Also for each UEFI firmware volume in
        :attr:`uefi.UEFIImage.volumes` it calls
        :meth:`uefi.UEFIVolume.export_markdown` to save the UEFI Firmware
        Volume statistics.

        :param file: Path to markdown file
        :type file: str
        """
        with open(file, 'w') as md:
            md.write('# Dasharo Openness Score\n\n')
            md.write('Openness Score for %s\n\n' % Path(self.image_path).name)
            md.write('Open-source code percentage: **%1.1f%%**\n' %
                     self._get_percentage(self.open_code_size))
            md.write('Closed-source code percentage: **%1.1f%%**\n\n' %
                     self._get_percentage(self.closed_code_size))

            md.write('* Image size: %d (%s)\n'
                     '* Number of entries: %d\n'
                     '* Number of regions: %d\n'
                     '* Number of volumes: %d\n'
                     '* Total open-source files size: %d (%s)\n'
                     '* Total closed-source files size: %d (%s)\n'
                     '* Total data size: %d (%s)\n'
                     '* Total empty size: %d (%s)\n\n' % (
                        self.image_size, hex(self.image_size),
                        self.num_entries,
                        self.num_regions,
                        self.num_volumes,
                        self.open_code_size, hex(self.open_code_size),
                        self.closed_code_size, hex(self.closed_code_size),
                        self.data_size, hex(self.data_size),
                        self.empty_size, hex(self.empty_size)))

            md.write('> Numbers given above already include the calculations')
            md.write(' from UEFI volumes\n> presented below. Only top level'
                     ' volumes have been presented\n\n')

            # Regions first
            md.write('## UEFI regions\n\n')
            md.write('| Region | Base | Size | Category |\n')
            md.write('| ------ | ---- | ---- | -------- |\n')
            self._export_regions_md(md, self.closed_code_regions,
                                    'closed-source')
            self._export_regions_md(md, self.data_regions, 'data')
            self._export_regions_md(md, self.empty_spaces, 'empty')
            md.write('\n')
            md.write('> These are regions defined by Intel flash descriptor'
                     ' but also holes\n> between those regions and UEFI'
                     ' Volumes which may or may not be empty.\n')

            for uefi_fv in self.volumes:
                md.write('\n')
                uefi_fv.export_markdown(md)

    def export_charts(self, dir):
        """Plots the pie charts with firmware image statistics

        Method plots two pie charts. One containing only the closed-source to
        open-source code ratio. Second the share percentage of all four image
        components categories: closed-source, open-source, data and empty
        space.

        :param dir: Path to the directory where the charts will be saved.
        :type dir: str
        """
        labels = 'closed-source', 'open-source'
        sizes = [self.closed_code_size, self.open_code_size]
        explode = (0, 0.1)

        fig, ax = plt.subplots()
        ax.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%')
        fig.suptitle('UEFI image code openness\n%s' %
                     Path(self.image_path).name)
        plt.savefig('%s_openness_chart.png' %
                    dir.joinpath(Path(self.image_path).name))

        labels = 'closed-source', 'open-source', 'data', 'empty'
        sizes = [self.closed_code_size, self.open_code_size,
                 self.data_size, self.empty_size]
        explode = (0, 0.1, 0, 0)

        fig, ax = plt.subplots()
        ax.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%')
        fig.suptitle('UEFI full image \n%s' %
                     Path(self.image_path).name)
        plt.savefig('%s_openness_chart_full_image.png' %
                    dir.joinpath(Path(self.image_path).name))


class UEFIVolume:
    """UEFIVolume class

    The main class representing an UEFI Firmware Volume.
    """

    debug = False

    # The ratio of NVAR entries vs all entries in given volume to callsify
    # whole volume as NVAR.
    NVAR_VOLUME_THRESHOLD = 90
    """Threshold used to determine if given UEFI Firmware Volume is NVAR
    storage. The threshold is defined as the number of NVAR entries divided by
    the total number of entries in given Firmware Volume expressed in
    percentage.
    """

    def __init__(self, uefi_entries, entry_idx, verbose=False):
        """UEFIVolume class init method

        Initializes the class fields for storing the UEFI Firmware Volume
        components classified to specific groups. Also calls
        :meth:`~coreboot.UEFIVolume._parse_volume_files` and
        :meth:`~coreboot.UEFIVolume._calculate_metrics` methods to parse the
        image and calculate the metrics.

        :param uefi_entries: Dictionary with the UEFI entries from the report.
        :type uefi_entries: dict
        :param entry_idx: Index in the UEFI entries dictionary pointing to the
                          beginning of the Firmware Volume
        :type entry_idx: int
        :param verbose: Optional parameter to turn on debug information during
                        the image parsing, defaults to False
        :type verbose: bool, optional
        """
        self.uefi_entries = uefi_entries
        """A copy of UEFI entries used to parse the Firmware Volume contents"""
        self.volume_idx = entry_idx
        """Index in the UEFI entries dictionary pointing to the beginning of
        the Firmware Volume
        """
        self.volume_base = uefi_entries[entry_idx]['base']
        """The Firmware Volume base address in flash"""
        self.volume_size = uefi_entries[entry_idx]['size']
        """The Firmware Volume size in flash"""
        self.volume_end = self.volume_base + self.volume_size
        """The Firmware Volume end address in flash"""
        self.volume_type = uefi_entries[entry_idx]['subtype']
        """The Firmware Volume subtype (FFSv2, FFSv3)"""
        self.volume_guid = uefi_entries[entry_idx]['name'].lstrip('-').strip()
        """Firmware Volume GUID"""
        self.volume_entries = []
        """A list of entries residing inside this Firmware Volume"""
        self.nested_volumes = []
        """A list of Firmware Volumes nested inside this Firmware Volume"""
        self.open_code_size = 0
        """Total number of bytes classified as open-source code"""
        self.closed_code_size = 0
        """Total number of bytes classified as closed-source code"""
        self.data_size = 0
        """Total number of bytes classified as data"""
        self.empty_size = 0
        """Total number of bytes classified as empty"""
        self.open_code_files = []
        """List holding Firmware Volume files classified as open-source code"""
        self.closed_code_files = []
        """List holding Firmware Volume files classified as closed-source
        code
        """
        self.data_files = []
        """List holding Firmware Volume files classified as data"""
        self.empty_files = []
        """List holding Firmware Volume empty spaces"""

        self.debug = verbose
        """Used to enable verbose debug output from the parsing process"""

        self._parse_volume_files()
        self._calculate_metrics()

    def __len__(self):
        """Returns the length of the UEFI Firmware Volume

        :return: Length of the UEFI Firmware Volume
        :rtype: int
        """
        return self.volume_size

    def __repr__(self):
        """UEFIVolume class representation

        :return: class representation
        :rtype: str
        """
        return "UEFIVolume()"

    def __str__(self):
        """Returns string representation of the UEFI Firmware Volume

        Prints the firmware image statistics.

        :return: UEFIVolume string representation
        :rtype: str
        """
        return 'UEFI Volume:\n' \
               '\tBase: %s\n' \
               '\tSize: %s\n' \
               '\tNumber of entries: %d\n' \
               '\tOpen-source code size: %d\n' \
               '\tClosed-source code size: %d\n' \
               '\tData size: %d\n' \
               '\tEmpty size: %d' % (
                    hex(self.volume_base),
                    hex(self.volume_size),
                    len(self.volume_entries),
                    self.open_code_size,
                    self.closed_code_size,
                    self.data_size,
                    self.empty_size)

    def _entry_is_inside_volume(self, entry):
        """Helper function to check if UEFI entry resides inside this UEFI
        Firmware Volume

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is inside this Firmware Volume, False
                 otherwise.
        :rtype: bool
        """
        # Each volume starts with an entry that has a base and size.
        # Automatically accept all files in the middle that has base of -1
        # (N/A). If we reach the end of volume (the last entry base + size
        # equal to volume_end) this function will not be called anymore.
        if entry['base'] != -1:
            if self._entry_is_region(entry):
                return False
            if self._entry_is_self_volume(entry):
                return False
            elif (entry['base'] < self.volume_base) or \
                 (entry['base'] >= self.volume_end):
                return False
            elif (entry['base'] >= self.volume_base) and \
                 (entry['base'] + entry['size'] <= self.volume_end):
                return True
            else:
                print('ERROR: Ignored the following entry in volume:')
                print(entry)
                return False
        else:
            # If there is at least one entry, it means the we can accept the
            # compressed ones, because the entries within this volume have
            # already started.
            if len(self.volume_entries) > 0:
                return True
            else:
                print('ERROR: Ignored the following entry in volume:')
                print(entry)
                return False

    def _is_end_of_volume(self, entry):
        """Helper function to check if UEFI entry is the last entry in this
        UEFI Firmware Volume

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is the last one in this Firmware Volume, False
                 otherwise.
        :rtype: bool
        """
        # Volume ends with a known size entry, never with a compressed one.
        if entry['base'] == -1:
            return False
        elif entry['base'] > self.volume_end:
            return True
        elif entry['base'] + entry['size'] > self.volume_end:
            return True
        else:
            return False

    def _entry_is_region(self, entry):
        """Helper function to check if UEFI entry is a region

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is a region, False otherwise.
        :rtype: bool
        """
        if entry['type'] == 'Region':
            return True
        else:
            return False

    def _entry_is_self_volume(self, entry):
        """Helper function to check if UEFI entry is the current UEFI Firmware
        Volume

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is the current UEFI Firmware Volume, False
                 otherwise.
        :rtype: bool
        """
        if entry['type'] == 'Volume' and \
           entry['base'] == self.volume_base and \
           entry['size'] == self.volume_size:
            return True
        else:
            return False

    def _entry_is_nested_volume(self, entry):
        """Helper function to check if given UEFI entry is an UEFI Firmware
        Volume nested in the current UEFI Firmware Volume

        Only FFSv2 volumes are counted, FFSv3 are compressed and do not have
        size, thus cannot be used to measure metrics.

        :param entry: UEFI image entry from the entries dictionary
        :type entry: dict
        :return: True if entry is a nested UEFI Firmware Volume, False
                 otherwise.
        :rtype: bool
        """
        # Volumes that are nested/uncompressed will have a valid size.
        if entry['type'] == 'Volume' and entry['size'] != -1 and \
           entry['subtype'] == 'FFSv2':
            if (entry['base'] < self.volume_base) or \
               (entry['base'] >= self.volume_end):
                return False
            elif (entry['base'] >= self.volume_base) and \
                 (entry['base'] + entry['size'] <= self.volume_end):
                return True

        return False

    def _parse_volume_files(self):
        """Extracts the UEFI entries that belong to the given Firmware Volumes
        and append them to :attr:`uefi.UEFIVolume.volume_entries`

        The function also detects nested uncompressed volumes and creates new
        instance of :class:`uefi.UEFIVolume` and appends them to
        :attr:`uefi.UEFIVolume.nested_volumes`.

        If :attr:`uefi.UEFIVolume.debug` is True, all Firmware Volume entries
        with their attributes are printed on the console at the end.
        """
        for i in range(self.volume_idx + 1, len(self.uefi_entries)):
            if self._entry_is_inside_volume(self.uefi_entries[i]):
                if self._entry_is_nested_volume(self.uefi_entries[i]):
                    nested_volume = UEFIVolume(self.uefi_entries, i,
                                               self.debug)
                    self.nested_volumes.append(nested_volume)
                    # Increment the index to skip all element belonging to the
                    # nested volume. Also continue the loop to avoid loop break
                    # condition check errors due to sudden index increase.
                    i += len(nested_volume.volume_entries)
                    continue
                else:
                    self.volume_entries.append(self.uefi_entries[i])

            if self._entry_is_self_volume(self.uefi_entries[i]):
                continue

            if self._is_end_of_volume(self.uefi_entries[i]):
                break

        if self.debug:
            print("UEFI volume entries:")
            for i in range(len(self.volume_entries)):
                print(self.volume_entries[i])

    def _classify_entries(self):
        """Checks all entries belonging to the UEFI Firmware Volume and
        classifies them

        Entries are classified to the two basic categories: data or empty
        Everything else is considered either closed-source code or data (in
        case of UEFI NVAR).

        If :attr:`uefi.UEFIVolume.debug` is True, all Firmware Volume entries
        classified so far as data and empty are printed on the console at the
        end.
        """
        # We only classify empty and non-empty pads and free space, everything
        # else will be considered as either closed-source for regular volumes
        # or data for NVAR store volumes
        for i in range(len(self.volume_entries)):
            if self._is_entry_empty_padding(self.volume_entries[i]):
                self.empty_files.append(self.volume_entries[i])
            elif self._is_entry_non_empty_padding(self.volume_entries[i]):
                self.data_files.append(self.volume_entries[i])
            elif self._is_entry_free_space(self.volume_entries[i]):
                self.empty_files.append(self.volume_entries[i])
            elif self._is_entry_empty_pad_file(self.volume_entries[i]):
                self.empty_files.append(self.volume_entries[i])
            elif self._is_entry_non_empty_pad_file(self.volume_entries[i]):
                self.data_files.append(self.volume_entries[i])

        if self.debug:
            print("UEFI volume empty entries:")
            [print(self.empty_files[i]) for i in range(len(self.empty_files))]
            print("UEFI volume data entries:")
            [print(self.data_files[i]) for i in range(len(self.data_files))]

    def _is_entry_empty_padding(self, entry):
        """Checks if an entry is an empty padding

        :param entry: A dictionary entry from the UEFI Firmware Volume entries
        :type entry: dict
        :return: True if an entry is an empty padding, False otherwise.
        :rtype: bool
        """
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Padding':
                if entry['subtype'] == 'Empty (0xFF)' or \
                   entry['subtype'] == 'Empty (0x00)':
                    return True

        return False

    def _is_entry_non_empty_padding(self, entry):
        """Checks if an entry is a non-empty padding

        :param entry: A dictionary entry from the UEFI Firmware Volume entries
        :type entry: dict
        :return: True if an entry is a non-empty pad file, False otherwise.
        :rtype: bool
        """
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Padding':
                if entry['subtype'] == 'Non-empty':
                    return True

        return False

    def _is_entry_free_space(self, entry):
        """Checks if an entry is a free space

        :param entry: A dictionary entry from the UEFI Firmware Volume entries
        :type entry: dict
        :return: True if an entry is a free space, False otherwise.
        :rtype: bool
        """
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Free space':
                return True

        return False

    def _is_entry_empty_pad_file(self, entry):
        """Checks if an entry is an empty pad file

        :param entry: A dictionary entry from the UEFI Firmware Volume entries
        :type entry: dict
        :return: True if an entry is an empty pad file, False otherwise.
        :rtype: bool
        """
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'File':
                if entry['subtype'] == 'Pad':
                    if 'Pad-file' in entry['name']:
                        return True

        return False

    def _is_entry_non_empty_pad_file(self, entry):
        """Checks if an entry is a non-empty pad file

        :param entry: A dictionary entry from the UEFI Firmware Volume entries
        :type entry: dict
        :return: True if an entry is a non-empty pad file, False otherwise.
        :rtype: bool
        """
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'File':
                if entry['subtype'] == 'Pad':
                    if 'Non-empty pad-file' in entry['name']:
                        return True

        return False

    def _sum_sizes(self, files):
        """Sums the size of the UEFI Firmware Volume files

        :param files: Dictionary of files to sum
        :type files: dict
        :return: Sum of the files' sizes
        :rtype: int
        """
        return sum(list(f['size'] for f in files))

    def _is_nvar_store_volume(self):
        """Determines if given UEFI Firmware Volume is a variable store

        :return: True if the Firmware Volume consists of NVAR entries
                 exceeding the :const:`uefi.UEFIVolume.NVAR_VOLUME_THRESHOLD`,
                 False otherwise.
        :rtype: bool
        """
        nvar_count = 0

        for i in range(len(self.volume_entries)):
            if self.volume_entries[i]['type'] == 'NVAR entry':
                nvar_count += 1

        nvar_ratio = (nvar_count * 100) / len(self.volume_entries)

        if nvar_ratio >= self.NVAR_VOLUME_THRESHOLD:
            return True
        else:
            return False

    def _calculate_metrics(self):
        """Calculates the sizes of the four basic firmware components
        categories

        Calls :meth:`~uefi.UEFIVolume._classify_entries` then sums the regions
        sizes from all 3 lists

        :attr:`uefi.UEFIVolume.closed_code_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.closed_code_size`

        :attr:`uefi.UEFIVolume.data_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.data_size`

        :attr:`uefi.UEFIVolume.empty_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.empty_size`

        At the end the method calls :meth:`uefi.UEFIVolume._normalize_sizes`
        """
        self._classify_entries()
        # We do not calculate any open-source code. Let's be honest, there
        # isn't any truly open-source code in vendor images.
        self.closed_code_size += self._sum_sizes(self.closed_code_files)
        self.data_size += self._sum_sizes(self.data_files)
        self.empty_size += self._sum_sizes(self.empty_files)
        self._normalize_sizes()

    def _normalize_sizes(self):
        """Checks if all Firmware Volume components sizes sum up to whole
        Firmware Volume size.

        For all nested volumes in :attr:`uefi.UEFIVolume.nested_volumes` sums
        the sizes from all 3 lists:

        :attr:`uefi.UEFIVolume.closed_code_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.closed_code_size`

        :attr:`uefi.UEFIVolume.data_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.data_size`

        :attr:`uefi.UEFIVolume.empty_files` sizes sum is added to
        :attr:`uefi.UEFIVolume.empty_size`

        At the end it sums all classified files and add the difference between
        the Firmware Volume size and classified files size to the
        :attr:`uefi.UEFIVolume.closed_code_size` or to the
        :attr:`uefi.UEFIVolume.data_size` if given Firmware Volume is variable
        storage.
        """
        for i in range(len(self.nested_volumes)):
            self.closed_code_size += self.nested_volumes[i].closed_code_size
            self.data_size += self.nested_volumes[i].data_size
            self.empty_size += self.nested_volumes[i].empty_size

        # If it is an NVAR store volume, treat the rest of the unclassified
        # volume space as data. Otherwise count it as a regular volume
        # containing closed-source drivers.
        classified_files_size = sum([self.empty_size,
                                     self.closed_code_size,
                                     self.data_size])
        if self._is_nvar_store_volume():
            self.data_size += (self.volume_size - classified_files_size)
        else:
            self.closed_code_size += (self.volume_size - classified_files_size)

    def _export_files_md(self, file, volume_files, category):
        """Write the Firmware Volume entries for given category to the
        markdown file

        :param file: Markdown file handle to write the entries' info to
        :type file: file
        :param volume_files: Dictionary containing entires to be written to
                             the markdown file.
        :type volume_files: dict
        :param category: Category of the entries to be written to the markdown
                         file. Should be one of: open-source, closed-source,
                         data, empty.
        :type category: str
        """
        for f in volume_files:
            file.write('| {} | {} | {} | {} | {} | {} |\n'.format(
                        f['name'].lstrip('-').lstrip(), f['type'],
                        f['subtype'], hex(f['base']), hex(f['size']),
                        category))

    def export_markdown(self, file):
        """Saves the openness report in markdown format for given UEFI
        Firmware Volume

        Saves the parsed information and classified UEFI Firmware Volume
        components into a markdown file.

        :param file: Markdown file handle
        :type file: str
        """
        file.write('## UEFI Volume %s\n\n' % self.volume_guid)
        file.write('* Base: %s\n'
                   '* Size: %s\n'
                   '* Number of entries: %d\n'
                   '* Open-source code size: %d (%s)\n'
                   '* Closed-source code size: %d (%s)\n'
                   '* Data size: %d (%s)\n'
                   '* Empty size: %d (%s)\n\n' %
                   (hex(self.volume_base),
                    hex(self.volume_size),
                    len(self.volume_entries),
                    self.open_code_size, hex(self.open_code_size),
                    self.closed_code_size, hex(self.closed_code_size),
                    self.data_size, hex(self.data_size),
                    self.empty_size, hex(self.empty_size)))

        if self._is_nvar_store_volume():
            file.write('> This is an UEFI NVAR storage volume. All'
                       ' entries except empty spaces are\n> counted as'
                       ' data. The table below is just a simplified view'
                       ' of top level\n> volume entries categorized as'
                       ' either data or empty space\n\n')
        else:
            file.write('> The table below is just a simplified view'
                       ' of top level volume entries\n> categorized as'
                       ' file that are known to contain either data or'
                       ' empty space.\n> Everything else is considered'
                       ' closed-source.\n\n')

        file.write('| Filename | File type | File subtype | Base |'
                   ' Size | Category |\n')
        file.write('| -------- | --------- | ------------ | ---- |'
                   ' ---- | -------- |\n')
        self._export_files_md(file, self.open_code_files, 'open-source')
        self._export_files_md(file, self.closed_code_files,
                              'closed-source')
        self._export_files_md(file, self.data_files, 'data')
        self._export_files_md(file, self.empty_files, 'empty')
