# Figure 1 presentation refinement

Figure 1 uses muted district colors, black italic district names, serif typography and smaller north arrows. A compact analysis-domain table replaces the three cards. The same unsimplified geoBoundaries district/national geometries, WGS84 transverse Mercator projection and geodesic scale bars are retained. No scientific analysis was rerun or result changed.

The current Word manuscript was built from the author's latest local edited file. Only `word/media/image1.png` was replaced in that source package; every other DOCX part, including all text, equations, captions, fields, tables and notes, was preserved byte for byte. The preexisting local edits are retained, and that source file was left untouched. Audit records identify both the earlier repository manuscript and the user's source version.

To redraw the figure from the supplied boundaries, using the existing Python 3.12 requirements and an installed Times New Roman font:

```powershell
python code/figure_sources/refine_figure1.py --output reproduced/figure1
```

Choose a new output directory. The command checks both source geometry hashes and all geodesic scale distances, then exports PNG, RGB TIFF at 320 dpi, vector PDF and a provenance record. It does not initiate satellite acquisition or run statistical models. The national GeoJSON is supplied losslessly compressed; its decompressed SHA-256 is checked against the original geometry. Font substitution can change pixels, so rendering on a system without the recorded font is not asserted to be identical.

The compact `Revision_Supplement_20261021.zip` remains the tested annual/joint-cell/five-figure replay archive. This optional Figure 1 redraw additionally needs the boundary files from the full repository. Existing scientific limitations and author-controlled declarations are unchanged. This presentation update does not remove the manuscript's generative-AI-use statement.
