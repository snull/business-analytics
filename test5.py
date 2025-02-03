import folium
import pandas as pd
import numpy as np
import geopandas as gpd
from folium.plugins import HeatMap
from shapely import Polygon
from shapely.geometry import Point, mapping
from scipy.stats import gaussian_kde
import matplotlib.pyplot as plt

from dbhandler import db_handler
from districts import District
from locations import Location
from sqlalchemy import func
from geoalchemy2.shape import to_shape

# Load cafe data from CSV


city_map = folium.Map(location=[35, 51], zoom_start=10)
session = db_handler()


# Define the district polygon
def create_district_polygon():
    # Example polygon coordinates (replace with your district's boundary)
    district = session.query(District).filter(District.name == "منطقه 3").first()

    pp = to_shape(district.geom)
    pp = Polygon(pp)
    pm = mapping(pp)
    print(pp)
    print(pm["coordinates"][0])
    # pp = Polygon(pp).exterior
    polygon_coords = [
        (77.5930, 12.9700),  # Bottom-left
        (77.5960, 12.9700),  # Bottom-right
        (77.5960, 12.9730),  # Top-right
        (77.5930, 12.9730),  # Top-left
        (77.5930, 12.9700)   # Close the polygon
    ]
    # print(pp)
    return pm["coordinates"][0], pp


def load_cafes(csv_file):
    district = session.query(District).filter(District.name == "منطقه 3").first()
    restaurants = (
        session.query(func.ST_X(Location.geom).label("latitude"), func.ST_Y(Location.geom).label("longitude"))
        .filter(Location.category == "خوراکی")
        .filter(func.ST_DWithin(Location.geom, district.geom, 0.01))
        .all()
    )
    print(restaurants)

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

    # df = pd.read_csv(csv_file)
    # geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    # geometry = [Point(xy) for xy in zip(restaurants['longitude'], restaurants['latitude'])]

    data = {
        'name': ['Cafe A', 'Cafe B', 'Cafe C', 'Cafe D', 'Cafe E', 'Cafe F', 'Cafe G', 'Cafe H'],
        'latitude': [12.9716, 12.9718, 12.9720, 12.9710, 12.9705, 12.9730, 12.9700, 12.9725],
        'longitude': [77.5946, 77.5950, 77.5955, 77.5940, 77.5935, 77.5960, 77.5930, 77.5958]
    }
    df = pd.DataFrame(restaurants)
    geometry = [Point(xy) for xy in zip(df['longitude'], df['latitude'])]
    return gpd.GeoDataFrame(df, geometry=geometry)


# Calculate kernel density estimation (KDE)
def calculate_kde(cafes, district_bounds, grid_size=100):
    district_polygon, pp = create_district_polygon()

    # Get the bounds of the polygon
    ymin, xmin, ymax, xmax = pp.bounds

    # Create a grid over the polygon bounds
    grid_x, grid_y = np.mgrid[xmin:xmax:grid_size * 1j, ymin:ymax:grid_size * 1j]
    grid_points = np.vstack([grid_x.ravel(), grid_y.ravel()]).T

    # Filter grid points to include only those inside the polygon
    grid_points_inside = [Point(xy) for xy in grid_points if pp.contains(Point(xy))]
    grid_coords_inside = np.array([[point.x, point.y] for point in grid_points_inside]).T  # Shape (2, N)

    # Extract cafe coordinates
    cafe_coords = np.vstack([cafes.geometry.x, cafes.geometry.y])  # Shape (2, M)

    # Compute KDE for points inside the polygon
    kde = gaussian_kde(cafe_coords)  # Pass cafe_coords with shape (2, M)
    density_inside = kde(grid_coords_inside)  # Pass grid_coords_inside with shape (2, N)

    # Create a mask for points inside the polygon
    density = np.full(grid_x.shape, np.nan)  # Initialize with NaN (outside the polygon)
    for i, point in enumerate(grid_points):
        if district_polygon.contains(Point(point)):
            row = int((point[0] - xmin) / (xmax - xmin) * (grid_size - 1))
            col = int((point[1] - ymin) / (ymax - ymin) * (grid_size - 1))
            density[row, col] = density_inside[i]

    return grid_x, grid_y, density


# Find the best spot (lowest density area)
def find_best_spot(grid_x, grid_y, density):
    min_density = np.min(density)
    min_indices = np.where(density == min_density)
    best_spots = list(zip(grid_y[min_indices], grid_x[min_indices]))
    for point in best_spots:
        folium.CircleMarker(
            location=point,
            radius=4,
            color='blue',
            fill=True,
            fill_color='blue'
        ).add_to(city_map)
    return best_spots


# Visualize the results
def visualize(cafes, grid_x, grid_y, density, best_spot):
    plt.figure(figsize=(10, 10))
    plt.imshow(np.rot90(density), cmap='YlOrRd', extent=[grid_x.min(), grid_x.max(), grid_y.min(), grid_y.max()])
    plt.colorbar(label='Cafe Density')
    plt.scatter(cafes.geometry.x, cafes.geometry.y, c='blue', s=10, label='Existing Cafes')
    plt.scatter(best_spot[0][0], best_spot[0][1], c='green', s=200, marker='*', label='Best Spot')
    plt.title('Cafe Density and Best Spot')
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.legend()
    plt.show()


# Main function
def main():
    # Load cafe data
    cafes = load_cafes('cafes.csv')

    # Define district bounds (min longitude, min latitude, max longitude, max latitude)
    district_bounds = (cafes.total_bounds[0], cafes.total_bounds[1], cafes.total_bounds[2], cafes.total_bounds[3])
    print("\n District Bounds: ", district_bounds, "\n")
    # Calculate KDE
    grid_x, grid_y, density = calculate_kde(cafes, district_bounds, grid_size=100)

    # Find the best spot
    best_spot = find_best_spot(grid_x, grid_y, density)
    print("Best spot(s) for your new cafe:")
    # print(best_spot)

    # Visualize the results
    #visualize(cafes, grid_x, grid_y, density, best_spot)
    HeatMap(best_spot[:10], radius=10).add_to(city_map)
    city_map.save('5low_density_restaurants_filtered.html')


if __name__ == "__main__":
    main()
    session.close()

