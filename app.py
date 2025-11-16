from flask import Flask, render_template, request, session, redirect
import json
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = "artecanete2025"

DATA_FILE = "data.json"
CONTROL_CAJA_FILE = "control_caja.json"

def cargar_datos():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE) as f:
            return json.load(f)
    return {"ventas": [], "devoluciones": [], "caja_actual": 200.00, "stock": {}}

def cargar_movimientos():
    if os.path.exists(CONTROL_CAJA_FILE):
        try:
            with open(CONTROL_CAJA_FILE) as f:
                return json.load(f)
        except:
            return []
    return []

@app.route('/')
def login():
    return '''
    <html><body style="font-family:Arial;text-align:center;padding:50px;background:#f0f0f0;">
    <h1>🛒 Arte Cañete - Panel</h1>
    <form method="post" action="/login" style="background:white;padding:30px;margin:auto;width:320px;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);">
    <input type="text" name="user" placeholder="Usuario" required style="width:100%;padding:12px;margin:8px 0;border:1px solid #ddd;border-radius:6px;font-size:16px;"><br>
    <input type="password" name="pass" placeholder="Contraseña" required style="width:100%;padding:12px;margin:8px 0;border:1px solid #ddd;border-radius:6px;font-size:16px;"><br>
    <button type="submit" style="width:100%;padding:12px;background:#007bff;color:white;border:none;border-radius:6px;font-size:16px;font-weight:bold;">Entrar</button>
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
    movimientos = cargar_movimientos()
    hoy = datetime.now().strftime("%d/%m/%Y")
    ventas = data.get("ventas", [])
    
    # === CAJA ACTUAL ===
    caja_actual = data.get("caja_actual", 200.0)
    ultimo_retiro = next((m for m in reversed(movimientos) if m.get("tipo") == "Retiro de dueño"), None)
    ultimo_retiro_texto = f"Último retiro: €{abs(ultimo_retiro['importe']):.2f} ({ultimo_retiro['fecha']})" if ultimo_retiro else "Sin retiros"

    # === VENTAS HOY ===
    ventas_hoy = [v for v in ventas if v["fecha"].startswith(hoy)]
    total_hoy = sum(v["total"] for v in ventas_hoy)

    # === VENTAS POR DÍA (ÚLTIMOS 7 DÍAS) ===
    ventas_por_dia = {}
    for i in range(6, -1, -1):
        fecha = (datetime.now() - timedelta(days=i)).strftime("%d/%m")
        ventas_por_dia[fecha] = 0
    for v in ventas:
        fecha_corta = v["fecha"][:5]
        if fecha_corta in ventas_por_dia:
            ventas_por_dia[fecha_corta] += v["total"]
    
    max_dia = max(ventas_por_dia.values()) if ventas_por_dia else 1
    grafico_dias = ""
    for fecha, total in ventas_por_dia.items():
        alto = int((total / max_dia) * 180) if max_dia > 0 else 0
        grafico_dias += f'''
        <div style="text-align:center;margin:0 8px;flex:1;">
            <div style="background:#007bff;height:{alto}px;width:100%;border-radius:6px;"></div>
            <small style="display:block;margin-top:5px;font-weight:bold;">{fecha}<br>€{total:.0f}</small>
        </div>'''

    # === VENTAS POR HORA (HOY) ===
    horas = {f"{h:02d}": 0 for h in range(9, 22)}
    for v in ventas_hoy:
        hora = v["fecha"].split()[1][:2]
        if hora in horas:
            horas[hora] += v["total"]
    max_hora = max(horas.values()) if horas else 1
    grafico_horas = ""
    for hora, total in horas.items():
        alto = int((total / max_hora) * 120) if max_hora > 0 else 0
        grafico_horas += f'''
        <div style="text-align:center;margin:0 3px;">
            <div style="background:#17a2b8;height:{alto}px;width:24px;border-radius:4px;margin:0 auto;"></div>
            <small>{hora}h</small>
        </div>'''

    # === TOP VENDEDORES ===
    vendedores = {}
    for v in ventas_hoy:
        vend = v["vendedor"]
        vendedores[vend] = vendedores.get(vend, 0) + v["total"]
    top_vendedores = sorted(vendedores.items(), key=lambda x: x[1], reverse=True)[:5]
    max_vend = max(vendedores.values()) if vendedores else 1
    grafico_vendedores = ""
    for vend, total in top_vendedores:
        ancho = int((total / max_vend) * 260) if max_vend > 0 else 0
        grafico_vendedores += f'''
        <div style="margin:6px 0;">
            <div style="display:flex;align-items:center;font-size:14px;">
                <span style="width:100px;font-weight:bold;">{vend}</span>
                <div style="flex:1;background:#eee;height:28px;border-radius:6px;">
                    <div style="background:#28a745;width:{ancho}px;height:100%;border-radius:6px;"></div>
                </div>
                <span style="margin-left:8px;font-weight:bold;">€{total:.2f}</span>
            </div>
        </div>'''

    # === TOP JUEGOS ===
    juegos = {}
    for v in ventas_hoy:
        for p in v["productos"]:
            juego = p["producto"]
            cant = p["cantidad"]
            juegos[juego] = juegos.get(juego, 0) + cant
    top_juegos = sorted(juegos.items(), key=lambda x: x[1], reverse=True)[:10]
    max_juego = max(juegos.values()) if juegos else 1
    grafico_juegos = ""
    for juego, cant in top_juegos:
        ancho = int((cant / max_juego) * 260) if max_juego > 0 else 0
        grafico_juegos += f'''
        <div style="margin:6px 0;">
            <div style="display:flex;align-items:center;font-size:14px;">
                <span style="width:160px;">{juego}</span>
                <div style="flex:1;background:#eee;height:28px;border-radius:6px;">
                    <div style="background:#ff6b6b;width:{ancho}px;height:100%;border-radius:6px;"></div>
                </div>
                <span style="margin-left:8px;font-weight:bold;">{cant} uds</span>
            </div>
        </div>'''

    # === RETIROS ===
    retiros_html = ""
    for m in movimientos[-5:]:
        if m.get("tipo") == "Retiro de dueño":
            retiros_html += f"<tr><td>{m['fecha']}</td><td style='color:red;font-weight:bold;'>-€{abs(m['importe']):.2f}</td></tr>"

    html = f'''
    <html><head><title>Dashboard Arte Cañete</title>
    <meta name="viewport" content="width=device-width,initial-scale=1">
    <style>
    body{{font-family:'Segoe UI',Arial;background:#f8f9fa;margin:0;padding:15px;}}
    .container{{max-width:1000px;margin:auto;}}
    .card{{background:white;padding:20px;margin:15px 0;border-radius:12px;box-shadow:0 4px 12px rgba(0,0,0,0.1);}}
    h1{{text-align:center;color:#007bff;margin:0 0 20px;font-size:28px;}}
    h2{{color:#343a40;margin:0 0 15px;font-size:18px;font-weight:600;}}
    .flex{{display:flex;flex-wrap:wrap;justify-content:space-between;}}
    table{{width:100%;border-collapse:collapse;margin-top:10px;}} th,td{{border:1px solid #ddd;padding:8px;text-align:left;}}
    th{{background:#f0f0f0;font-weight:600;}}
    .btn{{padding:10px 16px;background:#dc3545;color:white;border:none;border-radius:6px;text-decoration:none;font-weight:bold;display:inline-block;margin-top:20px;}}
    </style>
    </head><body>
    <div class="container">
    <h1>🛒 Dashboard Arte Cañete</h1>
    
    <div class="card">
        <h2>💰 Caja Actual</h2>
        <p style="font-size:32px;color:#28a745;font-weight:bold;margin:10px 0;">€{caja_actual:.2f}</p>
        <p style="color:#666;font-size:14px;">{ultimo_retiro_texto}</p>
        <p>Ventas hoy: <strong>{len(ventas_hoy)}</strong> | Total: <strong>€{total_hoy:.2f}</strong></p>
    </div>

    <div class="card">
        <h2>📅 Ventas por Día (Últimos 7 días)</h2>
        <div class="flex">{grafico_dias}</div>
    </div>

    <div class="flex">
        <div style="flex:1;min-width:300px;">
            <div class="card">
                <h2>🏆 Top Vendedores (Hoy)</h2>
                {grafico_vendedores or "<p style='color:#666;'>No hay ventas hoy</p>"}
            </div>
        </div>
        <div style="flex:1;min-width:300px;">
            <div class="card">
                <h2>🎮 Top Juegos (Hoy)</h2>
                {grafico_juegos or "<p style='color:#666;'>No hay ventas hoy</p>"}
            </div>
        </div>
    </div>

    <div class="card">
        <h2>📊 Ventas por Hora (Hoy)</h2>
        <div style="text-align:center;overflow-x:auto;">{grafico_horas}</div>
    </div>

    <div class="card">
        <h2>🔄 Últimos Retiros</h2>
        <table><tr><th>Fecha</th><th>Importe</th></tr>
        {retiros_html or "<tr><td colspan='2' style='text-align:center;color:#666;'>No hay retiros</td></tr>"}</table>
    </div>

    <a href="/logout" class="btn">Cerrar Sesión</a>
    </div>
    </body></html>'''
    return html

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/sync', methods=['POST'])
def sync():
    nuevo = request.json
    data = cargar_datos()
    data["caja_actual"] = nuevo.get("caja_actual", data["caja_actual"])
    
    for v in nuevo.get("ventas", []):
        if v not in data["ventas"]:
            data["ventas"].append(v)
            for p in v["productos"]:
                prod = p["producto"]
                if prod in data["stock"]:
                    data["stock"][prod] -= p["cantidad"]
    
    for d in nuevo.get("devoluciones", []):
        if d not in data["devoluciones"]:
            data["devoluciones"].append(d)
            if d["producto"] in data["stock"]:
                data["stock"][d["producto"]] += 1
            data["caja_actual"] -= d["total"]
    
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
