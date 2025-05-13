# import os
# import csv
# import pymysql
# from pymysql.cursors import DictCursor
# from dotenv import load_dotenv

# load_dotenv()

# DB_CONFIG = {
#     'host': os.getenv('DB_HOST', '127.0.0.1'),
#     'user': os.getenv('DB_USER', 'root'),
#     'password': os.getenv('DB_PASSWORD', '1234'),
#     'db': os.getenv('DB_NAME', 'interactions'),
#     'local_infile': 1,
#     'cursorclass': DictCursor
# }

# CSV_FILE_PATH = './exercises/exercises.csv'
# TABLE_NAME = 'exercises'


# def create_table(cursor):
#     cursor.execute(f"""
#         CREATE TABLE IF NOT EXISTS {TABLE_NAME} (
#             id INT AUTO_INCREMENT PRIMARY KEY,
#             unit VARCHAR(255),
#             name VARCHAR(255),
#             info TEXT,
#             file TEXT
#         )
#     """)


# def insert_csv_data(cursor, csv_path):
#     with open(csv_path, newline='', encoding='utf-8') as csvfile:
#         reader = csv.reader(csvfile)
#         headers = next(reader)  # skip header

#         for idx, row in enumerate(reader, start=1):
#             if len(row) != 4:
#                 print(f"[WARN] Skipping row {idx}: unexpected number of columns ({len(row)}). Row: {row}")
#                 continue

#             cursor.execute(
#                 f"INSERT INTO {TABLE_NAME} (unit, name, info, file) VALUES (%s, %s, %s, %s)",
#                 tuple(row)
#             )


# def main():
#     connection = None
#     try:
#         connection = pymysql.connect(**DB_CONFIG)
#         with connection.cursor() as cursor:
#             create_table(cursor)
#             insert_csv_data(cursor, CSV_FILE_PATH)
#         connection.commit()
#         print("[OK] Exercises successfully loaded into the database.")

#     except pymysql.MySQLError as e:
#         print(f"[ERROR] Database operation failed: {e}")
#     finally:
#         if connection:
#             connection.close()
#             print("[INFO] Connection closed.")


# if __name__ == "__main__":
#     main()
