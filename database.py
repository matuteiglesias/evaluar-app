import pymysql
import os

class Database:
    def __init__(self):
        # Example environment variables for database connection details
        db_host = os.environ.get('DB_HOST')
        db_user = os.environ.get('DB_USER')
        db_password = os.environ.get('DB_PASSWORD')
        db_name = os.environ.get('DB_NAME')

        self.connection = pymysql.connect(host=db_host,
                                          user=db_user,
                                          password=db_password,
                                          database=db_name,
                                          cursorclass=pymysql.cursors.DictCursor)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS interactions (response TEXT)")

    def save_interaction(self, response):
        self.cursor.execute("INSERT INTO interactions (response) VALUES (%s)", (response,))
        self.connection.commit()

    def close(self):
        self.cursor.close()
        self.connection.close()
