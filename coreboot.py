# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import pprint
import re
import os
import subprocess
from typing import List


class DasharoCorebootImage:

    region_pattern = r'\'(?P<region>[A-Z_]+?)\' ' \
                     r'\((?P<attribute>(read-only, |preserve, |CBFS, )??)' \
                     r'size (?P<size>\d+?), offset (?P<offset>\d+?)\)'

    # Regions to consider as data, they should not contain any code ever.
    # Some of the regions are used only by certain platforms and may not be met
    # on Dasharo builds.
    DATA_REGIONS = ['SI_DESC', 'RECOVERY_MRC_CACHE', 'RW_MRC_CACHE', 'RW_VPD',
                    'SMMSTORE', 'SHARED_DATA', 'VBLOCK_DEV', 'RW_NVRAM', 'GBB',
                    'CONSOLE', 'RW_FWID_A', 'RW_FWID_B', 'VBLOCK_A', 'RO_VPD',
                    'VBLOCK_B', 'HSPHY_FW', 'RW_ELOG', 'FMAP', 'RO_FRID',
                    'RO_FRID_PAD', 'SPD_CACHE', 'FPF_STATUS', 'RO_LIMITS_CFG',
                    'RW_DDR_TRAINING']

    # Regions that are not CBFSes and may contain open-source code
    # Their whole size is counted as code.
    CODE_REGIONS = ['BOOTBLOCK']

    # Regions that may contain code but in closed-source binary form
    # HSPHY_FW does not belong here, because it is part of ME which counts
    # as closed-source binary blob as a whole.
    BLOB_REGIONS = ['RW_VBIOS_CACHE', 'ME_RW_A', 'ME_RW_B', 'IFWI', 'SIGN_CSE']

    # Regions to not account for in calculations.
    # These are containers aggregating smaller regions.
    SKIP_REGIONS = ['RW_MISC', 'UNIFIED_MRC_CACHE', 'RW_SHARED',
                    'RW_SECTION_A', 'RW_SECTION_B', 'SI_ALL']

    # Regions to count as empty/unused
    EMPTY_REGIONS = ['UNUSED']

    def __init__(self, image_path):
        self.image_path = image_path
        self.image_size = os.path.getsize(image_path)
        self.fmap_regions = {}
        self.cbfs_images = []
        self.num_regions = 0
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0

        self._parse_cb_fmap_layout()

    def __len__(self):
        return self.image_size

    def _region_is_cbfs(self, region):
        if region['attributes'] == 'CBFS':
            return True
        else:
            return False

    def _parse_cb_fmap_layout(self):
        cmd = ["cbfstool", self.image_path, "layout", "-w"]
        layout = subprocess.run(cmd, text=True, capture_output=True)

        for match in re.finditer(self.region_pattern, layout.stdout):
            self.fmap_regions[self.num_regions] = {
                'region': match.group('region'),
                'offset': int(match.group('offset')),
                'size': int(match.group('size')),
                'attributes': match.group('attribute').strip(', '),
            }

            if self._region_is_cbfs(self.fmap_regions[self.num_regions]):
                cbfs = CBFSImage(self.image_path,
                                 self.fmap_regions[self.num_regions])
                self.cbfs_images.append(cbfs)

            self.num_regions = self.num_regions + 1

        print("Dasharo image regions:")
        [print(self.fmap_regions[i]) for i in range(self.num_regions)]


class CBFSImage:

    file_pattern = r'(?P<filename>[a-zA-Z0-9\(\)\/\.\,\_\-]*?)\s*' \
                   r'(?P<offset>0x[0-9a-f]+?)\s*' \
                   r'(?P<filetype>(bootblock|cbfs header|stage|simple elf|' \
                   r'fit_payload|optionrom|bootsplash|raw|vsa|mbi|microcode|' \
                   r'intel_fit|fsp|mrc|cmos_default|cmos_layout|spd|' \
                   r'mrc_cache|mma|efi|struct|deleted|null|amdfw){1}?)\s+' \
                   r'(?P<size>\d+?)\s+(?P<compression>\w+\b?).*'

    def __init__(self, image_path, region):
        self.image_path = image_path
        self.region_name = region['region']
        self.cbfs_size = region['size']
        self.cbfs_files = {}
        self.num_files = 0
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0

        self._parse_cbfs_files()

    def __len__(self):
        return self.cbfs_size

    def _parse_cbfs_files(self):
        cmd = ["cbfstool", self.image_path, "print", "-r", self.region_name]
        cbfs_content = subprocess.run(cmd, text=True, capture_output=True)

        for match in re.finditer(self.file_pattern, cbfs_content.stdout):
            self.cbfs_files[self.num_files] = {
                'filename': match.group('filename'),
                'offset': int(match.group('offset'), 16),
                'filetype': match.group('filetype'),
                'size': int(match.group('size')),
                'compression': match.group('compression'),
            }

            self.num_files = self.num_files + 1

        print("Region %s CBFS contents:" % self.region_name)
        [print(self.cbfs_files[i]) for i in range(self.num_files)]
