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

    # --- LIMPIEZA TOTAL ---
    # Convertimos a minúsculas y quitamos comillas, saltos de línea y retornos de carro
    # Esto deja el texto como una sola cadena continua
    texto_plano = texto_bruto.lower().replace('"', '').replace('\n', ' ').replace('\r', ' ')
    # Normalizamos espacios (convertir múltiples espacios en uno solo)
    texto_plano = ' '.join(texto_plano.split())

    # --- IDENTIFICACIÓN ---
    compania = "Energía XXI" if "energia xxi" in texto_plano else "Genérica"
    
    # --- EXTRACCIÓN DE IMPORTES (P + E) ---
    # Buscamos el número que sigue a "potencia contratada" y "energia consumida"
    # El patrón busca el texto, ignora posibles caracteres basura y captura el número con coma
    patron_pot = r"potencia contratada.*?([\d,.]+)\s*€"
    patron_ene = r"energía consumida.*?([\d,.]+)\s*€"
    
    m_pot = re.search(patron_pot, texto_plano)
    m_ene = re.search(patron_ene, texto_plano)
    
    v_pot = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
    v_ene = float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0
    
    # LA SUMA QUE ME PEDISTE
    suma_potencia_energia = round(v_pot + v_ene, 2)

    # --- RESTO DE DATOS ---
    # Consumos kWh
    consumos = {}
    for tramo, p in [('punta', 'p1'), ('llano', 'p2'), ('valle', 'p3')]:
        m = re.search(rf"{p}.*?([\d,.]+)\s*kwh", texto_plano)
        consumos[tramo] = float(m.group(1).replace(',', '.')) if m else 0.0

    # Potencia contratada (kW)
    m_kw = re.search(r"([\d,.]+)\s*kw", texto_plano)
    pot_kw = float(m_kw.group(1).replace(',', '.')) if m_kw else 0.0

    # Días de consumo
    m_dias = re.search(r"(\d+)\s*días", texto_plano)
    dias = int(m_dias.group(1)) if m_dias else 0

    # Fecha de factura
    m_fecha = re.search(r"emitida el ([\d]+ de \w+ de \d{4}|[\d/]+)", texto_plano)
    fecha = m_fecha.group(1) if m_fecha else "No encontrada"

    return {
        "Compañía": compania,
        "Fecha": fecha,
        "Días": dias,
        "Potencia (kW)": pot_kw,
        "Consumo Punta (kWh)": consumos['punta'],
        "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'],
        "Total Real": suma_potencia_energia # <--- Aquí está la suma de Potencia + Energía
    }

# --- APP STREAMLIT ---
st.set_page_config(page_title="Comparador Energía XXI", layout="wide")
st.title("⚡ Extractor Potencia + Energía")
st.info("Este código suma exclusivamente los términos de Potencia y Energía Consumida.")

uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)

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

        # Si existe el Excel, comparamos
        if os.path.exists("tarifas_companias.xlsx"):
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            res_comp = []
            for _, fact in df.iterrows():
                # Añadir actual
                res_comp.append({"Fecha": fact['Fecha'], "Tarifa": "📍 ACTUAL (Pot+Ene)", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})
                # Calcular otras
                for _, t in df_tarifas.iterrows():
                    coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                            (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                            (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                            (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                            (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    res_comp.append({"Fecha": fact['Fecha'], "Tarifa": t.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2)})
            
            st.subheader("📊 Comparativa")
            st.dataframe(pd.DataFrame(res_comp).sort_values("Ahorro", ascending=False), use_container_width=True, hide_index=True)
