import argparse
import json
from pathlib import Path
from typing import Any


def parse_float(value: Any) -> float | None:
    if value is None:
        return None

    try:
        return float(str(value).strip().replace(",", ""))
    except ValueError:
        return None


def is_valid_lon_lat(lon: float | None, lat: float | None) -> bool:
    return (
        lon is not None
        and lat is not None
        and -180 <= lon <= 180
        and -90 <= lat <= 90
    )


def make_arcgis_safe_value(value: Any) -> Any:
    """
    ArcGIS Pro imports GeoJSON properties most reliably when values are simple:
    string, number, bool, or null.

    Lists/dicts are converted to JSON strings so fields like
    google_photo_author_attributions do not break field creation.
    """
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return value


def make_arcgis_safe_properties(properties: dict[str, Any]) -> dict[str, Any]:
    return {
        key: make_arcgis_safe_value(value)
        for key, value in properties.items()
    }


def get_input_features(input_data: Any) -> list[dict[str, Any]]:
    """
    Supports either:
    1. Your current wrapped output:
       {
         "type": "RestaurantInspectionGoogleJoin",
         "features": [...]
       }

    2. A raw list of feature-like records:
       [...]
    """
    if isinstance(input_data, dict) and isinstance(input_data.get("features"), list):
        return input_data["features"]

    if isinstance(input_data, list):
        return input_data

    raise ValueError("Input JSON must contain a top-level 'features' list or be a list of records.")


def convert_feature(feature: dict[str, Any]) -> dict[str, Any] | None:
    """
    Converts your current feature format:

    {
      "type": "Feature",
      "geometry": {
        "longitude": -120.0,
        "latitude": 37.0,
        "spatialReference": {"wkid": 4326}
      },
      "attributes": {...}
    }

    into GeoJSON:

    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [-120.0, 37.0]
      },
      "properties": {...}
    }
    """
    geometry = feature.get("geometry") or {}

    # If it is already GeoJSON geometry, preserve it.
    if geometry.get("type") == "Point" and isinstance(geometry.get("coordinates"), list):
        coordinates = geometry["coordinates"]

        if len(coordinates) >= 2:
            lon = parse_float(coordinates[0])
            lat = parse_float(coordinates[1])

            if is_valid_lon_lat(lon, lat):
                properties = feature.get("properties") or feature.get("attributes") or {}

                return {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat],
                    },
                    "properties": make_arcgis_safe_properties(properties),
                }

    # Convert your current ArcGIS-ish geometry.
    lon = parse_float(geometry.get("longitude"))
    lat = parse_float(geometry.get("latitude"))

    if not is_valid_lon_lat(lon, lat):
        return None

    properties = feature.get("attributes") or feature.get("properties") or {}

    return {
        "type": "Feature",
        "geometry": {
            "type": "Point",
            "coordinates": [lon, lat],
        },
        "properties": make_arcgis_safe_properties(properties),
    }


def convert_json_to_geojson(input_path: Path, output_path: Path) -> None:
    with input_path.open("r", encoding="utf-8-sig") as infile:
        input_data = json.load(infile)

    input_features = get_input_features(input_data)

    geojson_features: list[dict[str, Any]] = []
    skipped_count = 0

    for feature in input_features:
        converted = convert_feature(feature)

        if converted is None:
            skipped_count += 1
            continue

        geojson_features.append(converted)

    output_data = {
        "type": "FeatureCollection",
        "name": output_path.stem,
        "features": geojson_features,
    }

    with output_path.open("w", encoding="utf-8") as outfile:
        json.dump(output_data, outfile, ensure_ascii=False, indent=2)

    print(f"Done.")
    print(f"Input features: {len(input_features)}")
    print(f"Output GeoJSON features: {len(geojson_features)}")
    print(f"Skipped features without valid coordinates: {skipped_count}")
    print(f"Wrote: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert restaurant_data.json into ArcGIS Pro-ready GeoJSON."
    )

    parser.add_argument(
        "input_json",
        help="Input JSON file, for example restaurant_data.json",
    )

    parser.add_argument(
        "output_geojson",
        help="Output GeoJSON file, for example restaurant_data.geojson",
    )

    args = parser.parse_args()

    input_path = Path(args.input_json)
    output_path = Path(args.output_geojson)

    if not input_path.exists():
        raise FileNotFoundError(f"Input file does not exist: {input_path}")

    if output_path.suffix.lower() != ".geojson":
        print("Warning: output file should usually end with .geojson for ArcGIS Pro.")

    convert_json_to_geojson(input_path, output_path)


if __name__ == "__main__":
    main()