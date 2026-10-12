import pathlib
d=pathlib.Path(__file__).parent
js=(d/'shared.js').read_text()
for f in sorted(d.glob('v*.html')):
    (d.parent/f.name.replace('v1.html','v1-command-bar.html').replace('v2.html','v2-workspace.html').replace('v3.html','v3-bold-type.html')).write_text(f.read_text().replace('/*SHARED*/',js))
    print('built',f.name)
