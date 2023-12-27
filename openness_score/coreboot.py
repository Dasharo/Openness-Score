# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import re
import os
import subprocess
from pathlib import Path
from typing import List
import matplotlib.pyplot as plt

"""This module is responsible for parsing coreboot images"""


class DasharoCorebootImage:
    """DasharoCorebootImage class

    The main class representing a coreboot-based firmware image
    """

    debug = False

    region_patterns = [
        r"'(?P<region>[A-Z_]+?)' ",
        r"\((?P<attribute>(read-only, |preserve, |CBFS, ){0,1}?)",
        r"size (?P<size>\d+?), offset (?P<offset>\d+?)\)"
    ]
    """Set of regular expressions used to extract the flashmap regions"""

    region_regexp = re.compile(''.join(region_patterns), re.MULTILINE)
    """Regular expression variable used to extract the flashmap regions"""

    # Regions to consider as data, they should not contain any code ever.
    # Some of the regions are used only by certain platforms and may not be met
    # on Dasharo builds.
    DATA_REGIONS = ['SI_DESC', 'RECOVERY_MRC_CACHE', 'RW_MRC_CACHE', 'RW_VPD',
                    'SMMSTORE', 'SHARED_DATA', 'VBLOCK_DEV', 'RW_NVRAM',
                    'CONSOLE', 'RW_FWID_A', 'RW_FWID_B', 'VBLOCK_A', 'RO_VPD',
                    'VBLOCK_B', 'HSPHY_FW', 'RW_ELOG', 'FMAP', 'RO_FRID',
                    'RO_FRID_PAD', 'SPD_CACHE', 'FPF_STATUS', 'RO_LIMITS_CFG',
                    'RW_DDR_TRAINING', 'GBB']
    """A list of region names known to contain data"""

    # Regions that are not CBFSes and may contain open-source code
    # Their whole size is counted as code.
    CODE_REGIONS = ['BOOTBLOCK']
    """A list of region names known to contain open-source code"""

    # Regions that may contain code but in closed-source binary form
    # HSPHY_FW does not belong here, because it is part of ME which counts
    # as closed-source binary blob as a whole.
    BLOB_REGIONS = ['RW_VBIOS_CACHE', 'ME_RW_A', 'ME_RW_B', 'IFWI', 'SI_ME',
                    'SIGN_CSE']
    """A list of region names known to contain closed-source code"""

    # Regions to not account for in calculations.
    # These are containers aggregating smaller regions.
    SKIP_REGIONS = ['RW_MISC', 'UNIFIED_MRC_CACHE', 'RW_SHARED', 'SI_ALL',
                    'RW_SECTION_A', 'RW_SECTION_B', 'WP_RO', 'RO_SECTION']
    """A list of region names known to be containers or aliases of other
    regions. These regions are skipped from classification."""

    # Regions to count as empty/unused
    EMPTY_REGIONS = ['UNUSED']
    """A list of region names known to be empty spaces, e.g. between IFD
    regions."""

    def __init__(self, image_path, verbose=False):
        """DasharoCorebootImage class init method

        Initializes the class fields for storing the firmware image components
        classified to specific groups. Also calls
        :meth:`~coreboot.DasharoCorebootImage._parse_cb_fmap_layout` and
        :meth:`~coreboot.DasharoCorebootImage._calculate_metrics` methods to
        parse the image and calculate the metrics.

        :param image_path: Path the the firmware image file being parsed.
        :type image_path: str
        :param verbose: Optional parameter to turn on debug information during
                        the image parsing, defaults to False
        :type verbose: bool, optional
        """
        self.image_path = image_path
        """Path to the image represented by DasharoCorebootImage class"""
        self.image_size = os.path.getsize(image_path)
        """Image size in bytes"""
        self.fmap_regions = {}
        """A dictionary holding the coreboot image flashmap regions"""
        self.cbfs_images = []
        """A list holding the regions with CBFS"""
        self.num_regions = 0
        """Total number of flashmap regions"""
        self.num_cbfses = 0
        """Total number of flashmap regions containing CBFSes"""
        self.open_code_size = 0
        """Total number of bytes classified as open-source code"""
        self.closed_code_size = 0
        """Total number of bytes classified as closed-source code"""
        self.data_size = 0
        """Total number of bytes classified as data"""
        self.empty_size = 0
        """Total number of bytes classified as empty"""
        self.open_code_regions = []
        """A list holding flashmap regions filled with open-source code"""
        self.closed_code_regions = []
        """A list holding flashmap regions filled with closed-source code"""
        self.data_regions = []
        """A list holding flashmap regions filled with data"""
        self.empty_regions = []
        """A list holding empty flashmap regions"""
        # This type of regions will be counted as closed-source at the end of
        # metrics calculation. Keep them in separate array to export them into
        # CSV later for review.
        self.uncategorized_regions = []
        """A list holding flashmap regions that could not be classified.
        Counted as closed-source code at the end of calculation process.
        """

        self.debug = verbose
        """Used to enable verbose debug output from the parsing process"""

        self._parse_cb_fmap_layout()
        self._calculate_metrics()

    def __len__(self):
        """Returns the length of the coreboot firmware image

        :return: Length of the firmware binary file
        :rtype: int
        """
        return self.image_size

    def __repr__(self):
        """DasharoCorebootImage class representation

        :return: class representation
        :rtype: str
        """
        return 'DasharoCorebootImage()'

    def __str__(self):
        """Returns string representation of the firmware image

        Prints the firmware image statistics.

        :return: DasharoCorebootImage string representation
        :rtype: str
        """
        return 'Dasharo image %s:\n' \
               '\tImage size: %d\n' \
               '\tNumber of regions: %d\n' \
               '\tNumber of CBFSes: %d\n' \
               '\tTotal open-source code size: %d\n' \
               '\tTotal closed-source code size: %d\n' \
               '\tTotal data size: %d\n' \
               '\tTotal empty size: %d' % (
                    self.image_path,
                    self.image_size,
                    self.num_regions,
                    self.num_cbfses,
                    self.open_code_size,
                    self.closed_code_size,
                    self.data_size,
                    self.empty_size)

    def _region_is_cbfs(self, region):
        """Checks if given region has a CBFS attribute

        :param region: Flashmap region entry from dictionary
        :type region: dict
        :return: True if regions contains CBFS attribute, false otherwise.
        :rtype: bool
        """
        if region['attributes'] == 'CBFS':
            return True
        else:
            return False

    def _parse_cb_fmap_layout(self):
        """Parses the cbfstool flashmap layout output

        Parses the output of 'cbfstool self.image_path layout -w' and extract
        the flashmap regions to a self.fmap_regions dictionary using the
        :const:`coreboot.DasharoCorebootImage.region_regexp` regular
        expression.

        If a flashmap region has a CBFS attribute, the self.cbfs_images list
        is appended with a new instance of :class:`coreboot.CBFSImage`.

        If :attr:`coreboot.DasharoCorebootImage.debug` is True, all flashmap
        regions with their attributes are printed on the console at the end.
        """
        cmd = ['cbfstool', self.image_path, 'layout', '-w']
        layout = subprocess.run(cmd, text=True, capture_output=True)

        for match in re.finditer(self.region_regexp, layout.stdout):
            self.fmap_regions[self.num_regions] = {
                'name': match.group('region'),
                'offset': int(match.group('offset')),
                'size': int(match.group('size')),
                'attributes': match.group('attribute').strip(', '),
            }

            if self._region_is_cbfs(self.fmap_regions[self.num_regions]):
                cbfs = CBFSImage(self.image_path,
                                 self.fmap_regions[self.num_regions],
                                 self.debug)
                self.cbfs_images.append(cbfs)
                self.num_cbfses += 1
                print(cbfs)

            self.num_regions += 1

        if self.debug:
            print('Dasharo image regions:')
            [print(self.fmap_regions[i]) for i in range(self.num_regions)]

    def _classify_region(self, region):
        """Classifies the flashmap regions into basic categories

        Each detected flashmap region is being classified into 4 basic
        categories and appended to respective lists. CBFS regions are
        processed separately and not included here.

        :attr:`coreboot.DasharoCorebootImage.open_code_regions` are appended
        with flashmap regions which name is found in
        :const:`coreboot.DasharoCorebootImage.CODE_REGIONS`

        :attr:`coreboot.DasharoCorebootImage.closed_code_regions` are appended
        with flashmap regions which name is found in
        :const:`coreboot.DasharoCorebootImage.BLOB_REGIONS`

        :attr:`coreboot.DasharoCorebootImage.empty_regions` are appended with
        flashmap regions which name is found in
        :const:`coreboot.DasharoCorebootImage.EMPTY_REGIONS`

        :attr:`coreboot.DasharoCorebootImage.data_regions` are appended with
        flashmap regions which name is found in
        :const:`coreboot.DasharoCorebootImage.DATA_REGIONS`

        Flashmap regions which names is found in
        :const:`coreboot.DasharoCorebootImage.SKIP_REGIONS` are not classified
        due to being cotnainers or aliases to other regions. Counting them
        would result in duplication of the sizes when calculating metrics.

        Any other unrecognized flashmap region falls into
        :attr:`coreboot.DasharoCorebootImage.data_regions` list which will be
        counted as closed-source code region because we were unable to
        identify what can be inside.

        :param region: Flashmap region entry from dictionary
        :type region: dict
        """
        if self._region_is_cbfs(region):
            # Skip CBFSes because they have separate class and methods to
            # calculate metrics
            return
        elif region['name'] in self.SKIP_REGIONS:
            return
        elif region['name'] in self.CODE_REGIONS:
            self.open_code_regions.append(region)
        elif region['name'] in self.BLOB_REGIONS:
            self.closed_code_regions.append(region)
        elif region['name'] in self.EMPTY_REGIONS:
            self.empty_regions.append(region)
        elif region['name'] in self.DATA_REGIONS:
            self.data_regions.append(region)
        elif region['attributes'] == 'read-only':
            # Regions with read-only attribute are containers. Skip them. The
            # FMAP region is an exception and there may be more, so keep this
            # IF branch at the very end.
            print('WARNING: Skipped %s region, suspected to be a container'
                  % region['name'])
            return
        else:
            self.uncategorized_regions.append(region)

    def _calculate_metrics(self):
        """Calculates the sizes of the four basic firmware components
        categories

        Calls :meth:`~coreboot.DasharoCorebootImage._classify_region` for each
        detected region. The sums the regions sizes from all 5 lists

        :attr:`coreboot.DasharoCorebootImage.open_code_regions` sizes sum is
        added to :attr:`coreboot.DasharoCorebootImage.open_code_size`

        :attr:`coreboot.DasharoCorebootImage.closed_code_regions` sizes sum is
        added to :attr:`coreboot.DasharoCorebootImage.closed_code_size`

        :attr:`coreboot.DasharoCorebootImage.data_regions` sizes sum is added
        to :attr:`coreboot.DasharoCorebootImage.data_size`

        :attr:`coreboot.DasharoCorebootImage.empty_regions` sizes sum is added
        to :attr:`coreboot.DasharoCorebootImage.empty_size`

        :attr:`coreboot.DasharoCorebootImage.uncategorized_regions` sizes sum
        is added to :attr:`coreboot.DasharoCorebootImage.closed_code_size`

        Additionally for each detected CBFS region their four basic
        component's categories are also added to the total metrics.

        :attr:`coreboot.CBFSImage.open_code_size` is added to
        :attr:`coreboot.DasharoCorebootImage.open_code_size`

        :attr:`coreboot.CBFSImage.closed_code_size` is added to
        :attr:`coreboot.DasharoCorebootImage.closed_code_size`

        :attr:`coreboot.CBFSImage.data_size` is added to
        :attr:`coreboot.DasharoCorebootImage.data_size`

        :attr:`coreboot.CBFSImage.empty_size` is added to
        :attr:`coreboot.DasharoCorebootImage.empty_size`

        At the end the method calls
        :meth:`coreboot.DasharoCorebootImage._normalize_sizes`
        """
        for i in range(self.num_regions):
            self._classify_region(self.fmap_regions[i])

        self.open_code_size += self._sum_sizes(self.open_code_regions)
        self.closed_code_size += self._sum_sizes(self.closed_code_regions)
        self.data_size += self._sum_sizes(self.data_regions)
        self.empty_size += self._sum_sizes(self.empty_regions)
        self.closed_code_size += self._sum_sizes(self.uncategorized_regions)
        if len(self.uncategorized_regions) != 0:
            print('INFO: Found %d uncategorized regions of total size %d bytes'
                  % (len(self.uncategorized_regions),
                     self._sum_sizes(self.uncategorized_regions)))
            print(self.uncategorized_regions)

        for i in range(self.num_cbfses):
            self.open_code_size += self.cbfs_images[i].open_code_size
            self.closed_code_size += self.cbfs_images[i].closed_code_size
            self.data_size += self.cbfs_images[i].data_size
            self.empty_size += self.cbfs_images[i].empty_size

        self._normalize_sizes()

    def _sum_sizes(self, regions):
        """Sums the size of the regions

        :param regions: Dictionary of regions to sum
        :type regions: dict
        :return: Sum of the region sizes
        :rtype: int
        """
        return sum(list(r['size'] for r in regions))

    def _normalize_sizes(self):
        """Checks if all firmware image components sizes sum up to whole image
        size

        This method acts as a safety check if there was no error during
        parsing and classification. Additionally it verifies whether the
        flashmap starts right at offset zero. It may happen that the flashmap
        does not start at offset zero, which is possible for Intel board
        coreboot images without IFD and ME regions specified. In such case the
        missing regions are counted as closed-source and added to
        :attr:`coreboot.DasharoCorebootImage.closed_code_size`
        """
        # It may happen that the FMAP does not cover whole flash size and the
        # first region will start with non-zero offset. Check if first region
        # offset is zero, if not count all bytes from the start of flash to the
        # start of first region as closed source.
        if self.fmap_regions[0]['offset'] != 0:
            self.closed_code_size += self.fmap_regions[0]['offset']

        # Final check if all sizes are summing up to whole image size
        full_size = sum([self.open_code_size, self.empty_size,
                         self.closed_code_size, self.data_size])
        if full_size != self.image_size:
            print('WARNING: Something went wrong.\n'
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
                        region['name'], hex(region['offset']),
                        hex(region['size']), category))

    def export_markdown(self, file, mkdocs):
        """Opens a file and saves the openness report in markdown format

        Saves the parsed information and classified image components into a
        markdown file. Also for each CBFS in
        :attr:`coreboot.DasharoCorebootImage.cbfs_images` it calls
        :meth:`coreboot.CBFSImage.export_markdown` to save the CBFS region
        statistics.

        :param file: Path to markdown file
        :type file: str
        :param mkdocs: Switch to export the report for mkdocs
        :type mkdocs: bool
        """
        with open(file, 'w') as md:
            if not mkdocs:
                md.write('# Dasharo Openness Score\n\n')

            md.write('Openness Score for %s\n\n' % Path(self.image_path).name)
            md.write('Open-source code percentage: **%1.1f%%**\n' %
                     self._get_percentage(self.open_code_size))
            md.write('Closed-source code percentage: **%1.1f%%**\n\n' %
                     self._get_percentage(self.closed_code_size))

            md.write('* Image size: %d (%s)\n'
                     '* Number of regions: %d\n'
                     '* Number of CBFSes: %d\n'
                     '* Total open-source code size: %d (%s)\n'
                     '* Total closed-source code size: %d (%s)\n'
                     '* Total data size: %d (%s)\n'
                     '* Total empty size: %d (%s)\n\n' % (
                        self.image_size, hex(self.image_size),
                        self.num_regions,
                        self.num_cbfses,
                        self.open_code_size, hex(self.open_code_size),
                        self.closed_code_size, hex(self.closed_code_size),
                        self.data_size, hex(self.data_size),
                        self.empty_size, hex(self.empty_size)))

            md.write('![](%s_openness_chart.png)\n\n' %
                     Path(self.image_path).name)
            md.write('![](%s_openness_chart_full_image.png)\n\n' %
                     Path(self.image_path).name)

            md.write('> Numbers given above already include the calculations')
            md.write(' from CBFS regions\n> presented below\n\n')

            # Regions first
            if not mkdocs:
                md.write('## FMAP regions\n\n')
            else:
                md.write('### FMAP regions\n\n')

            md.write('| FMAP region | Offset | Size | Category |\n')
            md.write('| ----------- | ------ | ---- | -------- |\n')
            self._export_regions_md(md, self.open_code_regions, 'open-source')
            self._export_regions_md(md, self.closed_code_regions,
                                    'closed-source')
            self._export_regions_md(md, self.data_regions, 'data')
            self._export_regions_md(md, self.empty_regions, 'empty')

            for cbfs in self.cbfs_images:
                md.write('\n')
                cbfs.export_markdown(md, mkdocs)

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
        fig.suptitle('Dasharo coreboot image code openness\n%s' %
                     Path(self.image_path).name)
        plt.savefig('%s_openness_chart.png' %
                    dir.joinpath(Path(self.image_path).name))

        labels = 'closed-source', 'open-source', 'data', 'empty'
        sizes = [self.closed_code_size, self.open_code_size,
                 self.data_size, self.empty_size]
        explode = (0, 0.1, 0, 0)

        fig, ax = plt.subplots()
        ax.pie(sizes, explode=explode, labels=labels, autopct='%1.1f%%')
        fig.suptitle('Dasharo coreboot full image component share\n%s' %
                     Path(self.image_path).name)
        plt.savefig('%s_openness_chart_full_image.png' %
                    dir.joinpath(Path(self.image_path).name))


class CBFSImage:
    """ CBFSImage class

    The main class representing a coreboot's CBFS
    """

    debug = False

    CBFS_FILETYPES = [
        'bootblock', 'cbfs header', 'stage', 'simple elf', 'fit_payload',
        'optionrom', 'bootsplash', 'raw', 'vsa', 'mbi', 'microcode',
        'intel_fit', 'fsp', 'mrc', 'cmos_default', 'cmos_layout', 'spd',
        'mrc_cache', 'mma', 'efi', 'struct', 'deleted', 'null', 'amdfw'
    ]
    """A list of all known CBFS filetypes for regexp matching"""

    OPEN_SOURCE_FILETYPES = [
        'bootblock', 'stage', 'simple elf', 'fit_payload',
    ]
    """A list of CBFS filetypes known to be open-source code"""

    CLOSED_SOURCE_FILETYPES = [
        'optionrom', 'vsa', 'mbi', 'microcode', 'fsp', 'mrc', 'mma', 'efi',
        'amdfw'
    ]
    """A list of CBFS filetypes known to be closed-source code"""

    DATA_FILETYPES = [
        'cbfs header', 'bootsplash', 'intel_fit', 'cmos_default',
        'cmos_layout', 'spd', 'mrc_cache', 'struct',
    ]
    """A list of CBFS filetypes known to be data"""

    # Some binary blobs containing code are not added as raw files or as fsp,
    # etc, for example refcode blob is a stage type. We keep them here to
    # account for such exceptions. Some non-x86 files are also here for the
    # future. The list may not be exhaustive. Search for 'cbfs-files' pattern
    # in coreobot Makefiles.
    CLOSED_SOURCE_EXCEPTIONS = [
        'fallback/refcode', 'fallback/secure_os', 'fallback/dram',
        'fallback/qcsdi', 'fallback/qclib', 'fallback/pmiccfg',
        'fallback/dcb', 'fallback/dcb_longsys1p8', 'fallback/aop',
        'fallback/uart_fw', 'fallback/spi_fw', 'fallback/i2c_fw',
        'fallback/cpucp', 'fallback/shrm', 'fallback/gsi_fw',
    ]
    """A list of CBFS filenames exceptions known to be closed-source code"""

    # Filetype raw can be anything and can also be named arbitrarily. We trust
    # that Dasharo binary is unmodified and standard names used by coreboot
    # have not been misused to hide blobs. These names are below for data and
    # code respecitvely. We also assume VBT to be data, becasue Intel publishes
    # VBT BSF/JSON files with the meaning of each byte in it. The lists may not
    # be exhaustive. Search for 'cbfs-files' pattern in coreobot Makefiles.
    RAW_DATA_FILES = [
        'config', 'revision', 'build_info', 'vbt.bin', 'payload_config',
        'payload_revision', 'etc/grub.cfg', 'logo.bmp', 'rt8168-macaddress',
        'atl1e-macaddress', 'wifi_sar_defaults.hex', 'ecrw.hash', 'pdrw.hash',
        'oem.bin', 'sbom', 'boot_policy_manifest.bin', 'key_manifest.bin',
        'txt_bios_policy.bin', 'apu/amdfw_a', 'apu/amdfw_b', 'me_rw.hash',
        'me_rw.version', 'vboot_public_key.bin',
        # SeaBIOS runtime config below https://www.seabios.org/Runtime_config
        'links', 'bootorder', 'etc/show-boot-menu', 'boot-menu-message',
        'etc/boot-menu-key', 'etc/boot-menu-wait', 'etc/boot-fail-wait',
        'etc/extra-pci-roots', 'etc/ps2-keyboard-spinup', 'etc/threads',
        'etc/optionroms-checksum', 'etc/pci-optionrom-exec',
        'etc/s3-resume-vga-init', 'etc/screen-and-debug', 'etc/sercon-port',
        'etc/advertise-serial-debug-port', 'etc/floppy0', 'etc/floppy1',
        'etc/usb-time-sigatt', 'etc/sdcard0', 'etc/sdcard1', 'etc/sdcard2',
        'etc/sdcard3'
    ]
    """A list of CBFS filenames known to be data"""

    # Everything derived from open-source code which is an executable code or
    # was created from open-source code in a reproducible way
    RAW_OPEN_SOURCE_FILES = [
        'fallback/dsdt.aml', 'vgaroms/seavgabios.bin', 'pagetables', 'pdpt',
        'pt', 'ecrw', 'pdrw', 'sff8104-linux.dtb', 'stm.bin', 'fallback/DTB',
        'oemmanifest.bin', 'smcbiosinfo.bin', 'genroms/pxe.rom',
    ]
    """A list of CBFS filenames known to be created from open-source code"""

    # PSE binary is treated as closed source as there is no guarantee of open
    # code availability for given build.
    RAW_CLOSED_SOURCE_FILES = [
        'doom.wad', 'ecfw1.bin', 'ecfw2.bin', 'apu/ecfw', 'ec/ecfw',
        'sch5545_ecfw.bin', 'txt_bios_acm.bin', 'txt_sinit_acm.bin',
        'apu/amdfw_a_body', 'apu/amdfw_b_body', 'smu_fw', 'smu_fw2',
        'dmic-1ch-48khz-16b.bin', 'dmic-2ch-48khz-16b.bin', 'me_rw',
        'dmic-4ch-48khz-16b.bin', 'max98357-render-2ch-48khz-24b.bin',
        'nau88l25-2ch-48khz-24b.bin', 'max98927-render-2ch-48khz-24b.bin',
        'max98927-render-2ch-48khz-16b.bin', 'dmic-2ch-48khz-32b.bin',
        'rt5514-capture-4ch-48khz-16b.bin', 'dmic-4ch-48khz-32b.bin',
        'max98373-render-2ch-48khz-24b.bin', 'dialog-2ch-48khz-24b.bin',
        'max98373-render-2ch-48khz-16b.bin', 'rt5682-2ch-48khz-24b.bin',
        'rt5663-2ch-48khz-24b.bin', 'ssm4567-render-2ch-48khz-24b.bin',
        'ssm4567-capture-4ch-48khz-32b.bin', 'pcm_allinone_lp4_3200.bin',
        'pcm_allinone_lp4_3733.bin', 'sspm.bin', 'spm_firmware.bin', 'AGESA',
        'cse_iom', 'cse_nphy', 'pse.bin', 'rmu.bin', 'tegra_mtc.bin', 'tz.mbn',
        'cdt.mbn', 'ddr.mbn', 'rpm.mbn'
    ]
    """A list of CBFS filenames known to be closed-source"""

    DASHARO_LAN_ROM_GUID = 'DEB917C0-C56A-4860-A05B-BF2F22EBB717'
    """GUID of the Dasharo UEFI Paylaod file that contains closed-source
    EFI driver for LAN NIC"""

    file_patterns = [
        r"(?P<filename>[a-zA-Z0-9\(\)\/\.\,\_\-]*?)\s+",
        r"(?P<offset>0x[0-9a-f]+?)\s+",
        r"(?P<filetype>(" + "|".join(CBFS_FILETYPES) + r"){1}?)\s+",
        r"(?P<size>\d+?)\s+(?P<compression>\w+?)(\s+\(\d+ \w+\))?$"
    ]
    """Set of regular expressions used to parse the cbfstool output"""

    file_regexp = re.compile(''.join(file_patterns), re.MULTILINE)
    """Regular expression variable used to parse the cbfstool output"""

    def __init__(self, image_path, region, verbose=False):
        """CBFSImage class init method

        Initializes the class fields for storing the CBFS region components
        classified to specific groups. Also calls
        :meth:`~coreboot.DasharoCorebootImage._parse_cbfs_files`,
        :meth:`~coreboot.DasharoCorebootImage._parse_cb_config` and
        :meth:`~coreboot.DasharoCorebootImage._calculate_metrics` methods to
        parse the CBFS and calculate the metrics.

        :param region: Path the the firmware image file being parsed.
        :type image_path: str
        :param region: The flashmap region where the CBFS resides.
        :type image_path: dict
        :param verbose: Optional parameter to turn on debug information during
                        the image parsing, defaults to False
        :type verbose: bool, optional
        """
        self.image_path = image_path
        """Path to the image represented by DasharoCorebootImage class"""
        self.region_name = region['name']
        """The region name where the CBFS is located"""
        self.cbfs_size = region['size']
        """The region size where the CBFS is located"""
        self.cbfs_files = {}
        """A dictionary holding the CBFS files and their attributes"""
        self.kconfig_opts = {}
        """A dictionary holding the coreboot config used to produce the
        CBFS
        """
        self.num_files = 0
        """Number of files in the CBFS"""
        self.num_opts = 0
        """Number of options coreboot config file found in CBFS"""
        self.open_code_size = 0
        """Total number of bytes classified as open-source code"""
        self.closed_code_size = 0
        """Total number of bytes classified as closed-source code"""
        self.data_size = 0
        """Total number of bytes classified as data"""
        self.empty_size = 0
        """Total number of bytes classified as empty"""
        self.open_code_files = []
        """A list holding CBFS files classified as open-source code"""
        self.closed_code_files = []
        """A list holding CBFS files classified as closed-source code"""
        self.data_files = []
        """A list holding CBFS files classified as data"""
        self.empty_files = []
        """A list holding CBFS empty spaces"""
        # This type of files will be counted as closed-source at the end of
        # metrics calculation. Keep them in separate array to export them into
        # CSV later for review.
        self.uncategorized_files = []
        """A list holding CBFS files that could not be classified. Counted
        as closed-source code at the end of calculation process.
        """
        self.edk2_ipxe = False
        """Variable to hold the status whether iPXE was built for EDK2"""
        self.ipxe_present = False
        """Variable to hold the status of iPXE presence in the CBFS"""
        self.ipxe_rom_id = None
        """Variable to hold the PCI ID used for iPXE build"""
        self.lan_rom_size = 0
        """Variable to hold the size of optional LAN EFI driver used in
        Dasharo builds. If such driver is detected based on coreboot config,
        the driver's size is subtracted from open-source code and added to
        closed-source code.
        """

        self.debug = verbose
        """Used to enable verbose debug output from the parsing process"""

        self._parse_cbfs_files()
        self._parse_cb_config()
        self._calculate_metrics()

    def __len__(self):
        """Returns the length of the CBFS region

        :return: Length of the CBFS
        :rtype: int
        """
        return self.cbfs_size

    def __repr__(self):
        """CBFSImage class representation

        :return: class representation
        :rtype: str
        """
        return 'CBFSImage()'

    def __str__(self):
        """Returns string representation of the CBFS

        Prints the firmware image statistics.

        :return: CBFSImage string representation
        :rtype: str
        """
        return 'CBFS region %s:\n' \
               '\tCBFS size: %d\n' \
               '\tNumber of files: %d\n' \
               '\tOpen-source files size: %d\n' \
               '\tClosed-source files size: %d\n' \
               '\tData size: %d\n' \
               '\tEmpty size: %d' % (
                    self.region_name,
                    self.cbfs_size,
                    self.num_files,
                    self.open_code_size,
                    self.closed_code_size,
                    self.data_size,
                    self.empty_size)

    def _parse_cbfs_files(self):
        """Parses the CBFS contents from cbfstool output

        Parses the output of 'cbfstool :attr:`coreboot.CBFSImage.image_path`
        print -r :attr:`coreboot.CBFSImage.region_name`' and extracts the CBFS
        files information to the :attr:`coreboot.CBFSImage.cbfs_files`
        dictionary using the :const:`coreboot.CBFSImage.file_regexp` regular
        expression.

        If :attr:`coreboot.CBFSImage.debug` is True, all CBFS contents with
        their attributes are printed on the console at the end.
        """
        cmd = ['cbfstool', self.image_path, 'print', '-r', self.region_name]
        cbfs_content = subprocess.run(cmd, text=True, capture_output=True)

        for match in re.finditer(self.file_regexp, cbfs_content.stdout):
            self.cbfs_files[self.num_files] = {
                'filename': match.group('filename'),
                'offset': int(match.group('offset'), 16),
                'filetype': match.group('filetype'),
                'size': int(match.group('size')),
                'compression': match.group('compression'),
            }

            self.num_files = self.num_files + 1

        if self.debug:
            print('Region %s CBFS contents:' % self.region_name)
            [print(self.cbfs_files[i]) for i in range(self.num_files)]

    def _calculate_metrics(self):
        """Calculates the sizes of the four basic firmware components
        categories

        Calls :meth:`~coreboot.CBFSImage._classify_file` for each detected
        CBFS file. Then sums the files' sizes from all 5 lists:

        :attr:`coreboot.CBFSImage.open_code_files` sizes sum is added to
        :attr:`coreboot.CBFSImage.open_code_size`

        :attr:`coreboot.CBFSImage.closed_code_files` sizes sum is added to
        :attr:`coreboot.CBFSImage.closed_code_size`

        :attr:`coreboot.CBFSImage.data_files` sizes sum is added to
        :attr:`coreboot.CBFSImage.data_size`

        :attr:`coreboot.CBFSImage.empty_files` sizes sum is added to
        :attr:`coreboot.CBFSImage.empty_size`

        :attr:`coreboot.CBFSImage.uncategorized_files` sizes sum is added to
        :attr:`coreboot.CBFSImage.closed_code_size`

        Additionally if a LAN EFI driver has been detected, it is subtracted
        from open-source code size (normally the driver is part ofthe payload
        considered to be open-source) and added to the closed-source size.

        At the end the method calls
        :meth:`coreboot.CBFSImage._normalize_sizes`
        """
        for i in range(self.num_files):
            self._classify_file(self.cbfs_files[i])

        self.open_code_size = self._sum_sizes(self.open_code_files)
        self.closed_code_size = self._sum_sizes(self.closed_code_files)
        self.data_size = self._sum_sizes(self.data_files)
        self.empty_size = self._sum_sizes(self.empty_files)
        self.closed_code_size += self._sum_sizes(self.uncategorized_files)
        if len(self.uncategorized_files) != 0:
            print('INFO: Found %d uncategorized files of total size %d bytes'
                  % (len(self.uncategorized_files),
                     self._sum_sizes(self.uncategorized_files)))
            print(self.uncategorized_files)

        # Account for an externally added LAN driver to the EDK2 payload. We
        # subtract the compressed size of the driver from the compressed size
        # of the paylaod counted as open-source and add the value to
        # closed-source.
        if self.lan_rom_size != 0:
            print('INFO: Found external LAN driver blob of size %d bytes'
                  % self.lan_rom_size)
            self.open_code_size -= self.lan_rom_size
            self.closed_code_size += self.lan_rom_size

        self._normalize_sizes()

    def _classify_file(self, file):
        """Classifies the CBFS file into basic categories.

        Each detected CBFS file is being classified into 4 basic categories
        and appended to respective lists.

        :attr:`coreboot.CBFSImage.open_code_files` are appended with CBFS
        files which type is found in
        :const:`coreboot.CBFSImage.OPEN_SOURCE_FILETYPES` and names are not
        found in :const:`coreboot.CBFSImage.CLOSED_SOURCE_EXCEPTIONS`. CBFS
        files of type 'raw' are also classified as open-source code if its
        name is found in :const:`coreboot.CBFSImage.RAW_OPEN_SOURCE_FILES` or
        if it is an iPXE legacy ROM (based on the PCI ID detected from
        coreboot's config).

        :attr:`coreboot.CBFSImage.closed_code_files` are appended with CBFS
        files which name is found in
        :const:`coreboot.CBFSImage.CLOSED_SOURCE_FILETYPES` or with CBFS
        file's type found in :const:`coreboot.CBFSImage.OPEN_SOURCE_FILETYPES`
        and name found in :const:`coreboot.CBFSImage.CLOSED_SOURCE_EXCEPTIONS`
        or with CBFS files of type 'raw' which names are found in
        :const:`coreboot.CBFSImage.RAW_CLOSED_SOURCE_FILES`.

        :attr:`coreboot.CBFSImage.empty_files` are appended with CBFS files
        with type 'null'.

        :attr:`coreboot.CBFSImage.data_files` are appended with CBFS files
        which type is found in :const:`coreboot.CBFSImage.DATA_FILETYPES` or
        with CBFS file of type 'raw' and names found in
        :const:`coreboot.CBFSImage.RAW_DATA_FILES`.

        Any other unrecognized CBFS files fall into
        :attr:`coreboot.CBFSImage.uncategorized_files` list which will be
        counted as closed-source code because we were unable to identify what
        can be inside.

        :param file: CBFS file entry from dictionary
        :type region: dict
        """
        if file['filetype'] in self.OPEN_SOURCE_FILETYPES:
            if file['filename'] not in self.CLOSED_SOURCE_EXCEPTIONS:
                self.open_code_files.append(file)
            else:
                self.closed_code_files.append(file)
        elif file['filetype'] in self.CLOSED_SOURCE_FILETYPES:
            self.closed_code_files.append(file)
        elif file['filetype'] in self.DATA_FILETYPES:
            self.data_files.append(file)
        elif file['filetype'] == 'null':
            self.empty_files.append(file)
        elif file['filetype'] == 'raw':
            if file['filename'] in self.RAW_DATA_FILES:
                self.data_files.append(file)
            elif file['filename'] in self.RAW_OPEN_SOURCE_FILES:
                self.open_code_files.append(file)
            elif file['filename'] in self.RAW_CLOSED_SOURCE_FILES:
                self.closed_code_files.append(file)
            # iPXE is added as a raw file
            elif self.ipxe_present and not self.edk2_ipxe:
                if file['filename'] == 'pci' + self.ipxe_rom_id + '.rom' or \
                   file['filename'] == 'pci' + self.ipxe_rom_id + '.rom.lzma':
                    self.open_code_files.append(file)
            else:
                self.uncategorized_files.append(file)
        else:
            self.uncategorized_files.append(file)

    def _normalize_sizes(self):
        """Ensures that all CBFS components sizes sum up to whole image size

        This function takes into account a situation when the CBFS is
        truncated (e.g. vboot RW CBFS regions). In such case we calculate the
        byte offset of the end of last file in CBFS and calculate the
        truncated size by subtracting the offset from the CBFS region size.
        The truncated size is then added to the
        :attr:`coreboot.CBFSImage.empty_size`.

        cbfstool prints only the sizes of files and does not account for the
        metadata surrounding the file. It is necessary to calculate the
        metadata size by subtarcting all file's sizes from the whole CBFS
        region size. The metadata size is then added to the
        :attr:`coreboot.CBFSImage.data_size`.
        """
        # We have to take into account truncated CBFSes like FW_MAIN_A or
        # FW_MAIN_B, where the space after the last file is empty but not
        # listed as such.
        last_file_end = (self.cbfs_files[self.num_files-1]['size'] +
                         self.cbfs_files[self.num_files-1]['offset'])
        truncated_size = self.cbfs_size - last_file_end

        # COREBOOT region will always have the bootblock at its end, so the
        # truncated_size will be always equal to 64 (size of metadata at the
        # beginning of the file). If the gap is bigger than 64 bytes, then it
        # means we have truncated CBFS and have to add the truncated_size to
        # the sum of empty files.
        if truncated_size > 64:
            self.empty_size += truncated_size

        # We have to normalize the total size of files in each group to the
        # total region size, because the cbfstool does not report the size of
        # the file metadata, so the sum of all file sizes would not match the
        # CBFS region size. This metadata will be counted as data bytes.
        metadata_size = self.cbfs_size - sum([self.open_code_size,
                                              self.empty_size,
                                              self.closed_code_size,
                                              self.data_size])

        self.data_size += metadata_size
        if self.debug:
            print('Size of metadata in %s CBFS: %d bytes'
                  % (self.region_name, metadata_size))

    def _sum_sizes(self, files):
        """Sums the size of the CBFS files

        :param files: Dictionary of files to sum
        :type files: dict
        :return: Sum of the files' sizes
        :rtype: int
        """
        return sum(list(f['size'] for f in files))

    def _get_kconfig_value(self, option):
        """Returns a value of given coreboot's Kconfig option

        :param option: Name of the Kconfig option without 'CONFIG\_' prefix.
        :type option: str
        :return: The value of Kconfig option
        :rtype: str
        """
        for i in range(len(self.kconfig_opts)):
            if self.kconfig_opts[i]['option'] == option:
                return self.kconfig_opts[i]['value']

        return None

    def _parse_cb_config(self):
        """Extracts and parses the CBFS config file

        The function uses the cbfstool to extract the coreboot's config and a
        regexp to extract the Kconfig names and values to
        :attr:`coreboot.CBFSImage.kconfig_opts`.

        Additionally the function calls
        :meth:`coreboot.CBFSImage._check_for_ipxe` and
        :meth:`coreboot.CBFSImage._check_for_lanrom`.
        """
        kconfig_pattern = r'^CONFIG_(?P<option>[A-Z0-9_]+?)=(?P<value>.*?)$'
        kconfig_pregexp = re.compile(kconfig_pattern, re.MULTILINE)

        cmd = ['cbfstool', self.image_path,
               'extract', '-n', 'config',
               '-f', '/tmp/cb_config_' + self.region_name,
               '-r', self.region_name]
        subprocess.run(cmd, text=True, capture_output=True)

        try:
            file = open('/tmp/cb_config_' + self.region_name, mode='r')
            cb_config = file.read()
            file.close()
        except FileNotFoundError:
            print('WARNING: Could not extract coreboot config')
            return

        for match in re.finditer(kconfig_pregexp, cb_config):
            self.kconfig_opts[self.num_opts] = {
                'option': match.group('option'),
                'value': match.group('value'),
            }
            self.num_opts = self.num_opts + 1

        if self.debug:
            print('Region %s CBFS config:' % self.region_name)
            [print(self.kconfig_opts[i]) for i in range(self.num_opts)]

        self._check_for_ipxe()
        self._check_for_lanrom()
        # Cleanup
        cmd = ['rm', '/tmp/cb_config_' + self.region_name]
        subprocess.run(cmd, text=True, capture_output=True)

    def _check_for_ipxe(self):
        """Checks whether iPXE was built int othe CBFS image and in what form

        The function checks for iPXE specific Kconfig options and sets the
        :attr:`coreboot.CBFSImage.edk2_ipxe`,
        :attr:`coreboot.CBFSImage.ipxe_present` and
        :attr:`coreboot.CBFSImage.ipxe_rom_id` based on the detected Kconfig
        values.
        """
        if self._get_kconfig_value('EDK2_ENABLE_IPXE') == 'y':
            self.edk2_ipxe = True
            # If EDK2 iPXE is chosen, CONFIG_PXE is selected as well and will
            # not be present in the config file. Worst case scenario If EDK2
            # iPXE option is set as default in the mainboard's Kconfig file
            # and will not be reflected in the CBFS config file.
            self.ipxe_present = True
        elif self._get_kconfig_value('PXE') == 'y':
            # Worst case scenario, PXE is set as default in the mainbaord's
            # Kconfig file and will not be reflected in the CBFS config file.
            # In such case the metrics will assume the pci$(pxe_rom_id).rom as
            # closed source. Also the PXE_ROM must not be found in the config,
            # it would mean an external binary.
            if self._get_kconfig_value('PXE_ROM') is None:
                self.ipxe_present = True

        self.ipxe_rom_id = self._get_kconfig_value('PXE_ROM_ID')
        # If the PXE ROM ID is not found, it means it has its default value.
        if self.ipxe_rom_id is None:
            self.ipxe_rom_id = '10ec,8168'

    def _check_for_lanrom(self):
        """Checks whether external LAN EFI driver has been included in UEFI
        Payload and calculates its estimated compressed size

        The function check for the LAn driver Kcofngi option. If it is
        present, then the cbfstool is called to extract the payload binary.
        Then UEFIExtract tries to extract the LAN EFI driver by the file GUID
        :attr:`coreboot.CBFSImage.DASHARO_LAN_ROM_GUID` from the payload
        binary. At the ned the extracted LAN EFI driver is compressed with
        lzma to estimate the driver's size occupying the UEFI Payload. The
        result is saved to :attr:`coreboot.CBFSImage.lan_rom_size`.
        """
        if self._get_kconfig_value('EDK2_LAN_ROM_DRIVER') is None:
            return
        # We determined there was an external LAN driver included. Now we
        # have to determine it's compressed size, because we have to
        # subtract the LAN driver size form compressed payload size.
        cmd = ['cbfstool', self.image_path,
               'extract', '-n', 'fallback/payload',
               '-f', '/tmp/payload_' + self.region_name,
               '-r', self.region_name,
               '-m', 'x86']
        subprocess.run(cmd, text=True, capture_output=True)

        lan_rom_file = '/tmp/lan_rom_' + self.region_name + '/body_1.bin'
        cmd = ['UEFIExtract', '/tmp/payload_' + self.region_name,
               self.DASHARO_LAN_ROM_GUID,
               '-o', '/tmp/lan_rom_' + self.region_name,
               '-m', 'body']
        subprocess.run(cmd, text=True, capture_output=True)

        if not Path(lan_rom_file).is_file():
            print('WARNING: Failed to extract LAN driver. '
                  'It will not be counted as closed-source')
            return
        # We do not use the same LZMA as cbfstool originally does, but the
        # resulting size different can be neglected, example: i225 EFI driver
        # uncompressed: 154064 bytes, cbfstool LZMA compressed 63445 bytes, OS
        # lzma (-6 default) compressed: 63320 bytes.
        cmd = ['lzma', '-z', '-c', lan_rom_file]
        lan_rom_compress = subprocess.run(cmd, text=False, capture_output=True)

        if lan_rom_compress.returncode == 0:
            self.lan_rom_size = len(lan_rom_compress.stdout)
        else:
            print('WARNING: Failed to compress LAN driver. '
                  'It will not be counted as closed-source')
            return

        # Cleanup
        cmd = ['rm', '-rf'
               '/tmp/payload_' + self.region_name,
               '/tmp/lan_rom_' + self.region_name]
        subprocess.run(cmd, text=True, capture_output=True)

    def _export_files_md(self, file, cbfs_files, category):
        """Writes the CBFS files for given category to the markdown file

        :param file: Markdown file handle to write the CBFS files' info to
        :type file: file
        :param cbfs_files: Dictionary containing CBFS files to be written to
                           the markdown file.
        :type regions: dict
        :param category: Category of the CBFS files to be written to the
                         markdown file. Should be one of: open-source,
                         closed-source, data, empty.
        :type category: str
        """
        for f in cbfs_files:
            file.write('| {} | {} | {} | {} | {} |\n'.format(
                        f['filename'], f['filetype'],
                        f['size'], f['compression'], category))

    def export_markdown(self, file, mkdocs):
        """Saves the openness report in markdown format for given CBFS region

        Saves the parsed information and classified CBFS components into a
        markdown file.

        :param file: Markdown file handle
        :type file: str
        :param mkdocs: Switch to export the report for mkdocs
        :type mkdocs: bool
        """
        if not mkdocs:
            file.write('## CBFS %s\n\n' % self.region_name)
        else:
            file.write('### CBFS %s\n\n' % self.region_name)

        file.write('* CBFS size: %d\n'
                   '* Number of files: %d\n'
                   '* Open-source files size: %d (%s)\n'
                   '* Closed-source files size: %d (%s)\n'
                   '* Data size: %d (%s)\n'
                   '* Empty size: %d (%s)\n\n' % (
                        self.cbfs_size,
                        self.num_files,
                        self.open_code_size, hex(self.open_code_size),
                        self.closed_code_size, hex(self.closed_code_size),
                        self.data_size, hex(self.data_size),
                        self.empty_size, hex(self.empty_size)))

        file.write('> Numbers given above are already normalized (i.e. they'
                   ' already include size\n> of metadata and possible'
                   ' closed-source LAN drivers included in the payload\n'
                   '> which are not visible in the table below)\n\n')

        file.write('| CBFS filename | CBFS filetype | Size | Compression |'
                   ' Category |\n')
        file.write('| ------------- | ------------- | ---- | ----------- |'
                   ' -------- |\n')

        self._export_files_md(file, self.open_code_files, 'open-source')
        self._export_files_md(file, self.closed_code_files, 'closed-source')
        self._export_files_md(file, self.data_files, 'data')
        self._export_files_md(file, self.empty_files, 'empty')
