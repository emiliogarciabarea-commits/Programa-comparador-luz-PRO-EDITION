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
    es_total_energies = re.search(r'TotalEnergies', texto_completo, re.IGNORECASE)
    es_xxi = re.search(r'Energía\s+XXI', texto_completo, re.IGNORECASE)
    es_octopus = re.search(r'octopus\s+energy', texto_completo, re.IGNORECASE)

    compania = "Genérica / Desconocida" 
    total_real = 0.0
    fecha = "No encontrada"
    dias = 0
    potencia = 0.0
    excedente = 0.0
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        if match_cons:
            consumos['punta'] = float(match_cons.group(1).replace(',', '.'))
            consumos['llano'] = float(match_cons.group(2).replace(',', '.'))
            consumos['valle'] = float(match_cons.group(3).replace(',', '.'))
        potencia = float(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo).group(1)) if re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo) else 0
        total_real = float(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)', texto_completo).group(1).replace(',', '.')) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)', texto_completo) else 0.0

    elif es_xxi:
        compania = "Energía XXI"
        # 1. Fecha de Cargo
        m_fecha = re.search(r'Fecha\s+de\s+cargo:\s*([\d]+\s+de\s+\w+\s+de\s+\d{4})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        # 2. Total Real (Suma Potencia + Energía Consumida)
        m_pot = re.search(r'Por\s+potencia\s+contratada\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        m_ene = re.search(r'Por\s+energía\s+consumida\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        if m_pot and m_ene:
            total_real = float(m_pot.group(1).replace(',', '.')) + float(m_ene.group(1).replace(',', '.'))
        else:
            m_total = re.search(r'TOTAL\s+IMPORTE\s+FACTURA\s*([\d,.]+)', texto_completo, re.IGNORECASE)
            total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

        # 3. Resto de datos
        m_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot_val = re.search(r'contratada\s+en\s+punta-llano:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_val.group(1).replace(',', '.')) if m_pot_val else 0.0
        
        # Consumos P1, P2, P3
        m_p1 = re.search(r'Consumo\s+en\s+P1:\s*([\d,.]+)', texto_completo)
        m_p2 = re.search(r'Consumo\s+en\s+P2:\s*([\d,.]+)', texto_completo)
        m_p3 = re.search(r'Consumo\s+en\s+P3:\s*([\d,.]+)', texto_completo)
        consumos['punta'] = float(m_p1.group(1).replace(',', '.')) if m_p1 else 0.0
        consumos['llano'] = float(m_p2.group(1).replace(',', '.')) if m_p2 else 0.0
        consumos['valle'] = float(m_p3.group(1).replace(',', '.')) if m_p3 else 0.0

    elif es_octopus:
        compania = "Octopus Energy"
        m_fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'\((\d+)\s+días\)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_val_pot = re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_val_ene = re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_val_pot.group(1).replace(',', '.')) if m_val_pot else 0.0) + (float(m_val_ene.group(1).replace(',', '.')) if m_val_ene else 0.0)

    elif es_total_energies:
        compania = "TotalEnergies"
        m_fecha = re.search(r'Fecha\s+emisión:\s*([\d.]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        # Lógica simplificada de suma para TotalEnergies
        total_real = 0.0
        for line in texto_completo.split('\n'):
            if "€" in line and any(x in line for x in ["Potencia", "Consumo", "Energía"]):
                vals = re.findall(r'([\d,.]+)\s*€', line)
                if vals: total_real += float(vals[-1].replace('.', '').replace(',', '.'))

    elif es_naturgy:
        compania = "Naturgy"
        fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        dias = int(re.search(r'Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE) else 0
        total_real = float(re.search(r'Subtotal\s*([\d,.]+)', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Subtotal\s*([\d,.]+)', texto_completo, re.IGNORECASE) else 0.0

    elif es_endesa_luz:
        compania = "Endesa Energía"
        fecha = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE) else "No encontrada"
        p_pot = re.search(r'Potencia\s+\.+\s*([\d,.]+)', texto_completo)
        p_ene = re.search(r'Energía\s+\.+\s*([\d,.]+)', texto_completo)
        total_real = (float(p_pot.group(1).replace(',', '.')) if p_pot else 0.0) + (float(p_ene.group(1).replace(',', '.')) if p_ene else 0.0)

    elif es_repsol:
        compania = "Repsol"
        fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        m_fijo = re.search(r'Término\s+fijo\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        m_ener = re.search(r'Energía\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        total_real = (float(m_fijo.group(1).replace(',', '.')) if m_fijo else 0.0) + (float(m_ener.group(1).replace(',', '.')) if m_ener else 0.0)

    elif es_iberdrola:
        compania = "Iberdrola"
        m_periodo = re.search(r'(\d{2}/\d{2}/\d{4})\s+a\s+(\d{2}/\d{2}/\d{4})', texto_completo)
        fecha = m_periodo.group(2) if m_periodo else "No encontrada"
        m_imp_pot = re.search(r'importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_imp_ene = re.search(r'kWh\s+hasta.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_imp_pot.group(1).replace(',', '.')) if m_imp_pot else 0.0) + (float(m_imp_ene.group(1).replace(',', '.')) if m_imp_ene else 0.0)

    else:
        # Fallback genérico
        m_total = re.search(r'(?:Total|Importe).*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = float(m_total.group(1).replace(',', '.')) if m_total else 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- Resto del código Streamlit (sin cambios) ---
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
            cols = ["Compañía", "Fecha", "Días", "Potencia (kW)", "Consumo Punta (kWh)", "Consumo Llano (kWh)", "Consumo Valle (kWh)", "Excedente (kWh)", "Total Real", "Archivo"]
            df_resumen_pdfs = df_resumen_pdfs[cols]

            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": f"📍 TU FACTURA ACTUAL",
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
                            "Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_estimado, 2), "Ahorro": round(ahorro, 2),
                            "Dias_Factura": fact['Días']
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            df_solo_ofertas = df_comp[~df_comp["Compañía/Tarifa"].str.contains("📍 TU FACTURA")]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index()
            ranking_total = ranking_total.sort_values(by="Ahorro", ascending=False)

            st.divider()
            
            if not ranking_total.empty:
                mejor_opcion_nombre = ranking_total.iloc[0]['Compañía/Tarifa']
                st.subheader("🏆 Resultado del Análisis")
                c1, c2 = st.columns(2)
                with c1: st.success(f"La mejor compañía es: **{mejor_opcion_nombre}**")
                with c2: st.metric(label="Ahorro Total Acumulado", value=f"{round(ranking_total.iloc[0]['Ahorro'], 2)} €")

            st.subheader("📊 Comparativa Detallada por Factura")
            
            df_mostrar = df_comp.drop(columns=['Dias_Factura'], errors='ignore')
            
            st.dataframe(
                df_mostrar,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Coste (€)": st.column_config.NumberColumn(format="%.2f"),
                    "Ahorro": st.column_config.NumberColumn(
                        format="%.2f",
                        help="Ahorro respecto a tu factura actual"
                    ),
                }
            )

            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Detalle Comparativa')
                ranking_total.to_excel(writer, index=False, sheet_name='Ranking Ahorro')
                df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos Facturas Originales')

            st.download_button(
                label="📥 Descargar Informe Completo",
                data=buffer_excel.getvalue(),
                file_name="estudio_ahorro_energetico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
