# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import re
import os
import subprocess
from pathlib import Path
from typing import List

debug = False


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
    BLOB_REGIONS = ['RW_VBIOS_CACHE', 'ME_RW_A', 'ME_RW_B', 'IFWI', 'SIGN_CSE',
                    'SI_ME']

    # Regions to not account for in calculations.
    # These are containers aggregating smaller regions.
    SKIP_REGIONS = ['RW_MISC', 'UNIFIED_MRC_CACHE', 'RW_SHARED', 'SI_ALL',
                    'RW_SECTION_A', 'RW_SECTION_B', 'WP_RO', 'RO_SECTION']

    # Regions to count as empty/unused
    EMPTY_REGIONS = ['UNUSED']

    def __init__(self, image_path):
        self.image_path = image_path
        self.image_size = os.path.getsize(image_path)
        self.fmap_regions = {}
        self.cbfs_images = []
        self.num_regions = 0
        self.num_cbfses = 0
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0
        self.open_code_regions = []
        self.closed_code_regions = []
        self.data_regions = []
        self.empty_regions = []
        # This type of regions will be counted as closed-source at the end of
        # metrics calculation. Keep them in separate array to export them into
        # CSV later for review.
        self.uncategorized_regions = []

        self._parse_cb_fmap_layout()
        self._calculate_metrics()

    def __len__(self):
        return self.image_size

    def __repr__(self):
        return 'DasharoCorebootImage()'

    def __str__(self):
        return 'Dasharo image %s:\n' \
               '\tImage size: %d\n' \
               '\tNumber of regions: %d\n' \
               '\tNumber of CBFSes: %d\n' \
               '\tTotal open-source files size: %d\n' \
               '\tTotal closed-source files size: %d\n' \
               '\tTotal data size: %d\n' \
               '\tTotal empty size: %d' % \
                (self.image_path,
                 self.image_size,
                 self.num_regions,
                 self.num_cbfses,
                 self.open_code_size,
                 self.closed_code_size,
                 self.data_size,
                 self.empty_size)

    def _region_is_cbfs(self, region):
        if region['attributes'] == 'CBFS':
            return True
        else:
            return False

    def _parse_cb_fmap_layout(self):
        cmd = ['cbfstool', self.image_path, 'layout', '-w']
        layout = subprocess.run(cmd, text=True, capture_output=True)

        for match in re.finditer(self.region_pregexp, layout.stdout):
            self.fmap_regions[self.num_regions] = {
                'name': match.group('region'),
                'offset': int(match.group('offset')),
                'size': int(match.group('size')),
                'attributes': match.group('attribute').strip(', '),
            }

            if self._region_is_cbfs(self.fmap_regions[self.num_regions]):
                cbfs = CBFSImage(self.image_path,
                                 self.fmap_regions[self.num_regions])
                self.cbfs_images.append(cbfs)
                self.num_cbfses += 1
                print(cbfs)

            self.num_regions += 1

        if debug:
            print('Dasharo image regions:')
            [print(self.fmap_regions[i]) for i in range(self.num_regions)]

    def _classify_region(self, region):
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
        for i in range(self.num_regions):
            self._classify_region(self.fmap_regions[i])

        self.open_code_size = self._sum_sizes(self.open_code_regions)
        self.closed_code_size = self._sum_sizes(self.closed_code_regions)
        self.data_size = self._sum_sizes(self.data_regions)
        self.empty_size = self._sum_sizes(self.empty_regions)
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
        return sum(list(r['size'] for r in regions))

    def _normalize_sizes(self):
        # It may happen that the FMAP does not cover whole flash size and the
        # first region will start with non-zero offset. Check if first region
        # offset is zero, if not count all bytes from the start of flash to the
        # start of first region as clsoed source.
        if self.fmap_regions[0]['offset'] != 0:
            self.closed_code_size += self.fmap_regions[0]['offset']

        # Final check if all sizes are summing up to whole image size
        full_size = sum([self.open_code_size, self.empty_size,
                         self.closed_code_size, self.data_size])
        if full_size != self.image_size:
            print('WARNING: Something went wrong.\n'
                  'The component sizes do not sum up to the image size. '
                  '%d != %d' % (full_size, self.image_size))


class CBFSImage:

    CBFS_FILETYPES = [
        'bootblock', 'cbfs header', 'stage', 'simple elf', 'fit_payload',
        'optionrom', 'bootsplash', 'raw', 'vsa', 'mbi', 'microcode',
        'intel_fit', 'fsp', 'mrc', 'cmos_default', 'cmos_layout', 'spd',
        'mrc_cache', 'mma', 'efi', 'struct', 'deleted', 'null', 'amdfw'
    ]

    OPEN_SOURCE_FILETYPES = [
        'bootblock', 'stage', 'simple elf', 'fit_payload',
    ]

    CLOSED_SOURCE_FILETYPES = [
        'optionrom', 'vsa', 'mbi', 'microcode', 'fsp', 'mrc', 'mma', 'efi',
        'amdfw'
    ]

    DATA_FILETYPES = [
        'cbfs header', 'bootsplash', 'intel_fit', 'cmos_default',
        'cmos_layout', 'spd', 'mrc_cache', 'struct',
    ]

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
        'me_rw.version', 'vboot_public_key.bin'
    ]

    # Everything derived from open-source code which is an executable code or
    # was created from open-source code in a reproducible way
    RAW_OPEN_SOURCE_FILES = [
        'fallback/dsdt.aml', 'vgaroms/seavgabios.bin', 'pagetables', 'pt',
        'pdpt', 'ecrw', 'pdrw', 'sff8104-linux.dtb', 'stm.bin', 'fallback/DTB',
        'oemmanifest.bin', 'smcbiosinfo.bin', 'genroms/pxe.rom'
    ]

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

    DASHARO_LAN_ROM_GUID = 'DEB917C0-C56A-4860-A05B-BF2F22EBB717'

    file_patterns = [
        r"(?P<filename>[a-zA-Z0-9\(\)\/\.\,\_\-]*?)\s+",
        r"(?P<offset>0x[0-9a-f]+?)\s+",
        r"(?P<filetype>(" + "|".join(CBFS_FILETYPES) + r"){1}?)\s+",
        r"(?P<size>\d+?)\s+(?P<compression>\w+?)(\s+\(\d+ \w+\))?$"
    ]

    file_regexp = re.compile(''.join(file_patterns), re.MULTILINE)

    def __init__(self, image_path, region):
        self.image_path = image_path
        self.region_name = region['name']
        self.cbfs_size = region['size']
        self.cbfs_files = {}
        self.kconfig_opts = {}
        self.num_files = 0
        self.num_opts = 0
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0
        self.open_code_files = []
        self.closed_code_files = []
        self.data_files = []
        self.empty_files = []
        # This type of files will be counted as closed-source at the end of
        # metrics calculation. Keep them in separate array to export them into
        # CSV later for review.
        self.uncategorized_files = []
        self.edk2_ipxe = False
        self.ipxe_present = False
        self.ipxe_rom_id = None
        self.lan_rom_size = 0

        self._parse_cbfs_files()
        self._parse_cb_config()
        self._calculate_metrics()

    def __len__(self):
        return self.cbfs_size

    def __repr__(self):
        return 'CBFSImage()'

    def __str__(self):
        return 'CBFS region %s:\n' \
               '\tCBFS size: %d\n' \
               '\tNumber of files: %d\n' \
               '\tOpen-source files size: %d\n' \
               '\tClosed-source files size: %d\n' \
               '\tData size: %d\n' \
               '\tEmpty size: %d' % \
                (self.region_name,
                 self.cbfs_size,
                 self.num_files,
                 self.open_code_size,
                 self.closed_code_size,
                 self.data_size,
                 self.empty_size)

    def _parse_cbfs_files(self):
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

        if debug:
            print('Region %s CBFS contents:' % self.region_name)
            [print(self.cbfs_files[i]) for i in range(self.num_files)]

    def _calculate_metrics(self):
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
                if file['filename'] == 'pci' + self.ipxe_rom_id + '.rom':
                    self.open_code_files.append(file)
            else:
                self.uncategorized_files.append(file)
        else:
            self.uncategorized_files.append(file)

    def _normalize_sizes(self):
        # We have to take into account truncated CBFSes like FW_MAIN_A or
        # FW_MAIN_B, where the space after the last file is empty but not
        # listed as such.
        last_file_end = self.cbfs_files[self.num_files-1]['size'] + \
                        self.cbfs_files[self.num_files-1]['offset']
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
        if debug:
            print('Size of metadata in %s CBFS: %d bytes'
                  % (self.region_name, metadata_size))

    def _sum_sizes(self, files):
        return sum(list(f['size'] for f in files))

    def _get_kconfig_value(self, option):
        for i in range(len(self.kconfig_opts)):
            if self.kconfig_opts[i]['option'] == option:
                return self.kconfig_opts[i]['value']

        return None

    def _parse_cb_config(self):
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

        if debug:
            print('Region %s CBFS config:' % self.region_name)
            [print(self.kconfig_opts[i]) for i in range(self.num_opts)]

        self._check_for_ipxe()
        self._check_for_lanrom()
        # Cleanup
        cmd = ['rm', '/tmp/cb_config_' + self.region_name]
        subprocess.run(cmd, text=True, capture_output=True)

    def _check_for_ipxe(self):
        if self._get_kconfig_value('EDK2_ENABLE_IPXE') == 'y':
            self.edk2_ipxe = True
            # If EDK2 iPXE is chosen, CONFIG_PXE is selected as well and will
            # not be present in the config file. Worst case scenario If EDK2
            # iPXE option is set as default in the mainboard's Kconfig file and
            # will not be reflected in the CBFS config file.
            self.ipxe_present = True
        elif self._get_kconfig_value('PXE') == 'y':
            # Worst case scenario, PXE is set as default in the mainbaord's
            # Kconfig file and wil not be reflected in the CBFS config file. In
            # such case the matrics will assume the pci$(pxe_rom_id).rom as
            # closed source. Also the PXE_ROM must not be found in the config,
            # it would mean an external binary.
            if self._get_kconfig_value('PXE_ROM') is None:
                self.ipxe_present = True

        self.ipxe_rom_id = self._get_kconfig_value('PXE_ROM_ID')
        # If the PXE ROM ID is not found, it means it has its default value.
        if self.ipxe_rom_id is None:
            self.ipxe_rom_id = '10ec,8168'

    def _check_for_lanrom(self):
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
