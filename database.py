'''
This file defines the Database class.
'''
import sqlite3
class Database:
    def __init__(self):
        self.connection = sqlite3.connect("interactions.db")
        self.cursor = self.connection.cursor()
        self.create_table()
    def create_table(self):
        self.cursor.execute("CREATE TABLE IF NOT EXISTS interactions (response TEXT)")
    def save_interaction(self, response):
        self.cursor.execute("INSERT INTO interactions VALUES (?)", (response,))
        self.connection.commit()
    def close(self):
        self.cursor.close()
        self.connection.close()