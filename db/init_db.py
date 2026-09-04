from db.connection import engine
from db.models import Base


def init_db():
    Base.metadata.create_all(engine)
