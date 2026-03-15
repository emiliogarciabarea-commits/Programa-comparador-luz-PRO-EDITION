
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

    # --- DETECCIÓN DE COMERCIALIZADORA ---
    # Se detecta Telecor/El Corte Inglés para aplicar su lógica específica
    es_eci = re.search(r'TELECOR S.A.|Energía El Corte Inglés', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)

    # 1. Búsqueda de Consumos
    # Se añaden patrones para capturar los datos de la tabla de consumo de ECI
    patrones_consumo = {
        'punta': [r'Punta\s+([\d,.]+)\s*(?:kWh)?', r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh'],
        'llano': [r'Llano\s+([\d,.]+)\s*(?:kWh)?', r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh'],
        'valle': [r'Valle\s+([\d,.]+)\s*(?:kWh)?', r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh']
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
    # En ECI aparece en los datos de suministro: "Punta: 3,45 kW"
    patron_potencia = r'(?:Potencia|Punta):\s*([\d,.]+)\s*kW'
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días
    # Patrones para "Fecha de Factura" y "Días de consumo" de ECI
    patron_fecha = r'(?:Fecha\s+de\s+Factura:|emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+)'
    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
    fecha = match_fecha.group(1) if match_fecha else "No encontrada"

    patron_dias = r'(?:Días\s+de\s+consumo:|(\d+)\s*días)'
    match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE)
    if match_dias:
        # Se extrae el número del grupo que haya hecho match
        dias_texto = match_dias.group(1) if match_dias.group(1) else re.search(r'\d+', match_dias.group(0)).group()
        dias = int(dias_texto)
    else:
        dias = 0

    # 4. Excedentes
    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
    
    # --- Lógica de cálculo de Total Real ---
    total_real = 0.0
    
    if es_eci:
        # Para El Corte Inglés: Suma de "Potencia facturada" + "Energia facturada"
        # Se buscan los totales de los bloques "FACTURACIÓN POTENCIA CONTRATADA" y "FACTURACIÓN ENERGÍA CONSUMIDA"
        patron_pot_eci = r'FACTURACIÓN\s+POTENCIA\s+CONTRATADA.*?([\d,.]+)\s*€'
        patron_ene_eci = r'FACTURACIÓN\s+ENERGÍA\s+CONSUMIDA.*?([\d,.]+)\s*€'
        
        m_pot = re.search(patron_pot_eci, texto_completo, re.DOTALL | re.IGNORECASE)
        m_ene = re.search(patron_ene_eci, texto_completo, re.DOTALL | re.IGNORECASE)
        
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
        
    elif es_xxi:
        patron_pot_xxi = r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€'
        patron_ene_xxi = r'por\s+energía\s+consumida\s*([\d,.]+)\s*€'
        m_pot = re.search(patron_pot_xxi, texto_completo, re.IGNORECASE)
        m_ene = re.search(patron_ene_xxi, texto_completo, re.IGNORECASE)
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
    else:
        # Lógica original para otros tipos de facturas
        patron_total = r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
    }

# El resto del código de la interfaz de Streamlit permanece igual
