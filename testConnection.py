import os
import pymysql

# Initialize connection variable
connection = None

# # For local development only; remove before deploying
# os.environ['DB_HOST'] = '34.42.138.123'
# os.environ['DB_USER'] = 'root'
# os.environ['DB_PASSWORD'] = '1234'
# os.environ['DB_NAME'] = 'interactions'

# # Load environment variables from .env file or your environment configuration
# db_host = os.getenv('DB_HOST')
# db_user = os.getenv('DB_USER')
# db_password = os.getenv('DB_PASSWORD')
# db_name = os.getenv('DB_NAME')

db_host = 'localhost' # Instead of dynamically fetching from os.environ
db_user = 'root'
db_password = '1234'
db_name = 'interactions'

# Try connecting to the database
try:
    connection = pymysql.connect(host=db_host,
                                 user=db_user,
                                 password=db_password,
                                 db=db_name,
                                 cursorclass=pymysql.cursors.DictCursor)
    
    print("Successfully connected to the database.")
except pymysql.MySQLError as e:
    print(f"Failed to connect to the database: {e}")
finally:
    if connection:
        connection.close()
