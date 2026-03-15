
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

    # 1. Búsqueda de Consumos (Adaptado para El Corte Inglés)
    patrones_consumo = {
        'punta': [r'Punta\s+([\d,.]+)\s*kWh', r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh'],
        'llano': [r'Llano\s+([\d,.]+)\s*kWh', r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh'],
        'valle': [r'Valle\s+([\d,.]+)\s*kWh', r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh']
    }
    
    consumos = {}
    for tramo, patrones in patrones_consumo.items():
        consumos[tramo] = 0.0
        for patron in patrones:
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                # Se usa findall y se toma el primer valor si hay varios (como en el detalle)
                valores = re.findall(patron, texto_completo, re.IGNORECASE)
                consumos[tramo] = float(valores[0].replace(',', '.'))
                break

    # 2. Búsqueda de Potencia (Específico: Punta: 3,45 kW)
    patron_potencia = r'Punta:\s*([\d,.]+)\s*kW'
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días
    # Para El Corte Inglés: "Fecha de Factura: 16/01/2025" y "Días de consumo: 23"
    patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
    fecha = match_fecha.group(1) if match_fecha else "No encontrada"

    patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
    match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE)
    dias = int(match_dias.group(1)) if match_dias else 0

    # 4. Excedentes
    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
    
    # --- Lógica específica de Factura Actual ---
    total_real = 0.0
    es_xxi = re.search(r'Comercializadora\s+de\s+Referencia|Energía\s+XXI', texto_completo, re.IGNORECASE)
    
    if es_xxi:
        patron_pot_xxi = r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€'
        patron_ene_xxi = r'por\s+energía\s+consumida\s*([\d,.]+)\s*€'
        m_pot = re.search(patron_pot_xxi, texto_completo, re.IGNORECASE)
        m_ene = re.search(patron_ene_xxi, texto_completo, re.IGNORECASE)
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
    else:
        # "TOTAL FACTURA 21,34€"
        patron_total = r'TOTAL\s+FACTURA\s*([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
    }

# ... (El resto del código de la interfaz Streamlit se mantiene igual)
