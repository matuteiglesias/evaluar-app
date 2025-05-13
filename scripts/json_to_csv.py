import pandas as pd
import json

def json_to_csv(json_filename, csv_filename):
    # Leer el archivo JSON
    with open(json_filename, 'r', encoding='utf-8') as jsonfile:
        data = json.load(jsonfile)
    
    # Convertir a DataFrame de pandas
    df = pd.DataFrame(data)
    
    # Convertir y guardar en CSV
    df.to_csv(csv_filename, index=False, encoding='utf-8-sig')

# Uso del script
if __name__ == "__main__":
    # Especifica el nombre del archivo JSON de entrada y el nombre del archivo CSV de salida
    json_to_csv('./data/teachers.json', './data/teachers.csv')
    json_to_csv('./data/tickets.json', './data/tickets.csv')
    json_to_csv('./data/user_feedback.json', './data/user_feedback.csv')
    json_to_csv('./data/interaction_records.json', './data/interaction_records.csv')
