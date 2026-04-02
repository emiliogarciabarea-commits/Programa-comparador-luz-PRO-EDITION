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

    # --- LIMPIEZA DE TEXTO (Clave para Energía XXI) ---
    # Eliminamos comillas y normalizamos espacios para que el regex no se pierda
    texto_limpio = texto_completo.replace('"', '').replace('\n', ' ')

    # --- DETECCIÓN DE COMPAÑÍA ---
    es_xxi = re.search(r'Energía\s+XXI', texto_limpio, re.I)
    es_octopus = re.search(r'octopus\s+energy', texto_limpio, re.I)
    
    compania = "Genérica"
    total_real = 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia, dias, fecha, excedente = 0.0, 0, "No encontrada", 0.0

    if es_xxi:
        compania = "Energía XXI"
        
        # 1. Extraer Importes: Potencia y Energía (Suma de ambos)
        # Buscamos el texto y el primer número con coma que le siga antes del símbolo €
        m_pot = re.search(r'Por\s+potencia\s+contratada\s*,?\s*([\d,.]+)\s*€', texto_limpio, re.I)
        m_ene = re.search(r'Por\s+energía\s+consumida\s*,?\s*([\d,.]+)\s*€', texto_limpio, re.I)
        
        v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        
        # IMPORTANTE: Solo la suma de estos dos, ignorando el resto de la factura
        total_real = v_pot + v_ene

        # 2. Consumos (P1, P2, P3)
        for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
            m = re.search(rf'{p}:?\s*([\d,.]+)\s*kWh', texto_limpio, re.I)
            if m: consumos[tramo] = float(m.group(1).replace(',', '.'))

        # 3. Datos generales
        m_pot_kw = re.search(r'([\d,.]+)\s*kW', texto_limpio)
        if m_pot_kw: potencia = float(m_pot_kw.group(1).replace(',', '.'))
        
        m_dias = re.search(r'(\d+)\s*días', texto_limpio)
        if m_dias: dias = int(m_dias.group(1))
        
        m_fecha = re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+)', texto_limpio, re.I)
        if m_fecha: fecha = m_fecha.group(1)

    elif es_octopus:
        compania = "Octopus Energy"
        # Lógica simplificada para Octopus sumando solo Potencia + Energía Activa
        m_v_pot = re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_limpio, re.I)
        m_v_ene = re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_limpio, re.I)
        total_real = (float(m_v_pot.group(1).replace(',', '.')) if m_v_pot else 0.0) + \
                     (float(m_v_ene.group(1).replace(',', '.')) if m_v_ene else 0.0)
        # (Resto de campos para Octopus...)

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ ---
st.set_page_config(page_title="Comparador", layout="wide")
st.title("⚡ Extractor Potencia + Energía")

uploaded_files = st.file_uploader("Sube tus PDFs de Energía XXI", type="pdf", accept_multiple_files=True)

if uploaded_files:
    datos_lista = []
    for f in uploaded_files:
        try:
            res = extraer_datos_factura(io.BytesIO(f.read()))
            res['Archivo'] = f.name
            datos_lista.append(res)
        except Exception as e:
            st.error(f"Error en {f.name}: {e}")

    if datos_lista:
        df = pd.DataFrame(datos_lista)
        st.write("### Datos extraídos (Total Real = Potencia + Energía)")
        st.dataframe(df, use_container_width=True)

        if os.path.exists("tarifas_companias.xlsx"):
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            resultados_comp = []
            
            for _, fact in df.iterrows():
                # Añadir la fila de la factura actual
                resultados_comp.append({
                    "Fecha": fact['Fecha'], "Tarifa": "📍 ACTUAL (P+E)", 
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0
                })
                
                # Calcular contra el Excel
                for _, t in df_tarifas.iterrows():
                    coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                            (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                            (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                            (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                            (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    
                    resultados_comp.append({
                        "Fecha": fact['Fecha'], "Tarifa": t.iloc[0], 
                        "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2)
                    })
            
            st.subheader("📊 Comparativa")
            st.dataframe(pd.DataFrame(resultados_comp).sort_values("Ahorro", ascending=False), use_container_width=True)
