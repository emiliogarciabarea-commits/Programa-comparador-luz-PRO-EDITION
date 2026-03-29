import pdfplumber
import re
import pandas as pd
import streamlit as st
import io
import os

# Función auxiliar para convertir texto a float de forma segura
def limpiar_float(valor):
    if not valor:
        return 0.0
    try:
        # Si el valor es una lista o match object, extraemos el string
        if not isinstance(valor, str):
            valor = str(valor)
        
        # Eliminamos espacios, símbolos de euro y unidades
        valor = valor.replace("€", "").replace("kWh", "").replace("kW", "").strip()
        
        # Lógica para formatos europeos (1.250,50 -> 1250.50)
        # Si hay puntos y comas, el punto suele ser de miles
        if "," in valor and "." in valor:
            valor = valor.replace(".", "") # Quitar miles
            valor = valor.replace(",", ".") # Cambiar decimal
        # Si solo hay coma, es el decimal
        elif "," in valor:
            valor = valor.replace(",", ".")
            
        return float(valor)
    except (ValueError, TypeError):
        return 0.0

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

    # Valores por defecto
    consumos = {'punta': 0.0, 'llano': 0.0, 'valle': 0.0}
    potencia = 0.0
    fecha = "No encontrada"
    dias = 0
    total_real = 0.0
    excedente = 0.0

    if es_el_corte_ingles:
        m_cons = re.search(r'Punta\s+Llano\s+Valle\s+Consumo\s+kWh\s+([\d,.]+)\s+([\d,.]+)\s+([\d,.]+)', texto_completo)
        if m_cons:
            consumos['punta'] = limpiar_float(m_cons.group(1))
            consumos['llano'] = limpiar_float(m_cons.group(2))
            consumos['valle'] = limpiar_float(m_cons.group(3))

        potencia = limpiar_float(re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo).group(1)) if re.search(r'Potencia\s+contratada\s+kW\s+([\d,.]+)', texto_completo) else 0.0
        
        m_fecha = re.search(r'Fecha\s+de\s+Factura:\s*([\d/]+)', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        m_dias = re.search(r'Días\s+de\s+consumo:\s*(\d+)', texto_completo)
        dias = int(m_dias.group(1)) if m_dias else 0
        
        total_real = limpiar_float(re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo).group(1)) if re.search(r'TOTAL\s+FACTURA\s+([\d,.]+)\s*€', texto_completo) else 0.0

    elif es_total_energies:
        m_fecha = re.search(r'(\d{2}\.\d{2}\.\d{4})', texto_completo)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"

        m_dias = re.search(r'(\d+)\s+día\(s\)', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        m_pot = re.search(r'([\d,.]+)\s*kW', texto_completo)
        potencia = limpiar_float(m_pot.group(1)) if m_pot else 0.0

        consumos['punta'] = limpiar_float(re.search(r'punta:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1)) if re.search(r'punta:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        consumos['llano'] = limpiar_float(re.search(r'llano:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1)) if re.search(r'llano:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0
        consumos['valle'] = limpiar_float(re.search(r'valle:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE).group(1)) if re.search(r'valle:\s*([\d,.]+)\s*kWh', texto_completo, re.IGNORECASE) else 0.0

        m_total = re.search(r'IMPORTE\s+TOTAL.*?([\d,.]+)\s*€', texto_completo, re.DOTALL | re.IGNORECASE)
        total_real = limpiar_float(m_total.group(1)) if m_total else 0.0

    elif es_endesa_luz:
        m_fecha = re.search(r'Fecha\s+emisión\s+factura:\s*([\d/]{10})', texto_completo, re.IGNORECASE)
        fecha = m_fecha.group(1) if m_fecha else "No encontrada"
        
        m_dias = re.search(r'(\d+)\s+días', texto_completo, re.IGNORECASE)
        dias = int(m_dias.group(1)) if m_dias else 0

        m_pot = re.search(r'punta-llano\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = limpiar_float(m_pot.group(1)) if m_pot else 0.0

        # Suma de conceptos para el total real
        val_pot = limpiar_float(re.search(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo).group(1)) if re.search(r'Potencia\s+\.+\s*([\d\s.,]+)€', texto_completo) else 0.0
        val_ene = limpiar_float(re.search(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo).group(1)) if re.search(r'Energía\s+\.+\s*([\d\s.,]+)€', texto_completo) else 0.0
        total_real = val_pot + val_ene

        m_p = re.search(r'Punta\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_l = re.search(r'Llano\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        m_v = re.search(r'Valle\s+[\d,.]+\s+[\d,.]+\s+[\d,.]+\s+[\w,.]+\s+([\d,.]+)', texto_completo, re.IGNORECASE)
        
        consumos['punta'] = limpiar_float(m_p.group(1)) if m_p else 0.0
        consumos['llano'] = limpiar_float(m_l.group(1)) if m_l else 0.0
        consumos['valle'] = limpiar_float(m_v.group(1)) if m_v else 0.0

    # ... (Resto de elifs: repsol, iberdrola, etc., usando limpiar_float() en cada extracción de número) ...

    else:
        # Lógica genérica mejorada
        m_pot = re.search(r'(?:Potencia\s+contratada.*?):\s*([\d,.]+)\s*kW', texto_completo, re.IGNORECASE)
        potencia = limpiar_float(m_pot.group(1)) if m_pot else 0.0
        
        # Búsqueda de consumos genéricos
        for tramo in ['punta', 'llano', 'valle']:
            patron = rf'{tramo}.*?([\d,.]+)\s*kWh'
            match = re.search(patron, texto_completo, re.IGNORECASE)
            if match:
                consumos[tramo] = limpiar_float(match.group(1))

        m_total = re.search(r'(?:Total\s+factura|Importe\s+total).*?([\d,.]+)\s*€', texto_completo, re.IGNORECASE)
        total_real = limpiar_float(m_total.group(1)) if m_total else 0.0

    return {
        "Fecha": fecha, "Días": dias, "Potencia (kW)": potencia,
        "Consumo Punta (kWh)": consumos['punta'], "Consumo Llano (kWh)": consumos['llano'],
        "Consumo Valle (kWh)": consumos['valle'], "Excedente (kWh)": excedente,
        "Total Real": round(total_real, 2)
    }

# --- PARTE DE STREAMLIT ---
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
                # Procesar cada factura
                file_bytes = io.BytesIO(uploaded_file.read())
                res = extraer_datos_factura(file_bytes)
                res['Archivo'] = uploaded_file.name
                datos_facturas.append(res)
            except Exception as e:
                st.error(f"Error procesando {uploaded_file.name}: {e}")

        if datos_facturas:
            df_resumen_pdfs = pd.DataFrame(datos_facturas)
            with st.expander("🔍 Ver y corregir datos extraídos", expanded=True):
                df_resumen_pdfs = st.data_editor(df_resumen_pdfs, use_container_width=True, hide_index=True)

            # Carga de tarifas y comparativa (se mantiene igual pero asegurando tipos numéricos)
            df_tarifas = pd.read_excel(excel_path)
            resultados_finales = []

            for _, fact in df_resumen_pdfs.iterrows():
                # Añadir la factura actual como referencia
                resultados_finales.append({
                    "Mes/Fecha": fact['Fecha'],
                    "Compañía/Tarifa": "📍 TU FACTURA ACTUAL",
                    "Coste (€)": fact['Total Real'],
                    "Ahorro": 0.0,
                    "Dias": fact['Días']
                })

                for _, tarifa in df_tarifas.iterrows():
                    try:
                        nombre_cia = tarifa.iloc[0]
                        # Asegurar que los precios del excel son float
                        p_pot1 = limpiar_float(tarifa.iloc[1])
                        p_pot2 = limpiar_float(tarifa.iloc[2])
                        p_punta = limpiar_float(tarifa.iloc[3])
                        p_llano = limpiar_float(tarifa.iloc[4])
                        p_valle = limpiar_float(tarifa.iloc[5])
                        p_exce = limpiar_float(tarifa.iloc[6])

                        coste_est = (fact['Días'] * p_pot1 * fact['Potencia (kW)']) + \
                                    (fact['Días'] * p_pot2 * fact['Potencia (kW)']) + \
                                    (fact['Consumo Punta (kWh)'] * p_punta) + \
                                    (fact['Consumo Llano (kWh)'] * p_llano) + \
                                    (fact['Consumo Valle (kWh)'] * p_valle) - \
                                    (fact['Excedente (kWh)'] * p_exce)
                        
                        # Añadir IVA aproximado (puedes ajustar el factor)
                        coste_est_iva = coste_est * 1.05 

                        ahorro = fact['Total Real'] - coste_est_iva
                        resultados_finales.append({
                            "Mes/Fecha": fact['Fecha'], 
                            "Compañía/Tarifa": nombre_cia,
                            "Coste (€)": round(coste_est_iva, 2), 
                            "Ahorro": round(ahorro, 2),
                            "Dias": fact['Días']
                        })
                    except:
                        continue

            # Mostrar resultados
            df_comp = pd.DataFrame(resultados_finales)
            df_comp = df_comp.sort_values(by=["Mes/Fecha", "Ahorro"], ascending=[True, False])
            
            st.subheader("📊 Comparativa Detallada")
            st.dataframe(df_comp, use_container_width=True, hide_index=True)
