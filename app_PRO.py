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

    # --- LIMPIEZA AGRESIVA PARA ENERGÍA XXI ---
    # Quitamos comillas y convertimos saltos de línea en espacios para que sea una sola línea de texto
    texto_limpio = texto_completo.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    
    # --- DETECCIÓN DE COMPAÑÍA ---
    es_xxi = re.search(r'Energía\s+XXI', texto_limpio, re.I)
    
    compania = "Genérica"
    total_real = 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia, dias, fecha, excedente = 0.0, 0, "No encontrada", 0.0

    if es_xxi:
        compania = "Energía XXI"
        
        # 1. SUMA DE POTENCIA + ENERGÍA (IGNORANDO EL RESTO)
        # Buscamos el número (ej: 7,98) que sigue a los conceptos clave
        m_pot = re.search(r'potencia\s+contratada\s*,\s*([\d,.]+)\s*€', texto_limpio, re.I)
        m_ene = re.search(r'energía\s+consumida\s*,\s*([\d,.]+)\s*€', texto_limpio, re.I)
        
        v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
        
        # El "Total Real" ahora es estrictamente la suma de estos dos términos
        total_real = v_pot + v_ene

        # 2. CONSUMOS kWh (P1, P2, P3)
        for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
            m = re.search(rf'{p}:?\s*([\d,.]+)\s*kWh', texto_limpio, re.I)
            if m: consumos[tramo] = float(m.group(1).replace(',', '.'))

        # 3. OTROS DATOS (kW, Días, Fecha)
        m_kw = re.search(r'([\d,.]+)\s*kW', texto_limpio)
        potencia = float(m_kw.group(1).replace(',', '.')) if m_kw else 0.0
        
        m_d = re.search(r'\((\d+)\s*días\)', texto_limpio) or re.search(r'(\d+)\s*días', texto_limpio)
        dias = int(m_d.group(1)) if m_d else 0
        
        m_f = re.search(r'Fecha\s+de\s+cargo:\s*([\d/]+)', texto_limpio, re.I)
        fecha = m_f.group(1) if m_f else "No encontrada"

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Comparador", layout="wide")
st.title("⚡ Extractor Potencia + Energía (Energía XXI)")

uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

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

        # Cargar tarifas y comparar
        if os.path.exists("tarifas_companias.xlsx"):
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            res_comp = []
            
            for _, fact in df.iterrows():
                # Fila de la factura actual del usuario
                res_comp.append({
                    "Fecha": fact['Fecha'], "Tarifa": "📍 TU FACTURA (Pot+Ene)", 
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0
                })
                
                # Comparar con las del Excel
                for _, t in df_tarifas.iterrows():
                    # Cálculo: (Días * Pot_P1 * kW) + (Días * Pot_P2 * kW) + (kWh_P1 * Precio_P1) + ...
                    coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                            (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                            (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                            (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                            (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    
                    res_comp.append({
                        "Fecha": fact['Fecha'], "Tarifa": t.iloc[0], 
                        "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2)
                    })
            
            st.subheader("📊 Comparativa de Ahorro")
            df_final = pd.DataFrame(res_comp).sort_values(by=["Fecha", "Ahorro"], ascending=[True, False])
            st.dataframe(df_final, use_container_width=True, hide_index=True)
