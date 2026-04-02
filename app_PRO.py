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

    if es_el_corte_ingles:
        compania = "El Corte Inglés"
        patron_cons_eci = r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)'
        match_cons = re.search(patron_cons_eci, texto_completo)
        consumos = {
            'punta': float(match_cons.group(1).replace(',', '.')) if match_cons else 0.0,
            'llano': float(match_cons.group(2).replace(',', '.')) if match_cons else 0.0,
            'valle': float(match_cons.group(3).replace(',', '.')) if match_cons else 0.0
        }
        potencia = float(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo).group(1)) if re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo) else 0
        total_real = float(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo).group(1).replace(',', '.')) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo) else 0.0
        excedente = 0.0 

    elif es_octopus:
        compania = "Octopus Energy"
        fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo).group(1) if re.search(r'Fecha\s+de\s+emisión:\s*([\d-]+)', texto_completo) else "No encontrada"
        dias = int(re.search(r'\((\d+)\s+días\)', texto_completo).group(1)) if re.search(r'\((\d+)\s+días\)', texto_completo) else 0
        potencia = float(re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo).group(1).replace(',', '.')) if re.search(r'Punta\s+([\d,.]+)\s*kW', texto_completo) else 0.0
        consumos = {
            'punta': float(re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Punta\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0,
            'llano': float(re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Llano\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0,
            'valle': float(re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Valle\s+.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        }
        v_pot = float(re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ene = float(re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Energía\s+Activa:?\s+([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_pot + v_ene
        excedente = float(re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Excedentes.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0

    elif es_naturgy:
        compania = "Naturgy"
        fecha = re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión:\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        dias = int(re.search(r'Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Bono\s+Social\s+(\d+)\s+días', texto_completo, re.IGNORECASE) else 0
        potencia = float(re.search(r'Potencia\s+contratada\s+P1:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s+P1:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        consumos = {
            'punta': float(re.search(r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+electricidad\s+Punta\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0,
            'llano': float(re.search(r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+electricidad\s+Llano\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0,
            'valle': float(re.search(r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo\s+electricidad\s+Valle\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        }
        excedente = abs(float(re.search(r'excedentes\s*(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.'))) if re.search(r'excedentes\s*(-?[\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        m_pot_val = re.search(r'Por\s+potencia\s+contratada\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ene_val = re.search(r'Por\s+energía\s+consumida\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_pot_val.group(1).replace(',', '.')) if m_pot_val else 0.0) + (float(m_ene_val.group(1).replace(',', '.')) if m_ene_val else 0.0)

    elif es_xxi:
        compania = "Energía XXI"
        # Fecha con soporte para saltos de línea
        m_fecha = re.search(r'Fecha\s+de\s+emisión:?\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        # Potencia con soporte para saltos de línea
        m_pot = re.search(r'Potencia\s+contratada\s*\(?P1\)?:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        # Días
        m_dias = re.search(r'(\d+)\s*días', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        # Consumos
        m_punta = re.search(r'Consumo.*?Punta.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        m_llano = re.search(r'Consumo.*?Llano.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        m_valle = re.search(r'Consumo.*?Valle.*?([\d,.]+)\s*kWh', texto_completo, re.DOTALL | re.IGNORECASE)
        consumos = {
            'punta': float(m_punta.group(1).replace(',', '.')) if m_punta else 0.0,
            'llano': float(m_llano.group(1).replace(',', '.')) if m_llano else 0.0,
            'valle': float(m_valle.group(1).replace(',', '.')) if m_valle else 0.0
        }
        # Suma de Término Fijo + Variable
        m_val_pot_xxi = re.search(r'Por\s+potencia\s+contratada.*?\s*([\d,.]+)\s*€', texto_completo, re.DOTALL | re.IGNORECASE)
        m_val_ene_xxi = re.search(r'Por\s+energía\s+consumida.*?\s*([\d,.]+)\s*€', texto_completo, re.DOTALL | re.IGNORECASE)
        total_real = (float(m_val_pot_xxi.group(1).replace(',', '.')) if m_val_pot_xxi else 0.0) + (float(m_val_ene_xxi.group(1).replace(',', '.')) if m_val_ene_xxi else 0.0)
        excedente = 0.0

    elif es_repsol:
        compania = "Repsol"
        fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE).group(1) if re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE) else "No encontrada"
        potencia = float(re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE).group(1)) if re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE) else 0
        v_fijo = float(re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ener = float(re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_fijo + v_ener
        consumos = {'punta': float(re.search(r'Consumo.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Consumo.*?([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        compania = "Iberdrola"
        potencia = float(re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE) else 0.0
        dias = int(re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.DOTALL | re.IGNORECASE).group(1)) if re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.DOTALL | re.IGNORECASE) else 0
        fecha = re.search(r'(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo).group(2) if re.search(r'(\d{2}/\d{2}/\d{2,4}).*?(\d{2}/\d{2}/\d{2,4})', texto_completo) else "No encontrada"
        consumos = {
            'punta': float(re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo) else 0.0,
            'llano': float(re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo) else 0.0,
            'valle': float(re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo).group(1).replace(',', '.')) if re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo) else 0.0
        }
        v_pot = float(re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        v_ene = float(re.search(r'Total\s+.*?kWh.*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE).group(1).replace(',', '.')) if re.search(r'Total\s+.*?kWh.*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE) else 0.0
        total_real = v_pot + v_ene
        excedente = 0.0
    else:
        # Fallback genérico para otros casos
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia = 0.0
        fecha = "No encontrada"
        dias = 0
        excedente = 0.0

    return {
        "Compañía": compania, "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- CÓDIGO INTERFAZ STREAMLIT (SIN CAMBIOS ESTRUCTURALES) ---
st.set_page_config(page_title="Energetika - Comparador Pro", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}'.")
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
                st.error(f"Error en {uploaded_file.name}: {e}")

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
                            "Dias_Factura": fact['Días'],
                            "p1": b_pot1, "p2": c_pot2, "ep": d_punta, "el": e_llano, "ev": f_valle, "exc": g_excedente
                        })
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            df_solo_ofertas = df_comp[~df_comp["Compañía/Tarifa"].str.contains("📍 TU FACTURA")]
            ranking_total = df_solo_ofertas.groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            if not ranking_total.empty:
                ganador = ranking_total.iloc[0]
                st.subheader("🏆 Mejor opción encontrada")
                c1, c2 = st.columns(2)
                c1.success(f"Tarifa: **{ganador['Compañía/Tarifa']}**")
                c2.metric("Ahorro Total", f"{round(ganador['Ahorro'], 2)} €")

            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp.drop(columns=['p1','p2','ep','el','ev','exc'], errors='ignore'), use_container_width=True, hide_index=True)

            # Botón de descarga
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Comparativa')
            st.download_button("📥 Descargar Informe Excel", buffer.getvalue(), "estudio_energetico.xlsx", "application/vnd.ms-excel", use_container_width=True)
