from app.database.models import Base
from app.database.connection import engine
from app.database.schema_migrations import ensure_image_url_columns

if __name__ == "__main__":
    Base.metadata.create_all(engine)
    ensure_image_url_columns()
    print("Tables created successfully")

