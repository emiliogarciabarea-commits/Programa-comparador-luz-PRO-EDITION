
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
    # Detectamos si es El Corte Inglés buscando "TELECOR" o el nombre comercial [cite: 1, 2]
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)

    # 1. Búsqueda de Consumos
    # Para ECI, extraemos los datos de la tabla de consumo por tramos [cite: 29, 97, 114]
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

    # 2. Búsqueda de Potencia [cite: 8, 74]
    patron_potencia = r'(?:Potencia|Punta):\s*([\d,.]+)\s*kW'
    match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
    potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0

    # 3. Fecha y Días 
    patron_fecha = r'(?:Fecha\s+de\s+Factura:|emitida\s+el)\s*([\d/]+)'
    match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
    fecha = match_fecha.group(1) if match_fecha else "No encontrada"

    patron_dias = r'(?:Días\s+de\s+consumo:?\s*(\d+)|(\d+)\s*días)'
    match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE)
    dias = 0
    if match_dias:
        dias = int(match_dias.group(1) if match_dias.group(1) else match_dias.group(2))

    # 4. Excedentes
    patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
    match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
    excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
    
    # --- LÓGICA DE TOTALES ---
    total_real = 0.0
    if es_el_corte_ingles:
        # SUMA SOLICITADA: Potencia facturada + Energía facturada [cite: 79, 109]
        # Buscamos los importes finales de cada sección en el detalle [cite: 68, 84]
        m_pot = re.search(r'FACTURACIÓN\s+POTENCIA\s+CONTRATADA\s+.*?([\d,.]+)\s*€', texto_completo, re.DOTALL | re.IGNORECASE)
        m_ene = re.search(r'FACTURACIÓN\s+ENERGÍA\s+CONSUMIDA\s+.*?([\d,.]+)\s*€', texto_completo, re.DOTALL | re.IGNORECASE)
        
        val_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        val_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        total_real = val_pot + val_ene
    elif es_xxi:
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

# --- INTERFAZ STREAMLIT (Asegúrate de que el resto del código esté identado a nivel 0) ---
st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}' en el repositorio.")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        datos_facturas = []
        for uploaded_file in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))
                res['Archivo'] = uploaded_file.name
                datos_facturas.append(res)
            except Exception as e:
                st.error(f"Error procesando {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Ver detalles de datos extraídos"):
                st.dataframe(df_resumen_pdfs, use_container_width=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'],
                    "Ahorro": 0.0
                })

                for index, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1 = pd.to_numeric(tarifa.iloc[1], errors='coerce')
                        c_pot2 = pd.to_numeric(tarifa.iloc[2], errors='coerce')
                        d_punta = pd.to_numeric(tarifa.iloc[3], errors='coerce')
                        e_llano = pd.to_numeric(tarifa.iloc[4], errors='coerce')
                        f_valle = pd.to_numeric(tarifa.iloc[5], errors='coerce')
                        g_excedente = pd.to_numeric(tarifa.iloc[6], errors='coerce')

                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + \
                                         (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * d_punta) + \
                                         (fact['Consumo Llano (kWh)'] * e_llano) + \
                                         (fact['Consumo Valle (kWh)'] * f_valle) - \
                                         (fact['Excedente (kWh)'] * g_excedente)
                        
                        ahorro = fact['Total Real'] - coste_estimado
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'],
                            "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2),
                            "Ahorro": round(ahorro, 2)
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Coste (€)"], ascending=[True, True])
            st.subheader("📊 Comparativa de Mercado")
            st.dataframe(df_comp, hide_index=True, use_container_width=True)
