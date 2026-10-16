"""Redraw Figure 1 from immutable boundaries; no scientific analysis is rerun.

Run using the project's existing Python 3.12 scientific interpreter. Geometry is
projected without simplification to a WGS84 transverse Mercator centred on 90 E.
Scale-bar vertices and true-north arrows are calculated with WGS84 geodesics.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.path import Path as MPath
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.lines import Line2D
import numpy as np
from PIL import Image
import pyproj
from pyproj import CRS, Geod, Transformer
import shapely
from shapely.geometry import shape, box, LineString
from shapely.geometry.polygon import orient
from shapely.ops import transform, unary_union

sys.stdout.reconfigure(encoding='utf-8')
P = Path(__file__).resolve().parent
ROOT = P.parent
F = P / 'Figures'
BASE = F / 'Figure_01_study_area_and_design'
INPUTS = [ROOT / 'NW_Bangladesh_2000_2024/verified_study_area.geojson',
          ROOT / 'dataset-download/boundaries/Bangladesh_ADM2_original.geojson']
EXPECTED = ['10699eaea184d4c194da746e671feec2a2c715c477f593b0118b17332f736f18',
            '54379ccc77f6f59dab3569ecc5f9b3850dbed2d65a5f43a034bdf92179f5621b']
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
assert [sha(p) for p in INPUTS] == EXPECTED, 'Boundary source has changed.'
verified, national = [json.loads(p.read_text(encoding='utf-8')) for p in INPUTS]
assert len(verified['features']) == 3 and len(national['features']) == 64

CRS_MAP = CRS.from_proj4('+proj=tmerc +lat_0=0 +lon_0=90 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs')
forward = Transformer.from_crs(4326, CRS_MAP, always_xy=True)
inverse = Transformer.from_crs(CRS_MAP, 4326, always_xy=True)
geod = Geod(ellps='WGS84')
COLORS = {'Naogaon': '#0072B2', 'Chapainawabganj': '#D55E00', 'Rajshahi': '#009E73'}
INK, MUTED, LINE = '#182C3C', '#506272', '#D4DDE4'
districts = {}
for ft in verified['features']:
    name = ft['properties']['district'].replace('Nawabganj', 'Chapainawabganj')
    districts[name] = transform(forward.transform, shape(ft['geometry']))
assert set(districts) == set(COLORS)
context = [transform(forward.transform, shape(ft['geometry'])) for ft in national['features']]
study_union = unary_union(list(districts.values()))

# Exact original aspect ratio keeps the manuscript's image extent unchanged.
WIDTH_PX, HEIGHT_PX, DPI = 2267, 1902, 320
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 8,
                     'text.color': INK, 'axes.edgecolor': LINE,
                     'svg.fonttype': 'none', 'pdf.fonttype': 42,
                     'path.simplify': False, 'savefig.facecolor': 'white'})
fig = plt.figure(figsize=(WIDTH_PX / DPI, HEIGHT_PX / DPI), facecolor='white')
all_labels = []


def text(x, y, value, **kwargs):
    label = fig.text(x, y, value, **kwargs)
    all_labels.append(label)
    return label


def add_geometry(ax, geom, **kwargs):
    polygons = list(geom.geoms) if geom.geom_type == 'MultiPolygon' else [geom]
    for polygon in polygons:
        polygon = orient(polygon, sign=1.0)
        rings = [polygon.exterior] + list(polygon.interiors)
        paths = []
        for ring in rings:
            coords = np.asarray(ring.coords)
            codes = np.full(len(coords), MPath.LINETO, dtype=np.uint8)
            codes[0], codes[-1] = MPath.MOVETO, MPath.CLOSEPOLY
            paths.append(MPath(coords, codes))
        ax.add_patch(PathPatch(MPath.make_compound_path(*paths), **kwargs))


def map_axes(rect, bounds, padding):
    ax = fig.add_axes(rect)
    x0, y0, x1, y1 = bounds
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    dx, dy = (x1 - x0) * (1 + padding), (y1 - y0) * (1 + padding)
    target_ratio = rect[2] * WIDTH_PX / (rect[3] * HEIGHT_PX)
    dx, dy = max(dx, dy * target_ratio), max(dy, dx / target_ratio)
    ax.set(xlim=(cx - dx / 2, cx + dx / 2), ylim=(cy - dy / 2, cy + dy / 2))
    ax.set_aspect('equal', adjustable='box')
    ax.set_facecolor('#FBFCFD')
    ax.set_xticks([]); ax.set_yticks([])
    for spine in ax.spines.values(): spine.set_linewidth(.6)
    return ax


def graticules(ax, longitudes, latitudes):
    """Project geographic graticules and place labels at their frame intersections."""
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    frame = box(xmin, ymin, xmax, ymax)
    bottom = LineString([(xmin, ymin), (xmax, ymin)])
    left = LineString([(xmin, ymin), (xmin, ymax)])
    for lon in longitudes:
        lats = np.linspace(19, 29, 300)
        xx, yy = forward.transform(np.full_like(lats, lon), lats)
        segment = LineString(np.column_stack([xx, yy]))
        ax.plot(xx, yy, lw=.35, color='#D9E1E7', ls=(0, (2, 3)), zorder=0)
        hit = segment.intersection(bottom)
        if hit.geom_type == 'Point':
            label = ax.annotate(f'{lon:g}°E', (hit.x, hit.y), xytext=(0, -5),
                                textcoords='offset points', ha='center', va='top',
                                fontsize=6.6, color=MUTED, clip_on=False)
            all_labels.append(label)
    for lat in latitudes:
        lons = np.linspace(86, 95, 300)
        xx, yy = forward.transform(lons, np.full_like(lons, lat))
        segment = LineString(np.column_stack([xx, yy]))
        ax.plot(xx, yy, lw=.35, color='#D9E1E7', ls=(0, (2, 3)), zorder=0)
        hit = segment.intersection(left)
        if hit.geom_type == 'Point':
            label = ax.annotate(f'{lat:g}°N', (hit.x, hit.y), xytext=(-4, 0),
                                textcoords='offset points', ha='right', va='center',
                                fontsize=6.6, color=MUTED, clip_on=False)
            all_labels.append(label)


scale_records = []


def scale_bar(ax, start_fraction, segment_km):
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    start = (xmin + (xmax-xmin)*start_fraction[0], ymin+(ymax-ymin)*start_fraction[1])
    lon, lat = inverse.transform(*start)
    points = [start]
    for distance in [segment_km * 1000, segment_km * 2000]:
        lon1, lat1, _ = geod.fwd(lon, lat, 90, distance)
        points.append(forward.transform(lon1, lat1))
    for i in range(2):
        xs, ys = zip(*points[i:i+2])
        ax.plot(xs, ys, color=INK if i == 0 else '#8796A2', lw=3,
                solid_capstyle='butt', zorder=8)
    for i, point in enumerate(points):
        label = ax.annotate(f'{i * segment_km:g}' + (' km' if i == 2 else ''),
                            point, xytext=(0, 5), textcoords='offset points',
                            ha='center', va='bottom', fontsize=6.7, zorder=9,
                            bbox={'fc': 'white', 'ec': 'none', 'alpha': .85, 'pad': .2})
        all_labels.append(label)
    scale_records.append({'segment_km': segment_km, 'vertices_projected_m': points,
                          'start_lon_lat': [lon, lat],
                          'geodesic_lengths_m': [geod.inv(lon, lat, *inverse.transform(*pt))[2] for pt in points[1:]]})


def north_arrow(ax, anchor=(.91, .82), length_fraction=.10):
    xmin, xmax = ax.get_xlim(); ymin, ymax = ax.get_ylim()
    base = (xmin + anchor[0] * (xmax-xmin), ymin + anchor[1] * (ymax-ymin))
    lon, lat = inverse.transform(*base)
    tip = forward.transform(*geod.fwd(lon, lat, 0, (ymax-ymin)*length_fraction)[:2])
    ax.annotate('', tip, base, arrowprops={'arrowstyle': '-|>', 'color': INK,
                                         'lw': .9, 'mutation_scale': 10}, zorder=9)
    label = ax.annotate('N', tip, xytext=(0, 3), textcoords='offset points',
                        ha='center', va='bottom', fontsize=7.8, fontweight='bold', zorder=9)
    all_labels.append(label)


text(.050, .958, 'A', fontsize=10.5, fontweight='bold')
text(.079, .958, 'Bangladesh', fontsize=10)
text(.446, .958, 'B', fontsize=10.5, fontweight='bold')
text(.476, .958, 'Northwestern study districts', fontsize=10)
a = map_axes([.061, .395, .293, .532], unary_union(context).bounds, .13)
b = map_axes([.448, .395, .505, .532], study_union.bounds, .21)
graticules(a, [88, 90, 92], [22, 24, 26])
graticules(b, [88, 88.5, 89], [24.25, 24.75, 25.25])

for ax in [a, b]:
    viewport = box(*[ax.get_xlim()[0], ax.get_ylim()[0], ax.get_xlim()[1], ax.get_ylim()[1]])
    for geom in context:
        if geom.intersects(viewport):
            add_geometry(ax, geom, facecolor='#E9EEF2', edgecolor='#B6C3CD', lw=.24, zorder=1)
    for name, geom in districts.items():
        add_geometry(ax, geom, facecolor=COLORS[name], edgecolor='white', lw=.65, zorder=3)

# Country-wide outer boundary has the same source as its ADM2 context polygons.
add_geometry(a, unary_union(context), facecolor='none', edgecolor='#8E9DA8', lw=.45, zorder=2)
x0, y0, x1, y1 = study_union.bounds
locator = Rectangle((x0-8500, y0-8500), x1-x0+17000, y1-y0+17000,
                    fill=False, lw=.8, edgecolor=INK, ls=(0, (3, 2)), zorder=7)
a.add_patch(locator)
label = a.annotate('B', (x1+8500, y1+8500), xytext=(4, 2), textcoords='offset points',
                   fontsize=7.2, fontweight='bold', ha='left', va='bottom')
all_labels.append(label)

for name, at in [('Naogaon', (88.77, 24.94)), ('Rajshahi', (88.66, 24.43))]:
    xy = forward.transform(*at)
    assert districts[name].contains(shape({'type':'Point', 'coordinates':xy})), name
    label = b.text(*xy, name, ha='center', va='center', fontsize=8.8,
                   color='white', fontweight='bold', zorder=8)
    all_labels.append(label)
# A full unbroken district name is easier to read than a name split over its polygon.
target = districts['Chapainawabganj'].representative_point()
label = b.annotate('Chapainawabganj', (target.x, target.y), xytext=(.035, .20),
                   textcoords='axes fraction', ha='left', va='center',
                   fontsize=8.1, fontweight='bold', color=INK, zorder=9,
                   arrowprops={'arrowstyle':'-', 'color':INK, 'lw':.7,
                               'connectionstyle':'angle,angleA=0,angleB=-90,rad=3'})
all_labels.append(label)
north_arrow(a, (.88, .79), .085)
north_arrow(b, (.91, .80), .10)
scale_bar(a, (.18, .055), 100)
scale_bar(b, (.47, .055), 20)
text(.953, .354, 'District reporting boundaries · WGS84 / transverse Mercator (90°E)',
     ha='right', color=MUTED, fontsize=6.7)

# Parallel evidence streams: no arrows implying identical support or causal flow.
text(.050, .310, 'C', fontsize=10.5, fontweight='bold')
text(.079, .310, 'Analytical design', fontsize=10)
fig.add_artist(Line2D([.05, .953], [.292, .292], transform=fig.transFigure, lw=.65, color=LINE))
columns = [
    (.050, 'PRIMARY ANNUAL ANALYSIS', '2000–2021',
     'JRC seasonal and permanent classes\nFixed annual support: 1,276.41 km²\nClimate and observation controls'),
    (.366, 'RADAR–OPTICAL ANALYSIS', '2015–2024',
     'Sentinel-1 / Dynamic World\nSeparate retrospective cohorts\nThreshold and recovery-gap sensitivity'),
    (.682, 'DATED IMAGE COMPARISON', 'Four selected months',
     '720 stratified pixel-months\nDated Sentinel-2; assisted review\nProxy agreement; unknowns retained'),
]
for x, heading, period, description in columns:
    text(x, .257, heading, fontsize=7.0, fontweight='bold', color=MUTED)
    text(x, .212, period, fontsize=11.1, fontweight='bold')
    text(x, .174, description, fontsize=7.35, va='top', linespacing=1.65)
for x in [.345, .661]:
    fig.add_artist(Line2D([x, x], [.085, .264], transform=fig.transFigure, lw=.55, color=LINE))
text(.050, .047, 'Separate analysis domains; satellite agreement is not independent accuracy.',
     fontsize=7.1, color=MUTED)

fig.canvas.draw()
renderer = fig.canvas.get_renderer()
outside = []
for label in all_labels:
    bounds = label.get_window_extent(renderer)
    if bounds.x0 < 0 or bounds.y0 < 0 or bounds.x1 > WIDTH_PX or bounds.y1 > HEIGHT_PX:
        outside.append(label.get_text())
assert not outside, f'Labels outside canvas: {outside}'
fig.savefig(BASE.with_suffix('.png'), dpi=DPI, facecolor='white')
fig.savefig(BASE.with_suffix('.pdf'), facecolor='white', metadata={'Title': 'Study area and analytical design'})
fig.savefig(BASE.with_suffix('.svg'), facecolor='white')
with Image.open(BASE.with_suffix('.png')) as image:
    assert image.size == (WIDTH_PX, HEIGHT_PX)
    image.convert('RGB').save(BASE.with_suffix('.tiff'), dpi=(DPI, DPI), compression='tiff_lzw')
plt.close(fig)
assert [sha(p) for p in INPUTS] == EXPECTED

manifest_path = P / 'setup/inline_figure_manifest.json'
manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
item = manifest[0]
old_caption = item['caption']
item['caption'] = old_caption.replace('separate radar–optical supplement', 'separate radar–optical analysis')
if 'north arrows are geodesic' not in item['caption']:
    item['caption'] = item['caption'].replace('Boundaries: geoBoundaries',
        'Maps use a WGS84 transverse Mercator projection centered on 90°E; scale bars and north arrows are geodesic. Boundaries: geoBoundaries')
item.update({'redraw_input': str(INPUTS[0]), 'redraw_input_sha256': EXPECTED[0],
             'input_sources': [{'path': str(p), 'sha256': expected} for p, expected in zip(INPUTS, EXPECTED)],
             'rendering': 'Unsimplified verified district boundaries and ADM2 context, WGS84 transverse Mercator centered on 90 E; geodesic scale bars and true-north arrows. Frozen analysis domains; no models or estimates changed.',
             'final_png_sha256': sha(BASE.with_suffix('.png')),
             'final_tiff_sha256': sha(BASE.with_suffix('.tiff')),
             'pixels': [WIDTH_PX, HEIGHT_PX]})
manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
for source in ['manuscript.md', 'manuscript_build.md']:
    file = P / 'manuscripts' / source
    content = file.read_text(encoding='utf-8')
    if old_caption != item['caption']:
        assert content.count(old_caption) == 1
        file.write_text(content.replace(old_caption, item['caption']), encoding='utf-8')
report = {'created_utc': datetime.now(timezone.utc).isoformat(), 'figure': 1,
          'projection_WKT': CRS_MAP.to_wkt(), 'unsimplified_geometry': True,
          'input_sources': item['input_sources'], 'geodesic_scale_bars': scale_records,
          'exports': [{'file': str(BASE.with_suffix('.'+ext)), 'sha256': sha(BASE.with_suffix('.'+ext))}
                      for ext in ['png', 'tiff', 'pdf', 'svg']],
          'pixels': [WIDTH_PX, HEIGHT_PX], 'dpi': DPI,
          'font_sizes_points': {'panel_titles': 10, 'district_labels': [8.1, 8.8],
                                'design_body': 7.35, 'cartographic_annotations': 6.7},
          'packages': {'matplotlib': matplotlib.__version__, 'pyproj': pyproj.__version__,
                       'shapely': shapely.__version__}, 'python_executable': sys.executable,
          'scientific_results_changed': False, 'outside_canvas_labels': outside,
          'manual_visual_review_required': True}
(P / 'setup/figure1_redesign_provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print('Figure 1 redrawn from verified geometry:', WIDTH_PX, 'x', HEIGHT_PX, 'pixels;', DPI, 'dpi.')
