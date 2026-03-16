import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
from fpdf import FPDF

def generar_pdf_ahorro(df_resumen, df_comparativo, mejor_cia, ahorro_anual):
    pdf = FPDF()
    pdf.add_page()
    
    # Configuración de página y título
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "INFORME DE AHORRO ENERGÉTICO", ln=True, align='C')
    pdf.ln(5)
    
    # 1. DATOS LEÍDOS DE LAS FACTURAS
    pdf.set_font("Arial", 'B', 12)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(0, 10, "1. Datos extraídos de tus facturas", ln=True, fill=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", 'B', 9)
    # Encabezados tabla datos
    pdf.cell(35, 8, "Fecha", 1)
    pdf.cell(25, 8, "Potencia", 1)
    pdf.cell(30, 8, "Punta (kWh)", 1)
    pdf.cell(30, 8, "Llano (kWh)", 1)
    pdf.cell(30, 8, "Valle (kWh)", 1)
    pdf.cell(30, 8, "Total Real", 1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    for _, fila in df_resumen.iterrows():
        pdf.cell(35, 7, str(fila['Fecha']), 1)
        pdf.cell(25, 7, f"{fila['Potencia (kW)']} kW", 1)
        pdf.cell(30, 7, str(fila['Consumo Punta (kWh)']), 1)
        pdf.cell(30, 7, str(fila['Consumo Llano (kWh)']), 1)
        pdf.cell(30, 7, str(fila['Consumo Valle (kWh)']), 1)
        pdf.cell(30, 7, f"{fila['Total Real']} e", 1, ln=True)
    
    pdf.ln(10)

    # 2. COMPARATIVA CON LA MEJOR COMPAÑÍA
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"2. Ahorro mensual con {mejor_cia}", ln=True, fill=True)
    pdf.ln(2)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(60, 8, "Periodo", 1)
    pdf.cell(45, 8, "Coste Actual", 1)
    pdf.cell(45, 8, f"Coste {mejor_cia}", 1)
    pdf.cell(40, 8, "Ahorro", 1, ln=True)
    
    pdf.set_font("Arial", '', 9)
    # Filtrar solo la mejor compañía para la tabla de ahorro mensual
    df_mejor = df_comparativo[df_comparativo["Compañía/Tarifa"] == mejor_cia]
    
    for _, fila in df_mejor.iterrows():
        coste_actual = df_comparativo[(df_comparativo["Mes/Fecha"] == fila["Mes/Fecha"]) & 
                                     (df_comparativo["Compañía/Tarifa"] == "📍 TU FACTURA ACTUAL")]["Coste (€)"].values[0]
        pdf.cell(60, 7, str(fila['Mes/Fecha']), 1)
        pdf.cell(45, 7, f"{coste_actual} e", 1)
        pdf.cell(45, 7, f"{fila['Coste (€)']} e", 1)
        pdf.set_font("Arial", 'B', 9)
        pdf.cell(40, 7, f"{fila['Ahorro']} e", 1, ln=True)
        pdf.set_font("Arial", '', 9)

    pdf.ln(10)

    # 3. TOTALES ANUALES
    pdf.set_fill_color(200, 255, 200)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 15, f"ESTIMACIÓN DE AHORRO ANUAL: {round(ahorro_anual, 2)} Euros", 1, ln=True, align='C', fill=True)
    
    return pdf.output(dest='S').encode('latin-1')

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)

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
        patron_dias = r'(\d+)\s*días'
        match_dias = re.search(patron_dias, texto_completo)
        dias = int(match_dias.group(1)) if match_dias else 0
        patron_excedente = r'Valoración\s+excedentes\s*(?:-?\d+[\d,.]*\s*€/kWh)?\s*(-?\d+[\d,.]*)\s*kWh'
        match_excedente = re.search(patron_excedente, texto_completo, re.IGNORECASE)
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
        "Total Real": total_real
    }

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
                    "Ahorro": 0.0,
                    "Dias_Factura": fact['Días']
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
                            "Ahorro": round(ahorro, 2),
                            "Dias_Factura": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])

            df_solo_ofertas = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index()
            ranking_total = ranking_total.sort_values(by="Ahorro", ascending=False)

            st.divider()
            
            if not ranking_total.empty:
                mejor_opcion_res = ranking_total.iloc[0]
                
                if mejor_opcion_res['Ahorro'] > 0.01:
                    st.subheader("🏆 Resultado del Análisis")
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        st.success(f"Mejor opción: **{mejor_opcion_res['Compañía/Tarifa']}**")
                    with c2:
                        st.metric(label="Ahorro Total en facturas subidas", value=f"{round(mejor_opcion_res['Ahorro'], 2)} €")
                    with c3:
                        dias_totales = df_resumen_pdfs['Días'].sum()
                        ahorro_anual_est = (mejor_opcion_res['Ahorro'] / dias_totales) * 365 if dias_totales > 0 else 0
                        st.metric(label="Estimado Ahorro Anual", value=f"{round(ahorro_anual_est, 2)} €")
                    
                    # Generación de PDF con todos los datos solicitados
                    pdf_bytes = generar_pdf_ahorro(
                        df_resumen_pdfs, 
                        df_comp, 
                        mejor_opcion_res['Compañía/Tarifa'], 
                        ahorro_anual_est
                    )
                    
                    st.download_button(
                        label="📥 Descargar Informe Detallado en PDF",
                        data=pdf_bytes,
                        file_name="informe_ahorro_completo.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )
                else:
                    st.info("✅ **Tu compañía actual parece ser la más económica.**")

            st.subheader("📊 Comparativa Detallada por Factura")
            st.dataframe(
                df_comp.drop(columns=['Dias_Factura'], errors='ignore'),
                column_config={
                    "Mes/Fecha": "📅 Periodo",
                    "Compañía/Tarifa": "🏢 Proveedor",
                    "Coste (€)": st.column_config.NumberColumn("Coste Estimado", format="%.2f €"),
                    "Ahorro": st.column_config.NumberColumn("Ahorro vs Actual", format="%.2f €")
                },
                hide_index=True, use_container_width=True
            )
