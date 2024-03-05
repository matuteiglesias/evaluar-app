import csv
import re

def txt_a_csv(ruta_txt, ruta_csv):
    # Abrir archivo txt para leer y archivo csv para escribir
    with open(ruta_txt, 'r', encoding='utf-8') as archivo_txt, \
         open(ruta_csv, 'w', newline='', encoding='utf-8') as archivo_csv:
        
        # Preparar el escritor csv y escribir la fila de encabezado
        escritor_csv = csv.writer(archivo_csv)
        escritor_csv.writerow(['ID', 'Nombre', 'Descripción'])

        # Leer el contenido completo del archivo txt
        contenido = archivo_txt.read()

        # Dividir el contenido en bloques por cada ejercicio
        bloques = contenido.split("Nombre e Info para ")[1:]  # Ignorar el primer split que no contiene ejercicio

        print(len(bloques))
        for bloque in bloques:
            # print(bloque)

            # Ajusta el inicio de cada bloque para que la extracción funcione correctamente
            bloque = "Nombre e Info para " + bloque
            id_ejercicio = re.search(r"Nombre e Info para (\d+).tex", bloque).group(1)
            nombre = re.search(r"Nombre: \*{0,2}(.*?)\*{0,2}\n", bloque).group(1)
            descripcion = re.search(r"Descripción: (.*)", bloque, re.DOTALL).group(1).strip()

            escritor_csv.writerow([id_ejercicio, nombre, descripcion])


# Especifica la ruta de tu archivo txt y el nombre deseado para el archivo csv
ruta_txt = './exercises/exsdesc.txt'  # Cambia esto por la ruta real de tu archivo txt
ruta_csv = './exercises/ejercicios.csv'

txt_a_csv(ruta_txt, ruta_csv)
