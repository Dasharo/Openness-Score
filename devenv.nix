{ pkgs, ... }:

with pkgs;
{
  packages = [
    coreboot-utils
    uefitool
    xz
    stdenv.cc.cc.lib
    glib
  ];

  languages.python.enable = true;
  languages.python.venv.enable = true;

 env.LD_LIBRARY_PATH = "${stdenv.cc.cc.lib}/lib";

 enterShell = ''
    echo "Welcome!"
    pip install -r ./requirements.txt
 '';

  # pre-commit.hooks = {
  #   # lint shell scripts
  #   shellcheck.enable = true;
  # };
}
