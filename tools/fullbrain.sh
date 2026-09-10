#!/bin/sh
# FR-PRP-04 full-brain protocol (D-63): 7 rates, 1 seed, 1000 ms.
# Rates are the union of TBD-07's proposed calibration and validation sets.
NET=data/networks/onfnet-malecns-v1.0-full.bin
OUT=data/fullbrain
for r in 10 20 40 80 120 160 200; do
  ./build/runnet.exe "$NET" "$r" 1000 1 --all > "$OUT/rate-$r-seed1.txt" 2>&1
  echo "rate $r done: $(grep '^RUN' "$OUT/rate-$r-seed1.txt")"
done
echo "ALL RATES COMPLETE"
