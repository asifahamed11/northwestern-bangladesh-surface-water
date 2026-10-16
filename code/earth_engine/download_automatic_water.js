/* NW Bangladesh automated open-water evidence, v2.0 timeout fix, 2026-10-13.
 * Paste into a NEW Earth Engine script and press Run, then the blue button.
 * Creates 14 CSV tasks. No imports, manual labels, or raster downloads needed.
 * All classifications are automated estimates, NOT human-verified accuracy.
 * Missing observations stay missing; exported zero supported area is NOT dry land.
 * Sources/methods: see automatic_water/METHOD.md in the supplied code kit.
 */
var FOLDER = 'NW_Bangladesh_automatic_water_2015_2024';
var BOUNDARY = 'projects/gen-lang-client-0603076418/assets/NW_Bangladesh_3districts';
var METHOD = 'automatic_open_water_v2';
var ORBIT_RULE = 'first_6_footprints_then_months_then_scenes_lexical_v2';
var FIRST = 2015, LAST = 2024, MIN_DAYS = 2, DW_CONFIDENCE = 0.8;
var TEN = ee.Projection('EPSG:32645').atScale(10);
var IDS = {
  annualOld: 'JRC/GSW1_4/YearlyHistory',
  annualCorrected: 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2016_2021',
  annualNew: 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2022_2024',
  monthlyOld: 'JRC/GSW1_4/MonthlyHistory',
  monthlyNew: 'projects/JRC/GSW1_5/MonthlyHistory_2022_2024',
  sar: 'COPERNICUS/S1_GRD', dw: 'GOOGLE/DYNAMICWORLD/V1'
};
function annualAsset(y) { return y < 2016 ? IDS.annualOld : (y < 2022 ? IDS.annualCorrected : IDS.annualNew); }
function annualCollection(y) {
  return ee.ImageCollection(annualAsset(y)).filter(ee.Filter.inList('year', [y, String(y)])).select('waterClass');
}
function pad(m) { return m < 10 ? '0' + m : String(m); }
function jrcCollection(y, m) {
  if (y >= 2022) return ee.ImageCollection(IDS.monthlyNew)
    .filter(ee.Filter.eq('system:index', y + '_' + pad(m)))
    .filter(ee.Filter.inList('year', [y, String(y)]))
    .filter(ee.Filter.inList('month', [m, String(m), pad(m)])).select('water');
  var d = ee.Date.fromYMD(y, m, 1);
  return ee.ImageCollection(IDS.monthlyOld).filterDate(d, d.advance(1, 'month')).select('water');
}
function dayProperties(image) {
  return image.set('_day', ee.Date(image.get('system:time_start')).format('YYYY-MM-dd'));
}
var boundary = ee.FeatureCollection(BOUNDARY);
var region = boundary.geometry();
var districts = boundary.map(function(f) {
  var name = ee.String(f.get('district'));
  return f.set('region', ee.Algorithms.If(name.compareTo('Nawabganj').eq(0), 'Chapainawabganj', name));
});
var SOURCE_PROJECTION = ee.Image(annualCollection(2000).first()).projection();
// Freeze the existing local export's ~30-m angular grid. Source categorical
// JRC images use default nearest-neighbor resampling if their native origin differs.
var PROJECTION = ee.Projection('EPSG:4326', [0.00026949458523585647, 0, 0, 0, -0.00026949458523585647, 0]);
var empty30 = ee.Image(0).updateMask(ee.Image(0)).setDefaultProjection(PROJECTION);
var annualImages = [], annualAudit = [];
for (var y = 2000; y <= 2024; y++) {
  var a = annualCollection(y);
  annualAudit.push(ee.Feature(null, {dataset: 'JRC_ANNUAL', year: y, month: 0, asset: annualAsset(y), actual_images: a.size(), unique_days: -1}));
  annualImages.push(ee.Image(ee.Algorithms.If(a.size().eq(1), a.first(), empty30)).rename('waterClass').unmask(0).toUint8().reproject(PROJECTION));
}
var annualAll = ee.ImageCollection.fromImages(annualImages);
var everWater = annualAll.map(function(i) { return i.gte(2).and(i.lte(3)); }).max().gt(0).setDefaultProjection(PROJECTION);
var firstFive = ee.ImageCollection.fromImages(annualImages.slice(0, 5));
var completeFive = firstFive.map(function(i) { return i.gte(1).and(i.lte(3)); }).sum().eq(5);
var seasonalInitial = firstFive.map(function(i) { return i.eq(2); }).sum().gte(3).and(completeFive);
var permanentInitial = firstFive.map(function(i) { return i.eq(3); }).sum().gte(3).and(completeFive);
var COHORTS = [
  {name: 'all_water', mask: everWater},
  {name: 'baseline_seasonal', mask: everWater.and(seasonalInitial)},
  {name: 'baseline_permanent', mask: everWater.and(permanentInitial)}
];
var sarAll = ee.ImageCollection(IDS.sar).filterBounds(region).filterDate(FIRST + '-01-01', (LAST + 1) + '-01-01')
  .filter(ee.Filter.eq('instrumentMode', 'IW')).filter(ee.Filter.eq('resolution_meters', 10))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
  .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
  .map(function(i) { return dayProperties(i).set('_track', ee.String(i.get('orbitProperties_pass')).cat('_').cat(ee.Number(i.get('relativeOrbitNumber_start')).format('%d'))); });
var dwAll = ee.ImageCollection(IDS.dw).filterBounds(region).filterDate(FIRST + '-01-01', (LAST + 1) + '-01-01').map(dayProperties);
function cleanRadar(i) {
  var angle = i.select('angle');
  return i.select('VV').updateMask(angle.gte(30).and(angle.lte(45))).reproject(TEN).copyProperties(i, ['_day', 'system:index']);
}
// Metadata-only orbit proxy: NEVER read ten years of radar pixels to select a track.
// The proxy uses at most six earliest scene footprints and a simplified boundary;
// it does not establish valid pixel coverage. Actual support is audited after export.
var tracks = ee.List(sarAll.aggregate_array('_track')).distinct().sort();
var rankingRegion = region.simplify(1000);
var rankingArea = rankingRegion.area(1000);
var orbitAudit = ee.FeatureCollection(tracks.map(function(key) {
  var c = sarAll.filter(ee.Filter.eq('_track', key));
  var months = ee.List(c.aggregate_array('_day')).map(function(d) { return ee.String(d).slice(0, 7); }).distinct().size();
  var representatives = c.sort('system:time_start').limit(6);
  var fraction = representatives.geometry(1000).intersection(rankingRegion, 1000).area(1000).divide(rankingArea).min(1);
  var quantized = fraction.multiply(1000).floor();
  var score = quantized.multiply(1e9).add(months.multiply(1e6)).add(c.size());
  return ee.Feature(null, {track: key, footprint_proxy_fraction: fraction, months_with_any_scene: months, scene_count: c.size(), rank_score: score,
    representative_scenes: representatives.size(), quantized_footprint_proxy: quantized, ranking_rule: ORBIT_RULE,
    sort_key: score.format('%016.0f').cat('_').cat(ee.String(key))});
}));
var selectedTrack = ee.String(ee.Algorithms.If(tracks.size().gt(0), orbitAudit.sort('sort_key', false).first().get('track'), 'NO_AVAILABLE_TRACK'));
var selectedSar = sarAll.filter(ee.Filter.eq('_track', selectedTrack));
function dailyMosaics(collection, bands) {
  var days = ee.List(collection.aggregate_array('_day')).distinct().sort();
  return ee.ImageCollection.fromImages(days.map(function(day) {
    return collection.filter(ee.Filter.eq('_day', day)).sort('system:index').select(bands).mosaic()
      .setDefaultProjection(TEN).set('_day', day);
  }));
}
function medianOrMissing(collection, bands) {
  var missing = ee.Image.constant(bands.map(function() { return 0; })).rename(bands).updateMask(ee.Image(0)).setDefaultProjection(TEN);
  return ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.median(), missing)).setDefaultProjection(TEN);
}
function countOrZero(collection, band) {
  return ee.Image(ee.Algorithms.If(collection.size().gt(0), collection.select(band).count(), ee.Image(0).rename(band))).unmask(0).setDefaultProjection(TEN);
}
function fraction30(image) {
  // Overlap-weighted fractions, not nearest-neighbor class resampling.
  return image.unmask(0, false).setDefaultProjection(TEN)
    .reduceResolution({reducer: ee.Reducer.mean(), maxPixels: 256}).reproject(PROJECTION);
}
function cellState(waterFraction, validFraction) {
  var ratio = waterFraction.divide(validFraction.max(1e-12));
  return {known: validFraction.gte(0.95).and(ratio.gte(0.8).or(ratio.lte(0.2))), water: ratio.gte(0.8)};
}
function pairBands(a, b, prefix) {
  var supported = a.known.and(b.known);
  return supported.rename(prefix + '_pair_area_km2')
    .addBands(supported.and(a.water.eq(b.water)).rename(prefix + '_same_area_km2'));
}
var AREA_NAMES = ['domain_area_km2', 'sar_observed_area_km2', 'sar_m15_water_area_km2', 'sar_m17_water_area_km2', 'sar_m19_water_area_km2',
  'dw_observed_area_km2', 'dw_known_area_km2', 'dw_water_area_km2', 'jrc_observed_area_km2', 'jrc_water_area_km2',
  'sar_dw_pair_area_km2', 'sar_dw_same_area_km2', 'sar_jrc_pair_area_km2', 'sar_jrc_same_area_km2', 'dw_jrc_pair_area_km2', 'dw_jrc_same_area_km2'];
var PROPERTIES = ['method', 'year', 'month', 'period', 'region', 'water_group', 'sar_track', 's1_images', 's1_days', 'dw_images', 'dw_days', 'jrc_images'];
function monthlyTable(y, m, selectedSar, selectedTrack) {
  var date = ee.Date.fromYMD(y, m, 1), end = date.advance(1, 'month');
  var sr = selectedSar.filterDate(date, end), dr = dwAll.filterDate(date, end), jc = jrcCollection(y, m);
  var cleanedSar = sr.map(cleanRadar);
  var sd = dailyMosaics(cleanedSar, ['VV']);
  var vv = medianOrMissing(sd, ['VV']);
  var valid10 = countOrZero(sd, 'VV').gte(MIN_DAYS);
  var sv = fraction30(valid10), sw15 = fraction30(vv.lte(-15).and(valid10)), sw17 = fraction30(vv.lte(-17).and(valid10)), sw19 = fraction30(vv.lte(-19).and(valid10));
  var preparedDw = dr.map(function(i) {
    var land = i.select(['trees', 'grass', 'crops', 'shrub_and_scrub', 'built', 'bare', 'snow_and_ice']).reduce(ee.Reducer.max()).rename('land');
    return i.select('water').addBands(land).reproject(TEN).copyProperties(i, ['_day', 'system:index']);
  });
  var dd = dailyMosaics(preparedDw, ['water', 'land']), dm = medianOrMissing(dd, ['water', 'land']);
  var observedDw = countOrZero(dd, 'water').gte(MIN_DAYS);
  var waterDw = observedDw.and(dm.select('water').gte(DW_CONFIDENCE));
  var landDw = observedDw.and(dm.select('land').gte(DW_CONFIDENCE)).and(dm.select('water').lte(1 - DW_CONFIDENCE));
  var dv = fraction30(waterDw.or(landDw)), dw = fraction30(waterDw), dObserved = fraction30(observedDw);
  var ji = ee.Image(ee.Algorithms.If(jc.size().eq(1), jc.first(), empty30.rename('water'))).unmask(0).reproject(PROJECTION);
  var jv = ji.gte(1).and(ji.lte(2)), jw = ji.eq(2);
  var sstate = cellState(sw17, sv), dstate = cellState(dw, dv), jstate = {known: jv, water: jw};
  var measures = ee.Image(1).rename('domain_area_km2').setDefaultProjection(PROJECTION)
    .addBands(sv.rename('sar_observed_area_km2')).addBands(sw15.rename('sar_m15_water_area_km2'))
    .addBands(sw17.rename('sar_m17_water_area_km2')).addBands(sw19.rename('sar_m19_water_area_km2'))
    .addBands(dObserved.rename('dw_observed_area_km2')).addBands(dv.rename('dw_known_area_km2')).addBands(dw.rename('dw_water_area_km2'))
    .addBands(jv.rename('jrc_observed_area_km2')).addBands(jw.rename('jrc_water_area_km2'))
    .addBands(pairBands(sstate, dstate, 'sar_dw')).addBands(pairBands(sstate, jstate, 'sar_jrc')).addBands(pairBands(dstate, jstate, 'dw_jrc'))
    .unmask(0).multiply(ee.Image.pixelArea().divide(1e6));
  var tables = COHORTS.map(function(cohort) {
    var sums = measures.updateMask(cohort.mask).reduceRegions({collection: districts, reducer: ee.Reducer.sum(), crs: PROJECTION, tileScale: 4});
    var attributes = {method: METHOD, year: y, month: m, period: y + '-' + pad(m), water_group: cohort.name, sar_track: selectedTrack,
      s1_images: sr.size(), s1_days: sd.size(), dw_images: dr.size(), dw_days: dd.size(), jrc_images: jc.size()};
    sums = sums.map(function(f) {
      var values = ee.Dictionary.fromLists(AREA_NAMES, AREA_NAMES.map(function(n) { return ee.Algorithms.If(f.get(n), f.get(n), 0); }));
      return ee.Feature(null, values).set('region', f.get('region')).set(attributes);
    });
    var union = ee.Feature(null, ee.Dictionary.fromLists(AREA_NAMES, AREA_NAMES.map(function(n) { return sums.aggregate_sum(n); })))
      .set(attributes).set('region', 'All_districts');
    return sums.merge(ee.FeatureCollection([union]));
  });
  return ee.FeatureCollection(tables).flatten();
}
function sceneTable(collection, sensor) {
  return ee.FeatureCollection(collection.toList(collection.size().max(1)).map(function(raw) {
    var i = ee.Image(raw), d = ee.Date(i.get('system:time_start'));
    return ee.Feature(null, {sensor: sensor, scene_id: i.id(), date: d.format('YYYY-MM-dd'), year: d.get('year'), month: d.get('month'),
      track: ee.Algorithms.If(sensor === 'S1', i.get('_track'), 'OPTICAL')});
  }));
}
function exportCsv(fc, name, selectors) {
  Export.table.toDrive({collection: fc, description: name, folder: FOLDER, fileNamePrefix: name, fileFormat: 'CSV', selectors: selectors});
}
var status = ui.Label('v2 TIMEOUT FIX — Run হয়েছে। নিচের button চাপলে 14টি export task তৈরি হবে।');
var button = ui.Button({label: 'CREATE 14 CSV DOWNLOAD TASKS', style: {color: 'blue'}, onClick: function() {
  button.setDisabled(true);status.setValue('Export graphs তৈরি হচ্ছে… এখানে দশ বছরের pixel audit চালানো হচ্ছে না।');
  // No evaluate()/getInfo() anywhere in this export-planning path. Heavy work
  // belongs to batch exports, which have a longer runtime budget than the UI.
  var inventory = annualAudit.slice();
  for (var y = FIRST; y <= LAST; y++) for (var m = 1; m <= 12; m++) {
    var date = ee.Date.fromYMD(y, m, 1), end = date.advance(1, 'month');
    [[selectedSar, 'S1', IDS.sar], [dwAll, 'DW', IDS.dw]].forEach(function(item) {
      var c = item[0].filterDate(date, end);
      inventory.push(ee.Feature(null, {dataset: item[1], year: y, month: m, asset: item[2], actual_images: c.size(), unique_days: ee.List(c.aggregate_array('_day')).distinct().size()}));
    });
    var j = jrcCollection(y, m);
    inventory.push(ee.Feature(null, {dataset: 'JRC_MONTHLY', year: y, month: m, asset: y < 2022 ? IDS.monthlyOld : IDS.monthlyNew, actual_images: j.size(), unique_days: -1}));
  }
  var pending = [];
  function addTask(collection, name, selectors) { pending.push({collection: collection, name: name, selectors: selectors}); }
  addTask(ee.FeatureCollection(inventory), 'auto_source_inventory', ['dataset', 'year', 'month', 'asset', 'actual_images', 'unique_days']);
  addTask(orbitAudit, 'auto_orbit_audit', ['track', 'footprint_proxy_fraction', 'quantized_footprint_proxy', 'months_with_any_scene', 'scene_count', 'rank_score', 'representative_scenes', 'ranking_rule', 'sort_key']);
  addTask(sceneTable(selectedSar, 'S1').merge(sceneTable(dwAll, 'DW')), 'auto_scene_inventory', ['sensor', 'scene_id', 'date', 'year', 'month', 'track']);
  var settings = ee.Feature(null, {method: METHOD, start_year: FIRST, end_year: LAST, sar_track: selectedTrack, minimum_unique_days: MIN_DAYS,
    dw_confidence: DW_CONFIDENCE, vv_primary_db: -17, vv_loose_db: -15, vv_strict_db: -19,
    angle_min: 30, angle_max: 45, agreement_cell_support: 0.95, agreement_water_fraction: 0.8,
    analysis_crs: 'EPSG:4326', analysis_transform: JSON.stringify([0.00026949458523585647, 0, 0, 0, -0.00026949458523585647, 0]),
    source_jrc_crs: SOURCE_PROJECTION.crs(), source_jrc_nominal_scale_m: SOURCE_PROJECTION.nominalScale(), boundary_asset: BOUNDARY,
    orbit_ranking_rule: ORBIT_RULE, orbit_proxy_max_scenes: 6,
    footprint: 'retrospective_annual_ever_water_2000_2024', initial_classes: 'strict_majority_2000_2004_all_five_observed',
    accuracy_status: 'AUTOMATED_AGREEMENT_NOT_GROUND_TRUTH', observations_imputed: 0});
  addTask(ee.FeatureCollection([settings]), 'auto_settings', ['method', 'start_year', 'end_year', 'sar_track', 'minimum_unique_days', 'dw_confidence',
    'vv_primary_db', 'vv_loose_db', 'vv_strict_db', 'angle_min', 'angle_max', 'agreement_cell_support', 'agreement_water_fraction',
    'analysis_crs', 'analysis_transform', 'source_jrc_crs', 'source_jrc_nominal_scale_m', 'boundary_asset', 'orbit_ranking_rule', 'orbit_proxy_max_scenes',
    'footprint', 'initial_classes', 'accuracy_status', 'observations_imputed']);
  for (var year = FIRST; year <= LAST; year++) {
    var months = [];
    for (var month = 1; month <= 12; month++) months.push(monthlyTable(year, month, selectedSar, selectedTrack));
    addTask(ee.FeatureCollection(months).flatten(), 'auto_monthly_' + year, PROPERTIES.concat(AREA_NAMES));
  }
  pending.forEach(function(task) { exportCsv(task.collection, task.name, task.selectors); });
  status.setValue('v2: 14 tasks তৈরি হয়েছে। Tasks → Run all। সব Completed হওয়ার পরে CSV download করো।');
  print('v2 uses batch exports. Source/orbit/coverage audits remain mandatory after download; task creation is not an audit pass.');
}});
Map.centerObject(boundary, 8);Map.addLayer(boundary, {color: 'red'}, 'Three-district boundary');
// Do not request a reprojected 25-year pixel composite as an interactive map layer.
ui.root.insert(0, ui.Panel([ui.Label('Automatic water research — no manual labels'), status, button,
  ui.Label('Estimates and sensor agreement; no 100% accuracy or publication guarantee.')]));
