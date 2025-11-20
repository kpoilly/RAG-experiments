from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

from core.config import settings as env

engine = create_engine(env.DB_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def create_db_and_tables():
    """
    Crée toutes les tables dans la base de données.
    Cette fonction doit être appelée au démarrage de l'application.
    """
    Base.metadata.create_all(bind=engine)
