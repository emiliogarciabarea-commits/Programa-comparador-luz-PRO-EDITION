import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os
from fpdf import FPDF # Asegúrate de añadir fpdf a tu requirements.txt

def generar_pdf_ahorro(periodo, actual_coste, mejor_nombre, mejor_coste, ahorro_periodo, ahorro_anual):
    pdf = FPDF()
    pdf.add_page()
    
    # Título
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Informe de Optimización Energética", ln=True, align='C')
    pdf.ln(10)
    
    # Resumen
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Análisis para el periodo: {periodo}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"- Coste en tu factura actual: {actual_coste} Euros", ln=True)
    pdf.cell(0, 8, f"- Mejor opcion detectada: {mejor_nombre}", ln=True)
    pdf.cell(0, 8, f"- Coste estimado con la mejor opción: {mejor_coste} Euros", ln=True)
    
    pdf.ln(10)
    pdf.set_fill_color(230, 255, 230)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 12, f"AHORRO EN ESTA FACTURA: {round(ahorro_periodo, 2)} Euros", ln=True, fill=True)
    pdf.set_text_color(0, 128, 0)
    pdf.cell(0, 12, f"ESTIMADO DE AHORRO ANUAL: {round(ahorro_anual, 2)} Euros", ln=True)
    
    return pdf.output(dest='S').encode('latin-1')

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- DETECCIÓN DE TIPO DE FACTURA ---
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
                # Guardamos coste real para PDF
                coste_real_factura = fact['Total Real']
                periodo_factura = fact['Fecha']
                dias_factura = fact['Días']

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
                        st.metric(label="Ahorro en esta subida", value=f"{round(mejor_opcion_res['Ahorro'], 2)} €")
                    with c3:
                        # Cálculo estimado anual: (Ahorro Total / Días totales subidos) * 365
                        dias_totales = df_resumen_pdfs['Días'].sum()
                        ahorro_anual_est = (mejor_opcion_res['Ahorro'] / dias_totales) * 365 if dias_totales > 0 else 0
                        st.metric(label="Estimado Ahorro Anual", value=f"{round(ahorro_anual_est, 2)} €")
                    
                    # Botón para descargar PDF basado en la mejor opción
                    mejor_coste_est = df_solo_ofertas[df_solo_ofertas["Compañía/Tarifa"] == mejor_opcion_res['Compañía/Tarifa']].iloc[0]['Coste (€)']
                    pdf_bytes = generar_pdf_ahorro(
                        df_resumen_pdfs.iloc[0]['Fecha'], 
                        df_resumen_pdfs.iloc[0]['Total Real'],
                        mejor_opcion_res['Compañía/Tarifa'],
                        mejor_coste_est,
                        mejor_opcion_res['Ahorro'],
                        ahorro_anual_est
                    )
                    st.download_button(
                        label="📥 Descargar Informe de Ahorro en PDF",
                        data=pdf_bytes,
                        file_name="informe_ahorro_energetico.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

                else:
                    st.info("✅ **Tu compañía actual parece ser la más económica.**")

            st.subheader("📊 Comparativa Detallada por Factura")
            df_comp["Estado"] = df_comp["Ahorro"].apply(
                lambda x: "🟢 Ahorro" if x > 0.01 else ("⚪ Actual" if abs(x) <= 0.01 else "🔴 Más caro")
            )

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

            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Detalle')
                ranking_total.to_excel(writer, index=False, sheet_name='Ranking')

            st.download_button(
                label="📥 Descargar Excel con todos los datos",
                data=buffer_excel.getvalue(),
                file_name="estudio_ahorro_energetico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
