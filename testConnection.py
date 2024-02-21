import os
import pymysql
import csv

## Conecta con cloud SQL proxy
# (base) matias@matias-ThinkPad-T470-W10DG:~$ ./cloud-sql-proxy -instances=evaluar-app:us-central1:my-sql-instance=tcp:3306^C
# (base) matias@matias-ThinkPad-T470-W10DG:~$ ./cloud-sql-proxy --address 0.0.0.0 --port 3306 evaluar-app:us-central1:my-sql-instance


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

# db_host = 'localhost' # Instead of dynamically fetching from os.environ
db_host = '127.0.0.1'
db_user = 'root'
db_password = '1234'
db_name = 'interactions'

# Initialize connection variable
connection = None

csv_file_path = './exercises/exercises.csv'

# Try connecting to the database
try:
    # Establish a database connection
    connection = pymysql.connect(host=db_host,
                                user=db_user,
                                password=db_password,
                                db=db_name,
                                local_infile=1,
                                cursorclass=pymysql.cursors.DictCursor)
    
    # cursor = connection.cursor()

    with connection.cursor() as cursor:
        # Create a new table
        create_table_query = """
        CREATE TABLE IF NOT EXISTS exercises (
            id INT AUTO_INCREMENT PRIMARY KEY,
            unit VARCHAR(255),
            name VARCHAR(255),
            info TEXT,
            file TEXT
        )
        """
        cursor.execute(create_table_query)

        
        # Open the CSV file and load the content
        with open(csv_file_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            next(reader)  # Skip the header row
            
            for row in reader:
                cursor.execute(
                    "INSERT INTO exercises (unit, name, info, file) VALUES (%s, %s, %s, %s)",
                    (*row,)  # Unpack the row list as separate arguments
                    # row
                )
        connection.commit()

    print("Successfully connected to the database.")
except pymysql.MySQLError as e:
    print(f"Failed to connect to the database: {e}")
finally:
    if connection:
        connection.close()