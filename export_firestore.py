import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
import json


cred = credentials.Certificate('evaluar-app-firebase-adminsdk-mvow6-456d541606.json')
firebase_admin.initialize_app(cred)


def export_firestore_collection(collection_name):
    db = firestore.client()
    collection_ref = db.collection(collection_name)
    docs = collection_ref.stream()
    
    # doc_list = []
    # for doc in docs:
    #     doc_dict = doc.to_dict()
    #     doc_dict["id"] = doc.id  # Opcional: agregar ID del documento
    #     doc_list.append(doc_dict)
    
    doc_list = []
    for doc in docs:
        doc_dict = doc.to_dict()
        # Intenta convertir todas las marcas de tiempo a string
        for key, value in doc_dict.items():
            if hasattr(value, 'isoformat'):
                doc_dict[key] = value.isoformat()
            elif isinstance(value, str):
                doc_dict[key] = value.encode('utf-8', errors='replace').decode('utf-8')  # Asegurar codificación UTF-8 para strings
        doc_list.append(doc_dict)

    # Exportar a JSON
    with open(f"./data/{collection_name}.json", "w", encoding='utf-8') as jsonfile:
        json.dump(doc_list, jsonfile, ensure_ascii=False, indent=4)  # ensure_ascii=False para manejar correctamente los caracteres especiales
    
    print(f"Exported {len(doc_list)} documents from {collection_name}")

if __name__ == "__main__":
    # Especifica el nombre de la colección que deseas exportar
    export_firestore_collection('teachers')
    export_firestore_collection('tickets')
    export_firestore_collection('user_feedback')
