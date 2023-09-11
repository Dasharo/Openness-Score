Dasharo Openness Score methodology
==================================

Dasharo Openness Score calculation methodology is different for UEFI images
and coreboot-based images mainly due to their different structure, but also
for calculation simplicity.

Calculating Dasharo Openness Score for UEFI images
--------------------------------------------------

Axiom: UEFI images are always assumed to be vendor firmware images, thus the
methodology assumes no open-source code.

The utility makes decisions based on the report produced by UEFIExtract.
The calculation flow looks as follows:

1. Look for the entries of type ``Region`` and save their properties for later.
   Also separate the BIOS Region which will be used later.
2. Start classifying entries:

   * Take all non-BIOS regions and classify them as either closed-source group
     or data regions, based on known region types. For unknown region
     types, classify it as closed-source region.
   * Take all entries in the BIOS region and extract UEFI Firmware Volumes
     from them. Create new :class:`uefi.UEFIVolume` instances, which trigger
     the UEFI Volume calculations described in section `Calculating metrics
     for UEFI Firmware Volumes`_. Save all instances in the array for future
     calculations.
   * Take all empty paddings between UEFI Firmware Volumes in BIOS region and
     between regions and add them to the empty region group.
   * Take all non-empty paddings between UEFI Firmware Volumes in BIOS region
     and between regions and add them to the data region group.

3. Sum up the size of all region groups: empty, data and closed-source.
4. Sum up the size of all groups from all :class:`uefi.UEFIVolume` instances
   saved in the array previously: empty, data and closed-source.
5. Check if the sums from point 3 and 4 give the total size of the image. If
   yes, do nothing. If not add the difference to the data group and print an
   error.
6. Export the data to markdown and pie charts using the
   :meth:`uefi.UEFIVolume.export_markdown`.

Calculating metrics for UEFI Firmware Volumes
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Axiom: Some UEFI Firmware Volumes may cotnain nested volumes that are
compressed. Compressed entries i nthe UEFIExtract report do not have the base
address of the components, just uncompressed size. To simplify the
calculations and reliably present the data on charts, compressed UEFI Firmware
Volumes are classified as closed-source as a whole.

Whenever a new instance of :class:`uefi.UEFIVolume` is created, the utility
performs the following steps:

1. Parse the report entries and extract only those belonging to given volume.
2. Create a new instance of :class:`uefi.UEFIVolume` for each nested
   uncompressed UEFI Firmware Volume (FFSv2). This triggers the whole UEFI
   Firmware Volume calculation procedure recursively.
3. Start classifying entries:

   * Take all empty paddings and volume free space inside the current UEFI
     Firmware Volume and add them to the empty group.
   * Take all non-empty paddings inside the current UEFI Firmware Volume and
     add them to the data group.
   * As the UEFI Firmware Volume is comprised of executable code mainly or
     blobs, we do not classify anything else.

4. Sum up the size of all groups classified up to now: empty, data and
   closed-source (there is currently no closed-source classified yet, so it
   will be 0).
5. Sum up the size of all groups from all nested :class:`uefi.UEFIVolume`
   instances: empty, data and closed-source.
6. Check if given UEFI Firmware Volume is an NVAR storage using
   :meth:`uefi.UEFIVolume._is_nvar_store_volume`. The volume is considered an
   NVAR storage if at least 90% (currently defined as 90% by
   :const:`uefi.UEFIVolume.NVAR_VOLUME_THRESHOLD`) of the volume entries are
   ``NVAR entry``.
7. If the volume is an NVAR storage, the difference between the volume size
   and classified entries size (so the unclassified bytes) are added up to the
   data group. Otherwise, if the volume is not NVAR storage, it must contain
   executabel code, thus the difference is counted as closed-source.

At this point the UEFI Firmware Volume metrics are ready to be included in
total calculations in step 4 of
`Calculating Dasharo Openness Score for UEFI images`_.

Calculating Dasharo Openness Score for coreboot images
------------------------------------------------------

coreboot images are processed with cbfstool and the output of cbfstool is
parsed by the utility to make decisions about the image components. The
calculation flow looks as follows:

1. Parse the flashmap layout printed by cbfstool and extract regions'
   attributes.
2. For each flashmap region containing CBFS, create a new instance of
   :class:`coreboot.CBFSImage` and save it to an array. Creating new instance
   of :class:`coreboot.CBFSImage` triggers the CBFS image calculations
   described in section `Calculating metrics for CBFS images`_.
3. Start classifying regions:

   * Skip regions containing CBFSes, they are calcululated inside
     :class:`coreboot.CBFSImage` instances
   * Flashmap regions, which names are found in
     :const:`coreboot.DasharoCorebootImage.CODE_REGIONS`, classify as
     open-source. Currently the only region applicable is BOOTBLOCK. Some
     architectures do not store bootblock as a CBFS file but as flashmap
     region.
   * Flashmap regions, which names are found in
     :const:`coreboot.DasharoCorebootImage.BLOB_REGIONS` (where regions known
     to contain blobs are defined), classify as closed-source.
   * Flashmap regions, which names are found in
     :const:`coreboot.DasharoCorebootImage.EMPTY_REGIONS`, classify as
     empty. Currently only the ``UNUSED`` flashmap region name applies.
   * Flashmap regions, which name is found in
     :const:`coreboot.DasharoCorebootImage.DATA_REGIONS` (where regions known
     to contain data only are defined), classify as data.
   * Flashmap regions, which names are found in
     :const:`coreboot.DasharoCorebootImage.SKIP_REGIONS` are not classified
     due to being cotnainers or aliases to other regions. Counting them would
     result in duplication of the sizes when calculating metrics. These are
     standard flashmap region names aggregating smaller, nested regions.
   * If any region does not apply to above rules, save it in a separate array
     of uncategorized regions. It will be counted as closed-source in next
     step.

4. Sum up the size of all region groups: empty, data, open-source and
   closed-source. Add the sum of uncategorized regions to closed-source.
5. Sum up the size of all groups from all :class:`coreboot.CBFSImage`
   instances saved in the array previously: empty, data, open-source and
   closed-source.
6. Check if the first flashmap region offset in flash starts at 0. If yes,
   then do nothing. Otherwise count all bytes from 0 to the given offset as
   closed-source (we don't know what lies before the first flashmap region, it
   can be ME or something else).
7. Check if all classified components sizes (empty, data, open-source and
   closed-source) calculated in point 4-6 sum up to the full image size. If
   not, print a warning.
8. Export the data to markdown and pie charts using the
   :meth:`coreboot.DasharoCorebootImage.export_markdown`.

Calculating metrics for CBFS images
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Axiom: coreboot's payload is always assumed to be open-source (with a small
exception known to Dasharo images which sometimes include EFI drivers for
Ethernet NICs).


CBFS regions are processed with cbfstool and the output of cbfstool is
parsed by the utility to make decisions about the CBFS components. The
calculation flow looks as follows:

1. Parse the CBFS content printed by cbfstool and extract CBFS files'
   attributes.
2. Extract the config file from CBFS and parse the build options used to
   produce given CBFS.
3. Check if iPXE has been included:

   * Check for EDK2_ENABLE_IPXE Kconfig value. If set, save the information
     that iPXE was built for EFI and included in EUFI payload.
   * If EDK2_ENABLE_IPXE was not set, check for PXE Kconfig vlaue. If set iPXE
     was added as a legacy OptionROM.
      * Check for PXE_ROM Kconfig value. If set, it means the iPXE was
        included as an external binary. It will be later counted as
        closed-source as we don't know its origin. If PXE_ROM was not set, it
        means it was built from source.
      * If iPXE was built from source, extract the PXE_ROM_ID Kconfig value
        and save the PCI ID used for the iPXE CBFS file name. If PXE_ROM_ID
        not present, assume default ``10ec,8168``.

4. Check if external Ethernet NIC EFI driver was included:

   * Check if EDK2_LAN_ROM_DRIVER Kconfig value is set. If not, go to step 5.
   * If yes, extract the ``fallback/payload`` from the CBFS and use
     UEFIExtract on it to extract the file with
     :attr:`coreboot.CBFSImage.DASHARO_LAN_ROM_GUID`.
   * Compress the extracted EFI driver with LZMA to estimate the compressed
     size.
   * Save the size of compressed EFI driver for later calculations.

5. Start classifying CBFS files:


   * CBFS files which type is found in
     :const:`coreboot.CBFSImage.OPEN_SOURCE_FILETYPES` and names are not
     found in :const:`coreboot.CBFSImage.CLOSED_SOURCE_EXCEPTIONS` classify
     as open-source.
   * CBFS files of type ``raw``, which names are found in
     :const:`coreboot.CBFSImage.RAW_OPEN_SOURCE_FILES` classify as
     open-source.
   * If the iPXE was detected to be built from source and included as legacy
     OptionROM CBFS file, classify ``pci<PXE_ROM_ID>.rom`` as open-source.
   * CBFS files which names are found in
     :const:`coreboot.CBFSImage.CLOSED_SOURCE_FILETYPES`, classify as
     closed-source. or with CBFS file's type found in
   * CBFS files which type is found in
     :const:`coreboot.CBFSImage.OPEN_SOURCE_FILETYPES` and name is found in
     :const:`coreboot.CBFSImage.CLOSED_SOURCE_EXCEPTIONS`, classify as
     closed-source.
   * CBFS files of type ``raw`` which names are found in
     :const:`coreboot.CBFSImage.RAW_CLOSED_SOURCE_FILES`, classify as
     close-source.
   * CBFS files with type ``null`` classify as empty.
   * CBFS files which type is found in
     :const:`coreboot.CBFSImage.DATA_FILETYPES` classify as data.
   * CBFS files of type ``raw`` and names found in
     :const:`coreboot.CBFSImage.RAW_DATA_FILES` classify as data.
   * CBFS files not applying to above rules should be save to an array of
     uncategorized files. They will be counted as closed-source code in next
     steps because we were unable to identify what can be inside.

6. Sum up the size of all file groups: empty, data, open-source and
   closed-source. Add the sum of uncategorized files to closed-source.
7. If an external Ethernet NIC EFI driver was detected, subtract the
   previously saved compressed EFI driver size from open-source and add it to
   closed-source group.
8. Check for truncated CBFS:

   * vboot RW CBFSes are often truncated from empty space and the cbfstool
     does not print empty space file at the end of CBFS. Check if the
     difference between last file offset + its size and the CBFS image size is
     bigger than 64 bytes. If yes, count the difference as empty. The 64 bytes
     is the size of metadata following the end of CBFSfile.
   * cbfstool prints the size of the files in CBFS, but does not account for
     file's metadata size. Sum up the size of all file groups: empty, data,
     open-source and closed-source. Then subtract it from the CBFS region size
     to obtain metadata size. Add the metadata size to data group. It will
     also ensure that the CBFS file groups sum up to whole CBFS size.

At this point the CBFS image metrics are ready to be included in total
calculations in step 5 of
`Calculating Dasharo Openness Score for coreboot images`_.
