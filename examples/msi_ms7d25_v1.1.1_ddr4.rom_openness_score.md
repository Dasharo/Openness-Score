# Dasharo Openness Score

Openness Score for msi_ms7d25_v1.1.1_ddr4.rom

Open-source code percentage: **42.8%**
Closed-source code percentage: **57.2%**

* Image size: 33554432 (0x2000000)
* Number of regions: 33
* Number of CBFSes: 3
* Total open-source code size: 6632421 (0x6533e5)
* Total closed-source code size: 8846847 (0x86fdff)
* Total data size: 939652 (0xe5684)
* Total empty size: 17135512 (0x1057798)

> Numbers given above already include the calculations from CBFS regions
> presented below

## FMAP regions

| FMAP region | Offset | Size | Category |
| ----------- | ------ | ---- | -------- |
| SI_ME | 0x1000 | 0x3ff000 | closed-source |
| SI_DESC | 0x0 | 0x1000 | data |
| RECOVERY_MRC_CACHE | 0x1000000 | 0x20000 | data |
| RW_MRC_CACHE | 0x1020000 | 0x20000 | data |
| RW_ELOG | 0x1040000 | 0x4000 | data |
| SHARED_DATA | 0x1044000 | 0x2000 | data |
| VBLOCK_DEV | 0x1046000 | 0x2000 | data |
| RW_VPD | 0x1048000 | 0x2000 | data |
| RW_NVRAM | 0x104a000 | 0x6000 | data |
| CONSOLE | 0x1050000 | 0x20000 | data |
| SMMSTORE | 0x1070000 | 0x40000 | data |
| HSPHY_FW | 0x10b0000 | 0x8000 | data |
| VBLOCK_A | 0x10b8000 | 0x10000 | data |
| RW_FWID_A | 0x15dbf00 | 0x100 | data |
| VBLOCK_B | 0x15dc000 | 0x10000 | data |
| RW_FWID_B | 0x1afff00 | 0x100 | data |
| RO_VPD | 0x1b00000 | 0x4000 | data |
| FMAP | 0x1b04000 | 0x800 | data |
| RO_FRID | 0x1b04800 | 0x100 | data |
| RO_FRID_PAD | 0x1b04900 | 0x700 | data |
| GBB | 0x1b05000 | 0x3000 | data |
| UNUSED | 0x400000 | 0xc00000 | empty |

## CBFS FW_MAIN_A

* CBFS size: 5324544
* Number of files: 13
* Open-source files size: 2183415 (0x2150f7)
* Closed-source files size: 1552213 (0x17af55)
* Data size: 5708 (0x164c)
* Empty size: 1583208 (0x182868)

> Numbers given above are already normalized (i.e. they already include size
> of metadata and possible closed-source LAN drivers included in the payload
 > which are not visible in the table below)

| CBFS filname | CBFS filetype | Size | Compression | Category |
| ------------ | ------------- | ---- | ----------- | -------- |
| fallback/romstage | stage | 101360 | none | open-source |
| fallback/ramstage | stage | 138510 | LZMA | open-source |
| fallback/dsdt.aml | raw | 10517 | none | open-source |
| fallback/postcar | stage | 33804 | none | open-source |
| fallback/payload | simple elf | 2029308 | none | open-source |
| cpu_microcode_blob.bin | microcode | 425984 | none | closed-source |
| fspm.bin | fsp | 720896 | none | closed-source |
| fsps.bin | fsp | 275249 | LZ4 | closed-source |
| config | raw | 2480 | none | data |
| revision | raw | 850 | none | data |
| build_info | raw | 142 | none | data |
| vbt.bin | raw | 1254 | LZMA | data |
| (empty) | null | 2148 | none | empty |

## CBFS FW_MAIN_B

* CBFS size: 5324544
* Number of files: 13
* Open-source files size: 2183415 (0x2150f7)
* Closed-source files size: 1552213 (0x17af55)
* Data size: 5708 (0x164c)
* Empty size: 1583208 (0x182868)

> Numbers given above are already normalized (i.e. they already include size
> of metadata and possible closed-source LAN drivers included in the payload
 > which are not visible in the table below)

| CBFS filname | CBFS filetype | Size | Compression | Category |
| ------------ | ------------- | ---- | ----------- | -------- |
| fallback/romstage | stage | 101360 | none | open-source |
| fallback/ramstage | stage | 138510 | LZMA | open-source |
| fallback/dsdt.aml | raw | 10517 | none | open-source |
| fallback/postcar | stage | 33804 | none | open-source |
| fallback/payload | simple elf | 2029308 | none | open-source |
| cpu_microcode_blob.bin | microcode | 425984 | none | closed-source |
| fspm.bin | fsp | 720896 | none | closed-source |
| fsps.bin | fsp | 275249 | LZ4 | closed-source |
| config | raw | 2480 | none | data |
| revision | raw | 850 | none | data |
| build_info | raw | 142 | none | data |
| vbt.bin | raw | 1254 | LZMA | data |
| (empty) | null | 2148 | none | empty |

## CBFS COREBOOT

* CBFS size: 5210112
* Number of files: 17
* Open-source files size: 2265591 (0x2291f7)
* Closed-source files size: 1552213 (0x17af55)
* Data size: 6124 (0x17ec)
* Empty size: 1386184 (0x1526c8)

> Numbers given above are already normalized (i.e. they already include size
> of metadata and possible closed-source LAN drivers included in the payload
 > which are not visible in the table below)

| CBFS filname | CBFS filetype | Size | Compression | Category |
| ------------ | ------------- | ---- | ----------- | -------- |
| fallback/romstage | stage | 101360 | none | open-source |
| fallback/ramstage | stage | 138510 | LZMA | open-source |
| fallback/dsdt.aml | raw | 10517 | none | open-source |
| fallback/postcar | stage | 33804 | none | open-source |
| fallback/payload | simple elf | 2029308 | none | open-source |
| bootblock | bootblock | 82176 | none | open-source |
| cpu_microcode_blob.bin | microcode | 425984 | none | closed-source |
| fspm.bin | fsp | 720896 | none | closed-source |
| fsps.bin | fsp | 275249 | LZ4 | closed-source |
| cbfs_master_header | cbfs header | 32 | none | data |
| intel_fit | intel_fit | 80 | none | data |
| config | raw | 2480 | none | data |
| revision | raw | 850 | none | data |
| build_info | raw | 142 | none | data |
| vbt.bin | raw | 1254 | LZMA | data |
| (empty) | null | 1892 | none | empty |
| (empty) | null | 1384292 | none | empty |
