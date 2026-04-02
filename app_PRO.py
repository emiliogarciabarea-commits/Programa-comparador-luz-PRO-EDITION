import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_factura(pdf_path):
    texto_bruto = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_bruto += pagina.extract_text() + "\n"

    # --- LIMPIEZA AGRESIVA (Clave para Energía XXI) ---
    # Quitamos comillas, saltos de línea y normalizamos espacios
    texto_limpio = texto_bruto.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    texto_limpio = ' '.join(texto_limpio.split()) # Elimina espacios múltiples

    # --- EXTRACCIÓN DE IMPORTES (SOLO POTENCIA + ENERGÍA) ---
    # Buscamos el número que sigue a las frases clave
    # La regex busca la frase, ignora basura intermedia y captura el número con coma/punto
    patron_pot = r"Por potencia contratada\s*[\s,]*\s*([\d,.]+)\s*€"
    patron_ene = r"Por energía consumida\s*[\s,]*\s*([\d,.]+)\s*€"
    
    m_pot = re.search(patron_pot, texto_limpio, re.IGNORECASE)
    m_ene = re.search(patron_ene, texto_limpio, re.IGNORECASE)
    
    v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
    v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
    
    # Esta es la suma que quieres:
    total_interes = round(v_pot + v_ene, 2)

    # --- CONSUMOS (P1, P2, P3) ---
    consumos = {}
    for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
        # Busca P1, luego cualquier cosa, y luego el número seguido de kWh
        m = re.search(rf"{p}.*?([\d,.]+)\s*kWh", texto_limpio, re.IGNORECASE)
        consumos[tramo] = float(m.group(1).replace(',', '.')) if m else 0.0

    # --- DATOS TÉCNICOS ---
    # Potencia contratada en kW (ej: 3,3 kW)
    m_kw = re.search(r"([\d,.]+)\s*kW", texto_limpio)
    potencia_kw = float(m_kw.group(1).replace(',', '.')) if m_kw else 0.0
    
    # Días (ej: 28 días)
    m_dias = re.search(r"(\d+)\s*días", texto_limpio, re.IGNORECASE)
    dias = int(m_dias.group(1)) if m_dias else 0
    
    # Fecha de emisión
    m_fecha = re.search(r"emitida el ([\d/]+|[\d]+\s+de\s+\w+\s+de\s+\d{4})", texto_limpio, re.IGNORECASE)
    fecha = m_fecha.group(1) if m_fecha else "No encontrada"

    return {
        "Compañía": "Energía XXI" if "energia xxi" in texto_limpio.lower() else "Otra",
        "Fecha": fecha,
        "Días": dias,
        "Potencia (kW)": potencia_kw,
        "Consumo Punta (kWh)": consumos['punta'],
        "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'],
        "Total Real (P+E)": total_interes
    }

# --- INTERFAZ ---
st.set_page_config(page_title="Comparador Energía XXI", layout="wide")
st.title("⚡ Extractor Potencia + Energía")

uploaded_files = st.file_uploader("Sube tus facturas", type="pdf", accept_multiple_files=True)

if uploaded_files:
    resultados = []
    for f in uploaded_files:
        try:
            datos = extraer_datos_factura(io.BytesIO(f.read()))
            datos['Archivo'] = f.name
            resultados.append(datos)
        except Exception as e:
            st.error(f"Error en {f.name}: {e}")

    if resultados:
        df = pd.DataFrame(resultados)
        st.write("### Datos Extraídos")
        st.dataframe(df, use_container_width=True)

        # COMPARACIÓN CON EXCEL
        if os.path.exists("tarifas_companias.xlsx"):
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            res_comp = []
            for _, fact in df.iterrows():
                # Añadir fila actual
                res_comp.append({"Fecha": fact['Fecha'], "Tarifa": "📍 ACTUAL (P+E)", "Coste (€)": fact['Total Real (P+E)'], "Ahorro": 0.0})
                
                for _, t in df_tarifas.iterrows():
                    # Cálculo: (días * precio_pot * kW) + (consumo * precio_ene)
                    coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                            (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                            (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                            (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                            (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    
                    res_comp.append({
                        "Fecha": fact['Fecha'], 
                        "Tarifa": t.iloc[0], 
                        "Coste (€)": round(coste, 2), 
                        "Ahorro": round(fact['Total Real (P+E)'] - coste, 2)
                    })
            
            st.subheader("📊 Comparativa vs Mercado")
            st.dataframe(pd.DataFrame(res_comp).sort_values("Ahorro", ascending=False), use_container_width=True, hide_index=True)
