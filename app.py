import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import simpledialog
from PIL import Image, ImageTk, ImageDraw
import json
import os
import requests
from datetime import datetime
import threading
import time

# --- CONSTANTES ---
juegos = []
ventas = []
devoluciones = []
caja_inicial = 200.00
caja_actual = caja_inicial
FSE_contador = 0
FST_contador = 0
retiros = [] # Inicializado aquí para el scope global
vendedores_disponibles = ["Vendedor 1", "Vendedor 2", "Vendedor 3"]
vendedor_actual = None
ADMIN_PASSWORD = "admin"
IMAGE_DIR = "imagenes"
PLACEHOLDER_IMAGE = "placeholder.png"
DATA_FILE = "tienda_data.json"
CONTROL_CAJA_FILE = "control_caja.json"

# --- URL DE TU PANEL WEB (Asegúrate de que esta URL sea la correcta) ---
SYNC_URL = "https://artecanete-panel.onrender.com/sync" 

# --- PRINTER ---
# Descomentar y ajustar IDs si usas impresora física
# try:
#     from escpos.printer import Usb
#     USB_VENDOR_ID = 0x04b8 
#     USB_PRODUCT_ID = 0x0202 
#     p = Usb(USB_VENDOR_ID, USB_PRODUCT_ID)
# except:
#     print("Impresora USB no conectada o IDs incorrectos. Se usará impresión simulada.")
#     p = None


# --- DATOS Y PERSISTENCIA ---
def cargar_datos():
    """Carga los datos principales del TPV (inventario, ventas, devoluciones)."""
    global juegos, ventas, devoluciones
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                data = json.load(f)
                juegos = data.get("juegos", [])
                ventas = data.get("ventas", [])
                devoluciones = data.get("devoluciones", [])
        except Exception as e:
            messagebox.showwarning("Error de Carga", f"No se pudo cargar {DATA_FILE}: {e}. Usando datos iniciales.")
            juegos = []
            ventas = []
            devoluciones = []

def cargar_control_caja():
    """Carga los movimientos de caja y actualiza los contadores y la caja actual."""
    global caja_actual, FSE_contador, FST_contador, retiros
    
    # Valores por defecto en caso de fallo
    caja_actual = caja_inicial
    FSE_contador = 0
    FST_contador = 0
    retiros = []

    if os.path.exists(CONTROL_CAJA_FILE):
        try:
            with open(CONTROL_CAJA_FILE, 'r') as f:
                control_data = json.load(f)
                
                # --- CORRECCIÓN DEL ERROR ANTERIOR ---
                # Verifica que lo cargado sea un diccionario
                if not isinstance(control_data, dict):
                    print(f"ATENCIÓN: {CONTROL_CAJA_FILE} no es un diccionario. Reiniciando control de caja.")
                    control_data = {} 
                # --- FIN CORRECCIÓN ---
                
                retiros = control_data.get("retiros", [])
                
                # Intentamos convertir a float, si falla, usamos el valor por defecto
                try:
                    caja_actual = float(control_data.get("caja_actual", caja_inicial))
                except (ValueError, TypeError):
                    caja_actual = caja_inicial
                    
                # Intentamos convertir contadores a int
                try:
                    FSE_contador = int(control_data.get("FSE_contador", 0))
                except (ValueError, TypeError):
                    FSE_contador = 0
                    
                try:
                    FST_contador = int(control_data.get("FST_contador", 0))
                except (ValueError, TypeError):
                    FST_contador = 0

        except Exception as e:
            messagebox.showwarning("Error de Carga", f"No se pudo cargar {CONTROL_CAJA_FILE}: {e}. Reiniciando control de caja.")
            # Los valores ya están reiniciados al principio de la función.

def guardar_datos():
    """Guarda los datos principales."""
    with open(DATA_FILE, 'w') as f:
        json.dump({"juegos": juegos, "ventas": ventas, "devoluciones": devoluciones}, f, indent=4)

def guardar_control_caja():
    """Guarda el estado de la caja y los contadores."""
    with open(CONTROL_CAJA_FILE, 'w') as f:
        json.dump({
            "caja_actual": caja_actual,
            "FSE_contador": FSE_contador,
            "FST_contador": FST_contador,
            "retiros": retiros
        }, f, indent=4)

def inicializar_datos():
    """Carga datos de persistencia y asegura la existencia de carpetas/archivos necesarios."""
    cargar_datos()
    cargar_control_caja()
    
    # --- CORRECCIÓN: Asegurar la imagen placeholder ---
    if not os.path.exists(IMAGE_DIR):
        os.makedirs(IMAGE_DIR)
        
    placeholder_path = os.path.join(IMAGE_DIR, PLACEHOLDER_IMAGE)
    if not os.path.exists(placeholder_path):
        try:
            # Crea una imagen placeholder si no existe
            placeholder_img = Image.new('RGB', (200, 200), color = 'lightgray')
            d = ImageDraw.Draw(placeholder_img)
            # Dibuja texto simple para indicar que no hay imagen
            d.text((45,90), "NO IMG", fill=(0,0,0), font=None) 
            placeholder_img.save(placeholder_path)
            print(f"Placeholder creado en: {placeholder_path}")
        except Exception as e:
            print(f"Error creando imagen placeholder. Asegúrate de tener PIL (Pillow) instalado: {e}")
    # --- FIN CORRECCIÓN ---
            
# --- Sincronización Web ---
def enviar_a_web():
    """Envía todos los datos relevantes a la URL de sincronización."""
    global caja_actual, FSE_contador, FST_contador, retiros
    try:
        payload = {
            "ventas": ventas,
            "devoluciones": devoluciones,
            "juegos": juegos,
            "caja_actual": caja_actual,
            "FSE_contador": FSE_contador,
            "FST_contador": FST_contador,
            "retiros": retiros 
        }
        
        # Sincronización asíncrona para no bloquear la interfaz gráfica
        def sync_worker():
            try:
                response = requests.post(SYNC_URL, json=payload, timeout=10)
                if response.status_code == 200:
                    print("✅ Sincronización web exitosa.")
                else:
                    print(f"❌ Error al sincronizar (HTTP {response.status_code}): {response.text}")
            except requests.exceptions.RequestException as e:
                print(f"❌ Error de conexión al sincronizar: {e}")

        threading.Thread(target=sync_worker).start()
        
    except Exception as e:
        print(f"Error general al preparar la sincronización: {e}")
        
# --- CLASE SELECTOR DE VENDEDOR ---

class VendedorSelector:
    def __init__(self, root):
        self.root = root
        self.root.title("Seleccionar Vendedor")
        self.root.geometry("400x300")
        self.root.configure(bg='#34495e')

        frame = tk.Frame(root, bg='#34495e', padx=20, pady=20)
        frame.pack(expand=True)

        tk.Label(frame, text="Iniciar Sesión", font=("Segoe UI", 16, "bold"), bg='#34495e', fg='white').pack(pady=10)

        self.vendedor_var = tk.StringVar(root)
        self.vendedor_var.set(vendedores_disponibles[0]) 

        vendedor_menu = ttk.OptionMenu(frame, self.vendedor_var, vendedores_disponibles[0], *vendedores_disponibles)
        vendedor_menu.config(width=20)
        vendedor_menu.pack(pady=10)

        tk.Button(frame, text="Entrar", command=self.seleccionar_vendedor, bg='#1abc9c', fg='white', font=("Segoe UI", 12, "bold"), width=15, relief=tk.RAISED, bd=3).pack(pady=10)

        tk.Button(frame, text="Administración (Admin)", command=self.mostrar_ventana_admin, bg='#e67e22', fg='white', font=("Segoe UI", 10), width=20, relief=tk.FLAT).pack(pady=15)

    def seleccionar_vendedor(self):
        global vendedor_actual
        vendedor_actual = self.vendedor_var.get()
        self.root.destroy()
        root_app = tk.Tk()
        AplicacionTPV(root_app)
        root_app.mainloop()

    def mostrar_ventana_admin(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Acceso Admin")
        ventana.geometry("300x150")
        ventana.configure(bg='#f8f9fa')

        tk.Label(ventana, text="Contraseña:", font=("Segoe UI", 12)).pack(pady=10)
        
        password_entry = ttk.Entry(ventana, show="*", width=20)
        password_entry.pack(pady=5)
        
        def verificar_admin():
            if password_entry.get() == ADMIN_PASSWORD:
                ventana.destroy()
                self.root.destroy()
                root_admin = tk.Tk()
                PanelAdmin(root_admin)
                root_admin.mainloop()
            else:
                messagebox.showerror("Error", "Contraseña incorrecta.")

        tk.Button(ventana, text="Acceder", command=verificar_admin, bg='#3498db', fg='white', font=("Segoe UI", 10)).pack(pady=10)


# --- CLASE APLICACIÓN TPV ---

class AplicacionTPV:
    def __init__(self, root):
        global vendedor_actual
        self.root = root
        self.root.title(f"TPV Arte Cañete - Sesión: {vendedor_actual}")
        self.root.geometry("1000x700")
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        
        # --- CORRECCIÓN: Ahora el archivo placeholder está garantizado antes de esta línea ---
        self.placeholder_img = Image.open(os.path.join(IMAGE_DIR, PLACEHOLDER_IMAGE)).resize((100, 100))
        self.placeholder_tk = ImageTk.PhotoImage(self.placeholder_img)
        # -------------------------------------------------------------------------------------
        
        self.carrito = {}
        
        self.crear_widgets()
        self.actualizar_lista_juegos()
        self.actualizar_caja_display()
        
        # Sincronización inicial al iniciar sesión
        enviar_a_web()
    
    def crear_widgets(self):
        # Frame Principal
        main_frame = tk.Frame(self.root, bg="#f8f9fa")
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Panel Izquierdo (Juegos)
        left_panel = tk.Frame(main_frame, bg="#ffffff", bd=2, relief=tk.GROOVE)
        left_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))

        tk.Label(left_panel, text="Inventario", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg="#2c3e50").pack(pady=(10, 5))

        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda name, index, mode: self.actualizar_lista_juegos(self.search_var.get()))
        ttk.Entry(left_panel, textvariable=self.search_var, font=("Segoe UI", 10), width=40).pack(pady=5, padx=10, fill=tk.X)

        # Listado de Juegos
        self.listbox_juegos = tk.Listbox(left_panel, font=("Consolas", 10), height=30, selectmode=tk.SINGLE, borderwidth=0, highlightthickness=0)
        self.listbox_juegos.pack(padx=10, pady=5, fill=tk.BOTH, expand=True)
        self.listbox_juegos.bind('<<ListboxSelect>>', self.mostrar_detalle_juego)

        # Detalle del Juego Seleccionado
        self.detail_frame = tk.Frame(left_panel, bg="#ecf0f1", padx=10, pady=10, bd=1, relief=tk.SOLID)
        self.detail_frame.pack(fill=tk.X, padx=10, pady=(5, 10))

        self.img_label = tk.Label(self.detail_frame, image=None, bg="#ecf0f1")
        self.img_label.pack(side=tk.LEFT, padx=(0, 10))
        self.img_label.image = self.placeholder_tk # Asegura que la imagen sea la de placeholder al inicio

        info_frame = tk.Frame(self.detail_frame, bg="#ecf0f1")
        info_frame.pack(side=tk.LEFT, fill=tk.Y)

        self.detalle_nombre = tk.Label(info_frame, text="Seleccione un juego", font=("Segoe UI", 12, "bold"), bg="#ecf0f1", wraplength=200, justify=tk.LEFT)
        self.detalle_nombre.pack(anchor='w')
        self.detalle_precio = tk.Label(info_frame, text="Precio: -", font=("Segoe UI", 10), bg="#ecf0f1", justify=tk.LEFT)
        self.detalle_precio.pack(anchor='w')
        self.detalle_stock = tk.Label(info_frame, text="Stock: -", font=("Segoe UI", 10), bg="#ecf0f1", justify=tk.LEFT)
        self.detalle_stock.pack(anchor='w')

        tk.Button(self.detail_frame, text="Añadir al Carrito", command=self.añadir_a_carrito, bg="#3498db", fg="white", font=("Segoe UI", 10, "bold")).pack(side=tk.RIGHT, padx=5)

        # Panel Derecho (Carrito y Pago)
        right_panel = tk.Frame(main_frame, bg="#ffffff", bd=2, relief=tk.GROOVE)
        right_panel.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0), pady=0, ipadx=5)

        tk.Label(right_panel, text="Carrito de Compra", font=("Segoe UI", 14, "bold"), bg="#ffffff", fg="#2c3e50").pack(pady=(10, 5))

        # Listado del Carrito
        self.listbox_carrito = tk.Listbox(right_panel, font=("Consolas", 10), height=15, selectmode=tk.SINGLE, borderwidth=0, highlightthickness=0)
        self.listbox_carrito.pack(padx=10, pady=5, fill=tk.X)
        self.listbox_carrito.bind('<Delete>', lambda e: self.quitar_de_carrito()) # Permite borrar con tecla Supr

        # Total y Controles
        total_frame = tk.Frame(right_panel, bg="#ecf0f1", padx=10, pady=10)
        total_frame.pack(fill=tk.X, padx=10, pady=5)
        
        tk.Label(total_frame, text="TOTAL:", font=("Segoe UI", 16, "bold"), bg="#ecf0f1", fg="#e74c3c").pack(side=tk.LEFT)
        self.total_label = tk.Label(total_frame, text="0.00 €", font=("Segoe UI", 16, "bold"), bg="#ecf0f1", fg="#e74c3c")
        self.total_label.pack(side=tk.RIGHT)

        # Botones de Pago
        btn_pay_frame = tk.Frame(right_panel, bg="#ffffff")
        btn_pay_frame.pack(pady=10)

        tk.Button(btn_pay_frame, text="Pagar Efectivo", command=lambda: self.procesar_pago("Efectivo"), bg="#2ecc71", fg="white", font=("Segoe UI", 11, "bold"), width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(btn_pay_frame, text="Pagar Tarjeta", command=lambda: self.procesar_pago("Tarjeta"), bg="#f1c40f", fg="white", font=("Segoe UI", 11, "bold"), width=15).pack(side=tk.LEFT, padx=5)
        
        tk.Button(right_panel, text="Vaciar Carrito", command=self.vaciar_carrito, bg="#e74c3c", fg="white", font=("Segoe UI", 10), width=30).pack(pady=5)
        
        # Controles de Caja
        tk.Label(right_panel, text="Control de Caja", font=("Segoe UI", 12, "bold"), bg="#ffffff", fg="#2c3e50").pack(pady=(10, 5))
        
        self.caja_label = tk.Label(right_panel, text="Caja Actual: 0.00 €", font=("Segoe UI", 11), bg="#ffffff", fg="#2980b9")
        self.caja_label.pack(pady=2)

        tk.Button(right_panel, text="Retiro de Caja", command=self.mostrar_ventana_retiro, bg="#e67e22", fg="white", font=("Segoe UI", 10), width=30).pack(pady=5)
        
        # Cierre y Sincronización
        sync_frame = tk.Frame(right_panel, bg="#ffffff")
        sync_frame.pack(pady=20, fill=tk.X)
        
        tk.Button(sync_frame, text="Sincronizar WEB", command=enviar_a_web, bg="#9b59b6", fg="white", font=("Segoe UI", 10, "bold"), width=15).pack(side=tk.LEFT, padx=5)
        tk.Button(sync_frame, text="Cerrar Sesión", command=self.cerrar_sesion, bg="#34495e", fg="white", font=("Segoe UI", 10), width=15).pack(side=tk.LEFT, padx=5)
        

    # --- LÓGICA DE JUEGOS ---
    def actualizar_lista_juegos(self, filtro=""):
        self.listbox_juegos.delete(0, tk.END)
        for juego in juegos:
            nombre = juego.get('nombre', 'Nombre Desconocido')
            
            # Usamos .get() con 0.0 como valor por defecto si 'precio' no existe
            precio = juego.get('precio', 0.0)
            stock = juego.get('stock', 0)
            
            if filtro.lower() in nombre.lower():
                stock_display = stock
                if stock <= 0:
                    stock_display = "AGOTADO"
                
                # Usamos el precio seguro
                display_text = f"{nombre[:30].ljust(30)} | {precio:.2f}€ | STOCK: {stock_display}"
                self.listbox_juegos.insert(tk.END, display_text)
                
                if stock <= 0:
                    self.listbox_juegos.itemconfig(tk.END, {'fg': 'red'})

    def mostrar_detalle_juego(self, event):
        try:
            seleccion = self.listbox_juegos.curselection()
            if not seleccion:
                return
            
            # El texto del listbox incluye el nombre, lo usamos para buscar el objeto
            nombre_listado = self.listbox_juegos.get(seleccion[0]).split('|')[0].strip()
            
            juego_seleccionado = next(j for j in juegos if j.get('nombre', '').startswith(nombre_listado))
            
            self.detalle_nombre.config(text=juego_seleccionado.get('nombre', '---'))
            
            # Usamos .get() con precio y stock seguro
            precio = juego_seleccionado.get('precio', 0.0)
            stock = juego_seleccionado.get('stock', 0)
            self.detalle_precio.config(text=f"Precio: {precio:.2f}€")
            self.detalle_stock.config(text=f"Stock: {stock}")

            img_path = os.path.join(IMAGE_DIR, juego_seleccionado.get('imagen', PLACEHOLDER_IMAGE))
            if not os.path.exists(img_path):
                 img_path = os.path.join(IMAGE_DIR, PLACEHOLDER_IMAGE)

            img = Image.open(img_path).resize((100, 100))
            self.tk_img = ImageTk.PhotoImage(img)
            self.img_label.config(image=self.tk_img)
            self.img_label.image = self.tk_img
            
        except StopIteration:
             self.detalle_nombre.config(text="Juego no encontrado")
        except Exception as e:
            print(f"Error mostrando detalle: {e}")
            self.img_label.config(image=self.placeholder_tk)

    # --- LÓGICA DEL CARRITO ---
    def añadir_a_carrito(self):
        try:
            seleccion = self.listbox_juegos.curselection()
            if not seleccion:
                messagebox.showwarning("Aviso", "Selecciona un juego del inventario primero.")
                return

            nombre_listado = self.listbox_juegos.get(seleccion[0]).split('|')[0].strip()
            juego_seleccionado = next(j for j in juegos if j.get('nombre', '').startswith(nombre_listado))
            
            # Usamos .get() con precio y stock seguro
            nombre = juego_seleccionado.get('nombre', 'Desconocido')
            precio = juego_seleccionado.get('precio', 0.0)
            stock = juego_seleccionado.get('stock', 0)

            if stock <= 0:
                messagebox.showerror("Error", f"{nombre} está agotado.")
                return

            if nombre in self.carrito:
                if self.carrito[nombre]['cantidad'] + 1 > stock:
                     messagebox.showwarning("Aviso", f"Solo quedan {stock} unidades de {nombre}.")
                     return
                self.carrito[nombre]['cantidad'] += 1
            else:
                self.carrito[nombre] = {
                    'precio_u': precio,
                    'cantidad': 1,
                    'id': juego_seleccionado.get('id', 'N/A')
                }
            
            self.actualizar_carrito_display()
            self.actualizar_lista_juegos(self.search_var.get()) # Actualiza el stock en la lista

        except StopIteration:
            messagebox.showerror("Error", "No se encontró el juego seleccionado.")
        except Exception as e:
            print(f"Error al añadir al carrito: {e}")
            messagebox.showerror("Error", "Error desconocido al añadir al carrito.")


    def quitar_de_carrito(self):
        try:
            seleccion = self.listbox_carrito.curselection()
            if not seleccion:
                return

            item_texto = self.listbox_carrito.get(seleccion[0])
            # Extraemos el nombre del juego del texto del listbox
            nombre_juego = item_texto.split('(')[0].strip()

            if nombre_juego in self.carrito:
                self.carrito[nombre_juego]['cantidad'] -= 1
                if self.carrito[nombre_juego]['cantidad'] <= 0:
                    del self.carrito[nombre_juego]
                
            self.actualizar_carrito_display()
            self.actualizar_lista_juegos(self.search_var.get())
            
        except Exception as e:
            print(f"Error al quitar del carrito: {e}")

    def vaciar_carrito(self):
        self.carrito = {}
        self.actualizar_carrito_display()
        self.actualizar_lista_juegos(self.search_var.get())

    def calcular_total(self):
        return sum(item['precio_u'] * item['cantidad'] for item in self.carrito.values())

    def actualizar_carrito_display(self):
        self.listbox_carrito.delete(0, tk.END)
        for nombre, item in self.carrito.items():
            subtotal = item['precio_u'] * item['cantidad']
            display_text = f"{nombre} ({item['cantidad']}x @ {item['precio_u']:.2f}€) = {subtotal:.2f}€"
            self.listbox_carrito.insert(tk.END, display_text)
            
        total = self.calcular_total()
        self.total_label.config(text=f"{total:.2f} €")

    # --- LÓGICA DE PAGO ---
    def procesar_pago(self, metodo_pago):
        global caja_actual, FSE_contador, FST_contador
        total = self.calcular_total()
        
        if total <= 0:
            messagebox.showwarning("Aviso", "El carrito está vacío.")
            return

        # 1. Aplicar descuentos de Fichas
        descuento_fichas = 0
        if metodo_pago == "Efectivo":
            # Si se paga en efectivo, permite aplicar fichas
            descuento_fichas = self.preguntar_fichas()
            if descuento_fichas < 0: # El usuario canceló o hubo error
                return
            total -= descuento_fichas
            
        # 2. Registrar Venta
        if total < 0: total = 0 # No debería pasar, pero por si acaso
        
        venta_id = len(ventas) + 1
        
        detalle_productos = []
        for nombre, item in self.carrito.items():
            detalle_productos.append({
                "nombre": nombre,
                "cantidad": item['cantidad'],
                "precio_u": item['precio_u'],
                "subtotal": item['precio_u'] * item['cantidad'],
                "id_juego": item['id']
            })
        
        registro_venta = {
            "id": venta_id,
            "fecha": datetime.now().isoformat(),
            "vendedor": vendedor_actual,
            "productos": detalle_productos,
            "total": total,
            "descuento_fichas": descuento_fichas,
            "metodo": metodo_pago
        }
        
        ventas.append(registro_venta)
        
        # 3. Actualizar Stock y Caja
        for nombre, item in self.carrito.items():
            for juego in juegos:
                if juego.get('nombre') == nombre:
                    juego['stock'] -= item['cantidad']
                    break
        
        if metodo_pago == "Efectivo":
            # Si se paga en efectivo, la caja recibe el total
            caja_actual += total
            
            # Si hubo descuento, actualiza el contador de fichas
            if descuento_fichas > 0:
                 FSE_contador += 1
                 messagebox.showinfo("Ficha Canjeada", f"Se ha canjeado una ficha FSE.")
        
        if metodo_pago == "Tarjeta":
             FST_contador += 1
             messagebox.showinfo("Ficha Canjeada", f"Se ha canjeado una ficha FST.")


        # 4. Finalizar Transacción
        self.imprimir_ticket(registro_venta)
        self.vaciar_carrito()
        guardar_datos()
        guardar_control_caja()
        self.actualizar_caja_display()
        
        messagebox.showinfo("Venta Exitosa", f"Venta {venta_id} completada por {total:.2f}€ con {metodo_pago}.")
        enviar_a_web() # Sincronizar después de la venta


    def preguntar_fichas(self):
        """Pregunta si desea aplicar descuento de fichas si el total es > 10€."""
        total = self.calcular_total()
        if total < 10.0:
            return 0 # No aplica descuento si el total es bajo
            
        ventana = tk.Toplevel(self.root)
        ventana.title("Aplicar Descuento de Ficha")
        ventana.geometry("400x200")
        ventana.transient(self.root) 
        ventana.grab_set()

        descuento = 0.0
        
        tk.Label(ventana, text=f"Total de Venta: {total:.2f}€", font=("Segoe UI", 12, "bold")).pack(pady=10)
        
        def aplicar():
            nonlocal descuento
            if total >= 10.0:
                descuento = 1.00 # 1€ de descuento por ficha
                ventana.destroy()
            else:
                 messagebox.showwarning("Aviso", "El total debe ser superior a 10€ para usar la ficha.")

        tk.Label(ventana, text="¿El cliente desea aplicar un descuento de ficha (1.00€)?", font=("Segoe UI", 10)).pack(pady=5)
        
        btn_frame = tk.Frame(ventana)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Sí, Aplicar 1.00€", command=aplicar, bg="#28a745", fg="white", font=("Segoe UI", 11, "bold")).pack(side="left", padx=10)
        tk.Button(btn_frame, text="No Aplicar", command=ventana.destroy, bg="#dc3545", fg="white", font=("Segoe UI", 11)).pack(side="left", padx=10)
        
        self.root.wait_window(ventana) # Espera a que la ventana se cierre

        return descuento

    # --- LÓGICA DE CAJA Y RETIROS ---
    def actualizar_caja_display(self):
        self.caja_label.config(text=f"Caja Actual: {caja_actual:.2f} €")
        
    def mostrar_ventana_retiro(self):
        global caja_actual, retiros
        
        ventana = tk.Toplevel(self.root)
        ventana.title("Retiro de Caja")
        ventana.geometry("350x250")
        ventana.transient(self.root)
        ventana.grab_set()

        tk.Label(ventana, text="Retiro de Efectivo", font=("Segoe UI", 14, "bold")).pack(pady=10)
        tk.Label(ventana, text=f"Saldo Actual: {caja_actual:.2f} €", font=("Segoe UI", 11)).pack(pady=5)
        
        tk.Label(ventana, text="Cantidad a Retirar (€):", font=("Segoe UI", 10)).pack(pady=5)
        cantidad_entry = ttk.Entry(ventana, width=20)
        cantidad_entry.pack()
        
        def retirar():
            # Usamos 'global' ya que caja_actual y retiros son variables de módulo.
            global caja_actual
            global retiros
            try:
                cantidad = float(cantidad_entry.get())
                if cantidad <= 0:
                    raise ValueError("Cantidad debe ser positiva.")
                
                if cantidad > caja_actual:
                    messagebox.showerror("Error", "La cantidad excede el saldo actual de la caja.")
                    return

                # Confirmación antes de retirar
                if messagebox.askyesno("Confirmar Retiro", f"¿Confirmas el retiro de {cantidad:.2f} €?"):
                    caja_actual -= cantidad
                    
                    # Registrar el retiro
                    retiro_info = {
                        "tipo": "Retiro",
                        "cantidad": -cantidad, # Se guarda como negativo
                        "fecha": datetime.now().isoformat(),
                        "vendedor": vendedor_actual,
                        "saldo_despues": caja_actual
                    }
                    retiros.append(retiro_info)
                    
                    guardar_control_caja()
                    self.actualizar_caja_display()
                    enviar_a_web() # Sincronizar después del retiro

                    messagebox.showinfo("Retiro Exitoso", f"Se han retirado {cantidad:.2f} €.\nNuevo Saldo: {caja_actual:.2f}")
                    ventana.destroy()
            except ValueError as e:
                messagebox.showerror("Error", f"Cantidad inválida. Asegúrate de usar números (ej: 100.50).")

        btn_frame = tk.Frame(ventana)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Retirar", bg="#28a745", fg="white", font=("Segoe UI", 11, "bold"), command=retirar).pack(side="left", padx=10)
        tk.Button(btn_frame, text="Cancelar", bg="#dc3545", fg="white", font=("Segoe UI", 11), command=ventana.destroy).pack(side="left", padx=10)

    def cerrar_aplicacion(self):
        guardar_datos()
        guardar_control_caja()
        enviar_a_web()
        self.root.destroy()

    def cerrar_sesion(self):
        guardar_datos()
        guardar_control_caja()
        enviar_a_web()
        self.root.destroy()
        # Vuelve a mostrar la ventana de selección de vendedor
        root_selector = tk.Tk()
        VendedorSelector(root_selector)
        root_selector.mainloop()
        
    # --- IMPRESIÓN ---
    def imprimir_ticket(self, venta):
        """Simulación de impresión del ticket."""
        # if p is None:
        #     print("\n--- INICIO TICKET SIMULADO ---")
        #     print(f"Venta ID: {venta['id']} | Fecha: {venta['fecha'].split('T')[0]}")
        #     print(f"Vendedor: {venta['vendedor']}")
        #     print("-" * 30)
        #     for item in venta['productos']:
        #         print(f"{item['nombre'][:20]:<20} {item['cantidad']:>2} x {item['precio_u']:.2f} = {item['subtotal']:.2f} €")
        #     print("-" * 30)
        #     print(f"TOTAL A PAGAR: {venta['total']:.2f} €")
        #     print(f"Método: {venta['metodo']}")
        #     if venta['descuento_fichas'] > 0:
        #          print(f"Descuento Ficha: {venta['descuento_fichas']:.2f} €")
        #     print("--- FIN TICKET SIMULADO ---\n")
        #     return
            
        # # Lógica de impresión física (comentada por defecto)
        # p.set(align='center')
        # p.text("ARTE CAÑETE\n")
        # p.text("TPV JUEGOS\n")
        # p.text("-" * 32 + "\n")
        # p.set(align='left')
        # p.text(f"Venta ID: {venta['id']} / {datetime.now().strftime('%d/%m/%Y %H:%M')}\n")
        # p.text(f"Vendedor: {venta['vendedor']}\n")
        # p.text("-" * 32 + "\n")
        
        # for item in venta['productos']:
        #     line = f"{item['nombre'][:20]:<20} {item['cantidad']:>2}x {item['subtotal']:.2f}\n"
        #     p.text(line)

        # p.text("-" * 32 + "\n")
        # p.set(align='right')
        # p.text(f"TOTAL: {venta['total']:.2f} EUR\n")
        # p.text(f"Pago: {venta['metodo']}\n")
        # if venta['descuento_fichas'] > 0:
        #      p.text(f"Dto. Ficha: {venta['descuento_fichas']:.2f} EUR\n")
        # p.text("¡Gracias por su compra!\n\n\n")
        # p.cut()
        pass # Simulación de impresión para no depender de la librería


# --- CLASE PANEL ADMIN ---

class PanelAdmin:
    def __init__(self, root):
        self.root = root
        self.root.title("Panel de Administración")
        self.root.geometry("800x600")
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar_aplicacion)
        
        self.crear_widgets()
        self.cargar_datos_admin()

    def crear_widgets(self):
        nb = ttk.Notebook(self.root)
        nb.pack(expand=True, fill="both", padx=10, pady=10)
        
        # Pestaña 1: Inventario
        self.inventario_frame = ttk.Frame(nb)
        nb.add(self.inventario_frame, text="Inventario")
        self.crear_inventario_widgets()

        # Pestaña 2: Reporte
        self.reporte_frame = ttk.Frame(nb)
        nb.add(self.reporte_frame, text="Reportes y Caja")
        self.crear_reporte_widgets()

    # --- WIDGETS INVENTARIO ---
    def crear_inventario_widgets(self):
        # Frame de lista de inventario
        list_frame = tk.Frame(self.inventario_frame, padx=10, pady=10)
        list_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(list_frame, text="Lista de Juegos", font=("Segoe UI", 12, "bold")).pack(pady=5)
        
        self.inventario_listbox = tk.Listbox(list_frame, font=("Consolas", 10), height=25)
        self.inventario_listbox.pack(fill=tk.BOTH, expand=True)
        self.inventario_listbox.bind('<<ListboxSelect>>', self.mostrar_detalle_admin)

        # Frame de detalles y edición
        edit_frame = tk.Frame(self.inventario_frame, padx=10, pady=10)
        edit_frame.pack(side=tk.RIGHT, fill=tk.Y)
        
        tk.Label(edit_frame, text="Detalles del Juego", font=("Segoe UI", 12, "bold")).pack(pady=5)

        self.campos = {}
        campos_layout = [("Nombre:", "nombre"), ("Precio (€):", "precio"), ("Stock:", "stock"), ("ID:", "id")]

        for label_text, key in campos_layout:
            frame = tk.Frame(edit_frame)
            frame.pack(fill=tk.X, pady=5)
            tk.Label(frame, text=label_text, width=10, anchor='w').pack(side=tk.LEFT)
            self.campos[key] = ttk.Entry(frame, width=25)
            self.campos[key].pack(side=tk.LEFT, fill=tk.X, expand=True)
            
        self.campos["id"].config(state='readonly') # ID no se puede editar

        tk.Label(edit_frame, text="Imagen:", width=10, anchor='w').pack(pady=(10, 0))
        self.img_admin_label = tk.Label(edit_frame, image=None) # Placeholder para la imagen

        btn_frame = tk.Frame(edit_frame)
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="Actualizar", command=self.actualizar_juego, bg="#3498db", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Nuevo", command=self.nuevo_juego, bg="#2ecc71", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Eliminar", command=self.eliminar_juego, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(edit_frame, text="Cargar Imagen", command=self.cargar_imagen, bg="#9b59b6", fg="white").pack(pady=5)
        tk.Button(edit_frame, text="Volver al TPV", command=self.volver_a_tpv, bg="#34495e", fg="white").pack(pady=10)

    # --- LÓGICA INVENTARIO ---
    def cargar_datos_admin(self):
        self.inventario_listbox.delete(0, tk.END)
        for juego in juegos:
            nombre = juego.get('nombre', 'Nombre Desconocido')
            stock = juego.get('stock', 0)
            self.inventario_listbox.insert(tk.END, f"{nombre[:30].ljust(30)} | STOCK: {stock}")

    def mostrar_detalle_admin(self, event):
        try:
            seleccion = self.inventario_listbox.curselection()
            if not seleccion:
                return
            
            nombre_listado = self.inventario_listbox.get(seleccion[0]).split('|')[0].strip()
            self.juego_seleccionado = next(j for j in juegos if j.get('nombre', '').startswith(nombre_listado))

            for key in self.campos:
                self.campos[key].config(state='normal') # Habilitar para escribir
                valor = self.juego_seleccionado.get(key, '')
                self.campos[key].delete(0, tk.END)
                self.campos[key].insert(0, valor)

            self.campos["id"].config(state='readonly') # ID no se puede editar
            
            # Cargar imagen
            img_path = os.path.join(IMAGE_DIR, self.juego_seleccionado.get('imagen', PLACEHOLDER_IMAGE))
            if not os.path.exists(img_path):
                 img_path = os.path.join(IMAGE_DIR, PLACEHOLDER_IMAGE)
            
            img = Image.open(img_path).resize((150, 150))
            self.tk_img_admin = ImageTk.PhotoImage(img)
            self.img_admin_label.config(image=self.tk_img_admin)
            self.img_admin_label.image = self.tk_img_admin
            self.img_admin_label.pack(pady=5)
            
        except StopIteration:
            messagebox.showerror("Error", "Juego no encontrado.")
        except Exception as e:
            print(f"Error mostrando detalle admin: {e}")

    def actualizar_juego(self):
        if not hasattr(self, 'juego_seleccionado'):
            messagebox.showwarning("Aviso", "Selecciona un juego para actualizar.")
            return

        try:
            # Validación y actualización
            nombre = self.campos["nombre"].get().strip()
            precio = float(self.campos["precio"].get())
            stock = int(self.campos["stock"].get())

            if not nombre or precio < 0 or stock < 0:
                raise ValueError("Campos inválidos.")

            self.juego_seleccionado['nombre'] = nombre
            self.juego_seleccionado['precio'] = precio
            self.juego_seleccionado['stock'] = stock
            # La imagen y el ID se actualizan por separado

            guardar_datos()
            self.cargar_datos_admin()
            messagebox.showinfo("Éxito", "Juego actualizado correctamente.")
            enviar_a_web() # Sincronizar después de la actualización de inventario

        except ValueError as e:
            messagebox.showerror("Error", f"Error de formato en campos: {e}")
        except Exception as e:
            messagebox.showerror("Error", f"Error al actualizar juego: {e}")

    def nuevo_juego(self):
        # Limpiar campos para un nuevo juego
        for key in self.campos:
            self.campos[key].config(state='normal')
            self.campos[key].delete(0, tk.END)
        
        self.campos["id"].config(state='readonly')
        
        # Pedir ID (o generarlo)
        nuevo_id = simpledialog.askstring("Nuevo Juego", "Introduce un ID único para el juego (ej: J001):")
        if not nuevo_id: return

        if any(j.get('id') == nuevo_id for j in juegos):
            messagebox.showerror("Error", "Ese ID ya existe.")
            return

        self.campos["id"].config(state='normal')
        self.campos["id"].insert(0, nuevo_id)
        self.campos["id"].config(state='readonly')
        self.campos["precio"].insert(0, "0.00")
        self.campos["stock"].insert(0, "0")
        
        # Crear la estructura básica del nuevo juego para usar en 'Actualizar'
        self.juego_seleccionado = {
            "id": nuevo_id,
            "nombre": "",
            "precio": 0.0,
            "stock": 0,
            "imagen": PLACEHOLDER_IMAGE
        }
        
        # Añadir a la lista global para que se guarde
        juegos.append(self.juego_seleccionado)
        self.cargar_datos_admin()
        
        messagebox.showinfo("Aviso", "Juego creado. Rellena los detalles y haz clic en 'Actualizar'.")
        
    def eliminar_juego(self):
        if not hasattr(self, 'juego_seleccionado'):
            messagebox.showwarning("Aviso", "Selecciona un juego para eliminar.")
            return
        
        if messagebox.askyesno("Confirmar Eliminación", f"¿Estás seguro de que quieres eliminar {self.juego_seleccionado.get('nombre')}?"):
            global juegos
            juegos = [j for j in juegos if j.get('id') != self.juego_seleccionado.get('id')]
            del self.juego_seleccionado
            guardar_datos()
            self.cargar_datos_admin()
            messagebox.showinfo("Éxito", "Juego eliminado.")
            enviar_a_web()

    def cargar_imagen(self):
        if not hasattr(self, 'juego_seleccionado'):
            messagebox.showwarning("Aviso", "Selecciona o crea un juego primero.")
            return
            
        filepath = filedialog.askopenfilename(defaultextension=".png", 
                                              filetypes=[("PNG files", "*.png"), ("JPEG files", "*.jpg"), ("All files", "*.*")])
        
        if not filepath:
            return
        
        try:
            # Abrir y guardar la imagen en la carpeta IMAGE_DIR
            img_original = Image.open(filepath)
            
            # Usar el ID del juego como nombre de la imagen para asegurar unicidad
            filename = f"{self.juego_seleccionado.get('id', 'temp')}.png"
            img_path_guardar = os.path.join(IMAGE_DIR, filename)
            
            # Guarda la imagen en formato PNG
            img_original.save(img_path_guardar, 'PNG')
            
            # Actualizar la referencia en la estructura del juego
            self.juego_seleccionado['imagen'] = filename
            guardar_datos()
            
            # Mostrar la nueva imagen
            img = img_original.resize((150, 150))
            self.tk_img_admin = ImageTk.PhotoImage(img)
            self.img_admin_label.config(image=self.tk_img_admin)
            self.img_admin_label.image = self.tk_img_admin
            
            messagebox.showinfo("Éxito", f"Imagen cargada como {filename}")
            enviar_a_web()

        except Exception as e:
            messagebox.showerror("Error", f"Error al cargar la imagen: {e}")


    # --- WIDGETS REPORTE ---
    def crear_reporte_widgets(self):
        self.reporte_text = tk.Text(self.reporte_frame, wrap="word", font=("Consolas", 10), padx=10, pady=10)
        self.reporte_text.pack(fill=tk.BOTH, expand=True)

        btn_frame = tk.Frame(self.reporte_frame, padx=10, pady=10)
        btn_frame.pack(fill=tk.X)
        tk.Button(btn_frame, text="Generar Reporte", command=self.generar_reporte, bg="#1abc9c", fg="white").pack(side=tk.LEFT, padx=5)
        tk.Button(btn_frame, text="Cerrar Lote", command=self.cerrar_lote_caja, bg="#e74c3c", fg="white").pack(side=tk.LEFT, padx=5)


    # --- LÓGICA REPORTE ---
    def generar_reporte(self):
        self.reporte_text.delete(1.0, tk.END)
        
        total_ventas = sum(v['total'] for v in ventas)
        total_devoluciones = sum(d['total_devuelto'] for d in devoluciones)
        ventas_netas = total_ventas - total_devoluciones
        
        total_efectivo = sum(v['total'] for v in ventas if v['metodo'] == 'Efectivo')
        total_tarjeta = sum(v['total'] for v in ventas if v['metodo'] == 'Tarjeta')
        
        total_retirado = sum(-r['cantidad'] for r in retiros if r.get('tipo') == 'Retiro')
        
        reporte = "--- REPORTE DETALLADO ---\n\n"
        reporte += f"SALDO DE CAJA ACTUAL: {caja_actual:.2f} €\n"
        reporte += f"CONTADOR FSE (Efectivo): {FSE_contador}\n"
        reporte += f"CONTADOR FST (Tarjeta): {FST_contador}\n"
        reporte += "---------------------------------------\n"
        reporte += f"VENTAS TOTALES (Brutas): {total_ventas:.2f} €\n"
        reporte += f"DEVOLUCIONES: {total_devoluciones:.2f} €\n"
        reporte += f"VENTAS NETAS (Sincronizadas): {ventas_netas:.2f} €\n"
        reporte += f"Efectivo Vendido: {total_efectivo:.2f} €\n"
        reporte += f"Tarjeta Vendida: {total_tarjeta:.2f} €\n"
        reporte += "---------------------------------------\n"
        reporte += f"TOTAL RETIRADO: {total_retirado:.2f} €\n\n"
        
        reporte += "DETALLE DE RETIROS:\n"
        if retiros:
            for r in retiros:
                fecha_str = datetime.fromisoformat(r['fecha']).strftime('%d/%m/%Y %H:%M')
                # El campo 'cantidad' se guarda como negativo en el retiro, por eso usamos abs() para mostrarlo como retiro positivo
                reporte += f"  [{fecha_str}] Retiro: {abs(r['cantidad']):.2f} € (Saldo después: {r['saldo_despues']:.2f})\n"
        else:
            reporte += "  No hay retiros registrados.\n"

        self.reporte_text.insert(1.0, reporte)


    def cerrar_lote_caja(self):
        """Reinicia los contadores, retiros y ajusta la caja para un nuevo lote."""
        if messagebox.askyesno("Confirmar Cierre de Lote", 
                               "Esto reiniciará los contadores FSE/FST y el historial de retiros.\nEl saldo de caja se mantendrá.\n\n¿Deseas continuar?"):
            global FSE_contador, FST_contador, retiros
            FSE_contador = 0
            FST_contador = 0
            retiros = []
            
            guardar_control_caja()
            self.generar_reporte() # Actualiza el reporte
            messagebox.showinfo("Cierre de Lote", "Lote de caja cerrado y contadores/retiros reiniciados.")
            enviar_a_web()

    # --- CIERRE ---
    def volver_a_tpv(self):
        self.root.destroy()
        root_app = tk.Tk()
        AplicacionTPV(root_app)
        root_app.mainloop()

    def cerrar_aplicacion(self):
        guardar_datos()
        guardar_control_caja()
        enviar_a_web()
        self.root.destroy()


# --- INICIO DEL PROGRAMA ---
if __name__ == "__main__":
    inicializar_datos()
    
    root = tk.Tk()
    VendedorSelector(root)
    root.mainloop()
