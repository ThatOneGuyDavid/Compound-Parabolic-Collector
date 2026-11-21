# Reproducing the draft

Use Python with a compatible OpenCascade wheel and Chromium for the browser
test. From the repository root:

```sh
python -m venv .venv
.venv/bin/pip install -r src/requirements-model.txt
.venv/bin/python src/build_model.py --variant printed
.venv/bin/python src/build_model.py --variant aluminum
.venv/bin/python src/export_rib_dxf.py
.venv/bin/python src/build_viewer.py
.venv/bin/python src/check_viewer.py
```

`check_viewer.py` currently expects Chromium at `/usr/bin/chromium`. The
drawings additionally need `rsvg-convert`:

```sh
.venv/bin/python src/draw_rib.py
.venv/bin/python sketches/draw_slats_04.py
```

The generators overwrite files under `models/v16/` and the root viewer/drawing.
Save any changes before regenerating. All CAD units are millimeters; GLB uses
meters. STL has no intrinsic unit metadata and should be imported as mm.

The packaged reports include the development project's independent slat and
export checks, including comparisons with historical versions. Historical
models and the comparison scripts are omitted from this current-version
publication draft. Current CAD generation checks delivered STEP and STL,
nominal rib/receiver clearances and assembly grouping; the DXF script reimports
its own output and checks closure, holes and sampled boundary deviation.

The HTML preview is self-contained for viewing. Keep the rest of the repository
alongside it to use its relative model-download links. The online viewer uses
GitHub Pages, serving `main` from the repository
root. `.nojekyll` serves the static files directly; `index.html` opens the
viewer. The README links to its GitHub Pages URL.
