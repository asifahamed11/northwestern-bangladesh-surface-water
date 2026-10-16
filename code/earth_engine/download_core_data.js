/* Google Earth Engine Code Editor script. Metadata-selection correction 2026-10-10.
 * Import a verified three-district boundary table as `study_area` first.
 * All years 2000-2024 are included. No fabricated values or interpolation.
 * First run audits source dates. Second run creates actual Drive export tasks.
 * This downloads core data; it does NOT certify pixel-level completeness.
 */
var CREATE_RASTER_TASKS = false; // Set true only after reviewing the audit/map.
var DRIVE_FOLDER = 'NW_Bangladesh_2000_2024';
var START_YEAR = 2000;
var END_YEAR = 2024;
var ERA_BANDS = [
  'potential_evaporation_sum', 'temperature_2m',
  'dewpoint_temperature_2m', 'total_precipitation_sum',
  'u_component_of_wind_10m', 'v_component_of_wind_10m'
];

if (typeof study_area === 'undefined') {
  throw new Error('Import the verified boundary FeatureCollection as study_area. See README.md.');
}
var boundary = ee.FeatureCollection(study_area);
var region = boundary.geometry();
Map.centerObject(boundary, 8);
Map.addLayer(boundary, {color: 'red'}, 'VERIFY: Rajshahi + Naogaon + Chapainawabganj');
print('Boundary properties: verify district names and provenance', boundary);

var IDS = {
  annualOld: 'JRC/GSW1_4/YearlyHistory',
  annualCorrected: 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2016_2021',
  annualNew: 'projects/global-surface-water/assets/GSW1_5/YearlyHistory_2022_2024',
  monthlyOld: 'JRC/GSW1_4/MonthlyHistory',
  monthlyNew: 'projects/JRC/GSW1_5/MonthlyHistory_2022_2024',
  chirps: 'UCSB-CHC/CHIRPS/V3/PENTAD',
  era: 'ECMWF/ERA5_LAND/MONTHLY_AGGR',
  basins: 'WWF/HydroSHEDS/v1/Basins/hybas_7'
};
function annualId(y) {
  return y < 2016 ? IDS.annualOld : (y < 2022 ? IDS.annualCorrected : IDS.annualNew);
}
function monthlyId(y) { return y < 2022 ? IDS.monthlyOld : IDS.monthlyNew; }
function yearAnnual(y) {
  return ee.ImageCollection(annualId(y)).filter(ee.Filter.eq('year', y)).select('waterClass');
}
function monthCollection(id, y, m) {
  if (id === IDS.monthlyNew) {
    // Verified provider indexes: 2022_01 ... 2024_12. No time_start exists.
    // Select the original image by its index and cross-check provider year/month.
    var index = y + '_' + (m < 10 ? '0' : '') + m;
    return ee.ImageCollection(id)
      .filter(ee.Filter.eq('system:index', index))
      .filter(ee.Filter.inList('year', [y, String(y)]))
      .filter(ee.Filter.inList('month', [m, String(m), m < 10 ? '0' + m : String(m)]));
  }
  var start = ee.Date.fromYMD(y, m, 1);
  return ee.ImageCollection(id).filterDate(start, start.advance(1, 'month'));
}

var rows = [];
function auditRow(id, y, m, expected, col, kind) {
  var count = col.size();
  var dates = ee.List(col.aggregate_array('system:time_start')).distinct().size();
  var byIndex = id === IDS.monthlyNew;
  var keys = byIndex
    ? ee.List(col.aggregate_array('system:index')).distinct().size() : dates;
  rows.push(ee.Feature(null, {
    dataset: kind, source_asset: id, year: y, month: m,
    expected_images: expected, actual_images: count,
    unique_timestamps: dates,
    period_key_basis: byIndex ? 'provider_index_year_month' : 'system_time_start',
    unique_period_keys: keys,
    period_count_ok: count.eq(expected).and(keys.eq(expected)),
    pixel_quality_status: 'NOT_YET_AUDITED'
  }));
}
for (var y = START_YEAR; y <= END_YEAR; y++) {
  auditRow(annualId(y), y, 0, 1, yearAnnual(y), 'JRC_ANNUAL');
  for (var m = 1; m <= 12; m++) {
    auditRow(monthlyId(y), y, m, 1, monthCollection(monthlyId(y), y, m), 'JRC_MONTHLY');
    auditRow(IDS.chirps, y, m, 6, monthCollection(IDS.chirps, y, m), 'CHIRPS_PENTAD');
    auditRow(IDS.era, y, m, 1, monthCollection(IDS.era, y, m), 'ERA5_LAND_MONTHLY');
  }
}
var inventory = ee.FeatureCollection(rows);
// ee.Number.eq/and yields numeric 0/1. Boolean false does NOT match numeric 0.
var failures = inventory.filter(ee.Filter.neq('period_count_ok', 1));
print('Expected inventory rows: ' + ((END_YEAR - START_YEAR + 1) * 37), inventory.size());
print('Missing/duplicate source periods (must be zero)', failures);
print('JRC 2022-2024 monthly asset: unfiltered image count',
  ee.ImageCollection(IDS.monthlyNew).size());
print('JRC 2022-2024 monthly asset: first raw image (inspect properties and bands)',
  ee.ImageCollection(IDS.monthlyNew).first());

// Asset timestamps and provenance are exported even if the audit fails.
Export.table.toDrive({collection: inventory, description: 'core_source_inventory_v2_2000_2024',
  folder: DRIVE_FOLDER, fileFormat: 'CSV', selectors: [
    'dataset', 'source_asset', 'year', 'month', 'expected_images',
    'actual_images', 'unique_timestamps', 'period_key_basis', 'unique_period_keys',
    'period_count_ok', 'pixel_quality_status'
  ]});
Export.table.toDrive({collection: boundary, description: 'verified_study_area',
  folder: DRIVE_FOLDER, fileFormat: 'GeoJSON'});
// These are FULL intersecting basins, not clipped district fragments.
// Intersecting basin boundaries do not include the entire upstream network.
Export.table.toDrive({
  collection: ee.FeatureCollection(IDS.basins).filterBounds(region),
  description: 'intersecting_full_hydrobasins_level7',
  folder: DRIVE_FOLDER, fileFormat: 'GeoJSON'
});

function label(m) { return 'm' + (m < 10 ? '0' : '') + m; }
function rasterTask(img, name, projection) {
  Export.image.toDrive({
    // Fill the final clipping mask too, so off-domain pixels agree with the nodata tag.
    image: img.clip(region).unmask(-9999, false), description: name, folder: DRIVE_FOLDER,
    fileNamePrefix: name, region: region,
    crs: projection.crs, crsTransform: projection.transform,
    maxPixels: 1e13, fileFormat: 'GeoTIFF',
    formatOptions: {cloudOptimized: true, noData: -9999}
  });
}
function nodata(img) {
  // Retains JRC's genuine 0=no observation; exported masks use -9999.
  return img.unmask(-9999, false);
}
var gridCache = {};
function sourceGrid(id, image) {
  if (!gridCache[id]) { gridCache[id] = image.select(0).projection().getInfo(); }
  return gridCache[id];
}

failures.size().evaluate(function(n, error) {
  if (error) { print('AUDIT ERROR: no raster tasks created', error); return; }
  if (n !== 0) { print('STOP: source periods failed audit. No raster tasks created.'); return; }
  if (!CREATE_RASTER_TASKS) {
    print('Date inventory passed. Verify the mapped boundary and save the audit.');
    print('Then set CREATE_RASTER_TASKS=true and run again. Pixel coverage still requires audit.');
    return;
  }
  // Export every year. A failure must be resolved, never substituted with zeros.
  for (var year = START_YEAR; year <= END_YEAR; year++) {
    var annual = ee.Image(yearAnnual(year).first());
    // Use the same verified selection for projection discovery and month exports.
    var firstWater = ee.Image(monthCollection(monthlyId(year), year, 1).first()).select('water');
    var chirpsYear = ee.ImageCollection(IDS.chirps)
      .filterDate(year + '-01-01', (year + 1) + '-01-01').select('precipitation');
    var eraYear = ee.ImageCollection(IDS.era)
      .filterDate(year + '-01-01', (year + 1) + '-01-01').select(ERA_BANDS);
    var annualGrid = sourceGrid(annualId(year), annual);
    var monthlyGrid = sourceGrid(monthlyId(year), firstWater);
    var rainGrid = sourceGrid(IDS.chirps, ee.Image(chirpsYear.first()));
    var eraGrid = sourceGrid(IDS.era, ee.Image(eraYear.first()));

    var waterMonths = [];
    var coverageMonths = [];
    var rainMonths = [];
    var eraMonths = [];
    for (var month = 1; month <= 12; month++) {
      var water = ee.Image(monthCollection(monthlyId(year), year, month).first()).select('water');
      waterMonths.push(nodata(water).toInt16().rename(label(month)));
      coverageMonths.push(water.gt(0).and(water.lte(2)).unmask(0, false).rename(label(month)));
      var rainSource = monthCollection(IDS.chirps, year, month).select('precipitation');
      // Six pentads per month. A pixel must have all six valid values.
      var rain = rainSource.sum().updateMask(rainSource.count().eq(6));
      rainMonths.push(nodata(rain).toFloat().rename(label(month) + '_rainfall_mm'));
      var era = ee.Image(monthCollection(IDS.era, year, month).first()).select(ERA_BANDS);
      var bandNames = ERA_BANDS.map(function(b) { return label(month) + '_' + b; });
      // Keep original units and signs. Do NOT call potential evaporation FAO ET0.
      eraMonths.push(nodata(era).toFloat().rename(bandNames));
    }
    rasterTask(nodata(annual).toInt16(), 'jrc_annual_' + year, annualGrid);
    rasterTask(ee.Image.cat(waterMonths), 'jrc_monthly_' + year, monthlyGrid);
    var validMonths = ee.ImageCollection.fromImages(coverageMonths.map(function(i) {
      return ee.Image(i).rename('valid');
    })).sum().toInt16().rename('valid_observed_months');
    rasterTask(validMonths, 'jrc_valid_months_' + year, monthlyGrid);
    rasterTask(ee.Image.cat(rainMonths), 'chirps_v3_monthly_' + year, rainGrid);
    rasterTask(ee.Image.cat(eraMonths), 'era5land_monthly_' + year, eraGrid);
  }
  print('Created ' + ((END_YEAR - START_YEAR + 1) * 5) + ' raster tasks plus 3 table tasks. Run tasks once; repeated Run creates duplicates.');
  print('Downloads retain native grids. No imputation, downscaling, or interpolation performed.');
});
