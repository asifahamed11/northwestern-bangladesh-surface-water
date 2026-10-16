"""Redraw two existing diagnostics at readable size, without refitting models."""
from pathlib import Path
import hashlib
import json
import numpy as np
import pandas as pd
import rasterio
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
from PIL import Image

P = Path(__file__).resolve().parent
ROOT = P.parent
manifest = json.loads((P / 'setup/inline_figure_manifest.json').read_text(encoding='utf-8'))
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'axes.titlesize': 10,
                     'axes.labelsize': 9.5, 'xtick.labelsize': 9, 'ytick.labelsize': 9,
                     'pdf.fonttype': 42, 'svg.fonttype': 'path'})


def save(fig, item, source, method):
    stem = P / 'Figures' / Path(item['png']).stem
    for extension in ['png', 'svg', 'pdf']:
        fig.savefig(stem.with_suffix('.' + extension), dpi=320, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    with Image.open(stem.with_suffix('.png')) as image:
        image.convert('RGB').save(stem.with_suffix('.tiff'), compression='tiff_lzw', dpi=(320, 320))
    item['redraw_input'] = str(source)
    item['redraw_input_sha256'] = hashlib.sha256(source.read_bytes()).hexdigest()
    item['rendering'] = method


# Categorical map uses the completed transition raster; no classification changes.
source = ROOT / 'research_outputs/analysis_20261013_completed_data/annual_transition_primary_pre2022.tif'
with rasterio.open(source) as dataset:
    values = dataset.read(1)
    groups = [[0], [11], [22], [33], [12, 13], [21, 31], [23], [32]]
    codes = np.full(values.shape, -1, dtype=np.int8)
    for n, group in enumerate(groups): codes[np.isin(values, group)] = n
    colors = ['#eee3c8', '#cccccc', '#68b5dc', '#164c8c', '#369e64', '#d44b43', '#9458bc', '#e79635']
    labels = ['No strict majority', 'Stable nonwater', 'Stable seasonal', 'Stable permanent',
              'Water gain', 'Water loss', 'Seasonal to permanent', 'Permanent to seasonal']
    fig, ax = plt.subplots(figsize=(6.7, 8.0))
    ax.imshow(np.ma.masked_less(codes, 0), cmap=ListedColormap(colors), vmin=-.5, vmax=7.5,
              extent=[dataset.bounds.left, dataset.bounds.right, dataset.bounds.bottom, dataset.bounds.top],
              interpolation='nearest', rasterized=True)
    ax.set_aspect(1 / np.cos(np.deg2rad(24.6)))
    ax.set_xlabel('Longitude (°E)'); ax.set_ylabel('Latitude (°N)')
    ax.set_title('Five-year source-class majority transitions\n2000–2004 to 2017–2021')
    ax.legend(handles=[Patch(color=c, label=l) for c, l in zip(colors, labels)], loc='upper center',
              bbox_to_anchor=(.5, -.09), ncol=2, fontsize=9, frameon=False)
    fig.subplots_adjust(left=.13, right=.99, top=.92, bottom=.17)
save(fig, manifest[2], source, 'Replotted the frozen categorical transition raster at 320 dpi using the original category groups and colors; no new classification or model fit.')

# Four district/union rows and two class columns replace the cramped 2x4 layout.
source = P / 'Supplementary_Data/Extended_Diagnostics/annual_jrc/annual_class_climate_adjusted.csv'
adjusted = pd.read_csv(source)
annual = pd.read_csv(P / 'Supplementary_Data/annual_common_support_water.csv')
regions = ['All_districts', 'Naogaon', 'Chapainawabganj', 'Rajshahi']
names = {'All_districts': 'Three-district union', 'Naogaon': 'Naogaon',
          'Chapainawabganj': 'Chapainawabganj', 'Rajshahi': 'Rajshahi'}
fig, axes = plt.subplots(4, 2, figsize=(7.2, 8.0), constrained_layout=True)
for row, region in enumerate(regions):
    for col, cls in enumerate(['seasonal', 'permanent']):
        ax = axes[row, col]
        frame = adjusted[(adjusted.region == region) & (adjusted.scope == 'primary_pre2022') &
                         (adjusted.source_class == cls)].sort_values('year')
        assert len(frame) == 22
        area = float(annual[annual.region == region].common_support_area_km2.iloc[0])
        ax.plot(frame.year, frame.observed_fraction * area, color='#777f8e', label='Observed source class', linewidth=1.15)
        ax.plot(frame.year, frame.fixed_climate_expected_fraction_model_derived * area,
                color='#b36518', label='Fixed-climate expectation', linewidth=1.25)
        ax.set_title(names[region] + ' | ' + cls.capitalize())
        ax.set_ylabel('Area (km²)'); ax.set_xticks([2000, 2010, 2021]); ax.grid(alpha=.15)
        if row == 3: ax.set_xlabel('Year')
handles, labels = axes[0, 0].get_legend_handles_labels()
fig.legend(handles, labels, loc='outside lower center', ncol=2, fontsize=9, frameon=False)
save(fig, manifest[4], source, 'Replotted the same 22-year baseline model expectation and observed series in a 4x2 layout; model values were read unchanged from the frozen CSV.')
(P / 'setup/inline_figure_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
print('Redrew Figures 3 and 5 from existing frozen outputs; no models refitted.')
