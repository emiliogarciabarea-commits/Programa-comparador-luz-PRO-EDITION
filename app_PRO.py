import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

# --- LÓGICA DE EXTRACCIÓN (SE MANTIENE IGUAL) ---
def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

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
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else "No encontrada"
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
        val_potencia = limpiar_valor_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo)
        val_energia = limpiar_valor_endesa(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo)
        total_real = val_potencia + val_energia
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
        valor_consumo = float(m_consumo_gen.group(1).replace(',', '.')) if m_consumo_gen else 0.0
        consumos = {'punta': valor_consumo, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        patron_potencia = r'Potencia\s+punta:\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_dias = r'Potencia\s+facturada.*?(\d+)\s+días'
        match_dias = re.search(patron_dias, texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_periodo = r'PERIODO\s+DE\s+FACTURACIÓN:?.*?(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})'
        match_periodo = re.search(patron_periodo, texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = match_periodo.group(2) if match_periodo else "No encontrada"
        m_punta = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_llano = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_valle = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        m_imp_potencia = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_energia = re.search(r'Total\s+[\d,.]+\s*kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_imp_potencia.group(1).replace(',', '.')) if m_imp_potencia else 0.0) + (float(m_imp_energia.group(1).replace(',', '.')) if m_imp_energia else 0.0)
        excedente = 0.0

    else:
        patrones_consumo = {
            'punta': [r'Consumo\s+en\s+P1:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh'],
            'llano': [r'Consumo\s+en\s+P2:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh'],
            'valle': [r'Consumo\s+en\s+P3:?\s*([\d,.]+)\s*kWh', r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh']
        }
        consumos = {}
        for tramo, patrones in patrones_consumo.items():
            consumos[tramo] = 0.0
            for patron in patrones:
                match = re.search(patron, texto_completo, re.IGNORECASE)
                if match:
                    consumos[tramo] = float(match.group(1).replace(',', '.'))
                    break
        patron_potencia = r'(?:Potencia\s+contratada(?:\s+en\s+punta-llano|\s+P1)?):\s*([\d,.]+)\s*kW'
        match_potencia = re.search(patron_potencia, texto_completo, re.IGNORECASE)
        potencia = float(match_potencia.group(1).replace(',', '.')) if match_potencia else 0.0
        patron_fecha = r'(?:emitida\s+el|Fecha\s+de\s+emisión:)\s*([\d/]+\s*(?:de\s+\w+\s+de\s+)?\d{2,4})'
        match_fecha = re.search(patron_fecha, texto_completo, re.IGNORECASE)
        fecha = match_fecha.group(1) if match_fecha else "No encontrada"
        if es_naturgy:
            match_dias_nat = re.search(r'Término\s+potencia\s+P1.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
            dias = int(match_dias_nat.group(1)) if match_dias_nat else 0
        else:
            match_dias = re.search(r'(\d+)\s*días', texto_completo)
            dias = int(match_dias.group(1)) if match_dias else 0
        match_excedente = re.search(r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh', texto_completo, re.IGNORECASE)
        excedente = abs(float(match_excedente.group(1).replace(',', '.'))) if match_excedente else 0.0
        es_xxi = re.search(r'Comercializadora\s+de\s+Referencia\s+Energética\s+por\s+XXI|Energía\s+XXI', texto_completo, re.IGNORECASE)
        if es_xxi:
            m_pot = re.search(r'por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            m_ene = re.search(r'por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = (float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0) + (float(m_ene.group(1).replace(',', '.')) if m_ene else 0.0)
        else:
            match_total = re.search(r'(?:Subtotal|Importe\s+total|Total\s+factura)\s*:?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
            total_real = float(match_total.group(1).replace(',', '.')) if match_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- CONFIGURACIÓN DE INTERFAZ APP ---
st.set_page_config(page_title="EnergySave Pro", layout="wide", page_icon="⚡")

# Sidebar - Menú lateral
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/2731/2731636.png", width=100)
    st.title("EnergySave Pro")
    st.info("Sube tus facturas en PDF para analizar el ahorro potencial.")
    uploaded_files = st.file_uploader("📂 Cargar Facturas", type="pdf", accept_multiple_files=True)
    st.divider()
    st.caption("v2.1 - Comparador Inteligente")

# Cuerpo Principal
st.title("⚡ Comparador de Facturas Eléctricas")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"⚠️ Error Crítico: No se encuentra el archivo '{excel_path}'.")
else:
    if not uploaded_files:
        st.warning("Por favor, carga una o más facturas en la barra lateral para comenzar.")
        # Dashboard vacío de bienvenida
        c1, c2, c3 = st.columns(3)
        c1.metric("Facturas cargadas", "0")
        c2.metric("Mejor Tarifa", "-")
        c3.metric("Ahorro Medio", "0.00 €")
    else:
        # Procesamiento
        datos_facturas = []
        for uploaded_file in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(uploaded_file.read()))
                res['Archivo'] = uploaded_file.name
                datos_facturas.append(res)
            except Exception as e:
                st.sidebar.error(f"Error en {uploaded_file.name}")

        if datos_facturas:
            # PESTAÑAS - Organizan la App
            tab1, tab2, tab3 = st.tabs(["📊 Análisis y Ahorro", "🔍 Datos Extraídos", "📥 Descargas"])

            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            # Cálculos (igual que tu código original)
            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'], "Ahorro": 0.0, "Dias_Factura": fact['Días']
                })
                for index, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1, c_pot2, d_punta, e_llano, f_valle, g_excedente = [pd.to_numeric(tarifa.iloc[i], errors='coerce') for i in range(1, 7)]
                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + \
                                         (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + \
                                         (fact['Consumo Punta (kWh)'] * d_punta) + \
                                         (fact['Consumo Llano (kWh)'] * e_llano) + \
                                         (fact['Consumo Valle (kWh)'] * f_valle) - \
                                         (fact['Excedente (kWh)'] * g_excedente)
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(fact['Total Real'] - coste_estimado, 2),
                            "Dias_Factura": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            ranking_total = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            # --- CONTENIDO PESTAÑA 1: DASHBOARD ---
            with tab1:
                if not ranking_total.empty:
                    mejor_opcion = ranking_total.iloc[0]
                    col1, col2, col3 = st.columns(3)
                    col1.metric("Mejor Compañía", mejor_opcion['Compañía/Tarifa'])
                    col2.metric("Ahorro Total", f"{round(mejor_opcion['Ahorro'], 2)} €", delta="Optimizado")
                    col3.metric("Facturas Analizadas", len(df_resumen_pdfs))
                    
                    st.divider()
                    st.subheader("📋 Comparativa de Costes por Factura")
                    st.dataframe(df_comp.drop(columns=['Dias_Factura'], errors='ignore'), use_container_width=True, hide_index=True)
                else:
                    st.error("No se pudieron calcular ofertas con los datos actuales.")

            # --- CONTENIDO PESTAÑA 2: EDICIÓN ---
            with tab2:
                st.subheader("🛠️ Revisión de Datos del PDF")
                st.write("Si el sistema no leyó correctamente algún dato, puedes corregirlo aquí directamente:")
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            # --- CONTENIDO PESTAÑA 3: DESCARGAS ---
            with tab3:
                st.subheader("📄 Generación de Reporte")
                
                buffer_excel = io.BytesIO()
                with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                    df_comp.to_excel(writer, index=False, sheet_name='Detalle Comparativa')
                    ranking_total.to_excel(writer, index=False, sheet_name='Ranking Ahorro')
                    df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos Facturas Originales')

                st.download_button(
                    label="💾 Descargar Estudio de Ahorro (Excel)",
                    data=buffer_excel.getvalue(),
                    file_name="estudio_energetico_pro.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
                st.success("El informe está listo para ser descargado.")
