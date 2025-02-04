import time
import requests
import streamlit as st
from geoalchemy2.shape import to_shape
from sqlalchemy import Column, Integer, String, Numeric
from geoalchemy2 import Geometry
from sqlalchemy.orm import relationship
from shapely.geometry import Polygon, Point, box, MultiPolygon
import folium
from streamlit_folium import st_folium
import logging

from dbhandler import Base, engine, db_handler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

url = 'https://raw.githubusercontent.com/rferdosi/tehran-districts/main/districts.json'

colors = [
    "red", "blue", "green", "yellow", "cyan", "purple", "pink", "DodgerBlue",
    "brown", "black", "maroon", "magenta", "lime", "teal", "navy", "olive",
    "fuchsia", "orange", "tomato",
]


class PolygonEntity(Base):
    __abstract__ = True  # Makes this a base class without its own table

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    geom = Column(Geometry("POLYGON", srid=4326), nullable=False, unique=True)

    def add_to_db(self, session):
        """Common method for both classes"""
        try:
            session.add(self)
            session.commit()
            logger.info(f"{self.__class__.__name__} '{self.name}' added successfully!")
        except Exception as e:
            session.rollback()
            # logger.error(f"Error adding {self.__class__.__name__}: {e}", exc_info=True)

    def add_to_map(self, map, color='green', fill_opacity=0.3):
        geom = to_shape(self.geom)
        folium.Polygon(
            locations=[(lat, lon) for lat, lon in geom.exterior.coords],
            color=color,
            fill=True,
            fill_opacity=fill_opacity,
            tooltip=f"{self.__class__.__name__}: {self.name}"
        ).add_to(map)

    @classmethod
    def delete_all(cls, session):
        """
        Deletes all districts from the database.
        """
        try:
            # Delete all rows in the district table
            session.query(cls).delete()
            session.commit()
            logger.info("All districts deleted successfully!")
        except Exception as e:
            session.rollback()
            logger.error(f"Error deleting districts: {e}", exc_info=True)


class District(PolygonEntity):
    __tablename__ = "district"

    heatmap = relationship("Heatmap")


class BannedDistrict(PolygonEntity):
    __tablename__ = "banned_district"

    reason = Column(String, nullable=True)


# Create tables if they don't exist
Base.metadata.create_all(engine)


@st.cache_data(ttl=600)
def fetch_geojson(url):
    response = requests.get(url)
    response.raise_for_status()
    return response.json()


@st.cache_data(ttl=600)
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


def select_district():
    session = db_handler()
    districts = session.query(District).all()

    selected_district = st.selectbox("Choose a district:", [district.name for district in districts])
    # st.write(f"Selected district: {selected_district}")
    selected_district = [d for d in districts
                         if d.name == selected_district][0]
    return selected_district


def extract_tehran_districts():
    st.title("🗺️ Extract Tehran Districts")
    st.write("Extract Tehran districts from a geojson file on github.")
    st.divider()
    state = False

    map_center = (35.71, 51.36)
    m = folium.Map(location=map_center, zoom_start=11)
    session = db_handler()
    districts = session.query(District).all()
    for i, district in enumerate(districts):
        if i > 18:
            i -= 18

        p = to_shape(district.geom)
        p = Polygon(p)
        folium.Polygon(
            locations=[(lon, lat) for lon, lat in p.exterior.coords],
            color=colors[i],
            weight=1,
            fill=True,
            fill_opacity=0.3,
            popup="<b>" + district.name + "</b>",
            tooltip="<b>" + district.name + "</b>",
            bubbling_mouse_events=True
        ).add_to(m)

    if st.button('Extract'):

        # District.delete_all_districts(session)
        st.toast("We are extracting right now!", icon='🚨')
        districts = extract_districts(fetch_geojson(url))
        st.toast(''':green[Successfully extracted districts.]''', icon='✅')
        # st.table(districts)
        for i, district in enumerate(districts):
            p = Polygon(districts[district])
            d = District(
                name=district,
                geom=f"SRID=4326;{p}"
            )
            d.add_to_db(session)
    st_folium(m, width=700, height=500)
    r = {}
    if not isinstance(districts, dict):
        table = {}
        for district in districts:
            name = district.name
            table[name] = Polygon(to_shape(district.geom)).exterior.coords
        districts = table
    st.table(districts)
    session.close()


def adding_polygon_base():
    # Create a Folium map centered on Tehran with drawing tools
    map_center = (35.71, 51.36)
    m = folium.Map(location=map_center, zoom_start=11)
    session = db_handler()
    districts = session.query(District).all()
    for district in districts:
        district.add_to_map(m, fill_opacity=0.1)
    banned_districts = session.query(BannedDistrict).all()
    for banned_district in banned_districts:
        banned_district.add_to_map(m, 'red', 0.15)
    draw = folium.plugins.Draw(
        draw_options={
            'polygon': True,
            'marker': False,
            'circlemarker': False,
            'circle': False,
            'polyline': False,
            'rectangle': False
        },
        edit_options={'edit': False}
    )
    draw.add_to(m)
    # Display the map and capture drawn features
    output = st_folium(m, width=700, height=500, key='add_district_map')
    return output


def add_district():
    st.title("➕ Add Districts")
    st.write("Add a new district by drawing a polygon on the map.")
    st.divider()

    # Get district name from user input
    session = db_handler()

    output = adding_polygon_base()

    # Process the drawn polygon
    if output.get('last_active_drawing'):
        drawn_data = output['last_active_drawing']
        if drawn_data['geometry']['type'] == 'Polygon':
            # Extract coordinates from the drawn polygon (lat, lng order)
            coordinates = drawn_data['geometry']['coordinates'][0]
            coordinates = [(lat, lon) for lon, lat in coordinates]

            with st.container(border=True):
                district_name = st.text_input("Enter district name:")
                col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
                with col1:
                    if st.button("Add District", type='primary'):
                        if not district_name:
                            st.error("Please enter a district name.")
                            return

                        try:
                            # Create and save the new district
                            # Create a Shapely Polygon
                            polygon = Polygon(coordinates)
                            new_district = District(
                                name=district_name,
                                geom=f"SRID=4326;{polygon.wkt}"
                            )
                            new_district.add_to_db(session)
                            st.success(f"District '{district_name}' added successfully!")
                        except Exception as e:
                            st.error(f"Error adding district: {e}")
                            session.rollback()
                        finally:
                            session.close()
                # with col2:
                #     if st.button("Clear"):
                #         st.rerun()
        else:
            st.warning("Please draw a polygon. Other shapes are not supported.")
    else:
        st.info("Draw a polygon on the map to add a new district.")
    session.close()


def add_banned_district():
    st.title("✖️ Add Banned Zones")
    st.write("Create exclusion zones that can span multiple districts")
    st.divider()

    session = db_handler()

    output = adding_polygon_base()

    # Process drawing
    if output.get('last_active_drawing'):
        drawn_data = output['last_active_drawing']
        if drawn_data['geometry']['type'] == 'Polygon':
            coordinates = drawn_data['geometry']['coordinates'][0]
            coordinates = [(lat, lon) for lon, lat in coordinates]

            with st.container(border=True):
                # Get banned zone details
                name = st.text_input("Banned District name:")
                reason = st.selectbox("Reason:",
                                      ['military', 'jungle', 'park', 'airport', 'government', 'highway', 'lake',
                                       'other'])
                col1, col2, col3 = st.columns([0.5, 0.25, 0.25])
                with col1:
                    if st.button("Save Banned Zone"):

                        try:
                            polygon = Polygon(coordinates)
                            banned_zone = BannedDistrict(
                                name=name,
                                reason=reason,
                                geom=f"SRID=4326;{polygon.wkt}")
                            banned_zone.add_to_db(session)
                            st.success("Banned zone created!")
                        except Exception as e:
                            st.error(f"Error adding banned district: {e}")
                            session.rollback()
                        finally:
                            session.close()
                # with col2:
                #     if st.button("Clear"):
                #         st.rerun()
        else:
            st.warning("Please draw a polygon. Other shapes are not supported.")

    else:
        st.info("Draw a polygon on the map to add a new banned district.")

    session.close()
