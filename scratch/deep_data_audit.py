import os
import sys
import json
import csv
from pathlib import Path
import numpy as np
import tifffile
from PIL import Image

def analyze_geojson(path):
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        features = data.get('features', [])
        count = len(features)
        types = set()
        props_keys = set()
        lats, lons = [], []
        for feat in features:
            geom = feat.get('geometry') or {}
            types.add(geom.get('type'))
            props = feat.get('properties') or {}
            props_keys.update(props.keys())
            coords = geom.get('coordinates')
            # Extract point or sample bounds
            def extract_coords(c):
                if isinstance(c, (list, tuple)):
                    if len(c) >= 2 and isinstance(c[0], (int, float)) and isinstance(c[1], (int, float)):
                        lons.append(c[0])
                        lats.append(c[1])
                    else:
                        for sub in c:
                            extract_coords(sub)
            extract_coords(coords)
        bbox = (min(lons), min(lats), max(lons), max(lats)) if lats and lons else None
        return {
            'format': 'GeoJSON',
            'feature_count': count,
            'geom_types': list(types),
            'bbox_wgs84': bbox,
            'sample_properties': list(props_keys)[:12],
            'crs': data.get('crs', {}).get('properties', {}).get('name', 'EPSG:4326 (WGS84 implied)')
        }
    except Exception as e:
        return {'format': 'GeoJSON', 'error': str(e)}

def analyze_csv(path):
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.reader(f)
            header = next(reader, [])
            rows = 0
            for _ in reader:
                rows += 1
        return {
            'format': 'CSV',
            'row_count': rows,
            'column_count': len(header),
            'columns': header[:15]
        }
    except Exception as e:
        return {'format': 'CSV', 'error': str(e)}

def analyze_tif(path):
    try:
        with tifffile.TiffFile(path) as tif:
            series = tif.series[0]
            shape = series.shape
            dtype = str(series.dtype)
            tags = {}
            for tag in tif.pages[0].tags.values():
                name = tag.name
                if 'geo' in name.lower() or 'model' in name.lower() or 'pixel' in name.lower():
                    tags[name] = str(tag.value)[:100]
            # Read sample for min/max
            arr = tif.pages[0].asarray()
            min_val = float(np.nanmin(arr)) if arr.size else None
            max_val = float(np.nanmax(arr)) if arr.size else None
            return {
                'format': 'GeoTIFF',
                'shape': shape,
                'dtype': dtype,
                'min_value': min_val,
                'max_value': max_val,
                'geotags': tags
            }
    except Exception as e:
        return {'format': 'GeoTIFF', 'error': str(e)}

def main():
    root = Path('.')
    print("=== AUDITING DATA PACKAGES ===")
    dirs_to_scan = [
        Path('mumbai_flood_data_package'),
        Path('mumbai_flood_data'),
        Path('data'),
        Path('.')
    ]
    
    inventory = []
    
    seen_files = set()
    for d in dirs_to_scan:
        if not d.exists():
            continue
        if d == Path('.'):
            # Only root files
            files = [f for f in d.glob('*') if f.is_file() and f.suffix.lower() in ['.geojson', '.csv', '.tif', '.json', '.sql']]
        else:
            files = [f for f in d.rglob('*') if f.is_file() and f.suffix.lower() in ['.geojson', '.csv', '.tif', '.json', '.sql']]
            
        for f in files:
            path_str = str(f)
            if path_str in seen_files:
                continue
            seen_files.add(path_str)
            
            # Skip package.json, etc.
            if f.name in ['package.json', 'package-lock.json', 'tsconfig.json']:
                continue
            if 'node_modules' in path_str or '.git' in path_str or '.next' in path_str:
                continue
                
            sz = f.stat().st_size
            ext = f.suffix.lower()
            
            info = {
                'path': path_str,
                'name': f.name,
                'size_bytes': sz,
                'extension': ext
            }
            
            if ext == '.geojson':
                info.update(analyze_geojson(f))
            elif ext == '.csv':
                info.update(analyze_csv(f))
            elif ext in ['.tif', '.tiff']:
                info.update(analyze_tif(f))
            elif ext == '.json':
                try:
                    with open(f, 'r', encoding='utf-8') as jf:
                        jdata = json.load(jf)
                    info['keys'] = list(jdata.keys()) if isinstance(jdata, dict) else len(jdata)
                except Exception as je:
                    info['json_error'] = str(je)
                    
            inventory.append(info)
            
    print(f"Inventoried {len(inventory)} data files.")
    
    with open('scratch/inventory_raw.json', 'w', encoding='utf-8') as out:
        json.dump(inventory, out, indent=2)
        
    # Print summary highlights
    for item in inventory:
        p = item['path']
        sz_kb = item['size_bytes'] / 1024
        fmt = item.get('format', item['extension'])
        print(f"[{fmt}] {p} ({sz_kb:.1f} KB)")
        if 'feature_count' in item:
            print(f"    Features: {item['feature_count']}, Geom: {item['geom_types']}, BBox: {item['bbox_wgs84']}")
        elif 'row_count' in item:
            print(f"    Rows: {item['row_count']}, Cols: {item['column_count']}")
        elif 'shape' in item:
            print(f"    Shape: {item['shape']}, Min: {item['min_value']}, Max: {item['max_value']}")

if __name__ == '__main__':
    main()
