from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import logging
from sqlalchemy import inspect



logging.basicConfig(level=logging.INFO)


SQLALCHEMY_DATABASE_URL = 'sqlite:///./players.db'

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

Base = declarative_base()


logging.info(f"Connecting to database at: {SQLALCHEMY_DATABASE_URL}")
Base.metadata.create_all(bind=engine)


inspector = inspect(engine)
tables = inspector.get_table_names()
logging.info("Database tables created.")
logging.info(f"database tables from inspector: {tables}")