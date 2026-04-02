import pdfplumber
import re
import io

def extraer_energia_xxi(pdf_path):
    texto_acumulado = ""
    
    # 1. Extracción limpia
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_acumulado += pagina.extract_text() + "\n"

    # 2. Pre-procesamiento: Quitamos comillas y saltos de línea extra 
    # para que el texto sea lineal y fácil de leer por el motor de RE
    texto_limpio = texto_acumulado.replace('"', '').replace('\n', ' ')

    # 3. Búsqueda de datos específicos
    # Buscamos el bloque "Por potencia contratada" seguido de cualquier cosa hasta el símbolo €
    match_potencia = re.search(r'Por potencia contratada\s+([\d,.]+)\s*€', texto_limpio, re.IGNORECASE)
    match_energia = re.search(r'Por energía consumida\s+([\d,.]+)\s*€', texto_limpio, re.IGNORECASE)
    
    # 4. Extracción de Consumos (P1, P2, P3)
    # Energía XXI suele usar P1, P2, P3 o Punta, Llano, Valle
    p1 = re.search(r'P1:?\s*([\d,.]+)\s*kWh', texto_limpio, re.IGNORECASE)
    p2 = re.search(r'P2:?\s*([\d,.]+)\s*kWh', texto_limpio, re.IGNORECASE)
    p3 = re.search(r'P3:?\s*([\d,.]+)\s*kWh', texto_limpio, re.IGNORECASE)

    # 5. Conversión a float segura
    def limpiar_float(match):
        if match:
            return float(match.group(1).replace(',', '.'))
        return 0.0

    val_potencia = limpiar_float(match_potencia)
    val_energia = limpiar_float(match_energia)
    
    consumo_punta = limpiar_float(p1)
    consumo_llano = limpiar_float(p2)
    consumo_valle = limpiar_float(p3)

    # 6. Resultado final (La suma que pediste)
    return {
        "Compañía": "Energía XXI",
        "Potencia (€)": val_potencia,
        "Energía (€)": val_energia,
        "Suma Base (Potencia + Energía)": round(val_potencia + val_energia, 2),
        "Consumo kWh": {
            "Punta": consumo_punta,
            "Llano": consumo_llano,
            "Valle": consumo_valle
        }
    }

# Ejemplo de uso
# datos = extraer_energia_xxi("tu_factura.pdf")
# print(f"Suma total requerida: {datos['Suma Base (Potencia + Energía)']} €")
