#!/bin/bash
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
D=/Users/quangdng/Documents/GitHub/OnmiDown/design-explore
for v in v1-command-bar v2-workspace v3-bold-type; do
 for s in empty analyzing result downloading done error-invalid error-unsupported error-network list; do
  for sz in "375,1500,m" "1280,1000,d"; do
   IFS=, read w h n <<< "$sz"
   "$C" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=$w,$h --virtual-time-budget=4000 --screenshot=$D/shots/$v-$s-$n.png "file://$D/$v.html?s=$s&bare&lang=en" >/dev/null 2>&1 &
  done
 done
 wait
done
