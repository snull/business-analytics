from heatmaps import Heatmap
from districts import District, select_district, BannedDistrict
from dbhandler import db_handler
import folium
import numpy as np
import streamlit as st
from folium.plugins import HeatMap
from geoalchemy2.shape import to_shape
from scipy.spatial.distance import cdist  # For filtering based on buffer distance
from shapely import Point, Polygon, MultiPoint
from sklearn.neighbors import KernelDensity
from sqlalchemy import func
from categories import select_category
from locations import Location
from sklearn.cluster import DBSCAN


def district_hash_func(district):
    return district.id


@st.cache_data(ttl=600, hash_funcs={District: district_hash_func})
def fetch_data(_session, district, subcategory):
    district_polygon = Polygon(to_shape(district.geom))
    district_centroid = district_polygon.centroid
    restaurants = (
        _session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"),
                       Location.name)
        .filter(Location.subcategory == subcategory)
        .filter(func.ST_DWithin(Location.geom, district.geom, 0.01))
        .all()
    )

    city_map = folium.Map(location=[district_centroid.x, district_centroid.y], zoom_start=12)

    district_group = folium.FeatureGroup(name="District").add_to(city_map)
    pp = to_shape(district.geom)
    pp = Polygon(pp)
    folium.Polygon(
        locations=[(lon, lat) for lon, lat in pp.exterior.coords],
        color="grey",
        weight=1,
        fill=True,
        fill_opacity=0.3,
        popup="<b>" + district.name + "</b>",
        # tooltip="<b>" + _district.name + "</b>"
    ).add_to(district_group)

    locations_group = folium.FeatureGroup(name="Locations").add_to(city_map)
    for point in restaurants:
        folium.CircleMarker(
            location=[point.latitude, point.longitude],
            radius=3,
            color='black',
            fill=True,
            fill_color='blue',
            popup="<b>" + point.name + "</b>"
        ).add_to(locations_group)
    # folium.LayerControl().add_to(city_map)

    # Convert the result to a NumPy array
    coords = np.array([(point.latitude, point.longitude) for point in restaurants])

    if len(coords) == 0:
        st.warning("No coordinates found for the selected category and district.")
        return None, city_map, None

    # Get banned zones that intersect with the district
    banned_districts = _session.query(BannedDistrict).filter(
        func.ST_Intersects(BannedDistrict.geom, district.geom)
    ).all()

    banned_districts_group = folium.FeatureGroup(name="Banned Districts").add_to(city_map)
    for banned_district in banned_districts:
        banned_district.add_to_map(banned_districts_group, 'red')
    # Create composite mask
    banned_polys = [to_shape(bz.geom) for bz in banned_districts]

    return coords, city_map, banned_polys


def banned_polys_hash_func(banned_polys):
    return str(banned_polys)


@st.cache_data(ttl=6000, hash_funcs={District: district_hash_func, list: banned_polys_hash_func})
def kde_module(coords, district, banned_polys):
    # Fit KDE model

    kde = KernelDensity(kernel="gaussian", bandwidth='silverman',
                        metric='haversine')  # Bandwidth controls smoothness
    kde.fit(np.radians(coords))  # Convert to radians for haversine metric

    # GridSearchCV for Hyper-parameter tuning. maybe later someday...
    # bandwidths = np.logspace(-3, 0, 30)
    # grid = GridSearchCV(KernelDensity(kernel='gaussian'), {'bandwidth': bandwidths}, cv=5)
    # grid.fit(np.radians(coords))
    # kde = grid.best_estimator_

    # Get the bounding box of all locations
    # min_lat, max_lat = min(coords[:, 0]), max(coords[:, 0])
    # min_lon, max_lon = min(coords[:, 1]), max(coords[:, 1])
    min_lat, min_lon, max_lat, max_lon = Polygon(to_shape(district.geom)).bounds

    # Define grid size
    grid_size = 0.001  # Adjust based on your city size

    # Create a grid of latitude and longitude points
    lat_points = np.arange(min_lat, max_lat, grid_size)
    lon_points = np.arange(min_lon, max_lon, grid_size)
    lat_grid, lon_grid = np.meshgrid(lat_points, lon_points)
    grid_coords = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])

    polygon_shape = to_shape(district.geom)
    mask = [polygon_shape.contains(Point(lat, lon)) for lat, lon in grid_coords]
    grid_coords = grid_coords[mask]

    district_poly = to_shape(district.geom)

    mask = []
    for lat, lon in grid_coords:
        point = Point(lat, lon)
        in_district = district_poly.contains(point)
        in_banned = any(bp.contains(point) for bp in banned_polys)
        mask.append(in_district and not in_banned)

    # Apply mask
    valid_grid_coords = grid_coords[mask]

    # Handle empty grid case
    if len(valid_grid_coords) == 0:
        return None, None
    # Evaluate density at each grid point
    density = np.exp(kde.score_samples(np.radians(valid_grid_coords)))

    # density = density.reshape(lat_grid.shape)

    # Normalize density for better scaling
    density = (density - density.min()) / (density.max() - density.min())

    return density, valid_grid_coords


# @st.cache_data(ttl=600)
def heatmap_module(_session, density, grid_coords, coords, _district, _city_map, category, sub_category, percentile,
                   buffer_distance):
    # Filter low-density areas
    low_density_threshold = np.percentile(density[density >= 0], percentile)  # Adjust threshold as needed
    low_density_mask = density < low_density_threshold

    low_density_locations = grid_coords[low_density_mask.ravel()]

    # Filter suggested locations with a buffer zone around existing businesses
    # buffer_distance = 0.005  # Approx ~500 meters, adjust as needed
    filtered_locations = [
        coord for coord in low_density_locations
        if np.min(cdist([coord], coords, metric='euclidean')) >= buffer_distance
    ]

    # buffer_distance = 500  # Buffer in meters
    # filtered_locations = [
    #     coord for coord in low_density_locations
    #     if all(geodesic(coord, existing_coord).meters >= buffer_distance for existing_coord in coords)
    # ]

    # Prepare heatmap data with density as weights
    filtered_density = density[low_density_mask.ravel()]  # Corresponding density for low-density locations
    filtered_density = filtered_density[[np.min(cdist([coord], coords, metric='euclidean')) >= buffer_distance
                                         for coord in low_density_locations]]  # Match density with filtered locations

    if len(filtered_locations) == 0:
        st.error("No locations found for selected category and district with the given parameters.")
        st.toast(":red[No locations found for selected category and district with the given parameters.]", icon='🚨')
        return _city_map
    # Normalize weights
    weights = ((filtered_density - filtered_density.min()) / (filtered_density.max() - filtered_density.min()))
    # print(weights)
    weights = 1 - weights

    heatmap_data = []
    heatmap_group = folium.FeatureGroup(name='Heatmap').add_to(_city_map)
    for coord, weight in zip(filtered_locations, weights):
        folium.Circle(
            location=[coord[0], coord[1]],
            radius=100,
            color='white',
            weight=0,
            fill_opacity=0,
            fill=False,
            fill_color='red',
            popup="<b>" + str(round(weight * 100, 2)) + "</b>"
        ).add_to(heatmap_group)
        heatmap_data.append([coord[0], coord[1], weight])

    # heatmap_data = [
    #     [coord[0], coord[1], weight]
    #     for coord, weight in zip(filtered_locations, weights)
    # ]

    filtered_locations = [coord.tolist() for coord in filtered_locations]
    filtered_locations = MultiPoint(filtered_locations)
    weights = weights.tolist()
    # Add heat map for filtered locations
    HeatMap(heatmap_data, control=True).add_to(_city_map)

    heatmap = Heatmap(geom=f"SRID=4326;{filtered_locations}", weights=weights, district=_district, category=category,
                      subcategory=sub_category, buffer_distance=buffer_distance, percentile=percentile)
    heatmap.add_to_db(_session)

    multipoint = MultiPoint(filtered_locations)
    if isinstance(multipoint, MultiPoint):
        # Extract individual points from the MultiPoint
        points = np.array([[point.x, point.y] for point in multipoint.geoms])
    else:
        # Handle the case where it's a single Point
        points = np.array([[multipoint.x, multipoint.y]])
    # Cluster the points and mark the highest density points

    weights = heatmap.weights
    highest_density_points = cluster_points(points, weights)
    # Add markers for the highest density points
    highest_density_points_group = folium.FeatureGroup(name="Highest Density Points").add_to(_city_map)
    for point in highest_density_points:
        html = f"<b>Local Max: {(point[1] * 100):.2f}<br> [ {point[0][0]:.4f}, {point[0][1]:.4f} ]</b>"
        folium.Marker(
            location=[point[0][0], point[0][1]],
            icon=folium.Icon(color="red", icon="info-sign"),
            popup=folium.Popup(html, max_width=100),
        ).add_to(highest_density_points_group)

    # Save the map
    folium.LayerControl().add_to(_city_map)
    # _city_map.save('low_density_restaurants_filtered.html')
    # print("Map saved as 'low_density_restaurants_filtered.html'")
    return _city_map, highest_density_points



@st.cache_data(ttl=6000)
def cluster_points(points, weights, eps=0.00003, min_samples=1):
    """Cluster points using DBSCAN and return the highest density point in each cluster."""
    # Perform DBSCAN clustering
    db = DBSCAN(eps=eps, min_samples=min_samples, metric='haversine').fit(np.radians(points))
    labels = db.labels_

    # Debugging: Print the number of clusters and noise points
    unique_labels = set(labels)
    num_clusters = len(unique_labels) - (1 if -1 in unique_labels else 0)  # Exclude noise
    num_noise = list(labels).count(-1)
    st.write(f":green[Number of clusters: {num_clusters}]")

    # Group points and weights by cluster
    clusters = {}
    for i, label in enumerate(labels):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append((points[i], weights[i]))

    # Find the highest density point in each cluster
    highest_density_points = []
    for label, points_in_cluster in clusters.items():
        if label != -1:  # Ignore noise points (label = -1)
            # Find the point with the highest weight in the cluster
            highest_density_point = max(points_in_cluster, key=lambda x: x[1])
            print(highest_density_point)
            highest_density_points.append(highest_density_point)  # Append the point coordinates

    return highest_density_points


# @st.cache_data(ttl=6000, hash_funcs={District: district_hash_func})
def generate_heatmap(buffer_distance, percentile, selected_category, selected_sub_category, selected_district, _session):
    with st.status("Generating heat map...", expanded=True) as status:
        progress_text = "Operation in progress. Please wait."
        percent_complete = 0
        sp_bar = st.progress(percent_complete, text=progress_text)
        st.write("Fetching data...")
        coords, city_map, banned_polys = fetch_data(_session, selected_district, selected_sub_category)
        percent_complete = 30
        sp_bar.progress(percent_complete, text=progress_text)

        if coords is not None:
            st.write(f":green[{len(coords)} existing businesses found!]")
            st.write("Running kde module...")
            density, grid_coords = kde_module(coords, selected_district, banned_polys)
            if density is None or grid_coords is None:
                st.error("No valid locations after applying banned district filters")
                return None

            percent_complete = 65
            sp_bar.progress(percent_complete, text=progress_text)

            st.write("Running heatmap module...")
            city_map, highest_density_points = heatmap_module(_session, density, grid_coords, coords,
                                                              selected_district, city_map,
                                                              selected_category,
                                                              selected_sub_category, percentile,
                                                              buffer_distance)
            percent_complete = 80
            sp_bar.progress(percent_complete, text=progress_text)

            # Save the Folium map as an HTML string
            st.write("Saving heat map...")
            city_map_html = city_map._repr_html_()  # Convert Folium map to HTML
            percent_complete = 100
            sp_bar.progress(percent_complete, text=progress_text)
            st.session_state.city_map_html = city_map_html  # Store HTML in session state
            st.session_state.heatmap_generated = True  # Set flag to indicate heatmap is generated
            sp_bar.empty()
            status.update(
                label=":green[Done!]", state="complete", expanded=False
            )
            st.toast("Heat map generated successfully.", icon='✅')

        else:
            st.error(
                f":red[No data found for the selected subcategory ( {selected_sub_category} ) and district ( {selected_district.name} ).]")
            status.update(
                label=f":red[No data found for the selected subcategory ( {selected_sub_category} ) and district ( {selected_district.name} ).]",
                state="error",
                expanded=False
            )
            return None
    return highest_density_points


def location_suggestion():
    # Initialize session state for storing the heatmap
    if 'heatmap_generated' not in st.session_state:
        st.session_state.heatmap_generated = False
    if 'city_map_html' not in st.session_state:
        st.session_state.city_map_html = None
    if 'highest_density_points' not in st.session_state:
        st.session_state.highest_density_points = None

    st.title("📍 Location Suggestion")
    st.write("Suggest locations based on created heat map in the selected district and sub category.")

    with st.container(border=True):
        col1, col2 = st.columns([0.33, 0.66])
        with col1:
            selected_district = select_district()

        with col2:
            selected = select_category()
            selected_sub_category = selected['sub_category']
            selected_category = selected['category']
        with col1:
            buffer_distance = st.number_input("Buffer distance(m):)", 0, 10000, 500) / 100000
        with col2:
            percentile = st.slider("Percentile:", 0, 100, 50)

    col1, col2 = st.columns([0.4, 0.6])

    with col1:
        if st.button("Generate", type='primary'):
            session = db_handler()
            highest_density_points = generate_heatmap(buffer_distance, percentile, selected_category,
                                                      selected_sub_category, selected_district, session)
            st.session_state.highest_density_points = highest_density_points
            session.close()
    with col2:
        if st.button("Clear"):
            st.session_state.heatmap_generated = False
            st.session_state.city_map_html = None
            st.rerun()

    if st.session_state.heatmap_generated and st.session_state.city_map_html is not None:
        # city_map = heatmap_module(session, density, grid_coords, coords, selected_district, city_map,
        #                           selected_category,
        #                           selected_sub_category, percentile)
        # city_map_html = city_map._repr_html_()
        # st.session_state.city_map_html = city_map_html  # Store HTML in session state
        st.components.v1.html(st.session_state.city_map_html, width=700, height=500)
        st.header("Highest Density Points in Clusters:")
        if st.session_state.highest_density_points is not None:
            st.dataframe(st.session_state.highest_density_points, use_container_width=True,
                         column_config={0: "", 1: "Coordinates", 2: "Weight"})
    print("_______________________________________________________________________________________")
