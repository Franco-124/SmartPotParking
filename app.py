"""
Entrypoint Streamlit — SmartSpot Analytics v2.
Responsabilidad única: orquestar auth → leer → persistir → renderizar.

PATRÓN DE REFRESCO: st.rerun() en lugar de while True + st.empty().
Cada st.rerun() es una ejecución limpia: sin keys duplicados.
session_state persiste el usuario autenticado entre ejecuciones.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
from datetime import datetime

import pandas as pd
import plotly.express as px
import streamlit as st

from settings import (
    CELDA_A, CELDA_B, COLORES, HISTORICO_N,
    NOMBRES_CELDAS, REFRESH_INTERVAL, UMBRAL_OCUPACION,
)
from data.database import get_last_n_readings, get_occupation_stats, init_db, insert_reading
from data.source import get_reading
from data.auth import init_users_table, login_user, register_user


# ── Configuración de página ────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartSpot Analytics",
    page_icon="🅿️",
    layout="wide",
)


# ── CSS global — aumenta tamaño de letra base de toda la app ──────────────
st.html("""
<style>
  /* Fuente base de Streamlit */
  html, body, [class*="st-"], .stMarkdown, .stCaption,
  .stMetric, .stTabs, label, p, span, div {
    font-size: 18px !important;
  }
  /* Títulos y subheaders */
  h1 { font-size: 2.2rem !important; }
  h2 { font-size: 1.7rem !important; }
  h3 { font-size: 1.4rem !important; }
  /* Valores de st.metric */
  [data-testid="stMetricValue"] { font-size: 2rem !important; }
  [data-testid="stMetricLabel"] { font-size: 1rem !important; }
  /* Tabs */
  .stTabs [data-baseweb="tab"] { font-size: 1rem !important; }
  /* Inputs y botones */
  input, textarea, button, .stButton button {
    font-size: 1rem !important;
  }
  /* Sidebar */
  [data-testid="stSidebar"] * { font-size: 15px !important; }
</style>
""")

# ── Inicialización única de tablas ─────────────────────────────────────────
if "db_initialized" not in st.session_state:
    init_db()
    init_users_table()
    st.session_state["db_initialized"] = True


# ── Helpers ────────────────────────────────────────────────────────────────

def _fmt_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


def _render_card(nombre: str, distancia: float, ocupado: bool) -> str:
    """HTML de tarjeta de celda — renderizada con st.html() (Streamlit ≥ 1.36)."""
    if ocupado:
        led_color  = "#ff3333"
        led_glow   = "0 0 8px 3px rgba(255,51,51,0.9),0 0 22px 6px rgba(255,51,51,0.4)"
        overlay    = COLORES["ocupado_bg"]
        border     = COLORES["ocupado"]
        status_col = "#ff7979"
        status_txt = "🔴 OCUPADO"
        inner_html = (
            '<div style="font-size:88px;line-height:1;'
            'text-shadow:0 0 24px rgba(255,80,80,0.8);">🚗</div>'
        )
    else:
        led_color  = "#33ff77"
        led_glow   = "0 0 8px 3px rgba(51,255,119,0.9),0 0 22px 6px rgba(51,255,119,0.4)"
        overlay    = COLORES["libre_bg"]
        border     = COLORES["libre"]
        status_col = "#55efc4"
        status_txt = "🟢 LIBRE"
        inner_html = (
            '<div style="font-size:64px;opacity:0.10;margin-top:10px;">🅿</div>'
        )

    return f"""
<div style="width:230px;border-radius:14px;overflow:hidden;
    border:2px solid {border};box-shadow:0 8px 32px rgba(0,0,0,0.5);
    background:#12121e;font-family:'Courier New',monospace;">
  <div style="background:#0a0a14;padding:10px 14px;
      display:flex;justify-content:space-between;align-items:center;
      border-bottom:1px solid rgba(255,255,255,0.05);">
    <span style="color:#ddd;font-size:16px;font-weight:700;letter-spacing:3px;">
      {nombre.upper()}
    </span>
    <div style="width:16px;height:16px;border-radius:50%;
        background:{led_color};box-shadow:{led_glow};"></div>
  </div>
  <div style="height:190px;
      background:linear-gradient(180deg,#1c1c2e 0%,#14141f 100%);
      position:relative;display:flex;align-items:center;justify-content:center;
      border-left:3px solid rgba(255,255,255,0.18);
      border-right:3px solid rgba(255,255,255,0.18);overflow:hidden;">
    <div style="position:absolute;inset:0;background:{overlay};pointer-events:none;"></div>
    <div style="position:absolute;top:0;bottom:0;left:50%;transform:translateX(-50%);
        width:2px;background:repeating-linear-gradient(
          to bottom,rgba(255,255,255,0.15) 0,rgba(255,255,255,0.15) 10px,
          transparent 10px,transparent 22px);"></div>
    <div style="position:absolute;bottom:0;left:0;right:0;height:4px;
        background:rgba(255,255,255,0.22);"></div>
    <div style="position:relative;z-index:1;text-align:center;">{inner_html}</div>
  </div>
  <div style="background:#0a0a14;padding:10px 14px;text-align:center;
      border-top:1px solid rgba(255,255,255,0.05);">
    <div style="color:{status_col};font-size:16px;font-weight:700;letter-spacing:1px;">
      {status_txt}
    </div>
    <div style="color:#666;font-size:14px;margin-top:4px;">{distancia:.1f} cm</div>
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════════════════
# PÁGINA DE AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════

def _auth_page() -> None:
    """Renderiza la pantalla de login/registro y detiene el script si no hay sesión."""

    # CSS de fondo para la página de auth
    st.html("""
    <style>
      section[data-testid="stMain"] > div:first-child {
        background: linear-gradient(135deg, #07070f 0%, #0f0f1e 100%);
        min-height: 100vh;
      }
      div[data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #07070f 0%, #0f0f1e 100%);
      }
    </style>
    """)

    # Centrado horizontal con columnas
    _, col, _ = st.columns([1, 1.4, 1])

    with col:
        # Logo y título
        st.html("""
        <div style="text-align:center;padding:48px 0 28px;">
          <div style="font-size:56px;margin-bottom:12px;">🅿️</div>
          <h1 style="color:#f0f0f0;margin:0 0 6px;font-size:26px;
              font-family:'Courier New',monospace;letter-spacing:2px;">
            SmartSpot Analytics
          </h1>
          <p style="color:#555;font-size:13px;margin:0;">
            Sistema de monitoreo IoT · Parqueadero inteligente
          </p>
        </div>
        """)

        login_tab, reg_tab = st.tabs(["🔑  Iniciar sesión", "📝  Crear cuenta"])

        # ── Login ──────────────────────────────────────────────────────────
        with login_tab:
            with st.form("form_login", clear_on_submit=False):
                username = st.text_input("Usuario", placeholder="Tu nombre de usuario")
                password = st.text_input("Contraseña", type="password", placeholder="••••••")
                submitted = st.form_submit_button(
                    "Entrar al sistema", use_container_width=True, type="primary"
                )

            if submitted:
                if not username or not password:
                    st.error("Completa todos los campos.")
                else:
                    ok, msg = login_user(username, password)
                    if ok:
                        st.session_state["user"] = username.strip()
                        st.session_state["session_start"] = datetime.now().isoformat(
                            timespec="seconds"
                        )
                        st.rerun()
                    else:
                        st.error(msg)

        # ── Registro ───────────────────────────────────────────────────────
        with reg_tab:
            with st.form("form_register", clear_on_submit=True):
                new_user  = st.text_input("Usuario", placeholder="Mínimo 3 caracteres")
                new_email = st.text_input("Correo electrónico", placeholder="tu@correo.com")
                new_pass  = st.text_input(
                    "Contraseña", type="password", placeholder="Mínimo 6 caracteres"
                )
                confirm   = st.text_input(
                    "Confirmar contraseña", type="password", placeholder="Repite la contraseña"
                )
                submitted_r = st.form_submit_button(
                    "Crear cuenta", use_container_width=True, type="primary"
                )

            if submitted_r:
                if not all([new_user, new_email, new_pass, confirm]):
                    st.error("Completa todos los campos.")
                elif new_pass != confirm:
                    st.error("Las contraseñas no coinciden.")
                else:
                    ok, msg = register_user(new_user, new_email, new_pass)
                    if ok:
                        st.success(msg)
                        st.info("Ya puedes iniciar sesión en la pestaña anterior.")
                    else:
                        st.error(msg)

        st.html("""
        <p style="text-align:center;color:#333;font-size:11px;margin-top:32px;">
          SmartSpot Analytics · ESP32 + HC-SR04 · Datos en tiempo real
        </p>
        """)


# ── Gate de autenticación ──────────────────────────────────────────────────
# Si no hay sesión activa, mostrar auth y detener el script aquí.
# st.stop() impide que el resto del código (dashboard) se ejecute.
if "user" not in st.session_state:
    _auth_page()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════
# DASHBOARD (solo usuarios autenticados llegan aquí)
# ══════════════════════════════════════════════════════════════════════════

# ── Sidebar ────────────────────────────────────────────────────────────────
with st.sidebar:
    st.html(f"""
    <div style="text-align:center;padding:24px 0 16px;">
      <div style="font-size:40px;">🅿️</div>
      <div style="color:#f0f0f0;font-size:17px;font-weight:700;
          font-family:'Courier New',monospace;letter-spacing:2px;margin-top:8px;">
        SmartSpot
      </div>
      <div style="color:#555;font-size:11px;letter-spacing:1px;">ANALYTICS</div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:0 0 16px;">
    <div style="padding:0 4px 20px;">
      <div style="color:#555;font-size:10px;text-transform:uppercase;
          letter-spacing:1.5px;margin-bottom:6px;">Sesión activa</div>
      <div style="color:#55efc4;font-size:15px;font-weight:700;">
        👤 {st.session_state['user']}
      </div>
      <div style="color:#444;font-size:11px;margin-top:4px;">
        Desde: {st.session_state.get('session_start','—')}
      </div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:0 0 16px;">
    <div style="color:#555;font-size:10px;text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px;">Sistema</div>
    <div style="color:#888;font-size:12px;line-height:1.7;">
      🔌 Fuente: <span style="color:#f0a500;">Mock (ESP32 pendiente)</span><br>
      📡 Sensores: HC-SR04 × 2<br>
      ⏱ Refresco: {REFRESH_INTERVAL:.0f} s<br>
      🎯 Umbral: {UMBRAL_OCUPACION} cm
    </div>
    """)

    st.divider()

    if st.button("🚪 Cerrar sesión", use_container_width=True):
        # Limpia solo las claves de sesión del usuario; db_initialized persiste.
        for k in ["user", "session_start"]:
            st.session_state.pop(k, None)
        st.rerun()


# ── Garantizar session_start (por si el usuario llegó por rerun directo) ───
if "session_start" not in st.session_state:
    st.session_state["session_start"] = datetime.now().isoformat(timespec="seconds")


# ── Leer y persistir ───────────────────────────────────────────────────────
reading   = get_reading()
ts        = reading["timestamp"]
dist_a    = reading["puesto_a"]
dist_b    = reading["puesto_b"]
ocupado_a = dist_a <= UMBRAL_OCUPACION
ocupado_b = dist_b <= UMBRAL_OCUPACION

insert_reading(CELDA_A, dist_a, ts)
insert_reading(CELDA_B, dist_b, ts)


# ── Header del dashboard ───────────────────────────────────────────────────
st.title("🅿️ SmartSpot Analytics")
st.caption(
    "Sistema de monitoreo IoT en tiempo real · "
    "Datos simulados (mock) · Actualización cada 1 s"
)
st.divider()

tab1, tab2 = st.tabs(["🅿️ Monitor en Vivo", "📊 Analítica de Ocupación"])


# ── Tab 1 · Monitor en Vivo ────────────────────────────────────────────────
with tab1:
    st.subheader("🚦 Estado de las Celdas")
    st.html(
        f"""
        <div style="display:flex;gap:48px;justify-content:center;padding:20px 0 28px;">
          {_render_card(CELDA_A, dist_a, ocupado_a)}
          {_render_card(CELDA_B, dist_b, ocupado_b)}
        </div>
        """
    )

    st.divider()
    st.subheader("📏 Métricas en Tiempo Real")
    col_a, col_b = st.columns(2)
    with col_a:
        st.metric(label=f"{CELDA_A} — distancia", value=f"{dist_a} cm")
        st.caption(f"Timestamp: `{ts}`")
    with col_b:
        st.metric(label=f"{CELDA_B} — distancia", value=f"{dist_b} cm")
        st.caption(f"Timestamp: `{ts}`")


# ── Tab 2 · Analítica de Ocupación ────────────────────────────────────────
with tab2:

    stats = get_occupation_stats(since=st.session_state["session_start"])
    for nombre in NOMBRES_CELDAS:
        stats.setdefault(nombre, {"ocupado": 0, "libre": 0})

    # KPIs
    st.subheader("⏱ KPIs — Sesión Actual")
    k1, k2, k3, k4 = st.columns(4)
    s_a = stats[CELDA_A]
    s_b = stats[CELDA_B]
    k1.metric(f"🔴 {CELDA_A} — Ocupado", _fmt_time(s_a["ocupado"]))
    k2.metric(f"🟢 {CELDA_A} — Libre",   _fmt_time(s_a["libre"]))
    k3.metric(f"🔴 {CELDA_B} — Ocupado", _fmt_time(s_b["ocupado"]))
    k4.metric(f"🟢 {CELDA_B} — Libre",   _fmt_time(s_b["libre"]))

    # Serie de tiempo
    rows = get_last_n_readings(HISTORICO_N)
    if rows:
        df = pd.DataFrame(rows, columns=["Puesto", "Distancia (cm)", "Timestamp"])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])

        fig_ts = px.line(
            df, x="Timestamp", y="Distancia (cm)", color="Puesto",
            markers=True,
            title=f"Últimas {HISTORICO_N} lecturas por celda",
            color_discrete_map={CELDA_A: "#3498db", CELDA_B: "#e67e22"},
        )
        fig_ts.add_hline(
            y=UMBRAL_OCUPACION, line_dash="dash", line_color="red",
            annotation_text=f"Umbral ocupación ({UMBRAL_OCUPACION} cm)",
            annotation_position="top left",
        )
        fig_ts.update_layout(
            xaxis_title="Tiempo", yaxis_title="Distancia (cm)",
            legend_title="Celda", height=380,
        )
        st.subheader("📈 Serie de Tiempo de Distancias")
        st.plotly_chart(fig_ts, use_container_width=True, key="chart_ts")

    # Distribución
    dist_data = []
    for nombre in NOMBRES_CELDAS:
        s     = stats[nombre]
        total = s["ocupado"] + s["libre"]
        if total > 0:
            dist_data.append({"Puesto": nombre, "Estado": "OCUPADO",
                               "Porcentaje": round(s["ocupado"] / total * 100, 1)})
            dist_data.append({"Puesto": nombre, "Estado": "LIBRE",
                               "Porcentaje": round(s["libre"]   / total * 100, 1)})

    if dist_data:
        df_dist  = pd.DataFrame(dist_data)
        fig_dist = px.bar(
            df_dist, x="Porcentaje", y="Puesto", color="Estado",
            orientation="h", barmode="stack",
            title="Distribución OCUPADO / LIBRE — sesión actual",
            color_discrete_map={"OCUPADO": COLORES["ocupado"], "LIBRE": COLORES["libre"]},
            text="Porcentaje",
        )
        fig_dist.update_traces(texttemplate="%{text:.1f}%", textposition="inside")
        fig_dist.update_layout(
            xaxis_title="Porcentaje (%)", yaxis_title="", height=220, legend_title="Estado",
        )
        st.subheader("📊 Distribución de Estados")
        st.plotly_chart(fig_dist, use_container_width=True, key="chart_dist")


# ── Refresco automático ────────────────────────────────────────────────────
time.sleep(REFRESH_INTERVAL)
st.rerun()
