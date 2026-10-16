/* Google Earth Engine Code Editor. Real historical calibration, no replacement values.
 * Same verified boundary and native climate grids as the study exports.
 * Export 38 rasters + 456-row source inventory; download to the named local folder.
 */
var CREATE_RASTER_TASKS = false;
var DRIVE_FOLDER = 'NW_Bangladesh_climate_baseline_1981_1999';
var study_area = ee.FeatureCollection('projects/gen-lang-client-0603076418/assets/NW_Bangladesh_3districts');
var region = study_area.geometry();
var CHIRPS = 'UCSB-CHC/CHIRPS/V3/PENTAD';
var ERA = 'ECMWF/ERA5_LAND/MONTHLY_AGGR';
var BANDS = ['potential_evaporation_sum','temperature_2m','dewpoint_temperature_2m',
  'total_precipitation_sum','u_component_of_wind_10m','v_component_of_wind_10m'];
function source(id,y,m) {
  var date=ee.Date.fromYMD(y,m,1);
  return ee.ImageCollection(id).filterDate(date,date.advance(1,'month'));
}
function label(m) { return 'm'+(m<10?'0':'')+m; }
var rows=[];
for(var y=1981;y<=1999;y++) {
  for(var m=1;m<=12;m++) {
    [[CHIRPS,'CHIRPS_PENTAD',6],[ERA,'ERA5_LAND_MONTHLY',1]].forEach(function(spec) {
      var col=source(spec[0],y,m), count=col.size();
      var dates=ee.List(col.aggregate_array('system:time_start')).distinct().size();
      rows.push(ee.Feature(null,{dataset:spec[1],source_asset:spec[0],year:y,month:m,
        expected_images:spec[2],actual_images:count,unique_timestamps:dates,
        period_count_ok:count.eq(spec[2]).and(dates.eq(spec[2]))}));
    });
  }
}
var inventory=ee.FeatureCollection(rows);
var failed=inventory.filter(ee.Filter.neq('period_count_ok',1));
print('Expected 456 rows',inventory.size()); print('Must be zero failures',failed);
Map.centerObject(study_area,8); Map.addLayer(study_area,{color:'red'},'Verified boundary');
function task(img,name,projection) {
  Export.image.toDrive({image:img.clip(region).unmask(-9999,false),description:name,
    folder:DRIVE_FOLDER,fileNamePrefix:name,region:region,crs:projection.crs,
    crsTransform:projection.transform,maxPixels:1e13,fileFormat:'GeoTIFF',
    formatOptions:{cloudOptimized:true,noData:-9999}});
}
failed.size().evaluate(function(n,error) {
  if(error || n!==0) { print('STOP: resolve inventory failure before export',error); return; }
  if(!CREATE_RASTER_TASKS) { print('Inventory passed. Set CREATE_RASTER_TASKS=true and run again.'); return; }
  Export.table.toDrive({collection:inventory,description:'baseline_source_inventory',
    folder:DRIVE_FOLDER,fileFormat:'CSV',selectors:['dataset','source_asset','year','month',
      'expected_images','actual_images','unique_timestamps','period_count_ok']});
  var rainGrid=ee.Image(source(CHIRPS,1981,1).first()).select('precipitation').projection().getInfo();
  var eraGrid=ee.Image(source(ERA,1981,1).first()).select(BANDS[0]).projection().getInfo();
  for(var year=1981;year<=1999;year++) {
    var rainMonths=[],eraMonths=[];
    for(var month=1;month<=12;month++) {
      var rainSource=source(CHIRPS,year,month).select('precipitation');
      var rain=rainSource.sum().updateMask(rainSource.count().eq(6));
      rainMonths.push(rain.toFloat().rename(label(month)+'_rainfall_mm'));
      var era=ee.Image(source(ERA,year,month).first()).select(BANDS);
      var names=BANDS.map(function(b) { return label(month)+'_'+b; });
      eraMonths.push(era.toFloat().rename(names));
    }
    task(ee.Image.cat(rainMonths),'chirps_v3_monthly_'+year,rainGrid);
    task(ee.Image.cat(eraMonths),'era5land_monthly_'+year,eraGrid);
  }
  print('38 real raster tasks + inventory. Run each task once. No SPI results are invented.');
});
