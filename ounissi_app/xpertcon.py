import time
import pandas as pd
from sqlalchemy import create_engine, text
from .models import XpertServer

# --- THE FIX: GLOBAL ENGINE VARIABLE ---
# This variable stays alive in server memory across all users and requests
_GLOBAL_ENGINE = None


def get_engine():
    """
    Creates the engine only ONCE. Subsequent calls reuse the already-connected pool.
    """
    global _GLOBAL_ENGINE
    if _GLOBAL_ENGINE is None:
        try:
            # Fetch active server details
            server = XpertServer.objects.get(active=True)

            connection_string = (
                f"mssql+pyodbc://{server.user}:{server.pwd}@"
                f"{server.servername}/{server.database}?driver={server.driver}"
            )

            # Create the engine with a persistent pool
            _GLOBAL_ENGINE = create_engine(
                connection_string,
                fast_executemany=True,
                pool_size=10,  # Keep 10 connections permanently open!
                max_overflow=20,  # Allow up to 20 extra if traffic spikes
                pool_pre_ping=True,  # Auto-reconnect if SQL server restarts
                pool_recycle=3600  # Refresh connections every hour
            )
            print(">>> SUCCESS: Global SQLAlchemy Engine Created & Pooled! <<<")
        except Exception as e:
            raise ValueError(f"XpertServer Connection ERROR:\n {e}")

    return _GLOBAL_ENGINE


class XpertConnect:
    def __init__(self):
        # Instantly grab the global engine. Zero network delay!
        self.engine = get_engine()

    # (We can remove open_session and close_session as SQLAlchemy handles it automatically)
    def open_session(self):
        pass

    def close_session(self):
        pass

    def run_query(self, query, parameters=None):
        if not self.engine:
            raise ValueError("Not connected to the database.")

        if parameters is None:
            parameters = {}

        start_time = time.time()

        # Instantly checks out a connection from the permanent pool
        with self.engine.connect() as connection:
            result = connection.execute(text(query), parameters)
            columns = list(result.keys())

            raw_cursor = result.cursor
            raw_cursor.arraysize = 1000  # Fast network chunks
            data_rows = raw_cursor.fetchall()

            print(f"Raw ODBC Fetch Time: {time.time() - start_time:.4f} seconds")

        # Connection is automatically returned to the pool for the next user!
        return {
            'columns': columns,
            'data_rows': data_rows
        }