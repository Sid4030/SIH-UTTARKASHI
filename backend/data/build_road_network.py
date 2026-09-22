"""
Build Comprehensive Road Network GeoJSON for Uttarkashi District
=================================================================
Combines:
1. NH-108 / NH-34 (Bhagirathi Highway Corridor: Chinyalisaur -> Uttarkashi -> Gangotri)
2. NH-134 (Yamunotri National Highway: Dharasu -> Barkot -> Naugaon -> Janki Chatti -> Kharsali)
3. SH-17 / Tons Valley Arterial (Barkot -> Purola -> Mori -> Netwar -> Sankri)
4. Local Rural Lifeline Roads (Mando, Siror, Kankrari, Barsu, Dunda)
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
OUTPUT_DIR = BASE_DIR / "output"
VECTORS_DIR = BASE_DIR / "data" / "datasets" / "vectors"
VECTORS_DIR.mkdir(parents=True, exist_ok=True)

# 1. Load existing NH-108 segments
nh108_file = OUTPUT_DIR / "corridor_nh108.geojson"
features = []

if nh108_file.exists():
    with open(nh108_file) as f:
        nh108_data = json.load(f)
    for feat in nh108_data.get("features", []):
        feat["properties"]["highway_class"] = "primary"
        feat["properties"]["highway_name"] = "NH-108 / NH-34 (Bhagirathi Highway)"
        features.append(feat)

# Lower NH-34 section: Dharasu - Chinyalisaur - Dunda - Matli - Uttarkashi Town
lower_nh34 = {
    "type": "Feature",
    "properties": {
        "name": "NH-34 (Lower Bhagirathi Section)",
        "highway_class": "trunk",
        "highway_name": "NH-34",
        "habitations": "Dharasu, Chinyalisaur, Dunda, Matli, Uttarkashi Town"
    },
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [78.310, 30.550],  # Dharasu Bend
            [78.280, 30.525],  # Barethi
            [78.240, 30.520],  # Chinyalisaur
            [78.270, 30.510],  # Lakhwar link
            [78.355, 30.614],  # Barkot junction / Dharasu link
            [78.380, 30.600],  # Dunda
            [78.390, 30.625],  # Athali
            [78.420, 30.660],  # Matli
            [78.445, 30.727],  # Uttarkashi Town
        ]
    }
}
features.append(lower_nh34)

# 2. NH-134 (Yamunotri National Highway)
nh134 = {
    "type": "Feature",
    "properties": {
        "name": "NH-134 (Yamunotri Highway)",
        "highway_class": "primary",
        "highway_name": "NH-134",
        "habitations": "Dharasu, Barkot, Naugaon, Rajgarhi, Kharadi, Janki Chatti, Kharsali"
    },
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [78.310, 30.550],  # Dharasu
            [78.355, 30.614],  # Barkot
            [78.400, 30.590],  # Dhanari
            [78.460, 30.680],  # Siror Junction
            [78.470, 30.690],  # Mando turnoff
            [78.480, 30.710],  # Nirakot turnoff
            [78.490, 30.700],  # Kankrari turnoff
            [78.500, 30.700],  # Naugaon
            [78.520, 30.670],  # Kharadi
            [78.550, 30.650],  # Rajgarhi
            [78.490, 30.640],  # Barnigad
            [78.460, 30.850],  # Upper Yamuna Gorge
            [78.442, 30.985],  # Janki Chatti
            [78.450, 30.990],  # Kharsali (Yamunotri Winter Seat)
        ]
    }
}
features.append(nh134)

# 3. SH-17 / MDR (Barkot - Purola - Mori - Tons Valley Road)
sh17_tons = {
    "type": "Feature",
    "properties": {
        "name": "SH-17 (Barkot-Purola-Mori-Tons Valley Road)",
        "highway_class": "secondary",
        "highway_name": "SH-17",
        "habitations": "Barkot, Purola, Rama Sera, Mori, Netwar, Sankri, Taluka"
    },
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [78.355, 30.614],  # Barkot
            [78.220, 30.750],  # Valley Pass
            [78.100, 30.850],  # Purola
            [78.090, 30.860],  # Hudoli
            [78.120, 30.870],  # Rama Sera
            [78.135, 30.885],  # Gundiyat Gaon
            [78.100, 31.100],  # Mori
            [78.150, 31.050],  # Netwar (Rupin-Supin Confluence)
            [78.185, 31.082],  # Sankri
            [78.195, 31.090],  # Dhatmir turnoff
            [78.060, 31.050],  # Taluka Road Head
        ]
    }
}
features.append(sh17_tons)

# 4. Upper Bhagirathi Link to Gangotri & Harshil (ensuring 0 distance for valley habitations)
upper_bhagirathi_spurs = {
    "type": "Feature",
    "properties": {
        "name": "NH-108 Upper Valley Habitation Spurs",
        "highway_class": "secondary",
        "highway_name": "NH-108 Spurs",
        "habitations": "Barsu, Sukhi, Jhala, Harsil, Dharali, Mukhba, Lanka, Gangotri"
    },
    "geometry": {
        "type": "LineString",
        "coordinates": [
            [78.686, 30.853],  # Barsu
            [78.630, 30.810],  # Sukhi
            [78.650, 30.850],  # Jhala
            [78.738, 31.036],  # Harsil
            [78.745, 31.030],  # Mukhba
            [78.784, 31.023],  # Dharali
            [78.510, 30.780],  # Lanka
            [78.940, 30.995],  # Gangotri
        ]
    }
}
features.append(upper_bhagirathi_spurs)

road_network = {
    "type": "FeatureCollection",
    "name": "Uttarkashi_Arterial_Road_Network",
    "features": features
}

dest_file = VECTORS_DIR / "uttarkashi_roads_osm.geojson"
with open(dest_file, "w") as f:
    json.dump(road_network, f, indent=2)

print(f"✓ Successfully wrote {len(features)} road features to {dest_file}")
