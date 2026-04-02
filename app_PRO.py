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

    # --- NORMALIZACIÓN ANTI-FANTASMAS ---
    # Colapsamos todos los espacios y saltos en uno solo para que "F e c h a" sea "Fecha"
    texto_normalizado = " ".join(texto_completo.split())

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.IGNORECASE)

    compania = "Genérica / Desconocida"

    # --- BLOQUE ENERGÍA XXI (CORREGIDO) ---
    if es_xxi:
        compania = "Energía XXI"
        
        # FECHA: Buscamos "emitida el" y capturamos hasta el año, ignorando lo que haya en medio
        m_fecha = re.search(r'emitida\s+el\s+([\d]{1,2}.*?\d{4})', texto_normalizado, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        # DÍAS: Buscamos el número que precede a la palabra "días" dentro de los paréntesis del periodo
        m_dias = re.search(r'\((\d+)\s*días\)', texto_normalizado)
        dias = int(m_dias.group(1)) if m_dias else 0

        # POTENCIA: Buscamos el valor kW
        m_pot = re.search(r'([\d,.]+)\s*kW', texto_normalizado)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        # CONSUMOS (P1, P2, P3)
        patrones_consumo = {
            'punta': [r'P1:?\s*([\d,.]+)\s*kWh', r'Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'P2:?\s*([\d,.]+)\s*kWh', r'Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'P3:?\s*([\d,.]+)\s*kWh', r'Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for p in patrones:
                m = re.search(p, texto_normalizado, re.IGNORECASE)
                if m:
                    consumos[tramo] = float(m.group(1).replace(',', '.'))
                    break
        
        # EXCEDENTE
        m_exc = re.search(r'excedentes.*?(-?\d+[\d,.]*)\s*kWh', texto_normalizado, re.IGNORECASE)
        excedente = abs(float(m_exc.group(1).replace(',', '.'))) if m_exc else 0.0

        # TOTAL REAL (Suma de los dos conceptos principales)
        m_val_pot = re.search(r'potencia\s+contratada.*?([\d,.]+)\s*€', texto_normalizado, re.IGNORECASE)
        m_val_ene = re.search(r'energía\s+consumida.*?([\d,.]+)\s*€', texto_normalizado, re.IGNORECASE)
        if m_val_pot and m_val_ene:
            total_real = float(m_val_pot.group(1).replace(',', '.')) + float(m_val_ene.group(1).replace(',', '.'))
        else:
            m_tot = re.search(r'Total\s+electricidad\s*([\d,.]+)\s*€', texto_normalizado, re.IGNORECASE)
            total_real = float(m_tot.group(1).replace(',', '.')) if m_tot else 0.0

    # --- RESTO DE COMPAÑÍAS (Tu lógica original simplificada) ---
    elif es_el_corte_ingles:
        compania = "El Corte Inglés"
        # ... (Tu código de ECI)
        return extraer_datos_eci(texto_completo) # Ejemplo de llamada externa si quieres modularizar

    # ... (Aquí irían los elif de Iberdrola, Naturgy, etc. con la misma lógica)

    # Devolvemos el diccionario con los datos extraídos
    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos.get('punta', 0.0), 
        "Consumo Llano (kWh)": consumos.get('llano', 0.0),
        "Consumo Valle (kWh)": consumos.get('valle', 0.0), 
        "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- Streamlit UI ---
st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

# (Lógica de carga de Excel y PDF similar a la tuya...)
