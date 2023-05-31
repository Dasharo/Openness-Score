{ pkgs, ... }:

with pkgs;
{
  packages = [
    coreboot-utils
    uefitool
    lzma
    stdenv.cc.cc.lib
    glib
  ];

  languages.python.enable = true;
  languages.python.venv.enable = true;

 enterShell = ''
    echo "Welcome!"
    pip install -r ./requirements.txt
 '';

  # pre-commit.hooks = {
  #   # lint shell scripts
  #   shellcheck.enable = true;
  # };
}
