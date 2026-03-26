import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
from pdf2image import convert_from_bytes
import pytesseract
from PIL import Image

def extraer_datos_factura(pdf_bytes):
    # Primero intentamos extraer texto normal para identificar la compañía
    texto_completo = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- ESTRATEGIA OCR PARA ENDESA (LA "FOTO") ---
    # Si es Endesa, usamos OCR para asegurar nitidez en fechas e importes
    if re.search(r'endesa\s+luz', texto_completo, re.IGNORECASE):
        # Convertimos la primera página del PDF en una imagen (foto)
        imagenes = convert_from_bytes(pdf_bytes, first_page=1, last_page=1)
        # Extraemos el texto de la "foto"
        texto_ocr = pytesseract.image_to_string(imagenes[0], lang='spa')
        lineas = [l.strip() for l in texto_ocr.split('\n') if l.strip()]
        
        # --- BUSQUEDA EN EL TEXTO DE LA FOTO ---
        fecha = "No encontrada"
        dias = 0
        potencia = 0.0
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        val_pot = 0.0
        val_ene = 0.0

        for i, linea in enumerate(lineas):
            # Fecha: Buscamos el patrón de fecha cerca de "emisión"
            if "emisión" in linea.lower() or "factura" in linea.lower():
                m_f = re.search(r'(\d{2}/\d{2}/\d{4})', linea)
                if m_f: fecha = m_f.group(1)

            # Días: Buscamos el número antes de "días"
            if "días" in linea.lower():
                m_d = re.search(r'(\d+)\s*días', linea.lower())
                if m_d: dias = int(m_d.group(1))

            # Potencia y Consumos (P1, Punta, Llano, Valle)
            if "P1" in linea:
                m = re.search(r'([\d,.]+)\s*kW', linea)
                if m: potencia = float(m.group(1).replace(',', '.'))
            
            if "Punta" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['punta'] = float(m.group(1).replace(',', '.'))
            
            if "Llano" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['llano'] = float(m.group(1).replace(',', '.'))

            if "Valle" in linea:
                m = re.search(r'([\d,.]+)\s*kWh', linea)
                if m: consumos['valle'] = float(m.group(1).replace(',', '.'))

            # Importes finales del resumen
            if "Potencia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: val_pot = float(m.group(1).replace(',', '.'))
            
            if "Energia" in linea and "€" in linea:
                m = re.search(r'([\d,.]+)\s*€', linea)
                if m: val_ene = float(m.group(1).replace(',', '.'))

        total_real = val_pot + val_ene
        
        return {
            "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
            "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
            "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": 0.0,
            "Total Real": round(total_real, 2)
        }

    # --- AQUÍ IRÍA EL RESTO DE TU CÓDIGO ORIGINAL (ELIF REPSOL, IBERDROLA, ETC.) ---
    # (Se mantiene igual que lo tienes para no perder compatibilidad)
    return {"Fecha": "No encontrada", "Días": 0, "Total Real": 0.0} # Placeholder

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Comparador OCR", layout="wide")
st.title("📸 Comparador de Facturas vía OCR")

uploaded_files = st.file_uploader("Sube tus facturas", type="pdf", accept_multiple_files=True)
if uploaded_files:
    datos = []
    for f in uploaded_files:
        content = f.read()
        res = extraer_datos_factura(content)
        res['Archivo'] = f.name
        datos.append(res)
    st.write(pd.DataFrame(datos))
