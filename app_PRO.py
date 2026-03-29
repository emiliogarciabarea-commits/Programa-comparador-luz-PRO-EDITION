import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

def extraer_datos_cliente(texto):
    # Buscamos el nombre y dirección (suele estar tras el CIF de la comercializadora o cerca de los datos de pago)
    # Este es un buscador genérico robusto para los formatos de Endesa, Iberdrola, etc.
    lineas = texto.split('\n')
    nombre = "No encontrado"
    direccion = "No encontrada"
    
    for i, linea in enumerate(lineas):
        if "CIF A" in linea or "Madrid" in linea or "Endesa" in linea:
            # El nombre suele estar 2-3 líneas después de los datos sociales en muchas facturas
            if i+1 < len(lineas) and len(lineas[i+1].strip()) > 5:
                nombre = lineas[i+1].strip()
                if i+2 < len(lineas):
                    direccion = lineas[i+2].strip()
                break
    return nombre, direccion

def extraer_datos_factura(pdf_path):
    texto_completo = ""
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            texto_completo += pagina.extract_text() + "\n"

    # --- DATOS DE CLIENTE (NUEVO) ---
    nombre_cli, direc_cli = extraer_datos_cliente(texto_completo)

    # --- DETECCIÓN DE TIPO DE FACTURA ---
    es_el_corte_ingles = re.search(r'Energía\s+El\s+Corte\s+Inglés|TELECOR', texto_completo, re.IGNORECASE)
    es_iberdrola = re.search(r'IBERDROLA\s+CLIENTES', texto_completo, re.IGNORECASE)
    es_naturgy = re.search(r'Naturgy', texto_completo, re.IGNORECASE)
    es_repsol = re.search(r'repsol', texto_completo, re.IGNORECASE)
    es_endesa_luz = re.search(r'Endesa\s+Energía|endesa\s+luz', texto_completo, re.IGNORECASE)

    if es_endesa_luz:
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        if m_fecha_etiqueta:
            fecha = m_fecha_etiqueta.group(1)
        else:
            m_fecha_generica = re.search(r'(\d{2}/\d{2}/\d{4})', texto_completo)
            fecha = m_fecha_generica.group(1) if m_fecha_generica else "No encontrada"

        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0

        def limpiar_valor_endesa(patron, texto):
            match = re.search(patron, texto, re.IGNORECASE)
            if match:
                valor_sucio = match.group(1)
                valor_limpio = valor_sucio.replace(" ", "").replace(".", "").replace(",", ".")
                try: return float(valor_limpio)
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

    elif es_el_corte_ingles:
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

    # [Aquí seguirían los elif de Repsol e Iberdrola igual que el código anterior]
    else:
        # Lógica genérica simplificada para el ejemplo
        consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
        potencia = 0.0
        fecha = "No encontrada"
        dias = 0
        total_real = 0.0
        excedente = 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2),
        "Nombre Cliente": nombre_cli,
        "Dirección": direc_cli
    }

st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"

if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}'")
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
            
            # Crear DataFrame específico para la nueva hoja de Clientes
            df_clientes = df_resumen_pdfs[['Archivo', 'Nombre Cliente', 'Dirección']].copy()

            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

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
                # [Lógica de cálculo de ahorro igual...]
                for index, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        b_pot1 = pd.to_numeric(tarifa.iloc[1], errors='coerce')
                        c_pot2 = pd.to_numeric(tarifa.iloc[2], errors='coerce')
                        d_punta = pd.to_numeric(tarifa.iloc[3], errors='coerce')
                        e_llano = pd.to_numeric(tarifa.iloc[4], errors='coerce')
                        f_valle = pd.to_numeric(tarifa.iloc[5], errors='coerce')
                        g_excedente = pd.to_numeric(tarifa.iloc[6], errors='coerce')
                        coste_estimado = (fact['Días'] * b_pot1 * fact['Potencia (kW)']) + (fact['Días'] * c_pot2 * fact['Potencia (kW)']) + (fact['Consumo Punta (kWh)'] * d_punta) + (fact['Consumo Llano (kWh)'] * e_llano) + (fact['Consumo Valle (kWh)'] * f_valle) - (fact['Excedente (kWh)'] * g_excedente)
                        resultados_finales.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": nombre_cia, "Coste (€)": round(coste_estimado, 2), "Ahorro": round(fact['Total Real'] - coste_estimado, 2), "Dias_Factura": fact['Días']})
                    except: continue

            df_comp = pd.DataFrame(resultados_finales).dropna(subset=['Coste (€)'])
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            ranking_total = df_comp[df_comp["Compañía/Tarifa"] != "📍 TU FACTURA ACTUAL"].groupby("Compañía/Tarifa")["Ahorro"].sum().reset_index().sort_values(by="Ahorro", ascending=False)

            # Preparar hoja de precios ganadora
            df_precios_ganadora = pd.DataFrame()
            if not ranking_total.empty:
                mejor_opcion_nombre = ranking_total.iloc[0]['Compañía/Tarifa']
                fila_ganadora = df_tarifas[df_tarifas.iloc[:, 0] == mejor_opcion_nombre]
                if not fila_ganadora.empty:
                    df_precios_ganadora = pd.DataFrame({"Concepto": ["Compañía Ganadora", "P1 Potencia", "P2 Potencia", "Punta", "Llano", "Valle", "Excedente"], "Valor": [mejor_opcion_nombre, fila_ganadora.iloc[0,1], fila_ganadora.iloc[0,2], fila_ganadora.iloc[0,3], fila_ganadora.iloc[0,4], fila_ganadora.iloc[0,5], fila_ganadora.iloc[0,6]]})

            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp.drop(columns=['Dias_Factura']), use_container_width=True, hide_index=True)

            # --- EXCEL CON 5 HOJAS ---
            buffer_excel = io.BytesIO()
            with pd.ExcelWriter(buffer_excel, engine='openpyxl') as writer:
                df_comp.to_excel(writer, index=False, sheet_name='Detalle Comparativa')
                ranking_total.to_excel(writer, index=False, sheet_name='Ranking Ahorro')
                df_resumen_pdfs.to_excel(writer, index=False, sheet_name='Datos Facturas Originales')
                if not df_precios_ganadora.empty:
                    df_precios_ganadora.to_excel(writer, index=False, sheet_name='Precios Tarifa Ganadora')
                df_clientes.to_excel(writer, index=False, sheet_name='Datos del Cliente')

            st.download_button(
                label="📥 Descargar Informe Completo (5 Hojas)",
                data=buffer_excel.getvalue(),
                file_name="estudio_ahorro_energetico.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
