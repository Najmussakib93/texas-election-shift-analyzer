import json

US_GEOJSON_IN = "data/us_counties.geojson"
TX_GEOJSON_OUT = "data/texas_counties.geojson"
TX_PREFIX = "48"  # Texas state FIPS prefix


def main():
    with open(US_GEOJSON_IN, "r", encoding="utf-8") as f:
        geo = json.load(f)

    features = geo.get("features", [])
    if not features:
        raise ValueError("No features found in input GeoJSON.")

    tx_features = []
    for feat in features:
        fid = feat.get("id")
        if not fid:
            continue

        fid = str(fid).zfill(5)
        if not fid.startswith(TX_PREFIX):
            continue

        if "properties" not in feat or feat["properties"] is None:
            feat["properties"] = {}

        # Ensure both id + properties.geoid exist
        feat["id"] = fid
        feat["properties"]["geoid"] = fid

        tx_features.append(feat)

    tx_geo = {"type": "FeatureCollection", "features": tx_features}

    with open(TX_GEOJSON_OUT, "w", encoding="utf-8") as f:
        json.dump(tx_geo, f)

    print(f"✅ Wrote {len(tx_features)} Texas counties to {TX_GEOJSON_OUT}")


if __name__ == "__main__":
    main()
