import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from .models import XpertServer
import time

class XpertConnect:
    def __init__(self):
        try:
            self.server = XpertServer.objects.get(active=True)

            self.engine = create_engine(
                f"mssql+pyodbc://{self.server.user}:{self.server.pwd}@"
                f"{self.server.servername}/{self.server.database}?driver={self.server.driver}",
                fast_executemany=True,  # Huge speedup
                pool_size=10,
                max_overflow=20
            )
            self.Session = sessionmaker(bind=self.engine)
            self.session = None

        except Exception as e:
            raise ValueError("XpertServer ERROR:\n {}".format(e))

    def open_session(self):
        if self.session is None:
            self.session = self.Session()

    def close_session(self):
        if self.session:
            self.session.close()
            self.session = None

    def run_query(self, query, parameters=None):
        if not self.engine:
            raise ValueError("Not connected to the database.")

        if parameters is None:
            parameters = {}

        with self.engine.connect() as connection:
            start_time = time.time()

            # 1. Execute the query
            result = connection.execute(text(query), parameters)

            # 2. Get column names
            columns = list(result.keys())

            # 3. Fetch raw rows as a list of tuples (extremely fast)
            data_rows = [tuple(row) for row in result.fetchall()]

            print(f"SQLAlchemy Fetch Time: {time.time() - start_time:.4f} seconds")

        # Return a simple dictionary instead of a Pandas DataFrame
        return {
            'columns': columns,
            'data_rows': data_rows
        }

    def get_query(self, query, parameters=None):
        # Kept for backward compatibility if you use it elsewhere
        if parameters is None:
            parameters = {}
        return query % parameters