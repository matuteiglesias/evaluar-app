import os
import pymysql
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv('./.env')

class Database:
    def __init__(self):
        # Fetch database connection details from environment variables
        db_host = os.getenv('DB_HOST')
        db_user = os.getenv('DB_USER')
        db_password = os.getenv('DB_PASSWORD')
        db_name = os.getenv('DB_NAME')

        # Establish connection to the database
        self.connection = pymysql.connect(host=db_host,
                                          user=db_user,
                                          password=db_password,
                                          database=db_name,
                                          cursorclass=pymysql.cursors.DictCursor)
        self.cursor = self.connection.cursor()
        self.create_table()

    def create_table(self):
        # Assuming you have a method to create table if it doesn't exist
        self.cursor.execute("CREATE TABLE IF NOT EXISTS interactions (response TEXT)")

    def save_interaction(self, response):
        # Save a new interaction to the database
        self.cursor.execute("INSERT INTO interactions (response) VALUES (%s)", (response,))
        self.connection.commit()

    def close(self):
        # Close the database connection
        self.cursor.close()
        self.connection.close()