#!/bin/bash

MINIO_CREDS="$1"
NC_CREDS="$2"
NO_DOWNLOAD="${3:-false}"

BINDIR="binaries"

usage() {
cat <<EOF
Compare Dasharo and proprietary firmware openness score

The script will download binaries to the 'binaries' directory and run openness_score.py with '--compare'.

Usage:
compare.sh MINIO_CREDS NOVACUSTOM_CREDS [no-download]

MINIO_CREDS - JSON with Dasharo MinIO credentials
NOVACUSTOM_CREDS - JSON with credentials to https://repo.palkeo.com/clevo-mirror
no-download - Do not download binaries (assume present in 'binaries' directory)

The JSONs should have the following structure:

{
  "login": "<LOGIN>",
  "password": "<PASSWORD>"
}

Replace <LOGIN> and <PASSWORD> with appropriate credentials.
EOF
}

download_protectli() {
  mkdir -p "$BINDIR/protectli" 
  repo_path="/tmp/protectli-firmware-updater"
  git clone https://github.com/protectli-root/protectli-firmware-updater.git "$repo_path"
  cp "$repo_path/images/fw6_all_YKR6LV30.bin" "$repo_path/images/protectli_all_fw6_vault_kbl_v1.0.14.rom" \
    "$repo_path/images/protectli_v1210_v0.9.3.rom"  "$repo_path/images/v1210_JPL.2LAN.S4G.PCIE.6W.013.bin" \
    "$repo_path/images/protectli_v1211_v0.9.3.rom" "$repo_path/images/v1211_JPL.2LAN.D8G.PCIE.6W.009.bin"\
    "$repo_path/images/protectli_v1410_v0.9.3.rom" "$repo_path/images/v1410_JPL.4LAN.S8GB.PCIE.6W.007B.bin"\
    "$repo_path/images/protectli_v1610_v0.9.3.rom" "$repo_path/images/v1610_JPL.6LAN.D16G.PCIE.007.bin" \
    "$repo_path/images/protectli_vp2410_v1.1.1.rom" "$repo_path/images/vp2410_GLK4L280.bin" \
    "$repo_path/images/protectli_vp2420_v1.2.1.rom" "$repo_path/images/vp2420_YELD4L13P.bin" \
    "$repo_path/images/protectli_vp2430_v0.9.0.rom" "$repo_path/images/vp2430_PRALNDZ4L10.bin" \
    "$repo_path/images/protectli_vp4600_v1.2.0.rom" "$repo_path/images/vp4630_v2_YW6L2318.bin" \
    "$repo_path/images/protectli_vp6600_v0.9.2.rom" "$repo_path/images/vp6630_ADZ6L314.bin" \
    "$BINDIR/protectli"
}

compare_protectli() {
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_all_fw6_vault_kbl_v1.0.14.rom" \
    -c "$BINDIR/protectli/fw6_all_YKR6LV30.bin" -p "Protectli FW6"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_v1210_v0.9.3.rom" \
    -c "$BINDIR/protectli/v1210_JPL.2LAN.S4G.PCIE.6W.013.bin" -p "Protectli V1210"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_v1211_v0.9.3.rom" \
    -c "$BINDIR/protectli/v1211_JPL.2LAN.D8G.PCIE.6W.009.bin" -p "Protectli V1211"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_v1410_v0.9.3.rom" \
    -c "$BINDIR/protectli/v1410_JPL.4LAN.S8GB.PCIE.6W.007B.bin" -p "Protectli V1410"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_v1610_v0.9.3.rom" \
    -c "$BINDIR/protectli/v1610_JPL.6LAN.D16G.PCIE.007.bin" -p "Protectli V1610"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_vp2410_v1.1.1.rom" \
    -c "$BINDIR/protectli/vp2410_GLK4L280.bin" -p "Protectli VP2410"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_vp2420_v1.2.1.rom" \
    -c "$BINDIR/protectli/vp2420_YELD4L13P.bin" -p "Protectli VP2420"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_vp2430_v0.9.0.rom" \
    -c "$BINDIR/protectli/vp2430_PRALNDZ4L10.bin" -p "Protectli VP2430"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_vp4600_v1.2.0.rom" \
    -c "$BINDIR/protectli/vp4630_v2_YW6L2318.bin" -p "Protectli VP4600"
  ./openness_score/openness_score.py "$BINDIR/protectli/protectli_vp6600_v0.9.2.rom" \
    -c "$BINDIR/protectli/vp6630_ADZ6L314.bin" -p "Protectli VP6600"
}

download_msi() {
  mkdir -p "$BINDIR/msi"

  bios_url="https://download.msi.com/bos_exe/mb"
  minio_bucket="dasharo-msi-uefi"

  # Z690-A DDR4
  wget -O "/tmp/7D25v1L.zip" "$bios_url/7D25v1L.zip"
  unzip "/tmp/7D25v1L.zip" -d "/tmp"
  cp "/tmp/7D25v1L/E7D25IMS.1L0" "$BINDIR/msi"

  # Z690-A-WIFI
  wget -O "/tmp/7D25vAL.zip" "$bios_url/7D25vAL.zip"
  unzip "/tmp/7D25vAL.zip" -d "/tmp"
  cp "/tmp/7D25vAL/E7D25IMS.AL0" "$BINDIR/msi"

  # Z790-P DDR4
  wget -O "/tmp/7E06v1F.zip" "$bios_url/7E06v1F.zip"
  unzip "/tmp/7E06v1F.zip" -d "/tmp"
  cp "/tmp/7E06v1F/E7E06IMS.1F0" "$BINDIR/msi"

  # Z790-P WIFI
  wget -O "/tmp/7E06vAH.zip" "$bios_url/7E06vAH.zip"
  unzip "/tmp/7E06vAH.zip" -d "/tmp"
  cp "/tmp/7E06vAH/E7E06IMS.AH0" "$BINDIR/msi"

  mc get "openness-score/$minio_bucket/MS-7D25/v1.1.4/msi_ms7d25_v1.1.4_ddr4.rom" "$BINDIR/msi"
  mc get "openness-score/$minio_bucket/MS-7D25/v1.1.4/msi_ms7d25_v1.1.4_ddr5.rom" "$BINDIR/msi"
  mc get "openness-score/$minio_bucket/MS-7E06/v0.9.2/msi_ms7e06_v0.9.2_ddr4.rom" "$BINDIR/msi"
  mc get "openness-score/$minio_bucket/MS-7E06/v0.9.2/msi_ms7e06_v0.9.2_ddr5.rom" "$BINDIR/msi"
}

compare_msi() {
  ./openness_score/openness_score.py "$BINDIR/msi/msi_ms7d25_v1.1.4_ddr4.rom" -c "$BINDIR/msi/E7D25IMS.1L0" -p "MS-7D25 DDR4"
  ./openness_score/openness_score.py "$BINDIR/msi/msi_ms7d25_v1.1.4_ddr5.rom" -c "$BINDIR/msi/E7D25IMS.AL0" -p "MS-7D25 DDR5"
  ./openness_score/openness_score.py "$BINDIR/msi/msi_ms7e06_v0.9.2_ddr4.rom" -c "$BINDIR/msi/E7E06IMS.1F0" -p "MS-7E06 DDR4"
  ./openness_score/openness_score.py "$BINDIR/msi/msi_ms7e06_v0.9.2_ddr4.rom" -c "$BINDIR/msi/E7E06IMS.AH0" -p "MS-7E06 DDR5"
}

download_novacustom() {
  mkdir -p "$BINDIR/novacustom"
  bios_url="https://repo.palkeo.com/clevo-mirror"
  dasharo_url="https://dl.3mdeb.com/open-source-firmware/Dasharo"

  wget_cmd="wget --user $NC_LOGIN --password $NC_PASSWORD"

  # V54/56 MTL
  $wget_cmd -O "/tmp/B10709.zip" "$bios_url/Vxx0TU/B10709.zip"
  unzip "/tmp/B10709.zip" -d "/tmp"
  cp "/tmp/B10709/V5xxTU(32M).09" "$BINDIR/novacustom"

  # NV4x ADL
  $wget_cmd -O "/tmp/B10703.zip" "$bios_url/NV4xPZ/B10703.zip"
  unzip "/tmp/B10703.zip" -d "/tmp"
  cp "/tmp/B10703/ALL/NV4xPZ(32M).03" "$BINDIR/novacustom"

  # NV4x TGL
  $wget_cmd -O "/tmp/B10705.zip" "$bios_url/NV4xMB_ME/B10705.zip"
  unzip "/tmp/B10705.zip" -d "/tmp"
  cp "/tmp/B10705/ALL/NV4XBX.05" "$BINDIR/novacustom"

  # NS5x ADL
  $wget_cmd -O "/tmp/B10709.zip" "$bios_url/NSxxPU/B10709.zip"
  unzip "/tmp/B10709.zip" -d "/tmp"
  cp "/tmp/B10709/ALL/NSx0PU(32M).09" "$BINDIR/novacustom"

  # NS5x TGL
  $wget_cmd -O "/tmp/B10716N.zip" "$bios_url/NS5xMU/B10716N.zip"
  unzip "/tmp/B10716N.zip" -d "/tmp"
  cp "/tmp/NS50_70MU.16N/ALL/68C1/NS50_70MU.16N" "$BINDIR/novacustom"

  wget -O "$BINDIR/novacustom/novacustom_v54x_mtl_v0.9.0.rom" "$dasharo_url/novacustom_v54x_mtl/v0.9.0/novacustom_v54x_mtl_v0.9.0.rom"
  wget -O "$BINDIR/novacustom/novacustom_v56x_mtl_v0.9.0.rom" "$dasharo_url/novacustom_v56x_mtl/v0.9.0/novacustom_v56x_mtl_v0.9.0.rom"
  wget -O "$BINDIR/novacustom/novacustom_nv4x_adl_v1.7.2_full.rom" "$dasharo_url/novacustom_nv4x_adl/v1.7.2/novacustom_nv4x_adl_v1.7.2_full.rom"
  wget -O "$BINDIR/novacustom/novacustom_nv4x_tgl_v1.5.2.rom" "$dasharo_url/novacustom_nv4x_tgl/v1.5.2/novacustom_nv4x_tgl_v1.5.2.rom"
  wget -O "$BINDIR/novacustom/novacustom_ns5x_adl_v1.7.2.rom" "$dasharo_url/novacustom_ns5x_adl/v1.7.2/novacustom_ns5x_adl_v1.7.2.rom"
  wget -O "$BINDIR/novacustom/novacustom_ns5x_tgl_v1.5.2.rom" "$dasharo_url/novacustom_ns5x_tgl/v1.5.2/novacustom_ns5x_tgl_v1.5.2.rom"
}

compare_novacustom() {
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_v54x_mtl_v0.9.0.rom" -c "$BINDIR/novacustom/V5xxTU(32M).09" -p "NC V540TU"
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_v56x_mtl_v0.9.0.rom" -c "$BINDIR/novacustom/V5xxTU(32M).09" -p "NC V560TU"
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_nv4x_adl_v1.7.2_full.rom" -c "$BINDIR/novacustom/NV4xPZ(32M).03" -p "NC NV4xPZ"
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_nv4x_tgl_v1.5.2.rom" -c "$BINDIR/novacustom/NV4XBX.05" -p "NC NV4xME_MB"
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_ns5x_adl_v1.7.2.rom" -c "$BINDIR/novacustom/NSx0PU(32M).09" -p "NC NSxxPU"
  ./openness_score/openness_score.py "$BINDIR/novacustom/novacustom_ns5x_tgl_v1.5.2.rom" -c "$BINDIR/novacustom/NS50_70MU.16N" -p "NC NS5xMU"
}

download_odroid() {
  mkdir -p "$BINDIR/odroid"
  bios_url="https://dn.odroid.com/ODROID-H4/bios"
  minio_bucket="dasharo-odroid-h4-plus-uefi"
  echo "Please download stock binaries from $bios_url to $BINDIR/odroid"
  read -p "Press any key after downloading binaries"
  
  mc get "openness-score/$minio_bucket/hardkernel_odroid_h4/v0.9.0/hardkernel_odroid_h4_v0.9.0.rom" "$BINDIR/odroid"
}

compare_odroid() {
  ./openness_score/openness_score.py "$BINDIR/odroid/hardkernel_odroid_h4_v0.9.0.rom" -c "$BINDIR/odroid/ADLN-H4_B1.07.bin" -p "Odroid H4"
}

if [ $# -lt 2 ]; then
  usage
  exit 1
fi

mkdir -p "$BINDIR"
MINIO_LOGIN=$(jq -r '.login' "$MINIO_CREDS")
MINIO_PASSWORD=$(jq -r '.password' "$MINIO_CREDS")
mc alias set openness-score "https://dl.dasharo.com" "$MINIO_LOGIN" "$MINIO_PASSWORD"

NC_LOGIN=$(jq -r '.login' "$NC_CREDS")
NC_PASSWORD=$(jq -r '.password' "$NC_CREDS")

if [ $NO_DOWNLOAD != "no-download" ]; then
  download_msi
  download_protectli
  download_odroid
  download_novacustom
fi
compare_msi
compare_protectli
compare_odroid
compare_novacustom
