from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Define the database connection
DATABASE_URL = "postgresql://postgres:1234@localhost:5432/business_analytics"
engine = create_engine(DATABASE_URL)

# Define the Base class
Base = declarative_base()


def db_handler():
    # Define the Session
    Session = sessionmaker(bind=engine)
    session = Session()
    return session
