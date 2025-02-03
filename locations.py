from sqlalchemy import Column, Integer, String, Numeric
from geoalchemy2 import Geometry
import logging
from dbhandler import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class Location(Base):
    __tablename__ = "location"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=True)
    rate = Column(Numeric, nullable=True)
    geom = Column(Geometry("POINT", srid=4326), nullable=False)
    token = Column(String, nullable=True, unique=True)
    category = Column(String, nullable=True)
    subcategory = Column(String, nullable=True)

    # def add_to_db(self):
    #     """Adds the current Location object to the database."""
    #     session = Session()
    #     try:
    #         session.add(self)
    #         session.commit()
    #         print(f"Location '{self.name}' added successfully!")
    #     except Exception as e:
    #         session.rollback()
    #         print(f"Error adding location: {e}")
    #     finally:
    #         session.close()

    def add_to_db(self, session):
        """Adds the current Location object to the database."""
        try:
            session.add(self)
            session.commit()
            print(f"Location '{self.name}' added successfully!")
            logger.info(f"Location '{self.name}' added successfully!")
        except Exception as e:
            session.rollback()
            print(f"Error adding Location: {e}")
            logger.error(f"Error adding Location: {e}", exc_info=True)


# Create tables if they don't exist
Base.metadata.create_all(engine)

# Usage example
if __name__ == "__main__":
    pass
