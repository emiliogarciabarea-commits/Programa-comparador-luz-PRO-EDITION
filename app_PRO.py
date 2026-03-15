
import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # Detección de proveedor: El Corte Inglés
    es_eci = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)

    # 1. Búsqueda de Consumos
    if es_eci:
        # Patrones específicos para El Corte Inglés (página 2 del PDF)
        # Busca el valor numérico justo después de "Punta", "Llano", "Valle" en la tabla de energía
        patrones_consumo = {
            'punta': [r'Punta\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€'], # Basado en la estructura de la tabla
            'llano': [r'Llano\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€'],
            'valle': [r'Valle\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€']
        }
    else:
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
    
    consumos = {}
    for tramo, patrones in patrones_consumo.items():
        consumos[tramo] = 0.0
        for patron in patrones:
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                consumos[tramo] = float(match.group(1).replace(',', '.'))
                break

    # 2. Búsqueda de Potencia
    if es_eci:
        # En ECI aparece como "Punta: 3,45 kW Valle: 3,45 kW"
        patron_potencia = r'Punta:\s*([\d,.]+)\s*kW'
    else:
        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
    
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días
    if es_eci:
        patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
        patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
    else:
        patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
        patron_dias = r'(\d+)\s*días'

    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
    fecha = match_fecha.group(1) if match_fecha else "No encontrada"

    match_dias = re.search(patron_dias, texto_completo)
    dias = int(match_dias.group(1)) if match_dias else 0

    # 4. Total Factura
    if es_eci:
        # ECI tiene "TOTAL FACTURA" seguido del importe
        patron_total = r'TOTAL\s+FACTURA\s*([\d,.]+)\s*€'
    else:
        patron_total = r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€'
        
    match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
    total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": 0.0,
        "Total Real": total_real
    }

# --- EL RESTO DEL CÓDIGO (INTERFAZ STREAMLIT) SE MANTIENE IGUAL ---
