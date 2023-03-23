# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import pprint
import re
import os
import subprocess
from typing import List


class DasharoCorebootImage:

    region_patterns = [
        r"'(?P<region>[A-Z_]+?)' ",
        r"\((?P<attribute>(read-only, |preserve, |CBFS, ){0,1}?)",
        r"size (?P<size>\d+?), offset (?P<offset>\d+?)\)"
    ]

    region_pregexp = re.compile(''.join(region_patterns), re.MULTILINE)

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

        for match in re.finditer(self.region_pregexp, layout.stdout):
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

    cbfs_filetypes = [
        'bootblock', 'cbfs header', 'stage', 'simple elf', 'fit_payload',
        'optionrom', 'bootsplash', 'raw', 'vsa', 'mbi', 'microcode',
        'intel_fit', 'fsp', 'mrc', 'cmos_default', 'cmos_layout', 'spd',
        'mrc_cache', 'mma', 'efi', 'struct', 'deleted', 'null', 'amdfw'
    ]

    open_source_filetypes = [
        'bootblock', 'stage', 'simple elf', 'fit_payload',
    ]

    closed_source_filetypes = [
        'optionrom', 'vsa', 'mbi', 'microcode', 'fsp', 'mrc', 'mma', 'efi',
        'amdfw'
    ]

    data_filetypes = [
        'cbfs header', 'bootsplash', 'intel_fit', 'cmos_default',
        'cmos_layout', 'spd', 'mrc_cache', 'struct',
    ]

    # Some binary blobs containing code are not added as raw files or as fsp,
    # etc, for example refcode blob is a stage type. We keep them here to
    # account for such exceptions. Some non-x86 files are also here for the
    # future. The list may not be exhaustive. Search for "cbfs-files" pattern
    # in coreobot Makefiles.
    closed_source_exceptions = [
        'fallback/refcode', 'fallback/secure_os', 'fallback/dram',
        'fallback/qcsdi', 'fallback/qclib', 'fallback/pmiccfg',
        'fallback/dcb', 'fallback/dcb_longsys1p8', 'fallback/aop',
        'fallback/uart_fw', 'fallback/spi_fw', 'fallback/i2c_fw',
        'fallback/cpucp', 'fallback/shrm', 'fallback/gsi_fw',
    ]

    # Filetype raw can be anything and can also be named arbitrarily. We trust
    # that Dasharo binary is unmodified and standard names used by coreboot
    # have not been misused to hide blobs. These names are below for data and
    # code respecitvely. We also assume VBT to be data, becasue Intel publishes
    # VBT BSF/JSON files with the meaning of each byte in it. The lists may not
    # be exhaustive. Search for "cbfs-files" pattern in coreobot Makefiles.
    raw_data_files = [
        'config', 'revision', 'build_info', 'vbt.bin', 'payload_config',
        'payload_revision', 'etc/grub.cfg', 'logo.bmp', 'rt8168-macaddress',
        'atl1e-macaddress', 'wifi_sar_defaults.hex', 'ecrw.hash', 'pdrw.hash',
        'oem.bin', 'sbom', 'boot_policy_manifest.bin', 'key_manifest.bin',
        'txt_bios_policy.bin', 'apu/amdfw_a', 'apu/amdfw_b', 'me_rw.hash',
        'me_rw.version', 'vboot_public_key.bin'
    ]

    # Everything derived from open-source code which is an executable code or
    # was created from open-source code in a reproducible way
    raw_open_source_files = [
        'fallback/dsdt.aml', 'vgaroms/seavgabios.bin', 'pagetables', 'pt',
        'pdpt', 'ecrw', 'pdrw', 'sff8104-linux.dtb', 'stm.bin', 'fallback/DTB',
        'oemmanifest.bin', 'smcbiosinfo.bin'
    ]

    # PSE binary is treated as closed source as there is no guarantee of open
    # code availability for given build.
    raw_closed_source_files = [
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

    file_patterns = [
        r"(?P<filename>[a-zA-Z0-9\(\)\/\.\,\_\-]*?)\s+",
        r"(?P<offset>0x[0-9a-f]+?)\s+",
        r"(?P<filetype>(" + "|".join(cbfs_filetypes) + r"){1}?)\s+",
        r"(?P<size>\d+?)\s+(?P<compression>\w+?)(\s+\(\d+ \w+\))?$"
    ]

    file_regexp = re.compile(''.join(file_patterns), re.MULTILINE)

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

        for match in re.finditer(self.file_regexp, cbfs_content.stdout):
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
