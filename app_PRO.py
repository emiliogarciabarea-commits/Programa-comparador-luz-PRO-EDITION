
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

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía El Corte Inglés|TELECOR S\.A\.', texto_completo, re.IGNORECASE)

    # 1. Búsqueda de Consumos
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    
    if es_el_corte_ingles:
        # Lógica específica para El Corte Inglés (Busca en el "Detalle de la Factura")
        # Busca el bloque de Energía Consumida y extrae los kWh de cada tramo
        p_punta = r'Punta\s+([\d,.]+)\s+kWh\s+[\d,.]+\s+€/kWh'
        p_llano = r'Llano\s+([\d,.]+)\s+kWh\s+[\d,.]+\s+€/kWh'
        p_valle = r'Valle\s+([\d,.]+)\s+kWh\s+[\d,.]+\s+€/kWh'
        
        m_punta = re.search(p_punta, texto_completo)
        m_llano = re.search(p_llano, texto_completo)
        m_valle = re.search(p_valle, texto_completo)
        
        if m_punta: consumos['punta'] = float(m_punta.group(1).replace(',', '.'))
        if m_llano: consumos['llano'] = float(m_llano.group(1).replace(',', '.'))
        if m_valle: consumos['valle'] = float(m_valle.group(1).replace(',', '.'))
    else:
        # Patrones originales para otras facturas
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
        for tramo, patrones in patrones_consumo.items():
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break

    # 2. Búsqueda de Potencia
    if es_el_corte_ingles:
        # En esta factura la potencia suele aparecer en "Potencia: Punta: X kW Valle: X kW"
        patron_potencia = r'Potencia:\s+Punta:\s*([\d,.]+)\s*kW'
    else:
        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
    
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días
    if es_el_corte_ingles:
        # Extrae "Fecha de Factura: 16/01/2025" y "Días de consumo: 23"
        m_fecha = re.search(r'Fecha de Factura:\s*([\d/]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        m_dias = re.search(r'Días de consumo:\s*(\d+)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
    else:
        patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
        match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"

        patron_dias = r'(\d+)\s*días'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0

    # 4. Excedentes (General)
    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
    
    # 5. Total Factura
    if es_el_corte_ingles:
        # Busca el total específico al final de la tabla de importes
        match_total = re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
    else:
        # Lógica original para otros proveedores
        es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
        if es_xxi:
            m_pot = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            m_ene = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = (float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0) + \
                         (float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0)
        else:
            patron_total = r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€'
            match_total = re.search(patron_total, texto_completo, re.IGNORECASE)
            total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": total_real
    }

# --- El resto del código de la interfaz Streamlit se mantiene igual ---
