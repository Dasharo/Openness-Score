# SPDX-FileCopyrightText: 2023 3mdeb <contact@3mdeb.com>
#
# SPDX-License-Identifier: MIT

import re
import os
import sys
import subprocess
from typing import List

debug = False


class UEFIImage:

    # Format: Type, Subtype, Name
    EMPTY_REGION_PADDING = [
        # First level padding present between IFD regions
        [ 'Padding', 'Empty (0xFF)', '- Padding' ],
        [ 'Padding', 'Empty (0x00)', '- Padding' ]
    ]

    EMPTY_BIOS_PADDING = [
        # Second level padding between volumes (ME firmware can also contain
        # such padding thus in separate array)
        [ 'Padding', 'Empty (0xFF)', '-- Padding' ],
        [ 'Padding', 'Empty (0x00)', '-- Padding' ]
    ]

    NON_EMPTY_REGION_PADDING = [
        # First level padding present between IFD regions
        [ 'Padding', 'Non-empty', '- Padding' ]
    ]

    NON_EMPTY_BIOS_PADDING = [
        # Second level padding between volumes (ME firmware can also contain
        # such padding thus in separate array)
        [ 'Padding', 'Non-empty', '-- Padding' ]
    ]

    # TODO: Ensure Reserved1, Reserved2, PTT, DevExp1 and DevExp2 are
    # indeed closed-source.
    CLOSED_SOURCE_REGIONS = [ 'ME', 'DevExp1', 'DevExp2', 'Microcode', 'EC',
                              'IE', 'PTT', 'Reserved1', 'Reserved2', ]

    DATA_REGIONS = ['Descriptor', 'GbE', 'PDR', '10GbE1', '10GbE2', ]

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

    def __init__(self, image_path):
        self.image_path = image_path
        self.image_size = os.path.getsize(image_path)
        self.uefi_entries = {}
        self.volumes = []
        self.regions = []
        self.bios_region = {}
        self.num_regions = 0
        self.num_volumes = 0
        self.num_entries = 0
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0
        self.closed_code_regions = []
        self.data_regions = []
        self.empty_spaces = []

        self._parse_uefi_image()
        self._calculate_metrics()

    def __len__(self):
        return self.image_size

    def __repr__(self):
        return "UEFIImage()"

    def __str__(self):
        return 'Vendor UEFI image %s:\n' \
               '\tImage size: %d\n' \
               '\tNumber of entries: %d\n' \
               '\tNumber of regions: %d\n' \
               '\tNumber of volumes: %d\n' \
               '\tTotal open-source files size: %d\n' \
               '\tTotal closed-source files size: %d\n' \
               '\tTotal data size: %d\n' \
               '\tTotal empty size: %d' % \
                (self.image_path,
                 self.image_size,
                 self.num_entries,
                 self.num_regions,
                 self.num_volumes,
                 self.open_code_size,
                 self.closed_code_size,
                 self.data_size,
                 self.empty_size)

    def _parse_uefi_image(self):
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

        if debug:
            print("UEFI image entries:")
            [print(self.uefi_entries[i]) for i in range(self.num_entries)]

    def _entry_is_volume(self, entry):
        # Take only the top level volumes. Volems that are nested/compressed
        # will have size of -1 (N/A).
        if entry['type'] == 'Volume' and entry['size'] != -1:
            return True
        else:
            return False

    def _is_entry_nested_volume(self, entry):
        # Ignore nested uncompressed volumes, they will be handled inside
        # UEFIVolume class. FSP-S is an example where multiple uncompressed
        # volumes exist.
        for i in range(self.num_volumes):
            volume_start = self.volumes[i].volume_base
            volume_end = self.volumes[i].volume_base + self.volumes[i].volume_size
            if entry['base'] >= volume_start and \
               entry['base'] + entry['size'] <= volume_end:
                return True
            
        return False


    def _entry_is_region(self, entry):
        if entry['type'] == 'Region':
            return True
        else:
            return False

    def _is_entry_inside_bios_region(self, entry):
        # We ignore nested/compressed entries. We only care about padding that
        # have a base and size which are inside BIOS region. We handle regions
        # separately.
        bios_start = self.bios_region['base']
        bios_end = self.bios_region['base'] + self.bios_region['size']
        if entry['base'] == -1:
            return False
        elif self._entry_is_region(entry):
            return False
        elif entry['base'] < bios_start or entry['base'] >= bios_end:
            return False
        elif entry['base'] >= bios_start and \
             entry['base'] + entry['size'] <= bios_end:
            return True
        else:
            print('ERROR: Could not determine if entry is in BIOS region')
            print(entry)
            return False

    def _classify_entries(self):
        for i in range(self.num_entries):
            if self._entry_is_volume(self.uefi_entries[i]) and \
               self._is_entry_inside_bios_region(self.uefi_entries[i]):
                if not self._is_entry_nested_volume(self.uefi_entries[i]):
                    volume = UEFIVolume(self.uefi_entries, i)
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
            elif entry_type in self.NON_EMPTY_BIOS_PADDING and \
                 self._is_entry_inside_bios_region(self.uefi_entries[i]):
                self.data_regions.append(self.uefi_entries[i])
            elif entry_type in self.EMPTY_REGION_PADDING:
                self.empty_spaces.append(self.uefi_entries[i])
            elif entry_type in self.NON_EMPTY_REGION_PADDING:
                self.data_regions.append(self.uefi_entries[i])

        if debug:
            print("UEFI image empty entries:")
            [print(self.empty_spaces[i]) for i in range(len(self.empty_spaces))]
            print("UEFI image data entries:")
            [print(self.data_regions[i]) for i in range(len(self.data_regions))]
            print("UEFI image closed-code entries:")
            [print(self.closed_code_regions[i]) for i in range(len(self.closed_code_regions))]

    def _sum_sizes(self, files):
        return sum(list(f['size'] for f in files))

    def _calculate_metrics(self):
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
        for i in range(self.num_regions):
            if self.regions[i]['subtype'] in self.CLOSED_SOURCE_REGIONS:
                self.closed_code_size += self.regions[i]['size']
            elif self.regions[i]['subtype'] in self.DATA_REGIONS:
                self.data_size += self.regions[i]['size']
            elif self.regions[i]['subtype'] == 'BIOS':
                # Do nothing. BIOS region is comprised of FVs which are parsed
                # separately.
                continue
            else:
                print('WARNING: Found unclassified region %s.\n'
                      'Counting it as closed-source.' % self.regions[i]['subtype'])

        # Final check if all sizes are summing up to whole image size
        full_size = sum([self.open_code_size, self.empty_size,
                         self.closed_code_size, self.data_size])

        self.data_size += (self.image_size - full_size)

        if full_size != self.image_size:
            print('ERROR: Something went wrong.\n'
                  'The component sizes do not sum up to the image size. '
                  '%d != %d' % (full_size, self.image_size))


class UEFIVolume:

    # The ratio of NVAR entries vs all entries in given volume to callsify
    # whole volume as NVAR.
    NVAR_VOLUME_THRESHOLD = 90

    def __init__(self, uefi_entries, entry_idx):
        self.uefi_entries = uefi_entries
        self.volume_idx = entry_idx
        self.volume_base = uefi_entries[entry_idx]['base']
        self.volume_size = uefi_entries[entry_idx]['size']
        self.volume_end = self.volume_base + self.volume_size
        self.volume_type = uefi_entries[entry_idx]['subtype']
        self.volume_entries = []
        self.nested_volumes = []
        self.open_code_size = 0
        self.closed_code_size = 0
        self.data_size = 0
        self.empty_size = 0
        self.open_code_files = []
        self.closed_code_files = []
        self.data_files = []
        self.empty_files = []

        self._parse_volume_files()
        self._calculate_metrics()

    def __len__(self):
        return self.volume_size

    def __repr__(self):
        return "UEFIVolume()"

    def __str__(self):
        return 'UEFI Volume:\n' \
               '\tBase: %s\n' \
               '\tSize: %s\n' \
               '\tNumber of entries: %d\n' \
               '\tOpen-source code size: %d\n' \
               '\tClosed-source code size: %d\n' \
               '\tData size: %d\n' \
               '\tEmpty size: %d' % \
                (hex(self.volume_base),
                 hex(self.volume_size),
                 len(self.volume_entries),
                 self.open_code_size,
                 self.closed_code_size,
                 self.data_size,
                 self.empty_size)

    def _entry_is_inside_volume(self, entry):
        # Each volume starts with an entry that has a base and size.
        # Automatically accept all files in the middle that has base of -1
        # (N/A). If we reach the end of volume (the last entry base + size
        # equal to volume_end) this function will not be called anymore.
        if entry['base'] != -1:
            if self._entry_is_region(entry):
                return False
            if self._entry_is_self_volume(entry):
                return False
            elif entry['base'] < self.volume_base or \
                 entry['base'] >= self.volume_end:
                return False
            elif entry['base'] >= self.volume_base and \
               entry['base'] + entry['size'] <= self.volume_end:
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
        if entry['type'] == 'Region':
            return True
        else:
            return False

    def _entry_is_self_volume(self, entry):
        if entry['type'] == 'Volume' and \
           entry['base'] == self.volume_base and \
           entry['size'] == self.volume_size:
            return True
        else:
            return False

    def _entry_is_nested_volume(self, entry):
        # Volumes that are nested/uncompressed will have a valid size.
        if entry['type'] == 'Volume' and entry['size'] != -1 and \
           entry['subtype'] == 'FFSv2':
            if entry['base'] < self.volume_base or \
               entry['base'] >= self.volume_end:
                return False
            elif entry['base'] >= self.volume_base and \
               entry['base'] + entry['size'] <= self.volume_end:
                return True

        return False

    def _parse_volume_files(self):
        for i in range(self.volume_idx + 1, len(self.uefi_entries)):
            if self._entry_is_inside_volume(self.uefi_entries[i]):
                if self._entry_is_nested_volume(self.uefi_entries[i]):
                    nested_volume = UEFIVolume(self.uefi_entries, i)
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

        if debug:
            print("UEFI volume entries:")
            [print(self.volume_entries[i]) for i in range(len(self.volume_entries))]

    def _classify_entries(self):
        # We only calssigy empty and non-empty pads and free space, everything
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

        if debug:
            print("UEFI volume empty entries:")
            [print(self.empty_files[i]) for i in range(len(self.empty_files))]
            print("UEFI volume data entries:")
            [print(self.data_files[i]) for i in range(len(self.data_files))]

    def _is_entry_empty_padding(self, entry):
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Padding':
                if entry['subtype'] == 'Empty (0xFF)' or \
                   entry['subtype'] == 'Empty (0x00)':
                    return True

        return False

    def _is_entry_non_empty_padding(self, entry):
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Padding':
                if entry['subtype'] == 'Non-empty':
                    return True

        return False

    def _is_entry_free_space(self, entry):
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'Free space':
                    return True

        return False

    def _is_entry_empty_pad_file(self, entry):
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'File':
                if entry['subtype'] == 'Pad':
                    if 'Pad-file' in entry['name']:
                        return True

        return False

    def _is_entry_non_empty_pad_file(self, entry):
        # The entry must have a base and size, otherwise it is compressed and
        # we don't care about it.
        if entry['base'] != -1 and entry['size'] != 0:
            if entry['type'] == 'File':
                if entry['subtype'] == 'Pad':
                    if 'Non-empty pad-file' in entry['name']:
                        return True

        return False

    def _sum_sizes(self, files):
        return sum(list(f['size'] for f in files))

    def _is_nvar_store_volume(self):
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
        self._classify_entries()
        # We do not calculate any open-source code. Let's be honest, there
        # isn't any truly open-source code in vendor images.
        self.closed_code_size += self._sum_sizes(self.closed_code_files)
        self.data_size += self._sum_sizes(self.data_files)
        self.empty_size += self._sum_sizes(self.empty_files)
        self._normalize_sizes()

    def _normalize_sizes(self):
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
