import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def limpiar_y_convertir(valor_str):
    """Convierte un string tipo '13,17' o ' 7,98 ' en float de forma segura."""
    if not valor_str:
        return 0.0
    try:
        # Quitamos espacios, comas de miles (si las hubiera) y cambiamos coma decimal por punto
        limpio = valor_str.strip().replace('.', '').replace(',', '.')
        return float(limpio)
    except:
        return 0.0

def extraer_datos_factura(pdf_path):
    texto_bruto = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_bruto += pagina.extract_text() + "\n"

    # Normalización inicial para evitar saltos de línea entre el texto y el número
    texto_normalizado = texto_bruto.replace('"', '').replace('\n', ' ').replace('\r', ' ')
    texto_normalizado = ' '.join(texto_normalizado.split())

    # --- EXTRACCIÓN DE IMPORTES (Suma Potencia + Energía) ---
    # Buscamos: "Por potencia contratada" -> cualquier cosa -> número con coma -> €
    patron_pot = r"potencia contratada.*?([\d,.]+)\s*€"
    patron_ene = r"energía consumida.*?([\d,.]+)\s*€"
    
    m_pot = re.search(patron_pot, texto_normalizado, re.IGNORECASE)
    m_ene = re.search(patron_ene, texto_normalizado, re.IGNORECASE)
    
    # Usamos la función de limpieza segura para evitar el "float error"
    v_pot = limpiar_y_convertir(m_pot.group(1)) if m_pot else 0.0
    v_ene = limpiar_y_convertir(m_ene.group(1)) if m_ene else 0.0
    
    total_interes = round(v_pot + v_ene, 2)

    # --- CONSUMOS kWh ---
    consumos = {}
    for tramo, p in [('punta', 'P1'), ('llano', 'P2'), ('valle', 'P3')]:
        m = re.search(rf"{p}.*?([\d,.]+)\s*kWh", texto_normalizado, re.IGNORECASE)
        consumos[tramo] = limpiar_y_convertir(m.group(1)) if m else 0.0

    # --- OTROS DATOS ---
    m_kw = re.search(r"([\d,.]+)\s*kW", texto_normalizado)
    potencia_kw = limpiar_y_convertir(m_kw.group(1)) if m_kw else 0.0
    
    m_dias = re.search(r"(\d+)\s*días", texto_normalizado, re.IGNORECASE)
    dias = int(m_dias.group(1)) if m_dias else 0
    
    m_fecha = re.search(r"emitida el ([\d/]+|[\d]+\s+de\s+\w+\s+de\s+\d{4})", texto_normalizado, re.IGNORECASE)
    fecha = m_fecha.group(1) if m_fecha else "No encontrada"

    return {
        "Compañía": "Energía XXI" if "energia xxi" in texto_normalizado.lower() else "Otra",
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
st.title("⚡ Extractor Potencia + Energía (Sin errores de Float)")

if not os.path.exists("tarifas_companias.xlsx"):
    st.error("Error: Sube el archivo 'tarifas_companias.xlsx' al mismo directorio.")
else:
    uploaded_files = st.file_uploader("Sube tus PDFs", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        datos_list = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos_list.append(res)
            except Exception as e:
                st.error(f"Error procesando {f.name}: {e}")

        if datos_list:
            df = pd.DataFrame(datos_list)
            st.subheader("1. Datos Extraídos (Suma P+E)")
            st.dataframe(df, use_container_width=True)

            # Comparativa
            df_tarifas = pd.read_excel("tarifas_companias.xlsx")
            res_comp = []
            for _, fact in df.iterrows():
                res_comp.append({"Fecha": fact['Fecha'], "Tarifa": "📍 ACTUAL (P+E)", "Coste (€)": fact['Total Real (P+E)'], "Ahorro": 0.0})
                
                for _, t in df_tarifas.iterrows():
                    coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + \
                            (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                            (fact['Consumo Punta (kWh)'] * t.iloc[3]) + \
                            (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                            (fact['Consumo Valle (kWh)'] * t.iloc[5])
                    res_comp.append({"Fecha": fact['Fecha'], "Tarifa": t.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real (P+E)'] - coste, 2)})
            
            st.subheader("2. Comparativa vs Mercado")
            st.dataframe(pd.DataFrame(res_comp).sort_values("Ahorro", ascending=False), use_container_width=True, hide_index=True)
