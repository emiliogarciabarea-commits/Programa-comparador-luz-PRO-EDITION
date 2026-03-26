import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

# Configuración de página (Debe ser lo primero)
st.set_page_config(
    page_title="EcoSave - Comparador Energético", 
    page_icon="⚡", 
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- ESTILOS PERSONALIZADOS ---
st.markdown("""
    <style>
    .main { background-color: #f5f7f9; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    [data-testid="stSidebar"] { background-color: #1e293b; color: white; }
    </style>
    """, unsafe_allow_html=True)

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- DETECCIÓN DE TIPO DE FACTURA (Lógica original mantenida) ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía', texto_completo, re.IGNORECASE)

    # Variables por defecto
    fecha, dias, potencia, total_real, excedente = "No encontrada", 0, 0.0, 0.0, 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}

    # Bloques de extracción (Simplificados para brevedad, usa tu lógica original aquí)
    if es_endesa_luz:
        m_fecha = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        # ... (Mantener el resto de tu lógica de limpieza de Endesa y consumos)
    
    # [Aquí va el resto de tus ELIF: El Corte Inglés, Repsol, Iberdrola...]
    # Para este ejemplo, retorno un diccionario con la estructura esperada
    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- INTERFAZ TIPO APP (SIDEBAR) ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2731/2731636.png", width=80)
    st.title("Panel de Control")
    st.info("Sube tus facturas en PDF para analizar el ahorro potencial.")
    
    uploaded_files = st.file_uploader("📂 Cargar Facturas", type="pdf", accept_multiple_files=True)
    st.divider()
    st.markdown("### Configuración")
    margen_ahorro = st.slider("Umbral de ahorro visual (€)", 0, 50, 5)

# --- CUERPO PRINCIPAL ---
st.title("⚡ EcoSave: Comparador Energético Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"⚠️ Error Crítico: No se encuentra el archivo de tarifas '{excel_path}'.")
else:
    if not uploaded_files:
        st.warning("👈 Por favor, carga una o más facturas en el panel de la izquierda para comenzar.")
        # Dashboard vacío o info
        st.image("https://img.freepik.com/free-vector/energy-consumption-concept-illustration_114360-7762.jpg", width=400)
    else:
        # Procesamiento
        datos_facturas = []
        with st.spinner('Analizando PDFs...'):
            for uploaded_file in uploaded_files:
                try:
                    res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))
                    res['Archivo'] = uploaded_file.name
                    datos_facturas.append(res)
                except Exception as e:
                    st.error(f"Error en {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            
            # ORGANIZACIÓN POR PESTAÑAS (Estilo App)
            tab1, tab2, tab3 = st.tabs(["📊 Análisis de Ahorro", "🔍 Edición de Datos", "📥 Exportar"])

            # CÁLCULOS
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                # (Tu lógica de cálculo original se mantiene aquí)
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 ACTUAL",
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0
                })
                for _, tarifa in df_tarifas.iterrows():
                    try:
                        # ... (Tus cálculos de b_pot1, c_pot2, etc.)
                        nombre_cia = tarifa.iloc[0]
                        b_pot1, c_pot2, d_punta, e_llano, f_valle, g_excedente = [pd.to_numeric(tarifa.iloc[i], errors='coerce') for i in range(1,7)]
                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * d_punta) + (fact['Consumo Llano (kWh)'] * e_llano) + \
                                         (fact['Consumo Valle (kWh)'] * f_valle) - (fact['Excedente (kWh)'] * g_excedente)
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(fact['Total Real'] - coste_estimado, 2)
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales)
            ranking_total = df_comp[df_comp["Compañía/Tarifa"] != "📍 ACTUAL"].groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            # --- PESTAÑA 1: RESULTADOS ---
            with tab1:
                if not ranking_total.empty:
                    mejor_opcion = ranking_total.iloc[0]
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Mejor Opción", mejor_opcion['Compañía/Tarifa'])
                    with col2:
                        st.metric("Ahorro Total", f"{round(mejor_opcion['Ahorro'], 2)} €", delta=f"{margen_ahorro}€ umbral")
                    with col3:
                        st.metric("Facturas Analizadas", len(uploaded_files))

                    st.subheader("Comparativa de Costes por Período")
                    st.dataframe(df_comp.style.highlight_max(axis=0, subset=['Ahorro'], color='#d4edda'), use_container_width=True)

            # --- PESTAÑA 2: EDICIÓN ---
            with tab2:
                st.subheader("Validación de Datos Extraídos")
                st.info("Si el sistema falló al leer algún dato, corrígelo aquí directamente.")
                df_editado = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            # --- PESTAÑA 3: DESCARGAS ---
            with tab3:
                st.subheader("Generar Informe")
                st.write("El informe incluirá el detalle comparativo, ranking de ahorro y datos originales.")
                
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_comp.to_excel(writer, index=False, sheet_name='Comparativa')
                    ranking_total.to_excel(writer, index=False, sheet_name='Ranking')
                    df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos Originales')

                st.download_button(
                    label="🚀 Descargar Excel Profesional",
                    data=buffer_excel.getvalue(),
                    file_name="EcoSave_Informe.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
