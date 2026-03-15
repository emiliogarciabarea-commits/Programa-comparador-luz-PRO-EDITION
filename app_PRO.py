
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

    # Detección de El Corte Inglés
    es_eci = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)

    # 1. Búsqueda de Consumos
    patrones_consumo = {
        'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh', r'Punta\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€'],
        'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh', r'Llano\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€'],
        'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh', r'Valle\s+([\d,.]+)\s+[\d,.]+\s+[\d,.]+\s+€']
    }
    
    consumos = {}
    for tramo, patrones in patrones_consumo.items():
        consumos[tramo] = 0.0
        # En ECI, los consumos están en una tabla de detalle (Punta, Llano, Valle)
        for patron in patrones:
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                consumos[tramo] = float(match.group(1).replace(',', '.'))
                break

    # 2. Búsqueda de Potencia
    patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?|Punta:)\s*([\d,.]+)\s*kW'
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días
    patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:|Fecha\s+de\s+Factura:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
    fecha = match_fecha.group(1).strip() if match_fecha else "No encontrada"

    patron_dias = r'(?:Días\s+de\s+consumo:|(\d+)\s*días)'
    match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE)
    if match_dias:
        # Intenta capturar el grupo 1, si no, busca el número inmediatamente después de "Días de consumo:"
        dias_val = match_dias.group(1) if match_dias.group(1) else re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo, re.IGNORECASE).group(1)
        dias = int(dias_val)
    else:
        dias = 0

    # 4. Excedentes
    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
    
    # --- Lógica específica de Factura Actual ---
    total_real = 0.0
    es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
    
    if es_xxi:
        patron_pot_xxi = r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€'
        patron_ene_xxi = r'por\s+energía\s+consumida\s*([\d,.]+)\s*€'
        m_pot = re.search(patron_pot_xxi, texto_completo, re.IGNORECASE)
        m_ene = re.search(patron_ene_xxi, texto_completo, re.IGNORECASE)
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
    else:
        patron_total = r'(?:Subtotal|Importe\s+total|TOTAL\s+FACTURA)\s*:?\s*([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
    }

# --- EL RESTO DEL CÓDIGO (INTERFAZ STREAMLIT) PERMANECE IGUAL ---
