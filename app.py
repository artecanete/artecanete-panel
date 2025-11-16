from flask import Flask, render_template, request, session, redirect, jsonify
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "artecanete2025"

DATA_FILE = "data.json"

# Stock inicial
STOCK_INICIAL = {
    "Catan": 50,
    "Dixit": 40,
    "Código Secreto": 30,
    "Carcassonne": 35
}

def cargar_datos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    else:
        return {
            "ventas": [],
            "devoluciones": [],
            "caja_actual": 200.00,
            "stock": STOCK_INICIAL.copy()
        }

def guardar_datos(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/')
def login():
    return '''
    <html><body style="font-family:Arial;text-align:center;padding:50px;background:#f0f0f0;">
    <h1>Arte Cañete - Panel</h1>
    <form method="post" action="/login" style="background:white;padding:20px;margin:auto;width:300px;border-radius:10px;">
    <input type="text" name="user" placeholder="Usuario" required style="width:100%;padding:10px;margin:10px 0;"><br>
    <input type="password" name="pass" placeholder="Contraseña" required style="width:100%;padding:10px;margin:10px 0;"><br>
    <button type="submit" style="width:100%;padding:10px;background:#007bff;color:white;border:none;border-radius:5px;">Entrar</button>
    </form></body></html>
    '''

@app.route('/login', methods=['POST'])
def do_login():
    if request.form['user'] == 'admin' and request.form['pass'] == 'artecanete2025':
        session['logged_in'] = True
        return redirect('/dashboard')
    return "Error", 401

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/')
    
    data = cargar_datos()
    hoy = datetime.now().strftime("%d/%m/%Y")
    ventas_hoy = [v for v in data.get("ventas", []) if v["fecha"].startswith(hoy)]
    total_hoy = sum(v["total"] for v in ventas_hoy)
    
    # === GRÁFICO 1: VENTAS POR HORA ===
    horas = {}
    for v in ventas_hoy:
        hora = v["fecha"].split()[1][:2]
        horas[hora] = horas.get(hora, 0) + v["total"]
    
    grafico_horas = ""
    max_val = max(horas.values()) if horas else 1
    for h in range(9, 22):
        hora = f"{h:02d}"
        valor = horas.get(hora, 0)
        alto = int((valor / max_val) * 200) if max_val > 0 else 0
        grafico_horas += f'''
        <div style="display:inline-block;width:40px;text-align:center;margin:0 5px;">
            <div style="background:#007bff;height:{alto}px;width:30px;margin:0 auto;border-radius:5px;"></div>
            <small>{hora}h<br>€{valor:.0f}</small>
        </div>'''

    # === GRÁFICO 2: TOP VENDEDORES ===
    vendedores = {}
    for v in ventas_hoy:
        vend = v["vendedor"]
        vendedores[vend] = vendedores.get(vend, 0) + v["total"]
    
    top_vendedores = sorted(vendedores.items(), key=lambda x: x[1], reverse=True)
    grafico_vendedores = ""
    max_vend = max(vendedores.values()) if vendedores else 1
    for vend, total in top_vendedores:
        ancho = int((total / max_vend) * 300) if max_vend > 0 else 0
        grafico_vendedores += f'''
        <div style="margin:8px 0;">
            <div style="display:flex;align-items:center;">
                <span style="width:120px;font-weight:bold;">{vend}</span>
                <div style="flex:1;background:#eee;height:25px;border-radius:5px;">
                    <div style="background:#28a745;width:{ancho}px;height:100%;border-radius:5px;"></div>
                </div>
                <span style="margin-left:10px;font-weight:bold;">€{total:.2f}</span>
            </div>
        </div>'''

    # === GRÁFICO 3: TOP JUEGOS ===
    productos = {}
    for v in ventas_hoy:
        for p in v["productos"]:
            prod = p["producto"]
            cant = p["cantidad"]
            productos[prod] = productos.get(prod, 0) + cant
    
    top_productos = sorted(productos.items(), key=lambda x: x[1], reverse=True)[:5]
    grafico_productos = ""
    max_prod = max(productos.values()) if productos else 1
    for prod, cant in top_productos:
        ancho = int((cant / max_prod) * 300) if max_prod > 0 else 0
        grafico_productos += f'''
        <div style="margin:8px 0;">
            <div style="display:flex;align-items:center;">
                <span style="width:150px;">{prod}</span>
                <div style="flex:1;background:#eee;height:25px;border-radius:5px;">
                    <div style="background:#ff6b6b;width:{ancho}px;height:100%;border-radius:5px;"></div>
                </div>
                <span style="margin-left:10px;font-weight:bold;">{cant} uds</span>
            </div>
        </div>'''

    # === STOCK CON COLORES ===
    stock_html = ""
    for prod, cant in data["stock"].items():
        color = "darkgreen" if cant > 10 else "orange" if cant > 0 else "red"
        stock_html += f"<li><strong>{prod}:</strong> <span style='color:{color};font-weight:bold;'>{cant}</span></li>"

    # === DEVOLUCIONES ===
    dev_html = ""
    for d in data.get("devoluciones", [])[-5:]:
        dev_html += f"<tr><td>{d['fecha']}</td><td>{d['numero_factura_original']}</td><td>€{d['venta_original']['total']:.2f}</td><td>{d['motivo']}</td><td>{d['vendedor']}</td></tr>"

    html = f'''
    <html><head><title>Panel Arte Cañete</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{{font-family:Arial;background:#f8f9fa;padding:10px;}}
    .card{{background:white;padding:20px;margin:10px;border-radius:10px;box-shadow:0 2px 5px rgba(0,0,0,0.1);}}
    table{{width:100%;border-collapse:collapse;}} th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}
    th{{background:#f0f0f0;}} .btn{{padding:8px 12px;background:#28a745;color:white;border:none;border-radius:5px;text-decoration:none;}}
    h2{{color:#343a40;margin-top:0;}}
    </style>
    </head><body>
    <h1 style="text-align:center;color:#007bff;">🛒 Panel Arte Cañete</h1>
    
    <div class="card"><h2>💰 Caja Actual: <span style="color:green;font-size:28px;">€{data.get("caja_actual", 200):.2f}</span></h2>
    <p>Ventas hoy: {len(ventas_hoy)} | Total: €{total_hoy:.2f}</p></div>
    
    <div class="card"><h2>📊 Ventas por Hora (Hoy)</h2><div style="text-align:center;">{grafico_horas}</div></div>
    
    <div class="card"><h2>🏆 Top Vendedores</h2>{grafico_vendedores or "<p>No hay ventas hoy</p>"}</div>
    
    <div class="card"><h2>🎮 Top Juegos Vendidos</h2>{grafico_productos or "<p>No hay ventas hoy</p>"}</div>
    
    <div class="card"><h2>📦 Stock Actual</h2><ul>{stock_html}</ul></div>
    
    <div class="card"><h2>🔄 Últimas Devoluciones</h2>
    <table><tr><th>Fecha</th><th>Factura</th><th>Total</th><th>Motivo</th><th>Vendedor</th></tr>{dev_html or "<tr><td colspan='5'>No hay devoluciones</td></tr>"}</table></div>
    
    <a href="/logout" class="btn" style="background:#dc3545;display:inline-block;margin:20px;">Cerrar Sesión</a>
    </body></html>'
    return html

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/sync', methods=['POST'])
def sync():
    nuevo = request.json
    data = cargar_datos()
    
    # Actualizar caja
    data["caja_actual"] = nuevo.get("caja_actual", data["caja_actual"])
    
    # Añadir ventas
    for v in nuevo.get("ventas", []):
        if v not in data["ventas"]:
            data["ventas"].append(v)
            # Restar stock
            for p in v["productos"]:
                prod = p["producto"]
                if prod in data["stock"]:
                    data["stock"][prod] -= p["cantidad"]
    
    # Añadir devoluciones
    for d in nuevo.get("devoluciones", []):
        if d not in data["devoluciones"]:
            data["devoluciones"].append(d)
            # Sumar stock
            if d["producto"] in data["stock"]:
                data["stock"][d["producto"]] += 1
            # Restar de caja
            data["caja_actual"] -= d["total"]
    
    guardar_datos(data)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
