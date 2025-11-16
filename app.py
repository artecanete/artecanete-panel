from flask import Flask, render_template, request, session, redirect, jsonify
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = "artecanete2025"

DATA_FILE = "data.json"

@app.route('/')
def login():
    return '''
    <html><body style="font-family:Arial;text-align:center;padding:50px;background:#f0f0f0;">
    <h1>Arte Cañete - Panel</h1>
    <form method="post" action="/login" style="background:white;padding:20px;margin:auto;width:300px;border-radius:10px;">
    <input type="text" name="user" placeholder="Usuario" style="width:100%;padding:10px;margin:10px 0;"><br>
    <input type="password" name="pass" placeholder="Contraseña" style="width:100%;padding:10px;margin:10px 0;"><br>
    <button type="submit" style="width:100%;padding:10px;background:#007bff;color:white;border:none;border-radius:5px;">Entrar</button>
    </form></body></html>
    '''

@app.route('/login', methods=['POST'])
def do_login():
    if request.form['user'] == 'admin' and request.form['pass'] == 'artecanete2025':
        session['logged_in'] = True
        return redirect('/dashboard')
    return "Error"

@app.route('/dashboard')
def dashboard():
    if not session.get('logged_in'):
        return redirect('/')
    try:
        with open(DATA_FILE) as f:
            data = json.load(f)
    except:
        data = {"ventas": [], "caja_actual": 200.00}
    
    hoy = datetime.now().strftime("%d/%m/%Y")
    ventas_hoy = [v for v in data.get("ventas", []) if v["fecha"].startswith(hoy)]
    
    html = f'''
    <html><head><title>Panel Arte Cañete</title>
    <style>body{{font-family:Arial;background:#f8f9fa;padding:20px;}} .card{{background:white;padding:20px;margin:10px;border-radius:10px;}}</style>
    </head><body>
    <h1>Panel Arte Cañete</h1>
    <div class="card"><h2>Caja: €{data.get("caja_actual", 200.00):.2f}</h2></div>
    <div class="card"><h2>Ventas Hoy ({hoy}): {len(ventas_hoy)}</h2>
    <table border="1" style="width:100%;"><tr><th>Hora</th><th>Factura</th><th>Productos</th><th>Total</th><th>Vendedor</th></tr>'''
    
    for v in ventas_hoy:
        productos = ', '.join([f"{p['cantidad']}x {p['producto']}" for p in v['productos']])
        html += f'<tr><td>{v["fecha"].split()[1]}</td><td>{v["numero_factura"]}</td><td>{productos}</td><td>€{v["total"]:.2f}</td><td>{v["vendedor"]}</td></tr>'
    
    html += '</table></div><a href="/logout" style="color:red;">Salir</a></body></html>'
    return html

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

@app.route('/sync', methods=['POST'])
def sync():
    data = request.json
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    return "OK"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
