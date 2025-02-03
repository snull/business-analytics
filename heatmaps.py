import logging
import time

import branca
from sklearn.model_selection import GridSearchCV

from districts import District, select_district, BannedDistrict
from dbhandler import Base, engine
from dbhandler import db_handler
import folium
import numpy as np
import streamlit as st
from folium.plugins import HeatMap
from geoalchemy2 import Geometry
from geoalchemy2.shape import to_shape
from scipy.spatial.distance import cdist  # For filtering based on buffer distance
from shapely import Point, Polygon, MultiPoint
from sklearn.neighbors import KernelDensity
from sqlalchemy import Column, Integer, String, ForeignKey, func, ARRAY, Float
from sqlalchemy.orm import relationship
from categories import fetch_categories, select_category
from locations import Location
from sklearn.cluster import DBSCAN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Heatmap(Base):
    __tablename__ = 'heatmap'

    id = Column(Integer, primary_key=True)
    geom = Column(Geometry('MULTIPOINT', srid=4326), nullable=False)  # Store all points as MULTIPOINT
    weights = Column(ARRAY(Float), nullable=False)  # Store weights as an array of floats (density values)
    district_id = Column(Integer, ForeignKey('district.id'))  # Foreign key to District table
    district = relationship(District.__name__, back_populates='heatmap')  # Relationship to District
    category = Column(String(255), nullable=True)  # Category field
    subcategory = Column(String(255), nullable=False)  # Subcategory field
    buffer_distance = Column(Float, nullable=True)
    percentile = Column(Float, nullable=True)

    def add_to_db(self, session):
        """Adds the current heat map object to the database."""
        try:
            session.add(self)
            session.commit()
            print(f"HeatMap '{self.id}' added successfully!")
            logger.info(f"HeatMap '{self.id}' added successfully!")
        except Exception as e:
            print(f"Error adding HeatMap: {e}")
            logger.error(f"Error adding HeatMap: {e}", exc_info=True)
            session.rollback()


# Create tables if they don't exist
Base.metadata.create_all(engine)





