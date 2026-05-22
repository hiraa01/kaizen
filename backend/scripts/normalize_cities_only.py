"""
Normalize university city names in the database.

Usage:
    python scripts/normalize_cities_only.py
"""

import os
import sys

sys.path.append('/app' if os.path.exists('/app') else os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if not os.path.exists('/app'):
    os.environ.setdefault("POSTGRES_HOST", "127.0.0.1")
    os.environ.setdefault("POSTGRES_PORT", "5435")

from database import SessionLocal
from scripts.import_osym_excel import normalize_city_name
from models import University


def main() -> None:
    db = SessionLocal()
    updated_count = 0

    try:
        universities = db.query(University).all()
        for university in universities:
            current_city = university.city or 'Bilinmiyor'
            normalized_city = normalize_city_name(current_city)

            if current_city != normalized_city:
                university.city = normalized_city
                updated_count += 1

        db.commit()
        print(f"City normalization completed. Updated rows: {updated_count}")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
