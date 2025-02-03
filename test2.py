from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from shapely.geometry import mapping, Point
import json
import folium
from folium.plugins import HeatMap
from dbhandler import db_handler
from locations import Location
from districts import District


# session = Session()
session = db_handler()

# GeoJSON output file path
GEOJSON_OUTPUT_PATH = "heatmap_data.geojson"
HEATMAP_HTML_PATH = "district_heatmap.html"

# SQLAlchemy models
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, Float



# class Location(Base):
#     __tablename__ = 'locations'
#     id = Column(Integer, primary_key=True)
#     name = Column(String)
#     rate = Column(Float)
#     geom = Column(Geometry('POINT', srid=4326))
#
#
# class District(Base):
#     __tablename__ = 'districts'
#     id = Column(Integer, primary_key=True)
#     name = Column(String)
#     geom = Column(Geometry('POLYGON', srid=4326))


def fetch_heatmap_data(district_name):
    """
    Fetch business density data for a given district and export it as GeoJSON.
    """
    try:
        # Get the district geometry

        district = session.query(District).filter(District.name == district_name).first()

        test_query = session.query(func.ST_AsText(district.geom)).filter(District.name == district_name).first()
        test = session.query(func.ST_AsText(Location.geom)).first()
        print("MMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM")
        print(test_query)
        print(test)

        if not district:
            print(f"District '{district_name}' not found.")
            return None
        print("=================================================================")
        print(district)
        print(district.name)
        print("=================================================================")
        # Query locations within the district
        businesses = (
            session.query(Location.geom, func.count(Location.id).label('business_count'))
            .filter(Location.category == "خوراکی")
            .filter(func.ST_Contains(district.geom, Location.geom))
            .group_by(Location.geom)
            .all()
        )
        print("\n=================================================================")
        print(businesses)
        print("=================================================================")

        features = []
        for geom, business_count in businesses:
            point = to_shape(geom)  # Convert to Shapely geometry
            feature = {
                "type": "Feature",
                "geometry": mapping(point),
                "properties": {
                    "business_count": business_count
                }
            }
            features.append(feature)

        geojson_data = {
            "type": "FeatureCollection",
            "features": features
        }
        print("\n=================================================================")
        print(geojson_data)
        print("=================================================================")
        # Write GeoJSON to file
        with open(GEOJSON_OUTPUT_PATH, "w", encoding="utf-8") as f:
            json.dump(geojson_data, f, ensure_ascii=False, indent=4)

        print(f"GeoJSON data saved to {GEOJSON_OUTPUT_PATH}")
        return geojson_data

    except Exception as e:
        print(f"Error fetching heatmap data: {e}")
        return None


def generate_heatmap(geojson_file):
    """
    Generates an interactive heatmap from the GeoJSON file.
    """
    try:
        # Load GeoJSON file
        with open(geojson_file, "r", encoding="utf-8") as f:
            geojson_data = json.load(f)

        heatmap_data = [
            (feature["geometry"]["coordinates"][0], feature["geometry"]["coordinates"][1],
             feature["properties"]["business_count"])
            for feature in geojson_data["features"]
        ]
        print("\n=================================================================")
        print(heatmap_data)
        print("=================================================================")

        # Set map center
        if heatmap_data:
            center = [heatmap_data[0][0], heatmap_data[0][1]]
        else:
            center = [35.733, 51.542]  # Default to Tehran
            print("\n\n<><><><><><><><><> Default Tehran <><><><><><><><><>\n\n")

        # Create a folium map
        district_map = folium.Map(location=center, zoom_start=13)

        # Add heatmap layer
        HeatMap(heatmap_data, radius=25, blur=15, max_zoom=14).add_to(district_map)
        district = session.query(District).filter(District.name == "منطقه 2").first()
        print("after heatmap")
        businesses = (
            session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"))
            .filter(Location.category == "خوراکی")
            .filter(func.ST_Contains(district.geom, Location.geom))
            .group_by(Location.geom)
            .all()
        )
        print("\n=================================================================")
        print(businesses)
        for point in businesses:
            print("hello")
            print(point.latitude, point.longitude)
            folium.CircleMarker(
                location=[point.latitude, point.longitude],
                radius=3,
                color='red',
                fill=True,
                fill_color='blue'
            ).add_to(district_map)
        kos =HeatMap(heatmap_data, radius=25, blur=15, max_zoom=14)
        print(kos)

        # Save heatmap as HTML
        district_map.save(HEATMAP_HTML_PATH)
        print(f"Heatmap saved to {HEATMAP_HTML_PATH}")

    except Exception as e:
        print(f"Error generating heatmap: {e}")


if __name__ == "__main__":
    district_name = input("Enter the district name: ")
    s = 'منطقه '
    district_name = s + district_name
    # Fetch heatmap data
    geojson_data = fetch_heatmap_data(district_name)

    if geojson_data:
        # Generate heatmap visualization
        generate_heatmap(GEOJSON_OUTPUT_PATH)
        print("Process completed successfully. Open the HTML file to view the heatmap.")
