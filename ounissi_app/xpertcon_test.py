import pyodbc
from .models import XpertServer

class XpertConnect:
    def __init__(self):
        self.connect = None
        self.cursor = None

    def connect(self):
        server = XpertServer.objects.get(active=True)  # Fetch active server details
        print(server)
        try:

            self.connect = pyodbc.connect(
                'DRIVER={' + server.driver + '};'
                'SERVER=' + server.servername + ';'
                'DATABASE=' + server.database + ';'
                'UID=' + server.user + ';'
                'PWD=' + server.pwd
            )
            self.cursor = self.connect.cursor()
        except XpertServer.DoesNotExist:
            raise ValueError("No active XpertServer found.")
        except pyodbc.Error as ex:
            raise ConnectionError(f"Database connection error: {ex}")

    def execute_quer(self, query):
        if not self.connect:
            raise ValueError("Not connected to the database. Call connect() first.")
        self.cursor.execute(query)
        return self.cursor

    def connect_close(self):
        if self.cursor:
            self.cursor.close()
        if self.connect:
            self.connect.close()
