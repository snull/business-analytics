import json

from geoalchemy2.shape import to_shape
from shapely import to_geojson

from dbhandler import db_handler
import streamlit as st
import requests
import math
from shapely.geometry import Polygon, Point, box, MultiPolygon
import folium
from streamlit_folium import st_folium

from districts import select_district
from locations import Location
from categories import fetch_categories, select_category


def fetch_geojson(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


def extract_districts(geojson_data):
    districts = {}
    for feature in geojson_data['features']:
        district_name = feature['properties']['name']
        coordinates = feature['geometry']['coordinates']
        if feature['geometry']['type'] == 'Polygon':
            polygon_coords = coordinates[0]
        else:
            continue

        swapped_coords = [(lat, lon) for lon, lat in polygon_coords]
        districts[district_name] = swapped_coords
    return districts


url = 'https://raw.githubusercontent.com/rferdosi/tehran-districts/main/districts.json'

EARTH_RADIUS = 6371000


def swap_coordinates(districts):
    swapped_districts = {}
    for district, coords in districts.items():
        swapped_districts[district] = [(lon, lat) for lat, lon in coords]
    return swapped_districts


def meters_to_degrees(meters, latitude):
    lat_deg = meters / 111320
    lon_deg = meters / (111320 * math.cos(math.radians(latitude)))
    return lat_deg, lon_deg


# Cache category data


# @st.cache_data(ttl=600)
def fetch_bundle_search_data(base_url, text, polygon_param, selected_sub_category, camera):
    request_url = f"{base_url}?bundle_slug={text}&text={selected_sub_category}&polygon={polygon_param}&camera={camera[0]}%2C{camera[1]}"
    response = requests.get(request_url)

    if response.status_code == 200:
        return response.json()
    return {}


def polygon_generator(coords):
    main_polygon_coords = [(lon, lat) for lat, lon in coords]
    large_polygon = Polygon(main_polygon_coords)

    if not large_polygon.is_valid:
        raise ValueError("The large polygon is invalid! Please check the coordinates.")

    # BOUNDINGING
    min_lat = min(coord[1] for coord in main_polygon_coords)
    max_lat = max(coord[1] for coord in main_polygon_coords)
    min_lon = min(coord[0] for coord in main_polygon_coords)
    max_lon = max(coord[0] for coord in main_polygon_coords)

    lat_step, lon_step = meters_to_degrees(500, min_lat)

    grid_cells = []
    lat = min_lat
    while lat < max_lat:
        lon = min_lon
        while lon < max_lon:
            cell = box(lon, lat, lon + lon_step, lat + lat_step)
            grid_cells.append(cell)
            lon += lon_step
        lat += lat_step

    smaller_polygons = [
        cell.intersection(large_polygon) for cell in grid_cells if cell.intersects(large_polygon)
    ]
    smaller_polygons = [poly for poly in smaller_polygons if not poly.is_empty]

    polygons_with_centroids = [
        {"polygon": poly, "centroid": poly.centroid.coords[0]} for poly in smaller_polygons
    ]

    map_center = ((min_lat + max_lat) / 2, (min_lon + max_lon) / 2)
    m = folium.Map(location=map_center, zoom_start=12)
    st.session_state.center = map_center

    folium.Polygon(
        locations=[(lat, lon) for lon, lat in large_polygon.exterior.coords],
        color="green",
        weight=2,
        fill=True,
        fill_opacity=0.3,
    ).add_to(m)

    for item in polygons_with_centroids:
        poly = item["polygon"]
        centroid = item["centroid"]
        if isinstance(poly, Polygon):
            folium.Polygon(
                locations=[(lat, lon) for lon, lat in poly.exterior.coords],
                color="green",
                weight=1,
                fill=True,
                fill_opacity=0.3,
            ).add_to(m)

        elif isinstance(poly, MultiPolygon):
            for sub_poly in poly.geoms:
                folium.Polygon(
                    locations=[(lat, lon) for lon, lat in sub_poly.exterior.coords],
                    color="green",
                    weight=1,
                    fill=True,
                    fill_opacity=0.3,
                ).add_to(m)

        # folium.Marker(
        #     location=(centroid[1], centroid[0]),
        #     popup=f"Centroid: {centroid[1]}, {centroid[0]}",
        #     icon=folium.Icon(color="red", icon="info-sign"),
        # ).add_to(m)

    return polygons_with_centroids, m


def scrape_data():
    if "center" not in st.session_state:
        st.session_state["center"] = [35.71, 51.36]
    if "zoom" not in st.session_state:
        st.session_state["zoom"] = 12
    if "markers" not in st.session_state:
        st.session_state["markers"] = []

    st.title("🔍 Scrape data")
    st.write("Scrape data (existing locations) in a selected district and sub category.")
    st.divider()

    selected = select_category()
    selected_sub_category = selected['sub_category']
    selected_category = selected['category']

    selected_district = select_district()
    district = to_geojson(to_shape(selected_district.geom), indent=2)
    district = json.loads(district)
    st.write(f"Selected district: {selected_district.name}")

    smaller_polygons, m = polygon_generator(district['coordinates'][0])
    fg = folium.FeatureGroup(name="Markers")
    # for marker in st.session_state["markers"]:
    #     fg.add_child(marker)
    st_folium(m, width=700, height=500, zoom=st.session_state.zoom, center=st.session_state.center, feature_group_to_add=fg)

    base_url = "https://search.raah.ir/v4/bundle-search/"
    text = selected.get("slug", "No slug")
    search_results = []
    unique_entries = set()
    if st.button("Scrape", type='primary'):
        session = db_handler()
        with st.status("Scraping Locations...", expanded=True) as status:
            progress_text = "Operation in progress. Please wait."
            percent_complete = 0
            sp_bar = st.progress(percent_complete, text=progress_text)
            step = 1/len(smaller_polygons)
            for poly in smaller_polygons:
                camera = poly.get("centroid")
                # polygon = poly.get("polygon")
                # polygon_coords = [(lon, lat) for lon, lat in polygon.exterior.coords]
                # polygon_param = "|".join(f"{lon},{lat}" for lon, lat in polygon_coords)
                polygon_param = ''
                bundle_data = fetch_bundle_search_data(base_url, text, polygon_param, selected_sub_category, camera)
                features = bundle_data.get("geojson", {}).get("features", [])
                poi_tokens = bundle_data.get("poi-tokens", [])
                counter = 0
                for feature in features:
                    poi_token = poi_tokens[counter]
                    counter += 1
                    properties = feature.get("properties", {})
                    geometry = feature.get("geometry", {})
                    place_name = properties.get("name", "Unknown Place")
                    rate = properties.get("rate")
                    coordinates = tuple(geometry.get("coordinates", [None, None]))

                    location = Location(
                        name=place_name,
                        geom=f"SRID=4326;POINT({coordinates[1]} {coordinates[0]})",
                        rate=rate,
                        token=poi_token,
                        category=selected_category,
                        subcategory=selected_sub_category,
                    )
                    marker = folium.CircleMarker(
                        location=[coordinates[1], coordinates[0]],
                        radius=3,
                        color='red',
                        fill=True,
                        fill_color='blue'
                    )
                    st.session_state["markers"].append(marker)

                    # fg.add_child(marker)

                    location.add_to_db(session)

                    if (place_name, coordinates) not in unique_entries:
                        unique_entries.add((place_name, coordinates))
                        search_results.append({
                            "name": place_name,
                            "coordinates": list(coordinates),
                        })
                percent_complete += step
                sp_bar.progress(percent_complete, text=f":green[{len(search_results)}] locations found! {progress_text}")

        session.close()
        st.table(search_results)
        st.write(f"Number of unique results: {len(search_results)}")



