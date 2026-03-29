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

    elif es_total_energies:
        # 1. Fecha y Días
        m_fecha = re.search(r'Fecha\s+emisión:\s*([\d.]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_dias = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        # 2. Potencia (kW)
        m_pot_kW = re.search(r'Potencia\s+P1:\s*([\d,.]+)', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_kW.group(1).replace(',', '.')) if m_pot_kW else 0.0

        # 3. ATAQUE DIRECTO A LA FILA "PERIODO" (Derecha del todo)
        # Buscamos líneas que empiecen por una fecha o por el número de días y pillamos el último importe
        lineas = texto_completo.split('\n')
        valores_periodo = []
        for l in lineas:
            # Si la línea tiene formato de periodo: "DD.MM.AAAA - DD.MM.AAAA ... Valor €"
            # O "XX día(s) ... Valor €"
            if re.search(r'\d{2}\.\d{2}\.\d{4}', l) or re.search(r'\d+\s+día\(s\)', l):
                # Buscamos todos los importes con coma (ej: 13,49) que estén al final
                matches = re.findall(r'([\d,.]+)\s*€', l)
                if matches:
                    # El valor real es el último de la fila (derecha del todo)
                    val = matches[-1].replace('.', '').replace(',', '.')
                    valores_periodo.append(float(val))
        
        # El total real es la suma de los dos primeros importes encontrados en esas filas (Potencia y Consumo)
        total_real = sum(valores_periodo[:2]) if valores_periodo else 0.0

        # 4. Consumos (kWh)
        def extraer_kwh(tipo, texto):
            patron = rf'{tipo}.*?([\d,.]+)\s*kWh'
            match = re.search(patron, texto, re.IGNORECASE)
            return float(match.group(1).replace('.', '').replace(',', '.')) if match else 0.0

        consumos = {
            'punta': extraer_kwh('Punta', texto_completo),
            'llano': extraer_kwh('Llano', texto_completo),
            'valle': extraer_kwh('Valle', texto_completo)
        }
        if sum(consumos.values()) == 0:
            m_gen = re.search(r'(\d+)\s*kWh\s+[\d,.]+\s*€/kWh', texto_completo)
            if m_gen: consumos['punta'] = float(m_gen.group(1))
        excedente = 0.0

    elif es_endesa_luz:
        m_fecha_etiqueta = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha_etiqueta.group(1) if m_fecha_etiqueta else "No encontrada"
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        def limpiar_endesa(patron, texto):
            m = re.search(patron, texto, re.IGNORECASE)
            return float(m.group(1).replace(" ", "").replace(".", "").replace(",", ".")) if m else 0.0
        total_real = limpiar_endesa(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo) + limpiar_endesa(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo)
        m_p = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_l = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_v = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        consumos = {'punta': float(m_p.group(1).replace(',', '.')) if m_p else 0.0, 'llano': float(m_l.group(1).replace(',', '.')) if m_l else 0.0, 'valle': float(m_v.group(1).replace(',', '.')) if m_v else 0.0}
        excedente = 0.0

    elif es_repsol:
        m_fecha = re.search(r'Fecha\s+de\s+emisión\s*([\d/]+)', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        m_pot = re.search(r'Potencia\s+contratada\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot.group(1).replace(',', '.')) if m_pot else 0.0
        m_dias = re.search(r'Días\s+facturados\s*(\d+)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0
        m_f = re.search(r'Término\s+fijo\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_e = re.search(r'Energía\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_f.group(1).replace(',', '.')) if m_f else 0.0) + (float(m_e.group(1).replace(',', '.')) if m_e else 0.0)
        m_c = re.search(r'Consumo\s+en\s+este\s+periodo\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE)
        consumos = {'punta': float(m_c.group(1).replace(',', '.')) if m_c else 0.0, 'llano': 0.0, 'valle': 0.0}
        excedente = 0.0

    elif es_iberdrola:
        m_pot_kW = re.search(r'Potencia\s+punta:\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = float(m_pot_kW.group(1).replace(',', '.')) if m_pot_kW else 0.0
        m_d = re.search(r'Potencia\s+facturada.*?(\d+)\s+días', texto_completo, re.IGNORECASE | re.DOTALL)
        dias = int(m_d.group(1)) if m_d else 0
        m_p = re.search(r'PERIODO.*?(\d{2}/\d{2}/\d{2,4})', texto_completo, re.IGNORECASE | re.DOTALL)
        fecha = m_p.group(1) if m_p else "No encontrada"
        m_pun = re.search(r'Punta\s*([\d,.]+)\s*kWh', texto_completo)
        m_lla = re.search(r'Llano\s*([\d,.]+)\s*kWh', texto_completo)
        m_val = re.search(r'Valle\s*([\d,.]+)\s*kWh', texto_completo)
        consumos = {'punta': float(m_pun.group(1).replace(',', '.')) if m_pun else 0.0, 'llano': float(m_lla.group(1).replace(',', '.')) if m_lla else 0.0, 'valle': float(m_val.group(1).replace(',', '.')) if m_val else 0.0}
        m_ip = re.search(r'Total\s+importe\s+potencia.*?\s*([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        m_ie = re.search(r'Total\s+[\d,.]+\s*kWh.*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = (float(m_ip.group(1).replace(',', '.')) if m_ip else 0.0) + (float(m_ie.group(1).replace(',', '.')) if m_ie else 0.0)
        excedente = 0.0

    else:
        # Fallback genérico
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
        "Total Real": round(total_real, 2)
    }

st.set_page_config(page_title="Comparador Energético", layout="wide")
st.title("⚡ Comparador de Facturas Eléctricas Pro")

excel_path = "tarifas_companias.xlsx"
if not os.path.exists(excel_path):
    st.error(f"No se encuentra el archivo '{excel_path}'")
else:
    uploaded_files = st.file_uploader("Sube tus facturas PDF", type="pdf", accept_multiple_files=True)
    if uploaded_files:
        datos = []
        for f in uploaded_files:
            try:
                res = extraer_datos_factura(io.BytesIO(f.read()))
                res['Archivo'] = f.name
                datos.append(res)
            except Exception as e: st.error(f"Error en {f.name}: {e}")
        
        if datos:
            df_pdfs = pd.DataFrame(datos)
            with st.expander("corregir datos", expanded=True):
                df_pdfs = st.data_editor(df_pdfs, use_container_width=True, hide_index=True)
            
            df_tar = pd.read_excel(excel_path)
            res_fin = []
            for _, fact in df_pdfs.iterrows():
                res_fin.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": "📍 TU FACTURA ACTUAL", "Coste (€)": fact['Total Real'], "Ahorro": 0.0})
                for _, t in df_tar.iterrows():
                    try:
                        coste = (fact['Días'] * t.iloc[1] * fact['Potencia (kW)']) + (fact['Días'] * t.iloc[2] * fact['Potencia (kW)']) + \
                                (fact['Consumo Punta (kWh)'] * t.iloc[3]) + (fact['Consumo Llano (kWh)'] * t.iloc[4]) + \
                                (fact['Consumo Valle (kWh)'] * t.iloc[5]) - (fact['Excedente (kWh)'] * t.iloc[6])
                        res_fin.append({"Mes/Fecha": fact['Fecha'], "Compañía/Tarifa": t.iloc[0], "Coste (€)": round(coste, 2), "Ahorro": round(fact['Total Real'] - coste, 2)})
                    except: continue
            
            df_comp = pd.DataFrame(res_fin).sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
