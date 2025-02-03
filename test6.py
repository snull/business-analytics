import geopandas as gpd
import matplotlib.pyplot as plt
from shapely.geometry import Point, Polygon
from sklearn.cluster import KMeans
import numpy as np
from districts import District
from sqlalchemy import func
from geoalchemy2.shape import to_shape
from dbhandler import db_handler
from locations import Location

session = db_handler()
# Load existing cafe locations (replace with actual data)
# Example: list of (longitude, latitude)
cafe_locations = [
    (12.4924, 41.8902),  # Example coordinates (longitude, latitude)
    (12.4950, 41.8915),
    (12.4962, 41.8928),
    (12.5000, 41.8950),
]

district = session.query(District).filter(District.name == "منطقه 3").first()

restaurants = (
    session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"))
    .filter(Location.category == "خوراکی")
    .filter(func.ST_DWithin(Location.geom, district.geom, 0.01))
    .all()
)

cafe_locations = restaurants
# Convert to GeoDataFrame
gdf = gpd.GeoDataFrame(geometry=[Point(x, y) for x, y in cafe_locations])

# Define study area (bounding box of the district)
district_boundary = Polygon([
    (12.4900, 41.8880),
    (12.5100, 41.8880),
    (12.5100, 41.8980),
    (12.4900, 41.8980),
])
pp = to_shape(district.geom)
pp = Polygon(pp)
district_boundary = pp




# Generate random candidate points within the district boundary
num_potential_spots = 200
lng_min, lat_min, lng_max, lat_max = district_boundary.bounds

# Generate points and check if they fall within the polygon
potential_spots = []
while len(potential_spots) < num_potential_spots:
    random_point = Point(
        np.random.uniform(lng_min, lng_max),
        np.random.uniform(lat_min, lat_max),
    )
    if district_boundary.contains(random_point):
        potential_spots.append(random_point)

# Perform K-Means clustering on existing cafes
X = np.array(cafe_locations)
num_clusters = 50
kmeans = KMeans(n_clusters=num_clusters, random_state=0).fit(X)
cluster_centers = kmeans.cluster_centers_
cluster_labels = kmeans.labels_
cluster_centers = np.array([(lon, lat) for lat, lon in cluster_centers])

# Find the farthest candidate point from cluster centers
best_spot = max(potential_spots, key=lambda loc: min(np.linalg.norm(np.array([loc.y, loc.x]) - center) for center in cluster_centers))

# Visualization
fig, ax = plt.subplots(figsize=(8, 8))
colors = [
    "red", "blue", "green", "yellow", "cyan", "purple", "pink", "DodgerBlue",
    "brown", "black", "maroon", "magenta", "lime", "teal", "navy", "olive",
    "fuchsia", "orange", "tomato", "red", "blue", "green", "yellow", "cyan", "purple", "pink", "DodgerBlue",
    "brown", "black", "maroon", "magenta", "lime", "teal", "navy", "olive",
    "fuchsia", "orange", "tomato", "red", "blue", "green", "yellow", "cyan", "purple", "pink", "DodgerBlue",
    "brown", "black", "maroon", "magenta", "lime", "teal", "navy", "olive",
    "fuchsia", "orange", "tomato", "red", "blue", "green", "yellow", "cyan", "purple", "pink", "DodgerBlue",
    "brown", "black", "maroon", "magenta", "lime", "teal", "navy", "olive",
    "fuchsia", "orange", "tomato",
]
for i in range(num_clusters):
    cluster_points = np.array(X)[cluster_labels == i]
    plt.scatter(cluster_points[:, 1], cluster_points[:, 0], c=colors[i], label=f'Cluster {i + 1}', s=50)

# Plot cluster centers
plt.scatter(cluster_centers[:, 1], cluster_centers[:, 0], c='yellow', marker='X', s=200, label='Cluster Centers')

# Plot the best spot
gpd.GeoSeries([best_spot]).plot(ax=ax, color='green', markersize=100, label="Best Spot")

# Plot district boundary
gpd.GeoSeries([district_boundary]).plot(ax=ax, edgecolor='black', facecolor='none')

# Plot potential spots
gpd.GeoSeries(potential_spots).plot(ax=ax, color='gray', markersize=10, alpha=0.5, label="Potential Spots")

plt.legend()
plt.title("Cafe Locations and Clusters")
plt.xlabel("Longitude")
plt.ylabel("Latitude")
plt.show()

print(f"Suggested best spot: {best_spot.y}, {best_spot.x}")