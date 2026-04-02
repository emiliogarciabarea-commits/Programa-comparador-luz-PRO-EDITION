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

    # --- DETECCIÓN DE COMPAÑÍA ---
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.I)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.I)
    es_total = re.search(r'TotalEnergies', texto_completo, re.I)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.I)
    es_endesa = re.search(r'Endesa\s+Energía', texto_completo, re.I)
    es_eci = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.I)

    compania = "Genérica"
    total_real = 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia, dias, fecha, excedente = 0.0, 0, "No encontrada", 0.0

    # --- LÓGICA ESPECÍFICA PARA ENERGÍA XXI ---
    if es_xxi:
        compania = "Energía XXI"
        # 1. Consumos P1, P2, P3
        for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
            m = re.search(rf'{p}:?\s*([\d,.]+)\s*kWh', texto_completo, re.I)
            if m: consumos[tramo] = float(m.group(1).replace(',', '.'))
        
        # 2. Potencia (kW), Días y Fecha
        m_pot_kw = re.search(r'([\d,.]+)\s*kW', texto_completo)
        if m_pot_kw: potencia = float(m_pot_kw.group(1).replace(',', '.'))
        
        m_dias = re.search(r'(\d+)\s*días', texto_completo)
        if m_dias: dias = int(m_dias.group(1))
        
        m_fecha = re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+|[\d]+\s+de\s+\w+)', texto_completo, re.I)
        if m_fecha: fecha = m_fecha.group(1)

        # 3. SUMA POTENCIA + ENERGÍA (Corregido para comillas y saltos de línea)
        # Buscamos el texto, saltamos posibles comillas/espacios y capturamos el número antes del €
        patron_pot = r'Por\s+potencia\s+contratada\s*\"?,\s*\"?([\d,.]+)\s*€'
        patron_ene = r'Por\s+energía\s+consumida\s*\"?,\s*\"?([\d,.]+)\s*€'
        
        val_pot = re.search(patron_pot, texto_completo, re.I)
        val_ene = re.search(patron_ene, texto_completo, re.I)
        
        v_p = float(val_pot.group(1).replace(',', '.')) if val_pot else 0.0
        v_e = float(val_ene.group(1).replace(',', '.')) if val_ene else 0.0
        total_real = v_p + v_e

    # --- LÓGICA PARA OCTOPUS ---
    elif es_octopus:
        compania = "Octopus Energy"
        m_val_pot = re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.I)
        m_val_ene = re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.I)
        total_real = (float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0) + \
                     (float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0)
        # ... (resto de campos de Octopus)

    # (Aquí irían los bloques elif para Naturgy, Endesa, etc., con la misma lógica de suma)

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Comparador Facturas", layout="wide")
st.title("⚡ Extractor de Potencia + Energía")

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for f in uploaded_files:
        datos = extraer_datos_factura(io.BytesIO(f.read()))
        datos['Archivo'] = f.name
        resultados.append(datos)
    
    df = pd.DataFrame(resultados)
    st.subheader("Resultados Extraídos (Suma de Términos)")
    st.write("El 'Total Real' ahora solo muestra la suma de Potencia + Energía.")
    st.dataframe(df, use_container_width=True)

    # Simulación de comparativa con Excel
    if os.path.exists("tarifas_companias.xlsx"):
        df_tarifas = pd.read_excel("tarifas_companias.xlsx")
        # Aquí seguiría tu lógica de cálculo de ahorro...
