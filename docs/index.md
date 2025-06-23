# Dasharo Openness Score

## What is Dasharo Openness Score

Have you ever wondered how open is your open-source firmware? How much
closed-source and binary blobs is still there? Dasharo Openness Score utility
answers those questions.

Dasharo Openness is a report showing the open-source code to closed-source
code ratio in the Dasharo firmware images. The results are also presented as a
pie chart for better visual representation of the firmware image components
and their share percentage.

Dasharo Openness Score utility is capable of parsing Dasharo coreboot-based
images as well as vendor UEFI images. Thanks to that one can easily compare
how many bytes of the firmware have been liberated as well as by how much the
Trusted Computing Base (TCB) has been reduced.

Dasharo Openness Score utility not only support Dasharo coreboot-based images,
but also many more coreboot distributions like heads.

## How does it work?

The utility leverages various tools like [coreboot's cbfstool][cbfstool] or
[LongSoft's UEFIExtract][uefiextract] to decompose and parse the firmware
images. The output from the utilities is used to detect the image type and then
to calculate the openness metrics.

For more details please refer to the [methodology document](./methodology.md)

[cbfstool]: https://github.com/coreboot/coreboot/tree/master/util/cbfstool
[uefiextract]: https://github.com/LongSoft/UEFITool
