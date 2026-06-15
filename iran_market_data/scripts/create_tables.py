from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from iran_market_data.app.storage.database import engine
from iran_market_data.app.storage.models import Base


def main() -> None:
    """Create all database tables defined in models.py."""
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")


if __name__ == "__main__":
    main()
