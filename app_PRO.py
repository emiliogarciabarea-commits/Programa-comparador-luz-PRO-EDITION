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

    # --- LIMPIEZA RADICAL (Elimina el formato de "tabla sucia") ---
    # Quitamos comillas y convertimos todo a una sola línea de texto sin saltos
    texto_limpio = texto_completo.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    # Normalizamos espacios: si hay 10 espacios, dejamos solo uno
    texto_limpio = ' '.join(texto_limpio.split())

    # --- DETECCIÓN DE COMPAÑÍA ---
    if "energia xxi" in texto_limpio.lower():
        compania = "Energía XXI"
    elif "octopus" in texto_limpio.lower():
        compania = "Octopus Energy"
    else:
        compania = "Genérica / Desconocida"

    # --- EXTRACCIÓN DE IMPORTES (LO QUE TE INTERESA) ---
    # Buscamos el número decimal que sigue a las palabras clave
    # El patrón ignora cualquier símbolo entre la palabra y el número (como comas o espacios)
    patron_pot = r"potencia contratada\s*[\s,]*\s*([\d,.]+)\s*€"
    patron_ene = r"energía consumida\s*[\s,]*\s*([\d,.]+)\s*€"
    
    m_pot = re.search(patron_pot, texto_limpio, re.IGNORECASE)
    m_ene = re.search(patron_ene, texto_limpio, re.IGNORECASE)
    
    v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
    v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
    
    # SUMA EXCLUSIVA DE LOS DOS TÉRMINOS
    total_interes = round(v_pot + v_ene, 2)

    # --- EXTRACCIÓN DE CONSUMOS (P1, P2, P3) ---
    consumos = {}
    for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
        # En Energía XXI suelen venir como P1: 100 kWh o P1 100 kWh
        m = re.search(rf"{p}[:\s]*([\d,.]+)\s*kWh", texto_limpio, re.IGNORECASE)
        consumos[tramo] = float(m.group(1).replace(',', '.')) if m else 0.0

    # --- OTROS DATOS NECESARIOS ---
    # Potencia en kW (ej: 4,6 kW)
    m_kw = re.search(r"([\d,.]+)\s*kW", texto_limpio)
    potencia_kw = float(m_kw.group(1).replace(',', '.')) if m_kw else 0.0
    
    # Días (ej: 28 días)
    m_dias = re.search(r"(\d+)\s*días", texto_limpio, re.IGNORECASE)
    dias = int(m_dias.group(1)) if m_dias else 0
    
    # Fecha (buscamos 'emitida el dd de mmm de aaaa')
    m_fecha = re.search(r"emitida el ([\d/]+|[\d]+\s+de\s+\w+\s+de\s+\d{4})", texto_limpio, re.IGNORECASE)
    fecha = m_fecha.group(1) if m_fecha else "No encontrada"

    return {
        "Compañía": compania,
        "Fecha": fecha,
        "Días": dias,
        "Potencia (kW)": potencia_kw,
        "Consumo Punta (kWh)": consumos['punta'],
        "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'],
        "Total Real (P+E)": total_interes
    }

# --- CÓDIGO STREAMLIT ---
st.set_page_config(page_title="Comparador Energía XXI", layout="wide")
st.title("⚡ Extractor de Términos (Solo Potencia + Energía)")

if not os.path.exists("tarifas_companias.xlsx"):
    st.error("Falta el archivo 'tarifas_companias.xlsx'")
else:
    uploaded_files = st.file_uploader("Sube tus facturas Energía XXI", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        datos_lista = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos_lista.append(res)
            except Exception as e:
                st.error(f"Error procesando {f.name}: {e}")

        if datos_lista:
            df = pd.DataFrame(datos_lista)
            st.subheader("1. Datos Extraídos de la Factura")
            st.write("El valor 'Total Real (P+E)' es la suma directa de la Potencia y la Energía.")
            st.dataframe(df, use_container_width=True)

            # Comparativa con Excel
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            comparativa = []

            for _, fact in df.iterrows():
                # Añadir la actual
                comparativa.append({
                    "Fecha": fact['Fecha'], "Compañía": "📍 TU FACTURA (Pot+Ene)",
                    "Coste (€)": fact['Total Real (P+E)'], "Ahorro (€)": 0.0
                })
                
                for _, t in df_tarifas.iterrows():
                    # Cálculo basado en los precios del Excel
                    coste_simulado = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                                     (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                                     (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                                     (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                                     (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    
                    comparativa.append({
                        "Fecha": fact['Fecha'], "Compañía": t.iloc[0],
                        "Coste (€)": round(coste_simulado, 2),
                        "Ahorro (€)": round(fact['Total Real (P+E)'] - coste_simulado, 2)
                    })

            st.subheader("2. Comparativa de Ahorro")
            df_comp = pd.DataFrame(comparativa).sort_values(by=["Fecha", "Ahorro (€)"], ascending=[True, False])
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
