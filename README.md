# Openness-Score

Dasharo Openness Score measuring utility

## Requirements

- [cbfstool](https://github.com/coreboot/coreboot/tree/master/util/cbfstool)
  installed on host system
- [UEFIExtract NE](https://github.com/LongSoft/UEFITool) installed in host
  system
- `lzma` compression tool installed on host system
- matplotlib: `pip3 install matplotlib`

## Checking Python style

Install the `pycodestyle`:

```bash
pip3 install pycodestyle
```

Test the code style with:

```bash
pycodestyle --show-source *.py
```
