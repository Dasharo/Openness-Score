# Openness-Score

Dasharo Openness Score measuring utility

## What is Dasharo Openness Score

Have you ever wondered how open is your open-source firmware? How much
closed-source and binary blobs is still there? Dasharo Openness Score utility
answers those questions.

Dasharo Openness is a report showing the open-source code to closed-source code
ratio in the Dasharo firmware images. The results are also presented as a pie
chart for better visual representation of the firmware image components and
their share percentage.

Dasharo Openness Score utility is capable of parsing Dasharo coreboot-based
images as well as vendor UEFI images. Thanks to that one can easily compare how
many bytes of the firmware have been liberated as well as by how much the
Trusted Computing Base (TCB) has been reduced.

Dasharo Openness Score utility not only support Dasharo coreboot-based images,
but also many more coreboot distributions like heads.

### Examples

The [examples directory](examples) contains sample Openness Score reports for:

- [Dasharo compatible with MSI PRO Z690-A DDR4 v1.1.1](examples/msi_ms7d25_v1.1.1_ddr4.rom_openness_score.md)
- [MSI PRO Z690-A DDR4 BIOS v1.20](examples/E7D25IMS.120_openness_score.md)
- [heads-x230-maximized-v0.2.0-1525-g77b5933](examples/heads-x230-maximized-v0.2.0-1525-g77b5933.rom_openness_score.md)
- [Dasharo compatible with ASUS KGPE-D16 v0.4.0](examples/asus_kgpe-d16_v0.4.0_16M_vboot_notpm.rom_openness_score.md)

## How does it work?

The utility leverages various tools like [coreboot's cbfstool](https://github.com/coreboot/coreboot/tree/master/util/cbfstool)
or [LongSoft's UEFIExtract](https://github.com/LongSoft/UEFITool) to decompose
and parse the firmware images. The output from the utilities is used to detect
the image type and then to calculate the openness metrics.

For more details please refer to the [methodology documentation](docs/methodology.md)

## Requirements

- [cbfstool](https://github.com/coreboot/coreboot/tree/master/util/cbfstool)
  installed on host system
- [UEFIExtract NE](https://github.com/LongSoft/UEFITool) installed in host
  system
- `lzma` compression tool installed on host system

Python requirements:

```
pip3 install -r requirements.txt
```


## Documentation

General documentation can be found in [docs directory](docs).

For detailed code documentation we use [Python Docstring](https://peps.python.org/pep-0257/)
in [Sphinx format](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html).

To view the documentation run the following:

```
make html
python -m http.server -d build/html 8080
```

## Checking Python style

Test the code style with:

```bash
pycodestyle --show-source *.py
```

We do not accept code that does not pass the style check.
