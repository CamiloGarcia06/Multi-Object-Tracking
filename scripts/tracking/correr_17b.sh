#!/usr/bin/env bash
# Tesis 17b: los 5 trackers de la 17 sobre los videos de prueba de DDR y SDR (video entero,
# mismas dets del campeón, ROI del montaje). Salida runs_17b/<tracker>/<video>.txt.
set -euo pipefail
R=/home/camilo-cachy/Multi-Object-Tracking
PY=/home/camilo-cachy/Projects/track-studio/.venv/bin/python
TR=/home/camilo-cachy/Projects/track-studio/trackers
OUT=$R/data/flow_eval/runs_17b
declare -A ROI=([bus_ddr_s6_v18]=roi_bus_ddr_s6.json [bus_sdr_s1_v08]=roi_bus_sdr_s1.json)
declare -A CAM=([bus_ddr_s6_v18]=ddr [bus_sdr_s1_v08]=sdr)
for v in bus_ddr_s6_v18 bus_sdr_s1_v08; do
  dets=$R/data/flow_eval/dets/$v.npy roi=$R/configs/cameras/${ROI[$v]} video=/home/camilo-cachy/videos/bus/${CAM[$v]}/$v.mkv
  mkdir -p $OUT/bytetrack_27
  echo "== $v bytetrack_27"
  $PY $R/scripts/flow/diag_bytetrack.py run --dets $dets --roi $roi \
      --tracker $TR/bytetrack_buffer90_match09.yaml --out $OUT/bytetrack_27/$v.txt
  for t in ocsort deepocsort_osnet deepocsort_osnet_iou020 botsort_osnet; do
    echo "== $v $t"
    $PY $R/scripts/tracking/run_boxmot.py run --dets $dets --video $video --roi $roi \
        --tracker $TR/$t.yaml --out $OUT/$t/$v.txt
  done
done
echo FIN
