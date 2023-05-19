# Dasharo Openness Score

Openness Score for heads-x230-maximized-v0.2.0-1525-g77b5933.rom

* Image size: 12582912 (0xc00000)
* Number of regions: 4
* Number of CBFSes: 1
* Total open-source code size: 7214814 (0x6e16de)
* Total closed-source code size: 157696 (0x26800)
* Total data size: 280714 (0x4488a)
* Total empty size: 4929688 (0x4b3898)

Open-source code percentage: **97.9%**
Closed-source code percentage: **2.1%**

> Numbers given above already include the calculations from CBFS regions
> presented below

## FMAP regions

| FMAP region | Offset | Size | Category |
| ----------- | ------ | ---- | -------- |
| RW_MRC_CACHE | 0x20000 | 0x10000 | data |
| FMAP | 0x30000 | 0x200 | data |

## CBFS COREBOOT

* CBFS size: 12385792
* Number of files: 10
* Open-source files size: 7214814 (0x6e16de)
* Closed-source files size: 26624 (0x6800)
* Data size: 214666 (0x3468a)
* Empty size: 4929688 (0x4b3898)

> Numbers given above are already normalized (i.e. they already include size
> of metadata and possible closed-source LAN drivers included in the payload
 > which are not visible in the table below)

| CBFS filname | CBFS filetype | Size | Compression | Category |
| ------------ | ------------- | ---- | ----------- | -------- |
| fallback/dsdt.aml | raw | 14615 | none | open-source |
| fallback/payload | simple elf | 7134663 | none | open-source |
| bootblock | bootblock | 65536 | none | open-source |
| cpu_microcode_blob.bin | microcode | 26624 | none | closed-source |
| header | cbfs header | 32 | none | data |
| config | raw | 824 | none | data |
| revision | raw | 691 | none | data |
| vbt.bin | raw | 1433 | LZMA | data |
| cmos_layout.bin | cmos_layout | 1884 | none | data |
| (empty) | null | 4929688 | none | empty |
