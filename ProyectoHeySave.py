import streamlit as st
import datetime
import pandas as pd
import time
import sqlite3

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(
    page_title="HeySave Web - DB",
    page_icon="💰",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# --- GESTIÓN DE BASE DE DATOS (SQLITE) ---
def init_db():
    conn = sqlite3.connect('heysave.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS usuarios (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, usuario TEXT UNIQUE, password TEXT,
                    nombre TEXT, dni TEXT, banco TEXT, saldo REAL DEFAULT 0, puntos INTEGER DEFAULT 0)''')
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
    .stButton>button { width: 100%; border-radius: 15px; font-weight: bold; }
    .card-container { display: flex; flex-wrap: wrap; gap: 15px; justify-content: center; }
    .suggestion-card { padding: 15px; border-radius: 12px; background-color: #f8f9fa; color: #000; border-left: 6px solid #4CAF50; margin-bottom: 10px; }
    .suggestion-card p, .suggestion-card b, .suggestion-card strong { color: #000 !important; }
    .reward-card { flex: 1 1 150px; min-width: 140px; border: 1px solid #eee; border-radius: 15px; padding: 20px; text-align: center; background-color: white; box-shadow: 0 4px 8px rgba(0,0,0,0.1); margin-bottom: 15px; }
    .reward-price { color: #FF9800; font-weight: bold; font-size: 1.2em; }
    .goal-complete { background-color: #dcfce7; border: 2px solid #22c55e; padding: 10px; border-radius: 10px; text-align: center; color: #14532d; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# --- VARIABLES ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_id' not in st.session_state: st.session_state.user_id = None
if 'usuario' not in st.session_state: st.session_state.usuario = ""
if 'reg_step' not in st.session_state: st.session_state.reg_step = 1
if 'temp_reg_data' not in st.session_state: st.session_state.temp_reg_data = {}

# --- LÓGICA ---
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
    # Obtener gastos y saldo
    gastos = run_query("SELECT categoria FROM transacciones WHERE usuario_id = ? AND tipo = 'Gasto'", (user_id,), return_data=True)
    saldo_actual = run_query("SELECT saldo FROM usuarios WHERE id = ?", (user_id,), return_data=True)[0][0]
    
    # 1. Caso: Sin gastos
    if not gastos:
        return ["👋 Aún no hay suficientes datos. Registra tu primer gasto en 'Inicio' para recibir consejos de la IA."]
    
    cats = set([g[0] for g in gastos])
    
    # 2. Análisis de Categorías
    if any("Alimentación" in c for c in cats): tips.append("🍔 **Comida:** Veo gastos recurrentes. Cocinar en casa ahorra hasta S/. 120/mes.")
    if any("Transporte" in c for c in cats): tips.append("🚕 **Movilidad:** Los taxis suman mucho a fin de mes. ¿Has probado rutas de bus o compartir viaje?")
    if any("Entretenimiento" in c for c in cats): tips.append("🎬 **Ocio:** Busca actividades gratuitas en la universidad o descuentos de estudiante.")
    if any("Moda" in c for c in cats): tips.append("👕 **Compras:** Antes de comprar ropa, espera 24 horas para evitar compras impulsivas.")
    
    # 3. Alertas de Saldo
    if saldo_actual < 20:
        tips.append("🚨 **URGENTE:** Tu saldo es crítico (Menor a S/. 20). ¡Detén los gastos hormiga ya!")
    elif saldo_actual < 50:
        tips.append("⚠️ **Cuidado:** Saldo bajo (< S/. 50). Prioriza solo lo esencial esta semana.")
        
    # 4. FIX: Si hay gastos pero no caen en ninguna categoría de alerta
    if not tips:
        tips.append("✅ **¡Todo en Orden!:** Tienes gastos registrados pero tus finanzas se ven saludables. No detecto excesos en categorías críticas. ¡Sigue así!")

    return tips

def calcular_nivel(puntos):
    if puntos < 100: return "Bronce 🥉", 100
    elif puntos < 500: return "Plata 🥈", 500
    elif puntos < 1500: return "Oro 🥇", 1500
    else: return "Diamante 💎", 5000

# --- PANTALLAS ---
def login_register_screen():
    st.title("💰 HeySave")
    st.subheader("Tu Asistente Financiero")
    
    tab_login, tab_register = st.tabs(["🔐 Iniciar Sesión", "📝 Crear Cuenta"])
    
    with tab_login:
        with st.form("login_form"):
            user = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Entrar"):
                data = run_query("SELECT id, usuario, nombre FROM usuarios WHERE usuario = ? AND password = ?", (user, password), return_data=True)
                if data:
                    st.session_state.logged_in = True
                    st.session_state.user_id = data[0][0]
                    st.session_state.usuario = data[0][1]
                    st.success(f"Bienvenido {data[0][2]}")
                    time.sleep(1); st.rerun()
                else: st.error("Error de credenciales")

    with tab_register:
        if st.session_state.reg_step == 1:
            st.markdown("### Paso 1: Datos Personales")
            with st.form("reg_s1"):
                r_user = st.text_input("Usuario (Nick)")
                r_pass = st.text_input("Contraseña", type="password")
                r_nombre = st.text_input("Nombre Completo")
                r_dni = st.text_input("DNI", max_chars=8)
                if st.form_submit_button("Siguiente ➡️"):
                    if r_user and r_pass and r_nombre and len(r_dni)==8:
                        if run_query("SELECT id FROM usuarios WHERE usuario = ?", (r_user,), return_data=True):
                            st.error("Usuario ocupado")
                        else:
                            st.session_state.temp_reg_data = {"user": r_user, "pass": r_pass, "nombre": r_nombre, "dni": r_dni}
                            st.session_state.reg_step = 2; st.rerun()
                    else: st.warning("Completa los datos")
        
        elif st.session_state.reg_step == 2:
            st.markdown("### Paso 2: Vincular Tarjeta")
            st.info(f"Hola **{st.session_state.temp_reg_data['nombre']}**, vincula tu tarjeta.")
            with st.form("reg_s2"):
                r_banco = st.selectbox("Banco", ["BCP", "Interbank", "BBVA", "Yape/Plin"])
                st.text_input("N° Tarjeta", placeholder="0000 0000 0000 0000")
                c1, c2 = st.columns(2)
                c1.text_input("Exp (MM/AA)"); c2.text_input("CVV", type="password")
                if st.form_submit_button("✅ Finalizar"):
                    d = st.session_state.temp_reg_data
                    if run_query("INSERT INTO usuarios (usuario, password, nombre, dni, banco) VALUES (?, ?, ?, ?, ?)", (d['user'], d['pass'], d['nombre'], d['dni'], r_banco)):
                        st.balloons(); st.success("Cuenta creada"); st.session_state.reg_step = 1; time.sleep(2); st.rerun()
                    else: st.error("Error al guardar")
            if st.button("⬅️ Volver"): st.session_state.reg_step = 1; st.rerun()

def main_app():
    user_id = st.session_state.user_id
    user_data = run_query("SELECT saldo, puntos, nombre, dni, banco FROM usuarios WHERE id = ?", (user_id,), return_data=True)[0]
    saldo_db, puntos_db = user_data[0], user_data[1]
    nivel_actual, prox_nivel = calcular_nivel(puntos_db)
    
    with st.sidebar:
        st.write(f"Usuario: **{st.session_state.usuario}**")
        st.metric("HeyPoints", f"{puntos_db} ⭐")
        st.info(f"Rango: {nivel_actual}")
        if st.button("Cerrar Sesión"):
            st.session_state.logged_in = False; st.session_state.user_id = None; st.rerun()

    st.title(f"Hola, {st.session_state.usuario} 👋")
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["🏠 Inicio", "🎯 Metas", "💡 Sugerencias", "🎁 Premios", "👤 Perfil"])

    with tab1:
        st.metric("💰 Saldo Disponible", f"S/. {saldo_db:.2f}")
        st.divider()
        c1, c2 = st.columns(2)
        desc = c1.text_input("Descripción"); monto = c2.number_input("Monto (S/.)", min_value=0.0, step=1.0)
        col1, col2 = st.columns(2)
        
        if col1.button("➖ Gasto", type="primary"):
            if desc and monto > 0:
                cat = detectar_categoria(desc)
                run_query("UPDATE usuarios SET saldo = saldo - ? WHERE id = ?", (monto, user_id))
                run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, datetime.date.today().strftime("%d/%m"), desc, cat, monto, 'Gasto'))
                st.toast(f"Gasto: {cat}"); time.sleep(0.5); st.rerun()
                
        if col2.button("➕ Ingreso"):
            if desc and monto > 0:
                run_query("UPDATE usuarios SET saldo = saldo + ? WHERE id = ?", (monto, user_id))
                run_query("INSERT INTO transacciones (usuario_id, fecha, descripcion, categoria, monto, tipo) VALUES (?, ?, ?, ?, ?, ?)",
                          (user_id, datetime.date.today().strftime("%d/%m"), desc, "Ingreso", monto, 'Ingreso'))
                st.success("Ingreso OK"); time.sleep(0.5); st.rerun()

        st.divider()
        hist = run_query("SELECT fecha, descripcion, categoria, monto, tipo FROM transacciones WHERE usuario_id = ? ORDER BY id DESC LIMIT 10", (user_id,), return_data=True)
        if hist:
            df = [{"Fecha": h[0], "Desc": h[1], "Cat": h[2], "Monto": f"{'-' if h[4]=='Gasto' else '+'} S/. {h[3]:.2f}"} for h in hist]
            st.dataframe(pd.DataFrame(df), use_container_width=True, hide_index=True)

    with tab2:
        st.subheader("🎯 Mis Metas")
        with st.expander("➕ Crear Nueva Meta"):
            n_name = st.text_input("Nombre"); n_obj = st.number_input("Objetivo", min_value=1.0)
            if st.button("Crear"):
                run_query("INSERT INTO metas (usuario_id, nombre, objetivo) VALUES (?, ?, ?)", (user_id, n_name, n_obj))
                st.rerun()
        
        metas = run_query("SELECT id, nombre, objetivo, ahorrado FROM metas WHERE usuario_id = ?", (user_id,), return_data=True)
        if not metas: st.info("Sin metas activas")
        for m in metas:
            mid, nom, obj, aho = m
            st.markdown(f"#### {nom}")
            st.progress(min(aho/obj, 1.0))
            st.caption(f"S/. {aho:.2f} / S/. {obj:.2f}")
            if aho >= obj:
                st.markdown(f"""<div class="goal-complete">¡META COMPLETADA! 🎉</div>""", unsafe_allow_html=True)
            else:
                ci, cb = st.columns([2,1])
                abo = ci.number_input(f"Abonar {nom}", min_value=0.0, step=10.0, key=f"ab_{mid}")
                if cb.button("Abonar", key=f"btn_{mid}"):
                    if abo > 0 and saldo_db >= abo:
                        pts = int(abo * 0.25)
                        run_query("UPDATE metas SET ahorrado = ahorrado + ? WHERE id = ?", (abo, mid))
                        run_query("UPDATE usuarios SET saldo = saldo - ?, puntos = puntos + ? WHERE id = ?", (abo, pts, user_id))
                        st.toast(f"+{pts} pts"); time.sleep(1); st.rerun()
                    else: st.error("Saldo insuficiente")
            st.divider()

    with tab3:
        st.subheader("💡 Tips Inteligentes")
        with st.spinner('Analizando...'): time.sleep(0.3)
        for t in analizar_gastos_y_sugerir(user_id):
            st.markdown(f"""<div class="suggestion-card">{t}</div>""", unsafe_allow_html=True)

    with tab4:
        st.subheader("🎁 Canje de Premios")
        st.caption("0.5 pts por S/. 2.00")
        premios = [
            {"img": "https://cdn-icons-png.flaticon.com/512/3081/3081162.png", "nom": "Café Gratis", "costo": 50, "code": "CAFE-FREE"},
            {"img": "https://cdn-icons-png.flaticon.com/512/2809/2809590.png", "nom": "2x1 Cine", "costo": 150, "code": "CINE-X2"},
            {"img": "https://cdn-icons-png.flaticon.com/512/2232/2232688.png", "nom": "Libro -20%", "costo": 300, "code": "BOOK-20"},
            {"img": "https://cdn-icons-png.flaticon.com/512/3050/3050253.png", "nom": "Spotify 1 Mes", "costo": 600, "code": "SPOT-1M"},
        ]
        cols = st.columns(2)
        for idx, p in enumerate(premios):
            with cols[idx % 2]:
                st.markdown(f"""<div class="reward-card"><img src="{p['img']}" width="50"><div class="reward-title">{p['nom']}</div><div class="reward-price">{p['costo']} Pts</div></div>""", unsafe_allow_html=True)
                if st.button(f"Canjear", key=f"r_{idx}"):
                    if puntos_db >= p['costo']:
                        run_query("UPDATE usuarios SET puntos = puntos - ? WHERE id = ?", (p['costo'], user_id))
                        run_query("INSERT INTO premios_canjeados (usuario_id, premio, codigo, fecha) VALUES (?, ?, ?, ?)", (user_id, p['nom'], p['code'], datetime.date.today().strftime("%d/%m/%Y")))
                        st.balloons(); time.sleep(1.5); st.rerun()
                    else: st.error("Faltan puntos")
        
        st.divider()
        st.markdown("### 📜 Mis Códigos")
        mp = run_query("SELECT fecha, premio, codigo FROM premios_canjeados WHERE usuario_id = ? ORDER BY id DESC", (user_id,), return_data=True)
        if mp:
            for item in mp:
                st.caption(f"{item[0]} - {item[1]}")
                st.code(item[2], language="text")
        else: st.info("Sin canjes")

    with tab5:
        c1, c2 = st.columns([1,2])
        c1.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        c2.markdown(f"### {user_data[2]}")
        c2.caption(f"DNI: {user_data[3]} | Banco: {user_data[4]}")
        st.divider()
        st.metric("Rango", nivel_actual)
        st.progress(min(puntos_db/prox_nivel, 1.0))
        st.caption(f"XP: {puntos_db} / {prox_nivel}")

if st.session_state.logged_in: main_app()
else: login_register_screen()