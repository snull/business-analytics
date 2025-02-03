from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from locations import Location  # Import your Location class
import numpy as np
from sklearn.neighbors import KernelDensity
import folium
from folium.plugins import HeatMap
from dbhandler import db_handler
from districts import District

# Database connection

session = db_handler()
district = session.query(District).filter(District.name == "منطقه 1").first()

# Query restaurants and extract coordinates using ST_X and ST_Y
restaurants = (
    session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude")).filter(
        Location.category == "سلامت").filter(func.ST_Contains(district.geom, Location.geom))
    .all())

# Convert the result to a NumPy array
coords = np.array([(point.latitude, point.longitude) for point in restaurants])
print(coords)

# Fit KDE model
kde =  KernelDensity(bandwidth=0.01, metric='haversine', kernel='gaussian', algorithm='ball_tree')  # Bandwidth controls smoothness
kde.fit(np.radians(coords))  # Convert to radians for haversine metric

# Get the bounding box of all locations
min_lat, max_lat = min(coords[:, 0]), max(coords[:, 0])
min_lon, max_lon = min(coords[:, 1]), max(coords[:, 1])

# Define grid size
grid_size = 0.001 # Adjust based on your city size

# Create a grid of latitude and longitude points
lat_points = np.arange(min_lat, max_lat, grid_size)
lon_points = np.arange(min_lon, max_lon, grid_size)
lat_grid, lon_grid = np.meshgrid(lat_points, lon_points)
grid_coords = np.column_stack([lat_grid.ravel(), lon_grid.ravel()])

# Evaluate density at each grid point
density = np.exp(kde.score_samples(np.radians(grid_coords)))
density = density.reshape(lat_grid.shape)

# Normalize density values to [0, 1]
density_normalized = (density - np.min(density)) / (np.max(density) - np.min(density))

# Find areas with low density (low competition)
low_density_threshold = np.percentile(density_normalized[density_normalized > 0], 90)  # Adjust threshold
low_density_mask = density_normalized < low_density_threshold
low_density_locations = grid_coords[low_density_mask.ravel()]

# Visualize low-density areas on a map
city_map = folium.Map(location=[(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom_start=12)
HeatMap(low_density_locations, radius=10).add_to(city_map)
city_map.save('low_density_restaurants.html')

raw_data_map = folium.Map(location=[(min_lat + max_lat) / 2, (min_lon + max_lon) / 2], zoom_start=12)
for point in restaurants:
    folium.CircleMarker(
        location=[point.latitude, point.longitude],
        radius=3,
        color='blue',
        fill=True,
        fill_color='blue'
    ).add_to(raw_data_map)
raw_data_map.save('raw_data_points.html')
