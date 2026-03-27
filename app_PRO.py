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

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)

    if es_el_corte_ingles:
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }
        patron_potencia = r'Potencia\s+contratada\s+kW\s+([\d,.]+)'
        match_potencia = re.search(patron_potencia, texto_completo)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_fecha = r'Fecha\s+de\s+Factura:\s*([\d/]+)'
        match_fecha = re.search(patron_fecha, texto_completo)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        patron_dias = r'Días\s+de\s+consumo:\s*(\d+)'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_total = r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€'
        match_total = re.search(patron_total, texto_completo)
        total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0
        excedente = 0.0 

    elif es_endesa_luz:
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else (re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo).group(1) if re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo) else "No encontrada")
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                v = match.group(1).replace(" ", "").replace(".", "").replace(",", ".")
                try: return float(v)
                except: return 0.0
            return 0.0

        total_real = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo) + limpiar_valor_endesa(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo)
        m_punta = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_llano = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_valle = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        excedente = 0.0

    elif es_repsol:
        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)
        m_consumo_gen = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {'punta': float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        match_potencia = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        match_dias = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        match_periodo = re.search(r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = match_periodo.group(2) if match_periodo else "No encontrada"
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0, 'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0, 'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0}
        total_real = (float(re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0) + (float(re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0)
        excedente = 0.0
    else:
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia = 0.0
        fecha = "No encontrada"
        dias = 0
        total_real = 0.0
        excedente = 0.0

    return {"Fecha": fecha, "Días": dias, "Potencia (kW)": potencia, "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'], "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente, "Total Real": round(total_real, 2)}

# --- CONFIGURACIÓN DE LA APP ---
st.set_page_config(page_title="Energy App Pro", layout="wide")

# CSS Personalizado: Fondos oscuros/verdes y colores de ahorro
st.markdown("""
    <style>
    .stApp { background-color: #0e1117; color: #ffffff; }
    [data-testid="stHeader"] { background: rgba(0,0,0,0); }
    
    /* Tarjetas de resultados principales en VERDE OSCURO */
    .metric-container {
        background-color: #064e3b; /* Verde bosque oscuro */
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #059669;
        margin-bottom: 20px;
    }
    .metric-label { color: #d1fae5; font-size: 0.9rem; font-weight: bold; text-transform: uppercase; }
    .metric-value { color: #ffffff; font-size: 1.8rem; font-weight: 800; }

    /* Contenedor de la tabla */
    .table-box { background-color: #161b22; padding: 15px; border-radius: 10px; }
    
    /* Estilos de texto para Ahorro */
    .txt-ahorro-pos { color: #10b981 !important; font-weight: bold; }
    .txt-ahorro-neg { color: #f87171 !important; font-weight: bold; }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ Energy Savings Advisor")
st.markdown("---")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"Archivo de tarifas '{excel_path}' no encontrado.")
else:
    with st.sidebar:
        st.header("Configuración")
        uploaded_files = st.file_uploader("Subir PDFs", type="pdf", accept_multiple_files=True)

    if uploaded_files:
        datos_facturas = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos_facturas.append(res)
            except Exception as e: st.error(f"Error en {f.name}: {e}")

        if datos_facturas:
            df_resumen = pd.DataFrame(datos_facturas)
            with st.expander("📝 Datos Extraídos (Editar si es necesario)"):
                df_resumen = st.data_editor(df_resumen, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados = []

            for _, fact in df_resumen.iterrows():
                resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})

                for _, tarifa in df_tarifas.iterrows():
                    try:
                        nombre = tarifa.iloc[0]
                        p1, p2, c_p, c_l, c_v, exc = pd.to_numeric(tarifa.iloc[1:7], errors='coerce')
                        coste = (fact['Días'] * p1 * fact['Potencia (kW)']) + (fact['Días'] * p2 * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * c_p) + (fact['Consumo Llano (kWh)'] * c_l) + \
                                (fact['Consumo Valle (kWh)'] * c_v) - (fact['Excedente (kWh)'] * exc)
                        ahorro = fact['Total Real'] - coste
                        resultados.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre, "Coste (€)": round(coste, 2), "Ahorro": round(ahorro, 2)})
                    except: continue

            df_comp = pd.DataFrame(resultados).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            ranking = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            # --- HEADER TIPO APP (VERDE OSCURO) ---
            if not ranking.empty:
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"""<div class="metric-container"><div class="metric-label">Mejor Opción</div><div class="metric-value">{ranking.iloc[0]['Compañía/Tarifa']}</div></div>""", unsafe_allow_html=True)
                with col2:
                    st.markdown(f"""<div class="metric-container"><div class="metric-label">Ahorro Total Estimado</div><div class="metric-value">+{round(ranking.iloc[0]['Ahorro'], 2)} €</div></div>""", unsafe_allow_html=True)

            # --- TABLA COMPARATIVA ---
            st.subheader("📊 Comparativa de Mercado")
            
            # Función para aplicar colores a la columna Ahorro
            def color_ahorro(val):
                if isinstance(val, str): return ""
                if val > 0: return 'color: #10b981'
                if val < 0: return 'color: #f87171'
                return ""

            # Formatear el Ahorro para que sea string con el signo +
            df_display = df_comp.copy()
            df_display['Ahorro'] = df_display['Ahorro'].apply(lambda x: f"+{x} €" if x > 0 else f"{x} €")
            
            # Mostramos el DataFrame (Streamlit aplica el estilo dark automáticamente)
            st.dataframe(df_display, use_container_width=True, hide_index=True)

            # Descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Comparativa')
            
            st.download_button("📥 DESCARGAR INFORME EXCEL", data=buffer.getvalue(), file_name="analisis_ahorro.xlsx", use_container_width=True)
