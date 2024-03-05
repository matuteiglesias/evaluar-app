import os
from evaluator import AnalizadorEjercicios  # Asegúrate de importar tu clase correctamente

def leer_contenido_archivo(nombre_archivo):
    with open(nombre_archivo, 'r', encoding='utf-8') as archivo:
        return archivo.read()


def main():
    carpeta_ejercicios = 'exercises'  # Asegúrate de que esta es la ruta correcta a la carpeta
    evaluador = AnalizadorEjercicios()  # Inicializa tu clase AnalizadorEjercicios aquí

    # Obtiene todos los archivos .tex y los ordena
    archivos_tex = sorted([archivo for archivo in os.listdir(carpeta_ejercicios) if archivo.endswith('.tex')])

    for archivo in archivos_tex:
        ruta_completa = os.path.join(carpeta_ejercicios, archivo)
        contenido_ejercicio = leer_contenido_archivo(ruta_completa)
            
        # Aquí asumimos que tu método evaluate solo necesita el contenido del ejercicio.
        # Ajusta los argumentos según sea necesario.
        nombre_info = evaluador.evaluate(contenido_ejercicio)
        print(f"Nombre e Info para {archivo}: {nombre_info}")

if __name__ == '__main__':
    main()
