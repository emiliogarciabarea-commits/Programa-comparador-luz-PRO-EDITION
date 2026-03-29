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
    es_totalenergies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)

    if es_el_corte_ingles:

        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }

        patron_potencia = r'Potencia\s+contratada\s+kW\s+([\d,.]+)'
        match_potencia = re.search(patron_potencia, texto_completo)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

        patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
        match_fecha = re.search(patron_fecha, texto_completo)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"

        patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0

        patron_total = r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
        excedente = 0.0 

    elif es_totalenergies:

        # Fecha (primera en formato DD.MM.AAAA)
        m_fecha = re.search(r'(\d{2}\.\d{2}\.\d{4})', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        # Días
        m_dias = re.search(r'(\d+)\s*d[ií]a', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # Potencia kW
        m_pot = re.search(r'(\d+[.,]?\d*)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        # Consumo kWh (detalle)
        m_cons = re.search(r'(\d+[.,]?\d*)\s*kWh', texto_completo)
        valor_consumo = float(m_cons.group(1).replace(',', '.')) if m_cons else 0.0

        consumos = {
            'punta': valor_consumo,
            'llano': 0.0,
            'valle': 0.0
        }

        # Valores € (cuidado con floats)
        def limpiar_valor(txt):
            txt = txt.replace(" ", "").replace(".", "").replace(",", ".")
            try:
                return float(txt)
            except:
                return 0.0

        m_val_energia = re.search(r'kWh\s+[\d,.]+\s+€/kWh\s+([\d,.]+)\s*€', texto_completo)
        val_energia = limpiar_valor(m_val_energia.group(1)) if m_val_energia else 0.0

        m_val_pot = re.search(r'kW\s+[\d,.]+\s+€/kW día\s+([\d,.]+)\s*€', texto_completo)
        val_potencia = limpiar_valor(m_val_pot.group(1)) if m_val_pot else 0.0

        total_real = val_potencia + val_energia
        excedente = 0.0

    elif es_endesa_luz:

        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        if m_fecha_etiqueta:
            fecha = m_fecha_etiqueta.group(1)
        else:
            m_fecha_generica = re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo)
            fecha = m_fecha_generica.group(1) if m_fecha_generica else "No encontrada"

        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                valor_sucio = match.group(1)
                valor_limpio = valor_sucio.replace(" ", "").replace(".", "")
                valor_limpio = valor_limpio.replace(",", ".")
                try: return float(valor_limpio)
                except: return 0.0
            return 0.0

        val_potencia = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo)
        val_energia = limpiar_valor_endesa(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo)
        total_real = val_potencia + val_energia

        m_punta = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        excedente = 0.0

    elif es_repsol:

        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)

        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + \
                     (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)

        m_consumo_gen = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        valor_consumo = float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0

        consumos = {'punta': valor_consumo, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    # resto del código IGUAL...

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }
