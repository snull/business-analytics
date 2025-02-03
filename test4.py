from geoalchemy2 import WKTElement
from geoalchemy2.shape import to_shape
from shapely import Polygon, Point
from sqlalchemy import func
from locations import Location  # Import your Location class
import numpy as np
from sklearn.neighbors import KernelDensity
from scipy.spatial.distance import cdist  # For filtering based on buffer distance
import folium
from folium.plugins import HeatMap
from dbhandler import db_handler
from districts import District
from geopy.distance import geodesic
from heatmaps import HeatMap

# Database connection
session = db_handler()
district = session.query(District).filter(District.name == "منطقه 1").first()
# print(district.geom)
# print(type(district.geom))
# test = [
#     [
#         51.3394203,
#         35.7829949
#     ],
#     [
#         51.3766022,
#         35.790016
#     ],
#     [
#         51.3810396,
#         35.7776258
#     ],
#     [
#         51.3456345,
#         35.7708674
#     ],
#     [
#         51.3393517,
#         35.7829904
#     ]
# ]
# swapped_coords = [(lat, lon) for lon, lat in test]
# test = swapped_coords
#
# p = Polygon(test)
# print(p)
# new_d = District(name="test", geom=f"SRID=4326;{p}")
# print("DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD")
# print(new_d.geom)
# new_d.add_to_db(session)
# print("DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD")
# print(new_d.geom)
# print(type(new_d.geom))
# z = f"POLYGON{test}"
# print(z)
# q = WKTElement(z)
# print(q)
# print(type(q))
# Query restaurants and extract coordinates using ST_X and ST_Y
# restaurants = (
#     session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"))
#     .filter(Location.category == "خوراکی")
#     .filter(func.ST_Contains(district.geom, Location.geom))
#     .all()
# )
restaurants = (
    session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"))
    .filter(Location.category == "سلامت")
    .filter(func.ST_DWithin(Location.geom, district.geom, 0.03))
    .all()
)

# Convert the result to a NumPy array
coords = np.array([(point.latitude, point.longitude) for point in restaurants])

if len(coords) == 0:
    print("No coordinates found for the selected category and district.")
    exit()

# Fit KDE model
kde = KernelDensity(kernel="epanechnikov", bandwidth="silverman", metric='haversine')  # Bandwidth controls smoothness
kde.fit(np.radians(coords))  # Convert to radians for haversine metric
# Get the bounding box of all locations
min_lat, max_lat = min(coords[:, 0]), max(coords[:, 0])
min_lon, max_lon = min(coords[:, 1]), max(coords[:, 1])
print("\n\nXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZ\n\n")
print(min_lat, max_lat, min_lon, max_lon)

min_lat, min_lon, max_lat, max_lon = Polygon(to_shape(district.geom)).bounds
print(min_lon, min_lat, max_lon, max_lat)
print(min_lat, max_lat, min_lon, max_lon)
print("\n\nXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZXYZ\n\n")
# Define grid size
grid_size = 0.001  # Adjust based on your city size

# Create a grid of latitude and longitude points
lat_points = np.arange(min_lat, max_lat, grid_size)
lon_points = np.arange(min_lon, max_lon, grid_size)
lat_grid, lon_grid = np.meshgrid(lat_points, lon_points)
grid_coords = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])
print("======================================")
print(grid_coords)
print(len(grid_coords))
print("======================================")

polygon_shape = to_shape(district.geom)
mask = [polygon_shape.contains(Point(lat, lon)) for lat, lon in grid_coords]
grid_coords = grid_coords[mask]
print("======================================")
print(grid_coords)
print(len(grid_coords))
print("======================================")
# Evaluate density at each grid point
density = np.exp(kde.score_samples(np.radians(grid_coords)))
print(len(density))
print(len(np.radians(grid_coords)))
print("SCORE:\n", )
#density = density.reshape(lat_grid.shape)

# Normalize density for better scaling
density = (density - density.min()) / (density.max() - density.min())
print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n")
print(density)
print("Shape:", density.shape)
print("Dimensions:", density.ndim)
print("Size:", density.size)
print("Data type:", density.dtype)
print("Item size:", density.itemsize)
print(type(density))

print("^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\n\n")

# Filter low-density areas
low_density_threshold = np.percentile(density[density >= 0], 50)  # Adjust threshold as needed
low_density_mask = density < low_density_threshold
print("\n\nNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN\n")
print(low_density_mask)
print(len(low_density_mask))
print("\nNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNNN\n\n")
low_density_locations = grid_coords[low_density_mask.ravel()]

print("\n\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n")
print(low_density_locations)
print(len(low_density_locations))
print("\nMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMMM\n\n")

# Filter suggested locations with a buffer zone around existing businesses

buffer_distance = 0.005  # Approx ~500 meters, adjust as needed
filtered_locations = [
    coord for coord in low_density_locations
    if np.min(cdist([coord], coords, metric='euclidean')) >= buffer_distance
]


# buffer_distance = 500  # Buffer in meters
# filtered_locations = [
#     coord for coord in low_density_locations
#     if all(geodesic(coord, existing_coord).meters >= buffer_distance for existing_coord in coords)
# ]

# print(filtered_locations)



# Prepare heatmap data with density as weights
filtered_density = density[low_density_mask.ravel()]  # Corresponding density for low-density locations
filtered_density = filtered_density[[np.min(cdist([coord], coords, metric='euclidean')) >= buffer_distance
                                     for coord in low_density_locations]]  # Match density with filtered locations

# Normalize weights
weights = ((filtered_density - filtered_density.min()) / (filtered_density.max() - filtered_density.min()))
# print(weights)
weights = 1 - weights

# Create weighted heatmap data in [latitude, longitude, weight] format
heatmap_data = [
    [coord[0], coord[1], weight]
    for coord, weight in zip(filtered_locations, weights)
]

print("/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\/\\")
print(heatmap_data)



# Visualize low-density areas on a map
z = Polygon(to_shape(district.geom)).centroid
print(z.coords)

city_map = folium.Map(location= [z.x, z.y], zoom_start=12)

# Add heat map for filtered locations
HeatMap(heatmap_data, radius=20).add_to(city_map)
for point in restaurants:
    folium.CircleMarker(
        location=[point.latitude, point.longitude],
        radius=3,
        color='red',
        fill=True,
        fill_color='blue'
    ).add_to(city_map)

pp = to_shape(district.geom)
pp = Polygon(pp)
folium.Polygon(
    locations=[(lon, lat) for lon, lat in pp.exterior.coords],
    color="grey",
    weight=1,
    fill=True,
    fill_opacity=0.3,
    popup="<b>" + district.name + "</b>",
    tooltip="<b>" + district.name + "</b>",
    bubbling_mouse_events=True
).add_to(city_map)
# Save the map
city_map.save('low_density_restaurants_filtered.html')
print("Map saved as 'low_density_restaurants_filtered.html'")
