import json

import folium
import pandas as pd
import streamlit as st
import numpy as np
from folium.plugins import HeatMap
from scipy.spatial.distance import cdist
from shapely import MultiPoint, Point, Polygon
from geoalchemy2.shape import to_shape
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker
from streamlit_folium import st_folium, folium_static

from categories import fetch_categories
from dbhandler import engine, db_handler
from districts import select_district
from heatmaps import Heatmap
from location_suggestion import generate_heatmap


def fetch_all_heatmaps(district):
    """Fetch all heatmaps from the database."""
    session = db_handler()

    subquery = (
        session.query(
            Heatmap.subcategory,
            func.max(Heatmap.id).label('max_id')
        )
        .filter(Heatmap.district_id == district.id)
        .filter(Heatmap.percentile == 100)
        .group_by(Heatmap.subcategory)
        .subquery()
    )

    heatmaps = (
        session.query(Heatmap)
        .join(
            subquery,
            (Heatmap.subcategory == subquery.c.subcategory) &
            (Heatmap.id == subquery.c.max_id)
        )
        .all()
    )
    # heatmaps = session.query(Heatmap).filter(Heatmap.district == district).filter(Heatmap.percentile == 100).all()

    session.close()

    return heatmaps


def evaluate_business_potential(selected_location, heatmaps):
    """Evaluate business potential for each subcategory at the selected location."""
    results = {}
    for heatmap in heatmaps:
        multipoint = to_shape(heatmap.geom)
        weights = heatmap.weights

        # Check if the selected location is within the heatmap's points
        if isinstance(multipoint, MultiPoint):
            points = np.array([[point.x, point.y] for point in multipoint.geoms])
        else:
            points = np.array([[multipoint.x, multipoint.y]])

        # Calculate the distance between the selected location and all points in the heatmap
        distances = np.linalg.norm(points - selected_location, axis=1)
        closest_point_index = np.argmin(distances)
        closest_point_density = weights[closest_point_index]
        distance = cdist([selected_location.tolist()],
                         [[points[closest_point_index][0], points[closest_point_index][1]]], metric='euclidean')
        if distance > 0.0007:
            continue

        # Store the result for this subcategory
        if heatmap.subcategory not in results.keys():
            results[heatmap.subcategory] = [closest_point_density, points[closest_point_index], heatmap.id]
        elif results[heatmap.subcategory][0] < closest_point_density:
            results[heatmap.subcategory] = [closest_point_density, points[closest_point_index], heatmap.id]
    return results


def suggest_best_subcategories(selected_location, district):
    """Suggest the best subcategories for the selected location."""
    # Fetch all heatmaps from the database
    heatmaps = fetch_all_heatmaps(district)

    # Evaluate business potential for each subcategory
    business_potential = evaluate_business_potential(selected_location, heatmaps)

    # Rank subcategories by business potential (higher density is better)
    ranked_subcategories = sorted(business_potential.items(), key=lambda x: x[1], reverse=True)
    return ranked_subcategories


def display_suggestions():
    st.title("💼 Business Suggestion")
    st.write(
        "Suggest the best subcategory to run a business in the selected location based on heatmap data"
    )
    st.divider()
    # Initialize default location in session state
    if "selected_location" not in st.session_state:
        st.session_state["selected_location"] = [35.7926, 51.5117]
    if "zoom" not in st.session_state:
        st.session_state["zoom"] = 12


    # Create a map centered on the last selected location
    m = folium.Map(location=st.session_state["selected_location"], zoom_start=st.session_state["zoom"])

    col1, col2 = st.columns([0.33, 0.66])
    with col1:
        selected_district = select_district()

    district_group = folium.FeatureGroup(name="District").add_to(m)
    district_polygon = Polygon(to_shape(selected_district.geom))
    folium.Polygon(
        locations=[(lon, lat) for lon, lat in district_polygon.exterior.coords],
        color="green",
        weight=1,
        fill=True,
        fill_opacity=0.3,
        # tooltip="<b>" + _district.name + "</b>"
    ).add_to(district_group)
    # Add a marker at the current selected location
    folium.Marker(
        location=st.session_state["selected_location"],
        popup="Selected Location",
        draggable=False,
        icon=folium.Icon(color="blue", icon="info-sign"),
    ).add_to(m)

    # Render the map and listen for user interactions
    map_data = st_folium(m, zoom=st.session_state["zoom"], height=500, width=700,
                         returned_objects=["last_clicked", "zoom", "center"])

    # Check if the user clicked on the map and update the session state
    if map_data and "last_clicked" in map_data and map_data["last_clicked"]:
        new_location = [
            map_data["last_clicked"]["lat"],
            map_data["last_clicked"]["lng"],
        ]

        # Immediately update the map and marker location
        st.session_state["selected_location"] = new_location
        st.session_state["zoom"] = map_data["zoom"]
        # Re-render the map with the updated marker position
        m = folium.Map(location=new_location, zoom_start=12)
        folium.Marker(
            location=new_location,
            popup="Selected Location",
            draggable=False,
            icon=folium.Icon(color="blue", icon="info-sign"),
        ).add_to(m)
        st_folium(m, zoom=st.session_state["zoom"], height=500, width=700)  # Re-render the map with the updated marker

    # Display the updated selected location
    st.write(
        f"Selected location: Latitude {st.session_state['selected_location'][0]:.6f}, "
        f"Longitude {st.session_state['selected_location'][1]:.6f}"
    )

    # Button to suggest subcategories
    if st.button("Suggest Best Subcategory"):
        # Ensure the location is passed as a NumPy array for processing
        selected_location_np = np.array(st.session_state["selected_location"])

        # Get ranked subcategories for the selected location
        ranked_subcategories = suggest_best_subcategories(selected_location_np, selected_district)

        # Display the top suggestions
        st.write("### Top Subcategory Suggestions:")
        if ranked_subcategories:
            table = {data[1][0]: data[1][1] for data in enumerate(ranked_subcategories)}
            table = pd.DataFrame(table).transpose()
            table = table.reset_index()

            st.dataframe(
                table,
                column_config={
                    "index_col": "",
                    1: "Business",
                    2: "Density",
                    3: "Coordinates",
                    4: "heatmap.id",
                },
                use_container_width=True,
            )

            lat, lon = st.session_state["selected_location"]
            city_map = folium.Map(location=[lat, lon], zoom_start=12)
            locations_group = folium.FeatureGroup(name="Locations").add_to(city_map)
            for loc in ranked_subcategories:
                folium.CircleMarker(
                    location=loc[1][1],
                    radius=3,
                    color='black',
                    fill=True,
                    fill_color='blue',
                    popup="<b>" + loc[0] + "</b>"
                ).add_to(locations_group)
            session = db_handler()
            heatmap = session.query(func.ST_AsGeoJSON(Heatmap.geom), Heatmap.weights).filter(
                Heatmap.id == ranked_subcategories[0][1][2]).first()
            session.close()
            geom = json.loads(heatmap[0])
            weights = heatmap[1]

            heatmap_group = folium.FeatureGroup(name='Heatmap').add_to(city_map)
            heatmap_data = []
            for coord, weight in zip(geom['coordinates'], weights):
                heatmap_data.append([coord[0], coord[1], weight])

            HeatMap(heatmap_data).add_to(heatmap_group)
            folium.LayerControl().add_to(city_map)
            folium_static(city_map, width=700, height=500)

        else:
            st.warning("No subcategories found for the selected location.")


def generate_heatmaps():
    # Initialize session state for storing the heatmap
    if 'heatmap_generated' not in st.session_state:
        st.session_state.heatmap_generated = False
    if 'city_map_html' not in st.session_state:
        st.session_state.city_map_html = None
    if 'running' not in st.session_state:
        st.session_state.running = False

    st.title("🔥 Generate Heat Map")
    st.write("Generate heat maps for all categories and subcategories in a region(district).")

    with st.container(border=True):

        with st.container(border=True):
            st.caption(
                "(if you want to use these generated heat maps as a base for business suggestion, you should "
                "leave the percentile to 100%)")
            custom_parameters = st.toggle("Custom Parameters")

        col1, col2 = st.columns([1, 1])

        with col1:
            buffer_distance = st.number_input("Buffer distance(m):)", 0, 10000, 500,
                                              disabled=(not custom_parameters)) / 100000
            selected_district = select_district()

        with col2:
            percentile = st.slider("Percentile:", 0, 100, 100, disabled=(not custom_parameters))

    categories, slugs = fetch_categories()
    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        if st.button("Generate", type='primary'):
            session = db_handler()
            for category, sub_categories in categories.items():
                for sub_category in sub_categories:
                    highest_density_points = generate_heatmap(buffer_distance, percentile, category,
                                                              sub_category, selected_district, session)
            st.toast("All possible Heat maps generated successfully.", icon='✅')
            session.close()
    with col2:
        if st.button("Clear"):
            st.session_state.heatmap_generated = False
            st.session_state.city_map_html = None
            st.session_state.highest_density_points = None
            st.rerun()

    print("_______________________________________________________________________________________")



# Run the Streamlit app
if __name__ == "__main__":
    display_suggestions()
