import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def limpiar_valor(texto_sucio):
    """Limpia strings con comas, € y comillas para convertirlos en float."""
    if not texto_sucio: return 0.0
    # Quitamos todo lo que no sea número o coma/punto
    limpio = re.sub(r'[^\d,.-]', '', texto_sucio)
    limpio = limpio.replace(',', '.')
    try:
        return float(limpio)
    except:
        return 0.0

def extraer_datos_factura(pdf_path):
    texto_bruto = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_bruto += pagina.extract_text() + "\n"

    # Normalizamos el texto quitando comillas y saltos de línea para que los regex no fallen
    texto = texto_bruto.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    texto = ' '.join(texto.split())

    # 1. BUSCAR IMPORTE TOTAL (La base de tu nuevo enfoque)
    # Buscamos "TOTAL IMPORTE FACTURA" seguido de un número y el símbolo €
    m_total = re.search(r"TOTAL IMPORTE FACTURA\s*([\d,.]+)\s*€", texto, re.I)
    total_factura = limpiar_valor(m_total.group(1)) if m_total else 0.0

    # 2. BUSCAR CONCEPTOS A RESTAR
    # IVA (Buscamos el importe al lado de 'IVA normal' o 'IVA reducido')
    m_iva = re.search(r"IVA\s+\w+\s*([\d,.]+)\s*€", texto, re.I)
    iva = limpiar_valor(m_iva.group(1)) if m_iva else 0.0

    # Impuesto Electricidad
    m_ie = re.search(r"Impuesto\s+electricidad\s*([\d,.]+)\s*€", texto, re.I)
    imp_elec = limpiar_valor(m_ie.group(1)) if m_ie else 0.0

    # Alquiler del contador
    m_alq = re.search(r"Alquiler\s+del\s+contador\s*([\d,.]+)\s*€", texto, re.I)
    alquiler = limpiar_valor(m_alq.group(1)) if m_alq else 0.0

    # Bono Social / Otros (En Energía XXI suele venir en 'Otros')
    m_otros = re.search(r"Otros\s*([\d,.]+)\s*€", texto, re.I)
    otros = limpiar_valor(m_otros.group(1)) if m_otros else 0.0

    # --- LÓGICA DE RESTA ---
    # Lo que queda tras quitar impuestos y alquiler es la suma de Potencia + Energía
    suma_potencia_energia = round(total_factura - iva - imp_elec - alquiler - otros, 2)

    # 3. DATOS PARA LA COMPARATIVA (Consumos y kW)
    m_kw = re.search(r"([\d,.]+)\s*kW", texto)
    potencia_kw = limpiar_valor(m_kw.group(1)) if m_kw else 0.0
    
    m_dias = re.search(r"(\d+)\s*días", texto, re.I)
    dias = int(m_dias.group(1)) if m_dias else 0

    consumos = {}
    for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
        m = re.search(rf"{p}.*?([\d,.]+)\s*kWh", texto, re.I)
        consumos[tramo] = limpiar_valor(m.group(1)) if m else 0.0

    return {
        "Compañía": "Energía XXI",
        "Días": dias,
        "Potencia (kW)": potencia_kw,
        "Consumo Punta (kWh)": consumos['punta'],
        "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'],
        "Total Real (P+E)": suma_potencia_energia # Resultado de la resta
    }

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Comparador Pro", layout="wide")
st.title("⚡ Comparador (Enfoque por Resta de Impuestos)")

uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)

if uploaded_files:
    datos = []
    for f in uploaded_files:
        try:
            res = extraer_datos_factura(io.BytesIO(f.read()))
            res['Archivo'] = f.name
            datos.append(res)
        except Exception as e:
            st.error(f"Error en {f.name}: {e}")

    if datos:
        df = pd.DataFrame(datos)
        st.write("### Datos calculados (Total - Impuestos - Alquiler)")
        st.dataframe(df, use_container_width=True)

        if os.path.exists("tarifas_companias.xlsx"):
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            # ... (aquí sigue el resto de tu lógica de comparación)
