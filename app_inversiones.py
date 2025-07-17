# -*- coding: utf-8 -*-
"""
Created on Mon Jul 14 12:02:26 2025

@author: UIN
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import io
import os

if not os.path.exists("registros_guardados"):
    os.makedirs("registros_guardados")





# --- Función FIFO para calcular ganancias por activo ---
def calcular_ganancias_fifo(transacciones):
    """
    transacciones: DataFrame con columnas ['tipo', 'cantidad', 'precio_unitario', 'fecha']
    tipo = 'compra' o 'venta'
    Retorna DataFrame con filas de ventas y ganancia/pérdida por fila.
    """
    lotes_compra = []
    resultados = []

    for i, fila in transacciones.iterrows():
        tipo = fila['tipo']
        cant = fila['cantidad']
        precio = fila['precio_unitario']
        fecha = fila['fecha']

        if tipo == 'compra':
            lotes_compra.append({'cantidad': cant, 'precio': precio})
        elif tipo == 'venta':
            cant_venta = cant
            ganancia = 0
            while cant_venta > 0 and lotes_compra:
                lote = lotes_compra[0]
                if lote['cantidad'] <= cant_venta:
                    cantidad_vendida = lote['cantidad']
                    ganancia += cantidad_vendida * (precio - lote['precio'])
                    cant_venta -= cantidad_vendida
                    lotes_compra.pop(0)
                else:
                    cantidad_vendida = cant_venta
                    ganancia += cantidad_vendida * (precio - lote['precio'])
                    lote['cantidad'] -= cantidad_vendida
                    cant_venta = 0
            resultados.append({'fecha': fecha, 'cantidad_vendida': cant, 'precio_venta': precio, 'ganancia': ganancia})
    return pd.DataFrame(resultados)

# --- Inicializar dataframe en sesión ---
if 'df_transacciones' not in st.session_state:
    st.session_state.df_transacciones = pd.DataFrame(columns=[
        'tipo', 'cantidad', 'precio_unitario', 'fecha', 'tipo_activo', 'activo'
    ])
else:
    for col in ['tipo', 'cantidad', 'precio_unitario', 'fecha', 'tipo_activo', 'activo']:
        if col not in st.session_state.df_transacciones.columns:
            st.session_state.df_transacciones[col] = pd.NA

st.title("Portafolio de Inversiones")


# Función para calcular posición actual y precio medio FIFO de posición abierta
def calcular_posicion_y_precio_medio_fifo(transacciones):
    lotes_compra = []

    for _, fila in transacciones.iterrows():
        tipo = fila['tipo']
        cant = fila['cantidad']
        precio = fila['precio_unitario']

        if tipo == 'compra':
            lotes_compra.append({'cantidad': cant, 'precio': precio})
        elif tipo == 'venta':
            cant_venta = cant
            while cant_venta > 0 and lotes_compra:
                lote = lotes_compra[0]
                if lote['cantidad'] <= cant_venta:
                    cant_venta -= lote['cantidad']
                    lotes_compra.pop(0)
                else:
                    lote['cantidad'] -= cant_venta
                    cant_venta = 0

    posicion = sum(l['cantidad'] for l in lotes_compra)

    if posicion > 0:
        precio_medio = sum(l['cantidad'] * l['precio'] for l in lotes_compra) / posicion
    else:
        precio_medio = 0

    return posicion, precio_medio


### OBTENER PRECIO ACTUAL

def obtener_precio_actual(ticker):
    import yfinance as yf
    try:
        # Intentar directo
        datos = yf.Ticker(ticker)
        hist = datos.history(period="1d")
        if not hist.empty:
            return hist['Close'][-1]
        
        # Si no hay datos, probar con sufijo USD (para cripto)
        datos = yf.Ticker(ticker + '-USD')
        hist = datos.history(period="1d")
        if not hist.empty:
            return hist['Close'][-1]
        
        return None
    except Exception as e:
        st.error(f"Error obteniendo precio para {ticker}: {e}")
        return None


equivalencias_yf = {
    'PHAG': 'PHAG.AS',      # WisdomTree Physical Silver - Amsterdam (EUR)
    'IGLN': 'IGLN.L',      # iShares Physical Gold ETC - Amsterdam (EUR)
    'BTC': 'BTC-EUR',       # Bitcoin en EUR
    'ETH': 'ETH-EUR',       # Ethereum en EUR
    'SOL': 'SOL-EUR',       # Solana en EUR
    'ADA': 'ADA-EUR',       # Cardano en EUR
    'XRP': 'XRP-EUR',       # Ripple en EUR
}






# Crear tabs
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Registro de transacciones", 
    "Cotización en tiempo real", 
    "Posición Global", 
    "Posiciones abiertas", 
    "Ganancias FIFO",
    "Informe hacienda",
])

# --- Ventana: Registro e Importación de Transacciones ---
with tab1:
    st.subheader("Registro e Importación de Transacciones")
    
    # Crear carpeta si no existe
    if not os.path.exists("registros_guardados"):
        os.makedirs("registros_guardados")
    
    # Inicializar DataFrame en sesión si no existe
    if 'df_transacciones' not in st.session_state:
        st.session_state.df_transacciones = pd.DataFrame(columns=['tipo', 'cantidad', 'precio_unitario', 'fecha', 'tipo_activo', 'activo'])
    
    # Inicializar variable para control de registro cargado
    if 'registro_actual' not in st.session_state:
        st.session_state.registro_actual = None

    # === Formulario manual ===
    st.markdown("### Añadir transacción manualmente")
    with st.form('form_transaccion', clear_on_submit=True):
        tipo = st.selectbox('Tipo de transacción', ['compra', 'venta'])
        tipo_activo = st.selectbox('Tipo de activo', ['ETF', 'Cripto', 'Acción', 'Bono', 'Materia Prima', 'Otro'])
        activo = st.text_input('Nombre del activo (ej. BTC, SPY, AAPL...)')
        cantidad = st.number_input(
            'Cantidad',
            min_value=0.0,
            value=1.0,
            step=0.00000001,
            format="%.8f"
        )
        precio = st.number_input('Precio unitario (€)', min_value=0.0, format="%.2f")
        fecha = st.date_input('Fecha')
        submitted = st.form_submit_button('Añadir transacción')

        if submitted:
            if activo.strip() == '':
                st.error("Por favor, introduce el nombre del activo.")
            else:
                nueva_fila = {
                    'tipo': tipo,
                    'cantidad': cantidad,
                    'precio_unitario': precio,
                    'fecha': pd.to_datetime(fecha),
                    'tipo_activo': tipo_activo,
                    'activo': activo.strip()
                }
                st.session_state.df_transacciones = pd.concat(
                    [st.session_state.df_transacciones, pd.DataFrame([nueva_fila])],
                    ignore_index=True
                )
                st.success('Transacción añadida correctamente.')
    
    st.divider()
    
    # === Importar desde archivo ===
    st.markdown("### Importar transacciones desde archivo")
    uploaded_file = st.file_uploader(
        "Sube tu archivo Excel o CSV con transacciones",
        type=['xlsx', 'xls', 'csv']
    )
    
    # Inicializar flag si no existe
    if 'archivo_procesado' not in st.session_state:
        st.session_state.archivo_procesado = False
    
    if uploaded_file is not None and not st.session_state.archivo_procesado:
        try:
            if uploaded_file.name.endswith('.csv'):
                df_cargado = pd.read_csv(uploaded_file)
            else:
                df_cargado = pd.read_excel(uploaded_file)

            # Normalización de columnas
            columnas_necesarias = ['activo', 'tipo', 'cantidad', 'precio_unitario', 'fecha', 'tipo_activo']
            columnas_actuales = df_cargado.columns.str.lower().tolist()

            mapping_columnas = {}
            for col in columnas_necesarias:
                for c in columnas_actuales:
                    if col in c:
                        mapping_columnas[c] = col
            df_cargado.rename(columns=mapping_columnas, inplace=True)

            faltantes = [c for c in columnas_necesarias if c not in df_cargado.columns]
            if faltantes:
                st.error(f"Faltan columnas necesarias: {faltantes}")
            else:
                # Conversión y limpieza
                df_cargado['cantidad'] = pd.to_numeric(df_cargado['cantidad'], errors='coerce')
                df_cargado['precio_unitario'] = pd.to_numeric(df_cargado['precio_unitario'], errors='coerce')
                df_cargado['fecha'] = pd.to_datetime(df_cargado['fecha'], errors='coerce')
                df_cargado['activo'] = df_cargado['activo'].astype(str)
                df_cargado['tipo_activo'] = df_cargado['tipo_activo'].astype(str)
                df_cargado['tipo'] = df_cargado['tipo'].str.lower().replace({'buy': 'compra', 'sell': 'venta'})

                if 'tipo_activo' not in df_cargado.columns:
                    df_cargado['tipo_activo'] = 'Otro'

                df_cargado.dropna(subset=columnas_necesarias, inplace=True)

                # Insertar en sesión
                st.session_state.df_transacciones = pd.concat(
                    [st.session_state.df_transacciones, df_cargado],
                    ignore_index=True
                )

                st.session_state.archivo_procesado = True  # Marcar como procesado
                st.success(f"{len(df_cargado)} transacciones importadas correctamente.")

        except Exception as e:
            st.error(f"Error al procesar el archivo: {e}")
    
    st.divider()
    
with tab1:
    st.subheader("Registro e Importación de Transacciones")

    # Crear carpeta si no existe
    if not os.path.exists("registros_guardados"):
        os.makedirs("registros_guardados")

    # Listar registros guardados (archivos .xlsx)
    archivos_registros = [f for f in os.listdir("registros_guardados") if f.endswith(".xlsx")]

    # --- 1. Cargar registros guardados ---
    registro_seleccionado = st.selectbox(
        "Carga uno de tus portafolios",
        options=[""] + archivos_registros,
        index=0
    )

    # Cargar archivo solo si cambia el registro seleccionado
    if registro_seleccionado:
        if 'registro_actual' not in st.session_state or st.session_state.registro_actual != registro_seleccionado:
            try:
                df_cargado = pd.read_excel(f"registros_guardados/{registro_seleccionado}")
                df_cargado['fecha'] = pd.to_datetime(df_cargado['fecha'], errors='coerce')
                df_cargado = df_cargado.dropna(subset=['fecha']).reset_index(drop=True)
                st.session_state.df_transacciones = df_cargado
                st.session_state.registro_actual = registro_seleccionado
                st.success(f"Registro {registro_seleccionado} cargado correctamente.")
            except Exception as e:
                st.error(f"Error al cargar el registro: {e}")

    st.divider()

    # --- 2. Guardar registro actual como Excel ---
    st.markdown("#### Guardar Portafolio")

    nombre_guardado = st.text_input("Nombre del archivo de registro (sin extensión)", value="Registro1")

    if st.button("Guardar registro actual"):
        if not nombre_guardado.strip():
            st.error("Introduce un nombre de archivo válido para guardar el registro.")
        else:
            ruta_guardado = f"registros_guardados/{nombre_guardado.strip()}.xlsx"
            try:
                st.session_state.df_transacciones.to_excel(ruta_guardado, index=False)
                st.success(f"Registro guardado correctamente en {ruta_guardado}.")
                # Actualizar lista de archivos luego de guardar
                archivos_registros = [f for f in os.listdir("registros_guardados") if f.endswith(".xlsx")]
            except Exception as e:
                st.error(f"Error al guardar el registro: {e}")

    st.divider()

    # --- 3. Eliminar registros guardados ---
    st.markdown("#### 🗑️ Eliminar Portafolio")

    if archivos_registros:
        registros_a_eliminar = st.multiselect(
            "Selecciona registros para eliminar",
            options=archivos_registros
        )
        if st.button("Eliminar registros seleccionados"):
            if registros_a_eliminar:
                errores = []
                for archivo in registros_a_eliminar:
                    ruta = os.path.join("registros_guardados", archivo)
                    try:
                        os.remove(ruta)
                    except Exception as e:
                        errores.append(f"{archivo}: {e}")
                if errores:
                    st.error(f"Errores al eliminar: {errores}")
                else:
                    st.success(f"Eliminados {len(registros_a_eliminar)} registros correctamente.")
                # Actualizar lista tras eliminación
                archivos_registros = [f for f in os.listdir("registros_guardados") if f.endswith(".xlsx")]
            else:
                st.warning("Selecciona al menos un registro para eliminar.")
    else:
        st.info("No hay registros guardados para eliminar.")

    st.divider()

    
    # === Mostrar transacciones registradas ===
    st.markdown("# Transacciones registradas")
    
        # === Eliminar transacciones seleccionadas ===
    st.markdown("#### 🗑️ Eliminar transacciones")
    
    if not st.session_state.df_transacciones.empty:
        # Mostrar una tabla con selección de filas (usando checkboxes)
        df_display = st.session_state.df_transacciones.copy()
        df_display.index = df_display.index.astype(str)  # índices como strings para keys únicos
        
        # Creamos un multiselect para elegir índices a eliminar
        filas_a_eliminar = st.multiselect(
            "Selecciona las filas a eliminar (por índice)",
            options=df_display.index.tolist(),
            format_func=lambda x: f"{x}: {df_display.loc[x, 'activo']} - {df_display.loc[x, 'tipo']} - {df_display.loc[x, 'fecha'].strftime('%Y-%m-%d')}"
        )
        
        if st.button("Eliminar transacciones seleccionadas"):
            if filas_a_eliminar:
                st.session_state.df_transacciones = st.session_state.df_transacciones.drop(
                    index=[int(i) for i in filas_a_eliminar]
                ).reset_index(drop=True)
                st.success(f"Eliminadas {len(filas_a_eliminar)} transacciones.")
            else:
                st.warning("Selecciona al menos una transacción para eliminar.")
    else:
        st.info("No hay transacciones para eliminar.")


    st.dataframe(
        st.session_state.df_transacciones,
        use_container_width=True,
        height=500
    )



# --- Segunda ventana: Precios actuales ---
with tab2:
    st.subheader("Precios actuales de tus activos en cartera")

    if not st.session_state.df_transacciones.empty:
        activos_unicos = st.session_state.df_transacciones['activo'].dropna().unique()

        precios = []
        precios_dict = {}

        for activo in activos_unicos:
            ticker_yf = equivalencias_yf.get(activo.upper(), activo)
            precio_actual = obtener_precio_actual(ticker_yf)

            precios.append({
                'Activo': activo,
                'Precio actual (€)': precio_actual if precio_actual is not None else "No disponible"
            })

            if precio_actual is not None:
                precios_dict[activo] = precio_actual

        # Guardamos en sesión para reutilizar
        st.session_state.precios_actuales = precios_dict

        df_precios = pd.DataFrame(precios)
        st.dataframe(df_precios)

    else:
        st.info("No tienes activos registrados para consultar precios actuales.")
        


        
# --- Tercera ventana: Posición Global ---      
with tab3:
    st.subheader("Posición Global de tu Cartera")

    if st.session_state.df_transacciones.empty:
        st.info("No tienes transacciones registradas.")
    else:
        if "precios_actuales" not in st.session_state:
            st.warning("Primero accede a la ventana 'Precios actuales' para cargar los precios en tiempo real.")
        else:
            import plotly.express as px

            activos = st.session_state.df_transacciones['activo'].dropna().unique()
            resumen = []

            for activo in activos:
                df_activo = st.session_state.df_transacciones[
                    st.session_state.df_transacciones['activo'] == activo
                ].sort_values('fecha')

                # FIFO para lotes abiertos
                lotes_abiertos = []
                for _, fila in df_activo.iterrows():
                    tipo = fila['tipo']
                    cantidad = fila['cantidad']
                    precio = fila['precio_unitario']
                    if tipo == 'compra':
                        lotes_abiertos.append({'cantidad': cantidad, 'precio': precio})
                    elif tipo == 'venta':
                        cantidad_vender = cantidad
                        while cantidad_vender > 0 and lotes_abiertos:
                            lote = lotes_abiertos[0]
                            if lote['cantidad'] <= cantidad_vender:
                                cantidad_vender -= lote['cantidad']
                                lotes_abiertos.pop(0)
                            else:
                                lote['cantidad'] -= cantidad_vender
                                cantidad_vender = 0

                posicion_abierta = sum(l['cantidad'] for l in lotes_abiertos)
                precio_medio_compra = (
                    sum(l['cantidad'] * l['precio'] for l in lotes_abiertos) / posicion_abierta
                    if posicion_abierta > 0 else 0
                )
                valor_compra = posicion_abierta * precio_medio_compra

                # Ganancias realizadas FIFO
                lotes_fifo = []
                ganancia_realizada = 0
                total_vendido = 0
                suma_precio_venta_pesada = 0

                for _, fila in df_activo.iterrows():
                    tipo = fila['tipo']
                    cantidad = fila['cantidad']
                    precio = fila['precio_unitario']
                    if tipo == 'compra':
                        lotes_fifo.append({'cantidad': cantidad, 'precio': precio})
                    elif tipo == 'venta':
                        cantidad_vender = cantidad
                        total_vendido += cantidad
                        suma_precio_venta_pesada += cantidad * precio
                        while cantidad_vender > 0 and lotes_fifo:
                            lote = lotes_fifo[0]
                            cantidad_usada = min(lote['cantidad'], cantidad_vender)
                            ganancia_realizada += cantidad_usada * (precio - lote['precio'])
                            lote['cantidad'] -= cantidad_usada
                            cantidad_vender -= cantidad_usada
                            if lote['cantidad'] == 0:
                                lotes_fifo.pop(0)

                precio_actual = st.session_state.precios_actuales.get(activo, None)
                valor_actual = precio_actual * posicion_abierta if precio_actual is not None else None
                pnl_no_realizado = (precio_actual - precio_medio_compra) * posicion_abierta if precio_actual else None

                # Inversión en ventas
                compras_fifo = []
                for _, r in df_activo[df_activo['tipo'] == 'compra'].sort_values('fecha').iterrows():
                    compras_fifo.append({'cantidad': r['cantidad'], 'precio': r['precio_unitario']})

                cantidad_a_calcular = total_vendido
                inversion_ventas = 0
                while cantidad_a_calcular > 0 and compras_fifo:
                    lote = compras_fifo[0]
                    usar = min(lote['cantidad'], cantidad_a_calcular)
                    inversion_ventas += usar * lote['precio']
                    lote['cantidad'] -= usar
                    cantidad_a_calcular -= usar
                    if lote['cantidad'] == 0:
                        compras_fifo.pop(0)

                balance = ganancia_realizada + (pnl_no_realizado if pnl_no_realizado is not None else 0)

                resumen.append({
                    "Activo": activo,
                    "Posición Abierta": round(posicion_abierta, 8),
                    "Precio Medio Compra (€)": precio_medio_compra,
                    "Valor Compra (€)": valor_compra,
                    "Valor Actual (€)": valor_actual if valor_actual is not None else 0,
                    "PNL No Realizado (€)": pnl_no_realizado if pnl_no_realizado is not None else 0,
                    "Unidades Vendidas": round(total_vendido, 8),
                    "Inversión en Ventas (€)": inversion_ventas,
                    "Ingreso por Ventas (€)": suma_precio_venta_pesada,
                    "Ganancia/Pérdida Realizada (€)": ganancia_realizada,
                    "Balance (€)": balance,
                })

            df_resumen = pd.DataFrame(resumen)

            st.markdown("### Resumen de Posición")
            st.dataframe(df_resumen.style.format({
                "Precio Medio Compra (€)": "€{:.2f}",
                "Valor Compra (€)": "€{:.2f}",
                "Valor Actual (€)": "€{:.2f}",
                "PNL No Realizado (€)": "€{:.2f}",
                "Inversión en Ventas (€)": "€{:.2f}",
                "Ingreso por Ventas (€)": "€{:.2f}",
                "Ganancia/Pérdida Realizada (€)": "€{:.2f}",
                "Balance (€)": "€{:.2f}"
            }), use_container_width=True)

            st.divider()

            # --- GRAFICOS VISUALES ---
            st.markdown("### Visualización de tu cartera")
            
            # --- Tabla Resumen Avanzada: Posiciones Abiertas, Cerradas y Global por Activo ---
            
            st.markdown("### 📊 Resumen de Posiciones Abiertas, Cerradas y Global")
            
            # --- Crear dataframe resumen avanzado ---
            tabla_resumen = []
            
            for idx, row in df_resumen.iterrows():
                activo = row["Activo"]
            
                # Posición Abierta
                pa = row["PNL No Realizado (€)"] if row["Posición Abierta"] > 0 else 0
            
                # Posición Cerrada
                pc = row["Ganancia/Pérdida Realizada (€)"]
            
                # Posición Global
                pg = pa + pc
            
                tabla_resumen.append({
                    "Activo": activo,
                    "Posiciones abiertas (€)": pa,
                    "Posiciones cerradas (€)": pc,
                    "Posición global (€)": pg
                })
            
            df_tabla_resumen = pd.DataFrame(tabla_resumen)
            
            # Añadir fila Total
            fila_total = {
                "Activo": "TOTAL",
                "Posiciones abiertas (€)": df_tabla_resumen["Posiciones abiertas (€)"].sum(),
                "Posiciones cerradas (€)": df_tabla_resumen["Posiciones cerradas (€)"].sum(),
                "Posición global (€)": df_tabla_resumen["Posición global (€)"].sum(),
            }
            df_tabla_resumen = pd.concat([df_tabla_resumen, pd.DataFrame([fila_total])], ignore_index=True)
            
            
            # Mostrar tabla numérica limpia y coloreada
            st.dataframe(
                df_tabla_resumen.style
                .format({"Posiciones abiertas (€)": "€{:.2f}",
                         "Posiciones cerradas (€)": "€{:.2f}",
                         "Posición global (€)": "€{:.2f}"})
                .applymap(lambda v: 'background-color: #d4f7d4' if v > 0 else ('background-color: #f7d4d4' if v < 0 else ''),
                          subset=["Posiciones abiertas (€)", "Posiciones cerradas (€)", "Posición global (€)"]),
                use_container_width=True
            )

            st.write("")
            st.write("")
            st.write("")
            st.write("")
            
            # --- Gráfico de barras agrupadas ---
            
            # Lista de todos los activos disponibles
            activos_todos = df_tabla_resumen["Activo"].tolist()
            
            # Multiselect para que el usuario elija activos a mostrar
            activos_seleccionados = st.multiselect(
                "Selecciona los activos para mostrar en el gráfico",
                options=activos_todos,
                default=activos_todos[:5]  # Mostrar por defecto los primeros 5 activos (puedes cambiar este número)
            )
            
            # Filtrar solo los activos seleccionados
            df_filtrado = df_tabla_resumen[df_tabla_resumen["Activo"].isin(activos_seleccionados)]
            
            # Extraer listas para el gráfico
            activos = df_filtrado["Activo"].tolist()
            abiertas = df_filtrado["Posiciones abiertas (€)"].tolist()
            cerradas = df_filtrado["Posiciones cerradas (€)"].tolist()
            globales = df_filtrado["Posición global (€)"].tolist()
            
            # Crear gráfico
            fig_barras = go.Figure()
            
            fig_barras.add_trace(go.Bar(
                x=activos,
                y=abiertas,
                name="Posiciones abiertas",
                marker_color="#4A90E2"  # azul claro
            ))
            
            fig_barras.add_trace(go.Bar(
                x=activos,
                y=cerradas,
                name="Posiciones cerradas",
                marker_color="#F5A623"  # naranja
            ))
            
            fig_barras.add_trace(go.Bar(
                x=activos,
                y=globales,
                name="Posición global",
                marker_color="#A3C686"
            ))
            
            fig_barras.update_layout(
                title="📊 Resumen de Resultados por Activo",
                xaxis_title="Activo",
                yaxis_title="Saldo (€)",
                barmode='group',
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5)
            )
            
            st.plotly_chart(fig_barras, use_container_width=True)

            
            
# --- Cuarta ventana: Posiciones abiertas ---         
with tab4:
        st.subheader("Posiciones abiertas de la cartera")
    
        if st.session_state.df_transacciones.empty:
            st.info("No hay transacciones registradas.")
        else:
            df = st.session_state.df_transacciones.copy()
    
            filas_resumen = []
            grupos = df.groupby(['activo', 'tipo_activo'])
    
            for (activo, tipo_activo), grupo in grupos:
                posicion, precio_medio = calcular_posicion_y_precio_medio_fifo(grupo)
                num_trans = len(grupo)
                filas_resumen.append({
                    'Activo': activo,
                    'Tipo de Activo': tipo_activo,
                    'Posición': posicion,
                    'Precio medio de compra (€)': round(precio_medio, 2),
                    'Nº de transacciones': num_trans
                })
    
            resumen = pd.DataFrame(filas_resumen)
    
            st.dataframe(resumen)    


            # Gráfico 1: PNL No Realizado por Activo
            fig_pnl = px.bar(
                df_resumen,
                x="PNL No Realizado (€)",
                y="Activo",
                orientation='h',
                color="PNL No Realizado (€)",
                color_continuous_scale=["red", "green"],
                title="PNL No Realizado por Activo"
            )
            st.plotly_chart(fig_pnl, use_container_width=True)

            # Gráfico 2: Distribución de Valor Actual por Activo
            if df_resumen["Valor Actual (€)"].sum() > 0:
                fig_pie = px.pie(
                    df_resumen,
                    values="Valor Actual (€)",
                    names="Activo",
                    title="Distribución de tu cartera por Valor Actual"
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            # Gráfico 3: Valor Actual vs Valor Compra
            fig_comp = px.bar(
                df_resumen,
                x="Activo",
                y=["Valor Compra (€)", "Valor Actual (€)"],
                barmode="group",
                title="Valor de Compra vs Valor Actual por Activo"
            )
            st.plotly_chart(fig_comp, use_container_width=True)
        
        
# --- Quinta ventana: Ganancias FIFO ---       
with tab5:
    # Selección del activo para cálculo FIFO
    if not st.session_state.df_transacciones.empty:
        activos_disponibles = [''] + st.session_state.df_transacciones['activo'].dropna().unique().tolist()
    else:
        activos_disponibles = ['']

    activo_seleccionado = st.selectbox("Selecciona el activo para calcular ganancias FIFO", options=activos_disponibles)

    if activo_seleccionado and activo_seleccionado != '':
        # Filtrar transacciones solo del activo seleccionado
        transacciones_activo = st.session_state.df_transacciones[
            st.session_state.df_transacciones['activo'] == activo_seleccionado
        ].sort_values('fecha')

        df_ganancias = calcular_ganancias_fifo(transacciones_activo)

        st.subheader(f"Ganancias por ventas FIFO de {activo_seleccionado}")
        if not df_ganancias.empty:
            st.dataframe(df_ganancias)
            ganancia_total = df_ganancias['ganancia'].sum()
            st.markdown(f"**Ganancia total:** €{ganancia_total:.2f}")
        else:
            st.write("No hay ventas registradas para este activo.")

        # Posición actual (cantidad neta)
        def calcular_posicion_actual(transacciones):
            compras = transacciones[transacciones['tipo'] == 'compra']['cantidad'].sum()
            ventas = transacciones[transacciones['tipo'] == 'venta']['cantidad'].sum()
            return compras - ventas

        posicion_actual = calcular_posicion_actual(transacciones_activo)
        st.markdown(f"**Posición actual:** {posicion_actual} unidades")

        # ROI básico (ganancia / inversión total)
        def calcular_inversion_total(transacciones):
            compras = transacciones[transacciones['tipo'] == 'compra']
            return (compras['cantidad'] * compras['precio_unitario']).sum()

        inversion_total = calcular_inversion_total(transacciones_activo)

        if inversion_total > 0 and not df_ganancias.empty and 'ganancia' in df_ganancias.columns:
            roi = (df_ganancias['ganancia'].sum() / inversion_total) * 100
            st.markdown(f"**ROI acumulado:** {roi:.2f}%")
        else:
            st.markdown("**ROI acumulado:** No disponible (sin compras o sin ganancias)")
    else:
        st.info("Por favor, selecciona un activo para calcular ganancias.")




# --- Sexta ventana: Informe Hacienda ---  

with tab6:
    st.subheader("🧾 Informe para Hacienda")

    if st.session_state.df_transacciones.empty:
        st.info("No hay transacciones registradas para generar el informe.")
    else:
        df = st.session_state.df_transacciones.copy()
        df["importe_total"] = df["precio_unitario"].astype(float) * df["cantidad"].astype(float)
        df["año"] = pd.to_datetime(df["fecha"]).dt.year

        # Función FIFO para ganancia total (ya la tienes)
        def calcular_ganancia_fifo(grupo):
            grupo = grupo.sort_values('fecha').copy()
            inventario = []
            ganancia_total = 0.0

            for _, fila in grupo.iterrows():
                tipo = fila['tipo']
                cantidad = fila['cantidad']
                precio_unitario = fila['precio_unitario']

                if tipo == 'compra':
                    inventario.append({'cantidad': cantidad, 'precio_unitario': precio_unitario})
                elif tipo == 'venta':
                    cantidad_a_vender = cantidad
                    coste_venta = 0.0

                    while cantidad_a_vender > 0 and inventario:
                        lote = inventario[0]
                        if lote['cantidad'] <= cantidad_a_vender:
                            coste_venta += lote['cantidad'] * lote['precio_unitario']
                            cantidad_a_vender -= lote['cantidad']
                            inventario.pop(0)
                        else:
                            coste_venta += cantidad_a_vender * lote['precio_unitario']
                            lote['cantidad'] -= cantidad_a_vender
                            cantidad_a_vender = 0

                    ingreso_venta = cantidad * precio_unitario
                    ganancia_total += ingreso_venta - coste_venta

            return ganancia_total

        # --- Informe resumen por activo y año ---
        resumen_hacienda = []
        grupos = df.groupby(["activo", "año"])

        for (activo, año), grupo in grupos:
            compras = grupo[grupo["tipo"] == "compra"]["importe_total"].sum()
            ventas = grupo[grupo["tipo"] == "venta"]["importe_total"].sum()
            ganancia_realizada = calcular_ganancia_fifo(grupo)

            resumen_hacienda.append({
                "Activo": activo,
                "Año": año,
                "Total Compras (€)": compras,
                "Total Ventas (€)": ventas,
                "Ganancia/Pérdida Realizada (€)": ganancia_realizada
            })

        df_resumen_hacienda = pd.DataFrame(resumen_hacienda)

        st.dataframe(
            df_resumen_hacienda.style.format({
                "Total Compras (€)": "€{:.2f}",
                "Total Ventas (€)": "€{:.2f}",
                "Ganancia/Pérdida Realizada (€)": "€{:.2f}"
            }),
            use_container_width=True
        )

        # Botones para descargar resumen
        csv_resumen = df_resumen_hacienda.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Descargar resumen para Hacienda (CSV)",
            data=csv_resumen,
            file_name="informe_hacienda_resumen.csv",
            mime="text/csv"
        )

        output_resumen_excel = io.BytesIO()
        with pd.ExcelWriter(output_resumen_excel, engine='xlsxwriter') as writer:
            df_resumen_hacienda.to_excel(writer, index=False, sheet_name='Resumen')
        output_resumen_excel.seek(0)

        st.download_button(
            label="📄 Descargar resumen para Hacienda (Excel)",
            data=output_resumen_excel,
            file_name="informe_hacienda_resumen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # --- Tabla detallada de ventas con FIFO ---
        st.markdown("---")
        st.subheader("Detalle de cada venta con cálculo FIFO")

        detalle_ventas = []

        activos = df['activo'].unique()
        for activo in activos:
            grupo_activo = df[df['activo'] == activo].sort_values('fecha').copy()
            inventario = []

            for _, fila in grupo_activo.iterrows():
                tipo = fila['tipo']
                cantidad = fila['cantidad']
                precio_unitario = fila['precio_unitario']
                fecha = fila['fecha']

                if tipo == 'compra':
                    inventario.append({'cantidad': cantidad, 'precio_unitario': precio_unitario})
                elif tipo == 'venta':
                    cantidad_a_vender = cantidad
                    coste_total_compra = 0.0
                    cantidad_total_vendida = 0.0

                    while cantidad_a_vender > 0 and inventario:
                        lote = inventario[0]
                        if lote['cantidad'] <= cantidad_a_vender:
                            coste_total_compra += lote['cantidad'] * lote['precio_unitario']
                            cantidad_a_vender -= lote['cantidad']
                            cantidad_total_vendida += lote['cantidad']
                            inventario.pop(0)
                        else:
                            coste_total_compra += cantidad_a_vender * lote['precio_unitario']
                            lote['cantidad'] -= cantidad_a_vender
                            cantidad_total_vendida += cantidad_a_vender
                            cantidad_a_vender = 0

                    if cantidad_total_vendida > 0:
                        precio_medio_compra = coste_total_compra / cantidad_total_vendida
                        balance = (precio_unitario - precio_medio_compra) * cantidad_total_vendida
                    else:
                        precio_medio_compra = 0
                        balance = 0

                    detalle_ventas.append({
                        "Activo": activo,
                        "Fecha venta": fecha,
                        "Cantidad vendida": cantidad_total_vendida,
                        "Precio medio compra (€)": precio_medio_compra,
                        "Precio venta (€)": precio_unitario,
                        "Balance (€)": balance
                    })

        df_detalle_ventas = pd.DataFrame(detalle_ventas)

        st.dataframe(
            df_detalle_ventas.style.format({
                "Precio medio compra (€)": "€{:.2f}",
                "Precio venta (€)": "€{:.2f}",
                "Balance (€)": "€{:.2f}",
                "Cantidad vendida": "{:.6f}"
            }),
            use_container_width=True
        )

        # Botones para descargar detalle
        csv_detalle = df_detalle_ventas.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📄 Descargar detalle de ventas (CSV)",
            data=csv_detalle,
            file_name="detalle_ventas.csv",
            mime="text/csv"
        )

        output_detalle_excel = io.BytesIO()
        with pd.ExcelWriter(output_detalle_excel, engine='xlsxwriter') as writer:
            df_detalle_ventas.to_excel(writer, index=False, sheet_name='Detalle Ventas')
        output_detalle_excel.seek(0)

        st.download_button(
            label="📄 Descargar detalle de ventas (Excel)",
            data=output_detalle_excel,
            file_name="detalle_ventas.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
