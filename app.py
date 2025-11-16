from flask import Flask, render_template, request, session, redirect
import json
from datetime import datetime, timedelta
import os
import plotly.graph_objects as go
from collections import defaultdict
import uuid

app = Flask(__name__)
app.secret_key = "artecanete2025" # Cambia esto por una clave secreta segura

# --- CONSTANTES DE ARCHIVO ---
DATA_FILE = "tienda_data.json" 

# --- Funciones de Persistencia para el Servidor ---

def get_initial_data():
    """Estructura inicial completa de datos para el servidor."""
    return {
        "juegos": [], 
        "ventas": [], 
        "devoluciones": [], 
        "caja_actual": 200.00,
        "FSE_contador": 0,
        "FST_contador": 0,
        "retiros": [] # La clave crucial que podría faltar
    }

def cargar_datos():
    """
    Carga los datos principales del TPV, asegurando que todas las claves existan.
    Esto protege contra errores 500 si el archivo guardado es de una versión anterior.
    """
    data = get_initial_data() # Inicializa con la estructura completa
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Fusiona la data cargada sobre la estructura inicial
                data.update(loaded_data)
        except Exception:
            # Si hay error al cargar, usamos la estructura inicial completa (data)
            print("Advertencia: Archivo de datos corrupto o vacío, usando estructura inicial.")
            pass
    return data

def guardar_datos(data):
    """Guarda todos los datos principales en un solo archivo."""
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error al guardar datos: {e}")

# --- SINCRONIZACIÓN WEB (ROBUSTA) ---
@app.route('/sync', methods=['POST'])
def sync():
    """Recibe el payload completo del TPV de escritorio y actualiza el estado del servidor."""
    try:
        nuevo_payload = request.json
        if not nuevo_payload:
            return {"status": "error", "message": "Payload de sincronización vacío."}, 400
            
        data = cargar_datos()

        # Helper para fusionar listas por ID (o 'fecha' para retiros)
        def merge_list(existing_list, new_list, id_key):
            ids_existentes = {item.get(id_key) for item in existing_list if item.get(id_key)}
            updates = 0
            for new_item in new_list:
                # Usamos una clave de ID que es única y consistente (UUID en Ventas.py)
                item_id = new_item.get(id_key)
                if item_id and item_id not in ids_existentes:
                    existing_list.append(new_item)
                    updates += 1
            return existing_list, updates

        # 1. Sincronización de Juegos (Inventario - El TPV es la fuente maestra)
        data['juegos'] = nuevo_payload.get('juegos', [])

        # 2. Sincronización de Ventas, Devoluciones y Retiros
        # Usamos 'id' para Ventas/Devoluciones, que ahora se genera con UUID
        data['ventas'], nuevas_ventas = merge_list(data['ventas'], nuevo_payload.get('ventas', []), 'id')
        data['devoluciones'], nuevas_devoluciones = merge_list(data['devoluciones'], nuevo_payload.get('devoluciones', []), 'id')
        # Usamos 'id' para Retiros también, ya que se generó un UUID en Ventas.py
        data['retiros'], nuevos_retiros = merge_list(data['retiros'], nuevo_payload.get('retiros', []), 'id') 

        # 3. Sincronización de Caja y Fichas (Reemplazar)
        data['caja_actual'] = nuevo_payload.get('caja_actual', data['caja_actual'])
        data['FSE_contador'] = nuevo_payload.get('FSE_contador', data['FSE_contador'])
        data['FST_contador'] = nuevo_payload.get('FST_contador', data['FST_contador'])

        # 4. Guardar Datos
        guardar_datos(data)

        return {
            "status": "success",
            "message": "Datos sincronizados.",
            "updates": {
                "nuevas_ventas": nuevas_ventas,
                "nuevos_retiros": nuevos_retiros
            }
        }, 200

    except Exception as e:
        # Devuelve el error para ayudar a la depuración en el TPV
        print(f"ERROR EN SINCRONIZACIÓN WEB: {e}")
        return {"status": "error", "message": f"Fallo interno del servidor: {str(e)}"}, 500

# --- LÓGICA DE REPORTES ---

def generar_reporte_html(data):
    """Genera el contenido HTML del dashboard de reportes."""
    
    ventas = data.get("ventas", [])
    devoluciones = data.get("devoluciones", [])
    juegos = data.get("juegos", [])
    retiros = data.get("retiros", [])
    
    # --- Cálculos Principales ---
    total_ventas_brutas = sum(v.get('total', 0) for v in ventas)
    total_devoluciones = sum(d.get('total_devuelto', 0) for d in devoluciones)
    ventas_netas = total_ventas_brutas - total_devoluciones
    
    total_efectivo_vendido = sum(v.get('total', 0) for v in ventas if v.get('metodo') == 'Efectivo')
    total_tarjeta_vendido = sum(v.get('total', 0) for v in ventas if v.get('metodo') == 'Tarjeta')
    
    # --- Stock Crítico ---
    stock_critico = [j for j in juegos if j.get('stock', 0) <= 5 and j.get('stock', 0) > 0]
    stock_critico_html = ""
    if stock_critico:
        stock_critico_html = "<table class='min-w-full divide-y divide-gray-200'><thead><tr><th class='px-4 py-2'>Nombre</th><th class='px-4 py-2'>Stock</th></tr></thead><tbody>"
        for j in stock_critico:
            stock_critico_html += f"<tr><td class='px-4 py-2'>{j.get('nombre', 'N/A')}</td><td class='px-4 py-2 text-red-600 font-bold'>{j.get('stock', 'N/A')}</td></tr>"
        stock_critico_html += "</tbody></table>"
    
    # --- Retiros ---
    retiros_recientes = sorted(retiros, key=lambda x: x.get('fecha', '0'), reverse=True)[:5]
    retiros_html = ""
    for r in retiros_recientes:
        try:
            fecha_iso = r.get('fecha', '')
            fecha = datetime.fromisoformat(fecha_iso).strftime('%d/%m/%Y %H:%M')
        except (ValueError, TypeError):
             fecha = "Fecha Inválida"
             
        importe = abs(r.get('cantidad', 0))
        retiros_html += f"<tr><td class='px-4 py-2 text-gray-600'>{fecha}</td><td class='px-4 py-2 text-red-600 font-semibold'>-{importe:.2f} €</td></tr>"
    
    # --- Ventas por Vendedor (Tabla) ---
    ventas_por_vendedor = defaultdict(float)
    for v in ventas:
        vendedor = v.get('vendedor', 'Desconocido')
        ventas_por_vendedor[vendedor] += v.get('total', 0)
    
    vendedor_html = "<table class='min-w-full divide-y divide-gray-200'><thead><tr><th class='px-4 py-2'>Vendedor</th><th class='px-4 py-2'>Total Ventas (€)</th></tr></thead><tbody>"
    for vendedor, total in ventas_por_vendedor.items():
        vendedor_html += f"<tr><td class='px-4 py-2'>{vendedor}</td><td class='px-4 py-2 font-semibold'>{total:.2f}</td></tr>"
    vendedor_html += "</tbody></table>"
    
    # --- Gráfico de Ventas por Hora (Plotly) ---
    ventas_por_hora = defaultdict(float)
    for v in ventas:
        try:
            dt = datetime.fromisoformat(v['fecha'])
            hora = dt.hour
            ventas_por_hora[hora] += v.get('total', 0)
        except:
            continue

    horas_labels = [f"{h:02}:00" for h in range(24)]
    valores_horas = [ventas_por_hora[h] for h in range(24)]

    fig = go.Figure(data=[
        go.Bar(x=horas_labels, y=valores_horas, marker_color='#3498db')
    ])
    fig.update_layout(
        title='Ventas por Hora (Todas las Fechas)',
        xaxis_title='Hora del Día',
        yaxis_title='Importe Total (€)',
        template='plotly_white',
        margin=dict(l=20, r=20, t=40, b=20),
        height=300
    )
    grafico_horas = fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    # --- HTML de la Página ---
    html = f'''
    <!doctype html>
    <html lang="es">
    <head>
        <title>Panel Admin - Arte Cañete TPV</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <script src="https://cdn.plot.ly/plotly-latest.min.js"></script>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap');
            body {{ font-family: 'Inter', sans-serif; }}
            .container {{ max-width: 1200px; margin: auto; padding: 20px; }}
            .card {{ background: #ffffff; padding: 20px; border-radius: 8px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); margin-bottom: 20px; }}
            .metric {{ text-align: center; padding: 15px; border-radius: 6px; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #f3f4f6; text-align: left; }}
            th {{ background-color: #f9fafb; font-weight: 600; }}
            .btn {{ transition: background-color 0.3s; }}
            .btn:hover {{ background: #c0392b; }}
        </style>
    </head>
    <body class="bg-gray-50">
    <div class="container">
    <h1 class="text-3xl font-bold text-gray-800 mb-6 border-b pb-2">Panel de Administración TPV</h1>
    
    <div class="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8">
        <div class="card metric bg-blue-100 border-l-4 border-blue-500">
            <h3 class="text-2xl text-blue-700">{data.get('caja_actual', 0.00):.2f} €</h3>
            <p class="text-sm text-gray-600">Saldo de Caja (Efectivo)</p>
        </div>
        <div class="card metric bg-green-100 border-l-4 border-green-500">
            <h3 class="text-2xl text-green-700">{ventas_netas:.2f} €</h3>
            <p class="text-sm text-gray-600">Ventas Netas Totales</p>
        </div>
        <div class="card metric bg-yellow-100 border-l-4 border-yellow-500">
            <h3 class="text-2xl text-yellow-700">{data.get('FST_contador', 0) + data.get('FSE_contador', 0)}</h3>
            <p class="text-sm text-gray-600">Fichas Canjeadas (Total)</p>
        </div>
        <div class="card metric bg-red-100 border-l-4 border-red-500">
            <h3 class="text-2xl text-red-700">{len(stock_critico)}</h3>
            <p class="text-sm text-gray-600">Juegos en Stock Crítico (&le; 5)</p>
        </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        <div class="card col-span-2">
            <h2 class="text-xl font-semibold mb-4 text-gray-800">📊 Resumen de Ventas y Vendedores</h2>
            <div class="grid grid-cols-2 gap-4 mb-6">
                <div class="p-3 bg-gray-50 rounded">Total Efectivo: <strong class="text-blue-600">{total_efectivo_vendido:.2f} €</strong></div>
                <div class="p-3 bg-gray-50 rounded">Total Tarjeta: <strong class="text-blue-600">{total_tarjeta_vendido:.2f} €</strong></div>
                <div class="p-3 bg-gray-50 rounded">Ventas Brutas: <strong class="text-green-600">{total_ventas_brutas:.2f} €</strong></div>
                <div class="p-3 bg-gray-50 rounded">Devoluciones: <strong class="text-red-600">-{total_devoluciones:.2f} €</strong></div>
            </div>
            
            <h3 class="text-lg font-semibold mt-6 mb-3 text-gray-700">Ventas Totales por Vendedor</h3>
            {vendedor_html}
        </div>
        
        <div class="card">
            <h2 class="text-xl font-semibold mb-4 text-gray-800">⚠️ Inventario y Flujo de Caja</h2>
            
            <h3 class="text-lg font-semibold mt-4 mb-3 text-gray-700">Stock Crítico</h3>
            {stock_critico_html or "<p class='text-center text-gray-500 py-4'>No hay productos en stock crítico.</p>"}
            
            <h3 class="text-lg font-semibold mt-6 mb-3 text-gray-700 border-t pt-4">Últimos Retiros de Caja</h3>
            <table class='min-w-full divide-y divide-gray-200'>
                <thead><tr><th class='px-4 py-2'>Fecha</th><th class='px-4 py-2'>Importe</th></tr></thead>
                <tbody>{retiros_html or "<tr><td colspan='2' class='text-center text-gray-500 py-4'>No hay retiros registrados.</td></tr>"}</tbody>
            </table>
        </div>
    </div>

    <div class="card mt-6">
        <h2 class="text-xl font-semibold mb-4 text-gray-800">📈 Distribución de Ventas por Hora</h2>
        <div id="plotly-graph" class="w-full overflow-hidden">
            {grafico_horas}
        </div>
    </div>

    <a href="/logout" class="btn bg-gray-500 hover:bg-gray-700 text-white font-bold py-2 px-4 rounded-md shadow-md mt-6">Cerrar Sesión</a>
    </div>
    </body></html>
    '''
    return html

# --- RUTAS DE FLASK ---

@app.route('/')
def login():
    if session.get('logged_in'):
        return redirect('/dashboard')
        
    return '''
    <html><body style="font-family: 'Inter', sans-serif;text-align:center;padding:50px;background:#f0f0f0;">
    <div style="background:white;padding:30px;border-radius:10px;max-width:400px;margin:auto;box-shadow:0 0 10px rgba(0,0,0,0.1);">
    <h1>Panel de Administración</h1>
    <form method="post" action="/login">
        <input type="password" name="password" placeholder="Contraseña Admin" style="padding:10px;margin:10px;width:80%;border:1px solid #ccc;border-radius:5px;">
        <button type="submit" style="padding:10px 20px;background:#007bff;color:white;border:none;border-radius:5px;cursor:pointer;">Acceder</button>
    </form>
    </div></body></html>
    '''

@app.route('/login', methods=['POST'])
def do_admin_login():
    if request.form['password'] == 'admin': 
        session['logged_in'] = True
    return redirect('/dashboard')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/')
        
    data = cargar_datos()
    return generar_reporte_html(data)

if __name__ == '__main__':
    if not os.path.exists(DATA_FILE):
        guardar_datos(get_initial_data()) 
        
    app.run(debug=True, port=5000)
