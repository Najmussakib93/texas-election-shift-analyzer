import json
from pathlib import Path

US_COUNTIES_GEOJSON = Path("data/us_counties.geojson")
TX_OUT = Path("data/texas_counties.geojson")


def norm_fips(x) -> str:
    return str(x).zfill(5)


def main():
    if not US_COUNTIES_GEOJSON.exists():
        raise FileNotFoundError(
            "Missing data/us_counties.geojson. Download a US counties GeoJSON first."
        )

    with US_COUNTIES_GEOJSON.open("r", encoding="utf-8") as f:
        geo = json.load(f)

    out_feats = []
    for feat in geo.get("features", []):
        props = feat.get("properties", {}) or {}

        geoid = props.get("geoid") or props.get("GEOID") or feat.get("id")
        if geoid is None:
            continue

        geoid = norm_fips(geoid)

        # Texas counties start with state FIPS "48"
        if not geoid.startswith("48"):
            continue

        name = props.get("name") or props.get("NAME") or props.get("NAMELSAD") or ""

        # Minimal, clean feature
        clean = {
            "type": "Feature",
            "id": geoid,
            "properties": {"geoid": geoid, "name": name},
            "geometry": feat.get("geometry"),
        }
        out_feats.append(clean)

    out_geo = {"type": "FeatureCollection", "features": out_feats}

    TX_OUT.parent.mkdir(parents=True, exist_ok=True)
    with TX_OUT.open("w", encoding="utf-8") as f:
        json.dump(out_geo, f)

    print(f"Wrote {len(out_feats)} features to {TX_OUT}")


if __name__ == "__main__":
    main()
