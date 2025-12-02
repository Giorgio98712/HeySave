import streamlit as st
import datetime
import pandas as pd
import time
import sqlite3
import re

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="HeySave - Dark Mode",
    page_icon="🌑",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- GESTIÓN DE BASE DE DATOS ---
def init_db():
    conn = sqlite3.connect('heysave.db')
    c = conn.cursor()
    # Tabla usuarios con nuevos campos
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, password TEXT,
                    nombre TEXT, dni TEXT, banco TEXT, saldo REAL DEFAULT 0, 
                    saldo_metas REAL DEFAULT 0, puntos INTEGER DEFAULT 0,
                    foto BLOB,
                    pais TEXT, direccion TEXT, postal TEXT)''')
    
    # Migraciones para usuarios existentes (por si acaso)
    columnas_nuevas = ["foto", "saldo_metas", "pais", "direccion", "postal"]
    for col in columnas_nuevas:
        try:
            tipo = "REAL" if "saldo" in col else "TEXT"
            if col == "foto": tipo = "BLOB"
            c.execute(f"ALTER TABLE usuarios ADD COLUMN {col} {tipo}")
        except:
            pass

    c.execute('''CREATE TABLE IF NOT EXISTS transacciones (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, fecha TEXT,
                    descripcion TEXT, categoria TEXT, monto REAL, tipo TEXT,
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS metas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, nombre TEXT,
                    objetivo REAL, ahorrado REAL DEFAULT 0,
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    c.execute('''CREATE TABLE IF NOT EXISTS premios_canjeados (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario_id INTEGER, premio TEXT,
                    codigo TEXT, fecha TEXT,
                    FOREIGN KEY(usuario_id) REFERENCES usuarios(id))''')
    conn.commit()
    conn.close()

def run_query(query, params=(), return_data=False):
    conn = sqlite3.connect('heysave.db')
    c = conn.cursor()
    try:
        c.execute(query, params)
        if return_data:
            data = c.fetchall()
            conn.close()
            return data
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        conn.close()
        return False

init_db()

# --- ESTILOS CSS ---
st.markdown("""
<style>
    /* 1. FONDO GENERAL */
    .stApp { background-color: #0E1117 !important; }
    
    /* 2. TEXTOS GLOBALES */
    h1, h2, h3, h4, h5, h6, p, span, label, div[data-testid="stMarkdownContainer"] p { color: #E6E6E6 !important; }
    .stCaption { color: #A0A0A0 !important; }

    /* 3. INPUTS Y SELECTBOXES */
    div[data-baseweb="input"], div[data-baseweb="select"] > div {
        background-color: #262730 !important;
        border-color: #4A4A4A !important;
        border-radius: 8px !important;
    }
    input[type="text"], input[type="password"], input[type="number"] { color: #FFFFFF !important; }
    div[data-baseweb="select"] span { color: #FFFFFF !important; }
    
    /* 4. OCULTAR BOTONES +/- (STEPPERS) */
    button[kind="secondaryFormSubmit"] { display: none; } 
    div[data-testid="stNumberInput"] button { display: none !important; }
    input[type=number]::-webkit-inner-spin-button, 
    input[type=number]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type=number] { -moz-appearance: textfield; }

    /* 5. TARJETA DE SALDO */
    .balance-card {
        background: linear-gradient(135deg, #1f1f1f 0%, #111111 100%);
        border: 1px solid #333;
        color: white !important;
        padding: 25px;
        border-radius: 20px;
        box-shadow: 0 4px 15px rgba(0,0,0,0.5);
        margin-bottom: 25px;
        text-align: center;
        position: relative;
        overflow: hidden;
    }
    .balance-title { font-size: 14px; opacity: 0.7; letter-spacing: 2px; text-transform: uppercase; color: #ccc !important;}
    .balance-amount { font-size: 42px; font-weight: bold; margin: 10px 0; color: #fff !important; }

    /* 6. OTROS */
    .stButton>button { background-color: #238636; color: white; border: none; height: 45px; border-radius: 8px; font-weight: 600; }
    .suggestion-card { background-color: #161B22; border: 1px solid #8b5cf6; color: #E6E6E6; padding: 15px; border-radius: 10px; margin-bottom: 10px; }
    div[data-testid="stExpander"] { background-color: #0d1117; border: 1px solid #30363D; border-radius: 8px; }
    
    /* FOTO DE PERFIL */
    div[data-testid="stImage"] img {
        border-radius: 50%;
        object-fit: cover;
    }
</style>
""", unsafe_allow_html=True)

# --- VARIABLES DE ESTADO ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'usuario' not in st.session_state: st.session_state.usuario = ""
if 'reg_step' not in st.session_state: st.session_state.reg_step = 1
if 'temp_reg_data' not in st.session_state: st.session_state.temp_reg_data = {}
if 'cc_num_input' not in st.session_state: st.session_state.cc_num_input = ""
if 'cc_exp_input' not in st.session_state: st.session_state.cc_exp_input = ""
if 'mostrar_camara' not in st.session_state: st.session_state.mostrar_camara = False

# --- FUNCIONES DE LIMPIEZA ---
def limpiar_solo_numeros(key, max_len=None):
    if key in st.session_state:
        val = st.session_state[key]
        clean = re.sub(r'\D', '', val)
        if max_len and len(clean) > max_len:
            clean = clean[:max_len]
        st.session_state[key] = clean

def formatear_tarjeta():
    raw = st.session_state.cc_num_input
    clean = re.sub(r'\D', '', raw)[:16]
    groups = [clean[i:i+4] for i in range(0, len(clean), 4)]
    st.session_state.cc_num_input = " ".join(groups)

def formatear_fecha():
    raw = st.session_state.cc_exp_input
    clean = re.sub(r'\D', '', raw)[:4] 
    if len(clean) >= 3:
        st.session_state.cc_exp_input = clean[:2] + "/" + clean[2:]
    else:
        st.session_state.cc_exp_input = clean

# --- OTRAS FUNCIONES ---
def detectar_banco_red(numero):
    n = numero.replace(" ", "")
    banco = "Desconocido"
    red = ""
    if n.startswith("4"): red = "Visa"
    elif n.startswith("5"): red = "Mastercard"
    else: red = "Tarjeta"
    if len(n) >= 4:
        if n.startswith(("4551", "4214", "5491")): banco = "BCP"
        elif n.startswith(("4550", "4919", "5160")): banco = "BBVA"
        elif n.startswith(("4213", "4458", "5204")): banco = "Interbank"
        elif n.startswith(("4555", "5406")): banco = "Scotiabank"
        elif n.startswith("4111"): banco = "Banco de la Nación"
        elif red in ["Visa", "Mastercard"]: banco = f"{red} Bank"
    return banco, red

def detectar_categoria(descripcion):
    desc = descripcion.lower()
    if any(x in desc for x in ["comida", "hamburguesa", "pizza", "starbucks", "menu", "kfc", "desayuno"]): return "Alimentación 🍔"
    elif any(x in desc for x in ["uber", "taxi", "bus", "gasolina", "cabify", "pasaje"]): return "Transporte 🚕"
    elif any(x in desc for x in ["cine", "netflix", "spotify", "fiesta", "entrada", "juego"]): return "Entretenimiento 🎬"
    elif any(x in desc for x in ["libro", "fotocopias", "curso", "pension", "universidad", "clase"]): return "Educación 📚"
    elif any(x in desc for x in ["ropa", "zapatilla", "polo", "tienda", "shopping"]): return "Moda 👕"
    else: return "Varios 📦"

def analizar_gastos_y_sugerir(user_id):
    tips = []
    gastos = run_query("SELECT categoria FROM transacciones WHERE usuario_id = ? AND tipo = 'Gasto'", (user_id,), return_data=True)
    saldo_actual = run_query("SELECT saldo FROM usuarios WHERE id = ?", (user_id,), return_data=True)[0][0]
    
    if not gastos: return ["👋 Registra tus primeros gastos para recibir consejos de la IA."]
    cats = set([g[0] for g in gastos])
    
    if any("Alimentación" in c for c in cats): tips.append("🍔 **Comida:** Cocinar en casa ahorra hasta S/. 120/mes.")
    if any("Transporte" in c for c in cats): tips.append("🚕 **Movilidad:** ¿Has probado compartir viaje o usar bus?")
    if any("Entretenimiento" in c for c in cats): tips.append("🎬 **Ocio:** Busca descuentos de estudiante.")
    
    if saldo_actual < 20: tips.append("🚨 **URGENTE:** Saldo crítico (< S/. 20).")
    elif saldo_actual < 50: tips.append("⚠️ **Cuidado:** Prioriza lo esencial (< S/. 50).")
        
    if not tips: tips.append("✅ **¡Finanzas Saludables!** Sigue así.")
    return tips

def calcular_nivel(puntos):
    if puntos < 100: return "Bronce 🥉", 100
    elif puntos < 500: return "Plata 🥈", 500
    elif puntos < 1500: return "Oro 🥇", 1500
    else: return "Diamante 💎", 5000

# --- LOGIN & REGISTRO ---
def login_register_screen():
    st.markdown("<h1 style='text-align: center; color: #D2A8FF;'>💸 HeySave</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #8B949E;'>Tu Billetera Digital en Dark Mode</p>", unsafe_allow_html=True)
    st.write("")
    
    tab_login, tab_register = st.tabs(["🔐 Iniciar Sesión", "📝 Crear Cuenta"])
    
    # --- PESTAÑA DE LOGIN ---
    with tab_login:
        with st.form("login_form"):
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            submitted = st.form_submit_button("Ingresar", type="primary")
            
            if submitted:
                data = run_query("SELECT id, usuario, nombre FROM usuarios WHERE usuario = ? AND password = ?", (user, password), return_data=True)
                if data:
                    st.session_state.logged_in = True
                    st.session_state.user_id = data[0][0]
                    st.session_state.usuario = data[0][1]
                    st.toast(f"Hola {data[0][2]}!"); time.sleep(1); st.rerun()
                else: st.error("Credenciales incorrectas")

    # --- PESTAÑA DE REGISTRO ---
    with tab_register:
        if st.session_state.reg_step == 1:
            st.markdown("##### Paso 1: Datos Personales")
            r_user = st.text_input("Usuario (Nick)")
            r_pass = st.text_input("Contraseña", type="password", help="Mínimo 5 letras/números y 1 especial")
            r_nombre = st.text_input("Nombre Completo")
            r_dni = st.text_input("DNI", key="reg_dni", max_chars=8, on_change=lambda: limpiar_solo_numeros("reg_dni", 8))
            
            if st.button("Siguiente ➡️"):
                errores = []
                has_special = bool(re.search(r"[^a-zA-Z0-9\s]", r_pass))
                if len(r_pass) < 6 or not has_special: errores.append("Contraseña insegura (Mín 5 chars + 1 especial).")
                if len(st.session_state.reg_dni) != 8: errores.append("DNI inválido (debe tener 8 dígitos).")
                if not r_user or not r_nombre: errores.append("Faltan datos.")

                if not errores:
                    if run_query("SELECT id FROM usuarios WHERE usuario = ?", (r_user,), return_data=True):
                        st.error("Usuario ocupado.")
                    else:
                        st.session_state.temp_reg_data = {"user": r_user, "pass": r_pass, "nombre": r_nombre, "dni": st.session_state.reg_dni}
                        st.session_state.reg_step = 2; st.rerun()
                else:
                    for err in errores: st.error(err)
        
        elif st.session_state.reg_step == 2:
            st.markdown("##### Paso 2: Datos Bancarios y Dirección")
            st.info(f"Hola **{st.session_state.temp_reg_data['nombre']}**, completa tu registro.")
            
            # --- NUEVOS CAMPOS OBLIGATORIOS ---
            st.markdown("**📍 Dirección de Facturación**")
            r_pais = st.text_input("País")
            r_direccion = st.text_input("Dirección")
            r_postal = st.text_input("Código Postal", key="reg_postal", max_chars=10, on_change=lambda: limpiar_solo_numeros("reg_postal", 10))
            
            st.divider()
            st.markdown("**💳 Tarjeta**")
            
            st.text_input("N° Tarjeta", key="cc_num_input", placeholder="0000 0000 0000 0000", on_change=formatear_tarjeta)
            
            tarjeta_actual = st.session_state.cc_num_input
            banco_detectado, red_detectada = detectar_banco_red(tarjeta_actual)
            
            if len(tarjeta_actual) >= 4:
                if banco_detectado != "Desconocido":
                    st.success(f"✅ Tarjeta detectada: **{banco_detectado}** ({red_detectada})")
                else:
                    st.warning(f"🤔 {red_detectada} detectada.")
            
            c1, c2 = st.columns(2)
            c1.text_input("Exp (MM/AA)", key="cc_exp_input", placeholder="MM/AA", on_change=formatear_fecha)
            c2.text_input("CVV", type="password", key="reg_cvv", max_chars=3, on_change=lambda: limpiar_solo_numeros("reg_cvv", 3))
            
            cb1, cb2 = st.columns(2)
            if cb1.button("⬅️ Volver"): st.session_state.reg_step = 1; st.rerun()
            
            if cb2.button("✅ Finalizar", type="primary"):
                tarjeta_limpia = st.session_state.cc_num_input.replace(" ", "")
                fecha_limpia = st.session_state.cc_exp_input
                cvv_limpio = st.session_state.reg_cvv
                
                # Validaciones
                errores_reg2 = []
                if not r_pais or not r_direccion or not st.session_state.reg_postal: errores_reg2.append("Faltan datos de dirección.")
                if len(tarjeta_limpia) != 16: errores_reg2.append("Tarjeta incompleta (16 dígitos).")
                if len(fecha_limpia) != 5: errores_reg2.append("Fecha incompleta (MM/AA).")
                if len(cvv_limpio) != 3: errores_reg2.append("CVV inválido (3 dígitos).")

                if errores_reg2:
                    for e in errores_reg2: st.error(e)
                else:
                    d = st.session_state.temp_reg_data
                    banco_final = banco_detectado if banco_detectado != "Desconocido" else f"{red_detectada} Genérico"
                    
                    run_query("INSERT INTO usuarios (usuario, password, nombre, dni, banco, pais, direccion, postal) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", 
                                (d['user'], d['pass'], d['nombre'], d['dni'], banco_final, r_pais, r_direccion, st.session_state.reg_postal))
                    st.balloons(); st.success("¡Cuenta Creada!"); st.session_state.reg_step = 1; time.sleep(2); st.rerun()

# --- APP PRINCIPAL ---
def main_app():
    user_id = st.session_state.user_id
    # Traemos el saldo_metas (el apartado especial)
    user_data = run_query("SELECT saldo, puntos, nombre, dni, banco, foto, saldo_metas FROM usuarios WHERE id = ?", (user_id,), return_data=True)[0]
    saldo_db, puntos_db, nombre_user, dni_user, banco_user, foto_blob, saldo_metas_db = user_data
    
    # Manejo de valor nulo para saldo_metas en usuarios viejos
    if saldo_metas_db is None: saldo_metas_db = 0.0

    nivel_actual, prox_nivel = calcular_nivel(puntos_db)
    
    # --- SIDEBAR ---
    with st.sidebar:
        if foto_blob: st.image(foto_blob, width=150)
        else: st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=150)
             
        st.write(f"Usuario: **{st.session_state.usuario}**")
        st.metric("HeyPoints", f"{puntos_db} ⭐")
        st.info(f"Rango: {nivel_actual}")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False; st.session_state.user_id = None; st.rerun()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Inicio", "🎯 Metas", "💡 Tips", "🎁 Premios", "👤 Perfil"])

    # --- TAB 1: DASHBOARD ---
    with tab1:
        st.markdown(f"""
        <div class="balance-card">
            <div class="balance-title">Saldo Disponible</div>
            <div class="balance-amount">S/. {saldo_db:,.2f}</div>
            <div style="font-size: 12px; opacity: 0.8; color: #ddd;">{banco_user} • **** {dni_user[-4:]}</div>
        </div>
        """, unsafe_allow_html=True)

        # Mostrar el "Apartado Especial" de Dinero de Metas
        if saldo_metas_db > 0:
            st.info(f"💰 **Dinero de Metas (Retirado):** S/. {saldo_metas_db:,.2f}")

        with st.container():
            c1, c2 = st.columns([2, 1])
            desc = c1.text_input("Descripción", placeholder="Ej. Almuerzo, Uber...")
            monto = c2.number_input("Monto (S/.)", min_value=0.0, step=0.01, format="%.2f")
            
            b1, b2 = st.columns(2)
            
            if b1.button("➖ Registrar Gasto", type="primary"):
                if desc and monto > 0:
                    if monto > saldo_db: st.error("🚫 Fondos insuficientes.")
                    else:
                        cat = detectar_categoria(desc)
                        run_query("UPDATE usuarios SET saldo = saldo - ? WHERE id = ?", (monto, user_id))
                        run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                                  (user_id, datetime.date.today().strftime("%d/%m"), desc, cat, monto, 'Gasto'))
                        st.rerun()
            
            if b2.button("➕ Registrar Ingreso"):
                if desc and monto > 0:
                    run_query("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (monto, user_id))
                    run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                              (user_id, datetime.date.today().strftime("%d/%m"), desc, "Ingreso", monto, 'Ingreso'))
                    st.rerun()

        # --- SECCIÓN: ÚLTIMOS MOVIMIENTOS (SIN TABLA, NATIVO Y BONITO) ---
        st.subheader("📝 Últimos Movimientos")
        
        hist_data = run_query("SELECT fecha, descripcion, categoria, tipo, monto FROM transacciones WHERE usuario_id = ? ORDER BY id DESC LIMIT 10", (user_id,), return_data=True)
        
        if hist_data:
            for h in hist_data:
                fecha, desc_txt, cat_txt, tipo, monto_val = h
                
                # Configuración visual nativa
                if tipo == "Gasto":
                    icon = "💸"
                    color_monto = "red"
                    signo = "-"
                else: # Ingreso
                    icon = "💰"
                    color_monto = "green"
                    signo = "+"
                
                # Tarjeta visual nativa usando st.container
                with st.container(border=True):
                    c_icon, c_det, c_mont = st.columns([1, 4, 2])
                    with c_icon:
                        st.markdown(f"# {icon}")
                    with c_det:
                        st.write(f"**{desc_txt}**")
                        st.caption(f"{cat_txt} • {fecha}")
                    with c_mont:
                        # Color nativo de Streamlit
                        st.markdown(f"#### :{color_monto}[{signo} S/. {monto_val:,.2f}]")
        else:
            st.info("No hay movimientos recientes.")

    # --- TAB 2: METAS ---
    with tab2:
        st.subheader("🎯 Mis Objetivos")
        with st.expander("➕ Nueva Meta", expanded=False):
            n_name = st.text_input("Nombre Meta")
            n_obj = st.number_input("Monto Objetivo", min_value=0.0, step=1.0, format="%.2f")
            
            if st.button("Crear Meta"):
                if n_obj > 0 and n_name:
                    run_query("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (?, ?, ?)", (user_id, n_name, n_obj))
                    st.rerun()
                else: st.error("Datos inválidos.")
        
        metas = run_query("SELECT id, nombre, objetivo, ahorrado FROM metas WHERE usuario_id = ?", (user_id,), return_data=True)
        for m in metas:
            mid, nom, obj, aho = m
            pct = min(aho/obj, 1.0)
            st.markdown(f"**{nom}** (S/. {aho:.2f} / S/. {obj:.2f})")
            st.progress(pct)
            
            if aho < obj:
                # Meta en progreso
                c1, c2 = st.columns([2, 1])
                abo = c1.number_input(f"Monto a abonar", key=f"ab_{mid}", min_value=0.0, step=1.0, label_visibility="collapsed")
                
                if c2.button("Abonar", key=f"btn_{mid}"):
                    if abo > 0 and saldo_db >= abo:
                        pts = int(abo * 0.25)
                        run_query("UPDATE metas SET ahorrado = ahorrado + ? WHERE id = ?", (abo, mid))
                        run_query("UPDATE usuarios SET saldo = saldo - ?, puntos = puntos + ? WHERE id = ?", (abo, pts, user_id))
                        st.toast(f"¡Guardado! +{pts} pts"); time.sleep(1); st.rerun()
                    else: st.error("Saldo insuficiente")
            else:
                # META COMPLETADA
                st.success("¡META COMPLETADA! 🎉")
                
                # --- SISTEMA DE RETIRO Y TRANSFERENCIAS ---
                st.write("**¿Qué deseas hacer con el dinero?**")
                
                # Radio button principal
                opcion_retiro = st.radio("Selecciona una opción:", 
                                         ["Mantener en Meta", 
                                          "Retirar a Billetera (Sin Puntos)", 
                                          "Transferir a un Banco"], 
                                         key=f"opt_{mid}", label_visibility="collapsed")
                
                # Opción 1: Retirar a apartado especial (anti-farming)
                if opcion_retiro == "Retirar a Billetera (Sin Puntos)":
                    st.caption("El dinero irá a 'Dinero de Metas' y no generará puntos si se vuelve a ahorrar.")
                    if st.button("Confirmar Retiro Interno", key=f"ret_{mid}"):
                        # Mueve dinero a saldo_metas, NO a saldo principal
                        run_query("UPDATE usuarios SET saldo_metas = saldo_metas + ? WHERE id = ?", (aho, user_id))
                        run_query("UPDATE metas SET ahorrado = 0 WHERE id = ?", (mid,))
                        run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                                  (user_id, datetime.date.today().strftime("%d/%m"), f"Retiro Meta: {nom}", "Ahorro", aho, 'Ingreso'))
                        st.balloons(); st.success("Dinero movido a tu apartado de Metas."); time.sleep(2); st.rerun()
                
                # Opción 2: Transferencia Externa
                elif opcion_retiro == "Transferir a un Banco":
                    # Sub-selección de tipo de transferencia
                    tipo_trans = st.radio("Tipo de Transferencia:", ["Mismo Banco", "Interbancario (CCI)"], key=f"type_{mid}", horizontal=True)
                    
                    if tipo_trans == "Mismo Banco":
                        n_cuenta = st.text_input("Número de Cuenta", key=f"cta_{mid}")
                        if st.button("Confirmar Transferencia", key=f"trans_banco_{mid}"):
                            if len(n_cuenta) > 5 and n_cuenta.isdigit(): # Validación básica
                                run_query("UPDATE metas SET ahorrado = 0 WHERE id = ?", (mid,))
                                run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                                          (user_id, datetime.date.today().strftime("%d/%m"), f"Transf. a {n_cuenta}: {nom}", "Transferencia", aho, 'Gasto'))
                                st.success("Transferencia exitosa."); time.sleep(2); st.rerun()
                            else: st.error("Número de cuenta inválido.")
                            
                    else: # Interbancario
                        cci_destino = st.text_input("Ingresa CCI (20 dígitos)", key=f"cci_{mid}", max_chars=20)
                        if st.button("Confirmar CCI", key=f"trans_cci_{mid}"):
                            if len(cci_destino) == 20 and cci_destino.isdigit():
                                run_query("UPDATE metas SET ahorrado = 0 WHERE id = ?", (mid,))
                                run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                                          (user_id, datetime.date.today().strftime("%d/%m"), f"Transf. CCI {cci_destino}: {nom}", "Transferencia", aho, 'Gasto'))
                                st.success("Transferencia CCI exitosa."); time.sleep(2); st.rerun()
                            else: st.error("El CCI debe tener 20 números.")
            st.divider()

    # --- TAB 3: SUGERENCIAS ---
    with tab3:
        st.subheader("🤖 HeySave AI Tips")
        with st.spinner('Analizando tus gastos...'): time.sleep(0.5)
        for t in analizar_gastos_y_sugerir(user_id):
            st.markdown(f"""<div class="suggestion-card">{t}</div>""", unsafe_allow_html=True)

    # --- TAB 4: PREMIOS ---
    with tab4:
        col_header, col_pts = st.columns([2,1])
        col_header.subheader("🎁 Canjea tus Puntos")
        col_pts.metric("Tus Puntos", f"{puntos_db}", delta="XP")
        premios = [
            {"img": "☕", "nom": "Café Gratis", "costo": 50, "code": "CAFE-FREE"},
            {"img": "🍿", "nom": "2x1 Cine", "costo": 150, "code": "CINE-X2"},
            {"img": "📚", "nom": "Libro -20%", "costo": 300, "code": "BOOK-20"},
            {"img": "🎧", "nom": "Spotify 1 Mes", "costo": 600, "code": "SPOT-1M"},
        ]
        cols = st.columns(2)
        for idx, p in enumerate(premios):
            with cols[idx % 2]:
                with st.container(border=True):
                    st.markdown(f"<div style='text-align:center; font-size:40px;'>{p['img']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:center; font-weight:bold; color: white;'>{p['nom']}</div>", unsafe_allow_html=True)
                    st.markdown(f"<div style='text-align:center; color:#f59e0b;'>{p['costo']} Pts</div>", unsafe_allow_html=True)
                    if st.button(f"Canjear", key=f"r_{idx}"):
                        if puntos_db >= p['costo']:
                            run_query("UPDATE usuarios SET puntos = puntos - ? WHERE id = ?", (p['costo'], user_id))
                            run_query("INSERT INTO premios_canjeados (usuario_id, premio, codigo, fecha) VALUES (?, ?, ?, ?)", 
                                     (user_id, p['nom'], p['code'], datetime.date.today().strftime("%d/%m/%Y")))
                            st.balloons(); time.sleep(1); st.rerun()
                        else: st.error("Puntos insuficientes")

    # --- TAB 5: PERFIL ---
    with tab5:
        c1, c2 = st.columns([1,2])
        with c1:
             if foto_blob: st.image(foto_blob, width=120)
             else: st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=120)
        with c2:
            st.markdown(f"<h2 style='margin:0;'>{nombre_user}</h2>", unsafe_allow_html=True)
            st.caption(f"DNI: {dni_user} | Banco: {banco_user}")
            st.markdown(f"<p style='color:#8B949E; margin-top:5px;'>{nivel_actual}</p>", unsafe_allow_html=True)
        
        st.divider()
        
        if not st.session_state.mostrar_camara:
            if st.button("📷 Actualizar Foto de Perfil"):
                st.session_state.mostrar_camara = True
                st.rerun()
        else:
            st.markdown("### Sonríe para la foto 😁")
            img_buffer = st.camera_input("Toma tu foto", label_visibility="collapsed")
            
            c_save, c_cancel = st.columns(2)
            
            if img_buffer is not None:
                if c_save.button("Guardar Foto", type="primary"):
                    bytes_data = img_buffer.getvalue()
                    run_query("UPDATE usuarios SET foto = ? WHERE id = ?", (bytes_data, user_id))
                    st.success("¡Foto actualizada!")
                    st.session_state.mostrar_camara = False 
                    time.sleep(1.5)
                    st.rerun()
            
            if c_cancel.button("Cancelar / Cerrar"):
                st.session_state.mostrar_camara = False
                st.rerun()

        st.markdown("### 📜 Historial de Canjes")
        mp = run_query("SELECT fecha, premio, codigo FROM premios_canjeados WHERE usuario_id = ? ORDER BY id DESC", (user_id,), return_data=True)
        if mp:
            for item in mp:
                st.info(f"📅 {item[0]} | {item[1]} -> Código: **{item[2]}**")
        else: st.caption("No has canjeado premios aún.")
        
        st.write("")
        if st.button("Cerrar Sesión", key="btn_logout_tab"):
            st.session_state.logged_in = False; st.session_state.user_id = None; st.rerun()

# --- EJECUCIÓN ---
if st.session_state.logged_in: main_app()
else: login_register_screen()