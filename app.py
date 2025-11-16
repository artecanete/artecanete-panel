from flask import Flask, request, session, redirect
from datetime import datetime
import json
from collections import defaultdict
import plotly.graph_objs as go
import plotly.io as pio
import os
import uuid

# Importar la configuración de Firebase
from firebase_config import DB

app = Flask(__name__)
# Usaremos una clave secreta del entorno para mayor seguridad
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'artecanete2025_default_key')

# --- FUNCIONES DE GRÁFICO ---
def generar_grafico_ventas(ventas):
    """Genera un gráfico de barras interactivo de ventas por hora."""
    ventas_por_hora = defaultdict(float)
    
    # Filtrar ventas de hoy y acumular por hora
    hoy = datetime.now().date()
    for v in ventas:
        try:
            # Asume que la fecha está en formato ISO
            fecha_venta = datetime.fromisoformat(v["fecha_venta"])
            if fecha_venta.date() == hoy:
                hora = fecha_venta.hour
                ventas_por_hora[hora] += sum(item['precio'] * item['cantidad'] for item in v['productos'])
        except Exception:
            pass

    horas = sorted(ventas_por_hora.keys())
    montos = [ventas_por_hora[h] for h in horas]

    fig = go.Figure(data=[
        go.Bar(
            x=[f"{h}:00" for h in horas], 
            y=montos,
            marker_color='#007bff'
        )
    ])
    
    fig.update_layout(
        title='Ventas Totales por Hora (Hoy)',
        xaxis_title='Hora del Día',
        yaxis_title='Monto Total Vendido (€)',
        xaxis_tickangle=-45,
        plot_bgcolor='#f8f9fa',
        paper_bgcolor='#f8f9fa',
        margin=dict(l=40, r=20, t=40, b=40),
        height=300
    )
    return pio.to_html(fig, full_html=False, include_plotlyjs='cdn')

# --- RUTAS DE LA APLICACIÓN ---

@app.route('/')
def login():
    """Página de login simple."""
    if 'logged_in' in session:
        return redirect('/dashboard')
        
    return '''
    <html><head><title>Login</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script><style>
        .login-card { max-width: 400px; margin: 100px auto; padding: 40px; }
    </style></head>
    <body class="bg-gray-100 font-sans">
    <div class="login-card bg-white rounded-xl shadow-2xl">
        <h1 class="text-3xl font-bold mb-6 text-gray-800">Acceso a Panel</h1>
        <form method="post" action="/login">
            <input type="password" name="password" placeholder="Contraseña de Administrador" required
                   class="w-full px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 mb-4 text-lg">
            <button type="submit" class="w-full bg-blue-600 text-white font-semibold py-3 rounded-lg hover:bg-blue-700 transition duration-300 shadow-md">
                Ingresar
            </button>
        </form>
    </div>
    </body></html>'''

@app.route('/login', methods=['POST'])
def do_login():
    """Maneja la autenticación. La clave es 'admin'."""
    ADMIN_PASSWORD = "admin" # Contraseña simple, cambiar en producción
    if request.form['password'] == ADMIN_PASSWORD:
        session['logged_in'] = True
        return redirect('/dashboard')
    else:
        return redirect('/')

@app.route('/dashboard')
def dashboard():
    """Muestra el panel de control, cargando datos desde Firebase."""
    if not session.get('logged_in'):
        return redirect('/')

    data = DB.get_data()
    ventas = data.get("ventas", [])
    caja_actual = data.get("caja_actual", 0.00)
    stock = data.get("stock", {})
    retiros = data.get("retiros", [])

    # Cálculo de métricas
    total_ventas = sum(sum(item['precio'] * item['cantidad'] for item in v['productos']) for v in ventas)
    
    # Ordenar retiros por fecha descendente
    try:
        retiros_ordenados = sorted(retiros, key=lambda r: r.get('fecha', ''), reverse=True)
    except TypeError:
        retiros_ordenados = retiros

    # 1. Gráfico de ventas por hora
    grafico_horas = generar_grafico_ventas(ventas)

    # 2. Resumen de Stock
    stock_html = ""
    for producto, cantidad in stock.items():
        stock_html += f"<tr><td>{producto}</td><td class='text-center'>{'<span class=\"text-red-500 font-bold\">' if cantidad < 5 else ''}{cantidad}{'</span>' if cantidad < 5 else ''}</td></tr>"

    # 3. Retiros
    retiros_html = ""
    for r in retiros_ordenados[:5]: # Mostrar solo los 5 últimos
        try:
            fecha_retiro = datetime.fromisoformat(r['fecha']).strftime('%d/%m/%Y %H:%M')
        except ValueError:
            fecha_retiro = r['fecha'] # Mostrar la fecha tal cual si no es ISO
            
        retiros_html += f"<tr><td>{fecha_retiro}</td><td class='text-right text-red-600'>-€{r['importe']:.2f}</td></tr>"
        
    html = f'''
    <html><head><title>Dashboard ArteCanete</title><meta name="viewport" content="width=device-width, initial-scale=1.0">
    <script src="https://cdn.tailwindcss.com"></script><style>
        .card {{ background-color: #fff; padding: 20px; border-radius: 12px; box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1); margin-bottom: 20px; }}
        h1 {{ border-bottom: 2px solid #007bff; padding-bottom: 10px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #e9ecef; }}
        th {{ background-color: #007bff; color: white; text-align: center; }}
        .metric-card {{ background-color: #e9f5ff; border: 1px solid #007bff; text-align: center; padding: 15px; border-radius: 8px; }}
        .metric-value {{ font-size: 2.5rem; font-weight: bold; color: #007bff; }}
        /* Responsive Grid */
        @media (min-width: 768px) {{
            .grid-cols-2 {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
            .grid-cols-3 {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
        }}
    </style></head>
    <body class="bg-gray-100 p-4 md:p-8 font-sans">
    <div class="max-w-7xl mx-auto">
        <h1 class="text-4xl font-extrabold text-gray-800 mb-8">Panel de Control de Tienda</h1>

        <div class="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div class="metric-card">
                <div class="text-sm font-medium text-gray-600">Total Vendido (Histórico)</div>
                <div class="metric-value">€{total_ventas:.2f}</div>
            </div>
            <div class="metric-card bg-green-100 border-green-600">
                <div class="text-sm font-medium text-gray-600">Caja Actual (Reportada)</div>
                <div class="metric-value text-green-600">€{caja_actual:.2f}</div>
            </div>
            <div class="metric-card bg-yellow-100 border-yellow-600">
                <div class="text-sm font-medium text-gray-600">Items Diferentes en Stock</div>
                <div class="metric-value text-yellow-600">{len(stock)}</div>
            </div>
        </div>

        <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
            
            <div class="card lg:col-span-2">
                <h2>📊 Ventas por Hora (Hoy)</h2>
                <div style="text-align:center;overflow-x:auto;">{grafico_horas}</div>
            </div>

            <div class="card">
                <h2>📦 Resumen de Stock</h2>
                <div class="max-h-96 overflow-y-auto">
                    <table>
                        <thead><tr><th>Producto</th><th class="text-center">Cantidad</th></tr></thead>
                        <tbody>{stock_html or "<tr><td colspan='2' style='text-align:center;color:#666;'>No hay datos de stock</td></tr>"}</tbody>
                    </table>
                </div>
            </div>

            <div class="card lg:col-span-1">
                <h2>🔄 Últimos Retiros de Caja</h2>
                <table>
                    <thead><tr><th>Fecha</th><th class="text-right">Importe</th></tr></thead>
                    <tbody>{retiros_html or "<tr><td colspan='2' style='text-align:center;color:#666;'>No hay retiros registrados</td></tr>"}</tbody>
                </table>
            </div>

        </div>

        <a href="/logout" class="mt-8 inline-block bg-red-600 text-white font-semibold py-2 px-6 rounded-lg hover:bg-red-700 transition duration-300">Cerrar Sesión</a>
    </div>
    </body></html>'''
    return html

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/sync', methods=['POST'])
def sync():
    """Endpoint llamado por el TPV local para sincronizar datos con Firebase."""
    nuevo = request.json
    
    # 1. Cargar el estado actual desde Firebase
    data = DB.get_data()
    
    # 2. Sincronizar Caja Actual
    data["caja_actual"] = nuevo.get("caja_actual", data["caja_actual"])
    
    # 3. Sincronizar Retiros de Caja (Añadir los nuevos que vienen del TPV)
    retiros_pendientes = nuevo.get("retiros_pendientes", [])
    if retiros_pendientes:
        data["retiros"].extend(retiros_pendientes)

    # Conjuntos de IDs existentes para evitar duplicados
    ventas_existentes_ids = set(v.get("id") for v in data["ventas"] if "id" in v)
    devoluciones_existentes_ids = set(d.get("id") for d in data["devoluciones"] if "id" in d)

    # 4. Sincronizar Ventas (añadir solo las nuevas)
    for v in nuevo.get("ventas", []):
        if v.get("id") and v["id"] not in ventas_existentes_ids:
            data["ventas"].append(v)
            # Actualizar Stock (restar)
            for p in v["productos"]:
                prod = p["producto"]
                cantidad = p["cantidad"]
                data["stock"][prod] = data["stock"].get(prod, 0) - cantidad


    # 5. Sincronizar Devoluciones (añadir solo las nuevas)
    for d in nuevo.get("devoluciones", []):
        if d.get("id") and d["id"] not in devoluciones_existentes_ids:
            data["devoluciones"].append(d)
            # Actualizar Stock (sumar)
            for p in d["productos"]:
                prod = p["producto"]
                cantidad = p["cantidad"]
                data["stock"][prod] = data["stock"].get(prod, 0) + cantidad


    # 6. Guardar el estado consolidado de vuelta a Firebase
    if DB.set_data(data):
        return {"status": "success", "message": "Sincronización completa con Firebase."}, 200
    else:
        return {"status": "error", "message": "Error al guardar en Firebase."}, 500

if __name__ == '__main__':
    # La inicialización de Firebase ocurre en firebase_config.py
    print("Dashboard iniciado.")
    # NOTA: En Render, el servidor usará Gunicorn o similar. 
    # Este 'run' es solo para pruebas locales.
    app.run(debug=True)
