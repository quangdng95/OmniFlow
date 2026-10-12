#!/bin/bash
C="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
D=/Users/quangdng/Documents/GitHub/OnmiDown/design-explore
W=/private/tmp/claude-502/-Users-quangdng-Documents-GitHub-OnmiDown/3ea6c4f3-920c-4cea-a4a3-3a9f9bed23cc/scratchpad
for v in v1-command-bar v2-workspace v3-bold-type; do
 for s in empty analyzing result downloading done error-invalid error-unsupported error-network list; do
  for lg in en; do
  echo "<body style='margin:0'><iframe src='file://$D/$v.html?s=$s&bare&lang=$lg' width=375 height=1500 style='border:0'></iframe>" > $W/w-$v-$s.html
  "$C" --headless=new --disable-gpu --hide-scrollbars --force-device-scale-factor=1 --window-size=520,1520 --virtual-time-budget=4000 --screenshot=$D/shots/$v-$s-m.png "file://$W/w-$v-$s.html" >/dev/null 2>&1 &
  done
 done; wait
done
python3 - <<PY
from PIL import Image
S="$W"
states="empty analyzing result downloading done error-invalid error-unsupported error-network list".split()
for v in ["v1-command-bar","v2-workspace","v3-bold-type"]:
    ims=[Image.open(f"$D/shots/{v}-{s}-m.png").convert("RGB").crop((0,0,375,1000)) for s in states]
    sheet=Image.new("RGB",(375*5+40,1000*2+10),"#888")
    for k,i in enumerate(ims): sheet.paste(i,((k%5)*385,(k//5)*1010))
    sheet.save(f"{S}/{v}-m.png")
PY
