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
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.IGNORECASE)

    compania = "Genérica / Desconocida" # Valor por defecto

    # ... (Se mantienen igual las lógicas de ECI, Octopus, TotalEnergies, Naturgy, Endesa, Repsol e Iberdrola) ...
    # [Omitido por brevedad para centrar la respuesta en la corrección de Energía XXI, pero debe ir en tu código]

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        # ... (resto de lógica ECI)
    elif es_octopus:
        compania = "Octopus Energy"
        # ... (resto de lógica Octopus)
    # ... [Insertar aquí el resto de elifs originales] ...

    elif es_xxi or "comercializadora de referencia de endesa" in texto_completo.lower():
        compania = "Energía XXI"
        
        # 1. Consumos P1, P2, P3
        patrones_consumo = {
            'punta': [r'P1:?\s*([\d,.]+)\s*kWh', r'Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'P2:?\s*([\d,.]+)\s*kWh', r'Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'P3:?\s*([\d,.]+)\s*kWh', r'Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break
        
        # 2. Potencia
        match_potencia = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        
        # 3. Fecha (Buscamos "emitida el" o "Fecha de cargo")
        match_fecha = re.search(r'emitida\s+el\s+([\d]+\s+de\s+\w+\s+de\s+\d{4})', texto_completo, re.IGNORECASE)
        if not match_fecha:
            match_fecha = re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+|[\d]+\s+de\s+\w+\s+de\s+\d{4})', texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1).strip() if match_fecha else "No encontrada"
        
        # 4. Días
        match_dias = re.search(r'\((\d+)\s*días\)', texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        
        # 5. Excedente
        match_excedente = re.search(r'Valoración\s+excedentes.*?(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        
        # 6. TOTAL REAL (CORRECCIÓN CRÍTICA PARA ENERGÍA XXI)
        # Buscamos la línea "TOTAL IMPORTE FACTURA" y limpiamos comillas y espacios
        match_total = re.search(r'TOTAL\s+IMPORTE\s+FACTURA[^\d]*([\d,.]+)', texto_completo, re.IGNORECASE)
        if match_total:
            # Limpiamos posibles comillas o basura antes de convertir
            valor_limpio = match_total.group(1).replace('"', '').replace(' ', '').replace(',', '.')
            total_real = float(valor_limpio)
        else:
            total_real = 0.0

    else:
        # Lógica genérica por si falla la detección específica
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia = 0.0
        fecha = "No encontrada"
        dias = 0
        excedente = 0.0
        total_real = 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- El resto del código Streamlit se mantiene igual que en tu versión original ---
