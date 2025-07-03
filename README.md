# Openness-Score

Dasharo Openness Score measuring utility.

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

## Usage

```bash
usage: openness_score.py [-c proprietary_file] [-p PLATFORM] [-o OUTPUT] [-v] [-m [-V] [file]

Calculate Dasharo Openness Score for firmware images

positional arguments:
  file                  Firmware binary file to be parsed

options:
  -c proprietary_file, --compare proprietary_file
                        Compare Dasharo and proprietary firmware scores and store result in a Markdown table. file should be the Dasharo binary and proprietary_file should  be the proprietary firmware binary.
  -p PLATFORM, --platform PLATFORM
                        Platform model to provide to the table when --compare is set.
  -o OUTPUT, --output OUTPUT
                        Specifies the directory where to store the results
  -a MICROARCH, --microarch MICROARCH
                        CPU michroarchitecture supported by the firmware binary to be passed to ifdtool
  -v, --verbose         Print verbose information during the image parsing
  -m, --mkdocs          Export the report for Dasharo mkdocs
  -V, --version         show program's version number and exit
```

For example:

```bash
./openness_score.py ~/msi_ms7d25_v1.1.1_ddr4.rom --microarch adl
```

Microarchitecture for common Dasharo platforms are listed below:

- `Protectli FW6` - `sklkbl`
- `Protectli V1210/V1211/V1410/V1610` - `jsl`
- `Protectli VP2410` - `glk`
- `Protectli VP2420` - `ehl`
- `Protectli VP2430/VP2440` - `adl`
- `Protectli VP46xx` - `cnl`
- `Protectli VP32xx` - `adl`
- `Protectli VP66xx` - `adl`
- `MSI` (any) - `adl`
- `Novacustom NV4x / NS5x TGL` - `tgl`
- `Novacustom NV4x / NS5x ADL` - `adl`
- `Novacustom V54x/V56x` - `mtl`
- `ODROID` - `adl`

The utility will produce 3 files:

- `<filename>_openness_chart.png` - a pie chart image showing the share
  percentage of open-source code and closed-source code relative to total
  executable code detected in the image
- `<filename>_openness_chart_full_image.png` - a pie chart image showing the
  share percentage of open-source code, closed-source code, data and empty
  space relative to total image size
- `<filename>_openness_score.md` - a report in markdown format presenting
  precise numbers and detailed classification of firmware image components
  to closed-source, open-source, data and empty categories

Example with `--compare` flag:

```bash
./openness_score/openness_score.py msi_ms7d25_v1.1.4_ddr4.rom -c E7D25IMS.1M1 -p "MS-7D25"
```

Aside from the 3 files mentioned above, this will also produce `compare.md` - A
Markdown table containing the score comparison between the two binaries. If the
file already exists, the result will be appended as a single row.

The table contains the following metrics:

- `closed-source diff`
- `data size diff`
- `empty space diff`

Each metric is calculated using the formula:

```txt
(Dasharo <type> size - Proprietary <type> size) * 100 / Proprietary <type> size
```

`<type>` is replaced by `closed-source`, `data` or `empty space` accordingly.

You can use `scripts/compare.sh` to generate a comparison table for common
Dasharo platforms. For more information, see the script's help.

**The utility currently supports coreboot and pure UEFI images only.**

### Examples

The [examples directory](examples) contains sample Openness Score reports for:

- [Dasharo compatible with MSI PRO Z690-A DDR4 v1.1.1](examples/msi_ms7d25_v1.1.1_ddr4.rom_openness_score.md)
- [MSI PRO Z690-A DDR4 BIOS v1.20](examples/E7D25IMS.120_openness_score.md)
- [heads-x230-maximized-v0.2.0-1544-g21b87ff](examples/heads-x230-maximized-v0.2.0-1554-g21b87ff.rom_openness_score.md)
- [Dasharo compatible with ASUS KGPE-D16 v0.4.0](examples/asus_kgpe-d16_v0.4.0_16M_vboot_notpm.rom_openness_score.md)

## How does it work?

The utility leverages various tools like [coreboot's cbfstool](https://github.com/coreboot/coreboot/tree/master/util/cbfstool)
or [LongSoft's UEFIExtract](https://github.com/LongSoft/UEFITool) to decompose
and parse the firmware images. The output from the utilities is used to detect
the image type and then to calculate the openness metrics.

For more details please refer to the [methodology documentation](docs/methodology.md)

## Requirements

* Install [Nix package manager](https://nixos.org/download.html) 

> We recommend `Single-user` installation. Especially on SELinux-enabled
> systems, where `Multi-user` installation is [currently not
> supported](https://github.com/NixOS/nix/issues/2374)

* Install [devenv](https://devenv.sh/getting-started/)

> We recommend to install both `Cachix` and `devenv` using the `Newcomers`
> method.

* Enter devenv shell

```bash
devenv shell
```

* Now you have all dependencies in place, and can proceed with using the
  scripts

## Documentation

The documentation sources can be found in [docs directory](docs).

We use [Python Docstring](https://peps.python.org/pep-0257/) in
[Sphinx format](https://sphinx-rtd-tutorial.readthedocs.io/en/latest/docstrings.html)
to generate detailed code documentation automatically.

To generate the documentation run the following:

```bash
(venv) mkdocs serve
```

Open the web browser and type `localhost:8000` as address.

## Checking Python style

Test the code style with:

```bash
pycodestyle --show-source openness_score/*.py
```

We do not accept code that does not pass the style check.
