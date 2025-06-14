import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Initialize Firebase Admin
cred = credentials.Certificate('./env/evaluar-app-firebase-adminsdk-mvow6-456d541606.json')
firebase_admin.initialize_app(cred)

db = firestore.client()

# Read the CSV file
teachers_df = pd.read_csv('./teachers.csv', dtype=str)

# Populate Firestore
# # Populate Firestore for tickets. Use with caution, as it will overwrite the current tickets collection.

# for index, row in teachers_df.iterrows():
#     teacher_data = {
#         'teacherId': row['teacherId'],
#         'surname': row['surname'],
#         'name': row['name'],
#         'email': row['email'],
#         'currentLoad': 0,  # Start with 0 since no tickets are assigned yet
#         'maxLoad': 99,  # Start with 99 since no tickets are assigned yet
#     }
#     db.collection('teachers').document(row['teacherId']).set(teacher_data)

# print("Firestore populated with teacher data.")

