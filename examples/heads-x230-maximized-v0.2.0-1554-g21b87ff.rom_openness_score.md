# Dasharo Openness Score

Openness Score for heads-x230-maximized-v0.2.0-1554-g21b87ff.rom

Open-source code percentage: **97.9%**
Closed-source code percentage: **2.1%**

* Image size: 12582912 (0xc00000)
* Number of regions: 4
* Number of CBFSes: 1
* Total open-source code size: 7398475 (0x70e44b)
* Total closed-source code size: 157696 (0x26800)
* Total data size: 74513 (0x12311)
* Total empty size: 4952228 (0x4b90a4)

> Numbers given above already include the calculations from CBFS regions
> presented below

## FMAP regions

| FMAP region | Offset | Size | Category |
| ----------- | ------ | ---- | -------- |
| RW_MRC_CACHE | 0x20000 | 0x10000 | data |
| FMAP | 0x30000 | 0x200 | data |

## CBFS COREBOOT

* CBFS size: 12385792
* Number of files: 14
* Open-source files size: 7398475 (0x70e44b)
* Closed-source files size: 26624 (0x6800)
* Data size: 8465 (0x2111)
* Empty size: 4952228 (0x4b90a4)

> Numbers given above are already normalized (i.e. they already include size
> of metadata and possible closed-source LAN drivers included in the payload
 > which are not visible in the table below)

| CBFS filname | CBFS filetype | Size | Compression | Category |
| ------------ | ------------- | ---- | ----------- | -------- |
| fallback/romstage | stage | 84776 | none | open-source |
| fallback/ramstage | stage | 105555 | LZMA | open-source |
| fallback/dsdt.aml | raw | 14522 | none | open-source |
| fallback/postcar | stage | 29972 | none | open-source |
| fallback/payload | simple elf | 7137282 | none | open-source |
| bootblock | bootblock | 26368 | none | open-source |
| cpu_microcode_blob.bin | microcode | 26624 | none | closed-source |
| cbfs_master_header | cbfs header | 32 | none | data |
| config | raw | 2989 | LZMA | data |
| revision | raw | 724 | none | data |
| build_info | raw | 101 | none | data |
| vbt.bin | raw | 1433 | LZMA | data |
| cmos_layout.bin | cmos_layout | 2012 | none | data |
| (empty) | null | 4952228 | none | empty |
