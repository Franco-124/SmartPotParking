"""
Entrypoint Streamlit — SmartSpot Analytics v2.
Orquesta: auth → leer (serial COM11) → persistir → renderizar.
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
    CELDA_A, CELDA_B, CELDA_C, CELDA_D,
    CO_MAX_RAW, CO_UMBRAL_MODERADO, CO_UMBRAL_NORMAL,
    COLORES, HISTORICO_N, NOMBRES_CELDAS,
    REFRESH_INTERVAL, UMBRAL_OCUPACION,
)
from data.database import (
    get_last_co_readings, get_last_n_readings,
    get_occupation_stats, init_db,
    insert_co_reading, insert_reading,
)
from data.source import get_reading, get_source
from data.auth import init_users_table, login_user, register_user


# ── Configuración de página ────────────────────────────────────────────────
st.set_page_config(
    page_title="SmartSpot Analytics",
    page_icon="🅿️",
    layout="wide",
)

st.html("""
<style>
  html, body, [class*="st-"], .stMarkdown, .stCaption,
  .stMetric, .stTabs, label, p, span, div {
    font-size: 18px !important;
  }
  h1 { font-size: 2.2rem !important; }
  h2 { font-size: 1.7rem !important; }
  h3 { font-size: 1.4rem !important; }
  [data-testid="stMetricValue"] { font-size: 2rem !important; }
  [data-testid="stMetricLabel"] { font-size: 1rem !important; }
  .stTabs [data-baseweb="tab"]  { font-size: 1rem !important; }
  input, textarea, button, .stButton button { font-size: 1rem !important; }
  [data-testid="stSidebar"] * { font-size: 15px !important; }
</style>
""")

if "db_initialized" not in st.session_state:
    init_db()
    init_users_table()
    st.session_state["db_initialized"] = True


# ══════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════

def _fmt_time(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s"


def _render_parking_card(nombre: str, distancia: float, ocupado: bool, tiempo: str) -> str:
    if ocupado:
        led_color  = "#ff3333"
        led_glow   = "0 0 8px 3px rgba(255,51,51,0.9),0 0 22px 6px rgba(255,51,51,0.4)"
        overlay    = COLORES["ocupado_bg"]
        border     = COLORES["ocupado"]
        status_col = "#ff7979"
        status_txt = "🔴 OCUPADO"
        inner      = ('<div style="font-size:88px;line-height:1;'
                      'text-shadow:0 0 24px rgba(255,80,80,0.8);">🚗</div>')
    else:
        led_color  = "#33ff77"
        led_glow   = "0 0 8px 3px rgba(51,255,119,0.9),0 0 22px 6px rgba(51,255,119,0.4)"
        overlay    = COLORES["libre_bg"]
        border     = COLORES["libre"]
        status_col = "#55efc4"
        status_txt = "🟢 LIBRE"
        inner      = '<div style="font-size:64px;opacity:0.10;margin-top:10px;">🅿</div>'

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
    <div style="position:relative;z-index:1;text-align:center;">{inner}</div>
  </div>
  <div style="background:#0a0a14;padding:10px 14px;text-align:center;
      border-top:1px solid rgba(255,255,255,0.05);">
    <div style="color:{status_col};font-size:16px;font-weight:700;letter-spacing:1px;">
      {status_txt}
    </div>
    <div style="color:#666;font-size:13px;margin-top:3px;">{distancia:.1f} cm</div>
    <div style="color:#444;font-size:11px;margin-top:2px;">hace {tiempo}</div>
  </div>
</div>"""


def _render_co_card(co_raw: int, tendencia: str) -> str:
    pct = min(100, round(co_raw / CO_MAX_RAW * 100, 1))

    if co_raw < CO_UMBRAL_NORMAL:
        status_txt = "🟢 NORMAL"
        bar_color  = "#27ae60"
        status_col = "#55efc4"
        border     = "#27ae60"
        led_glow   = "0 0 8px 3px rgba(39,174,96,0.9),0 0 20px 6px rgba(39,174,96,0.4)"
        led_color  = "#33ff77"
        desc       = "Calidad del aire óptima"
    elif co_raw < CO_UMBRAL_MODERADO:
        status_txt = "🟡 MODERADO"
        bar_color  = "#f39c12"
        status_col = "#f9ca24"
        border     = "#f39c12"
        led_glow   = "0 0 8px 3px rgba(243,156,18,0.9),0 0 20px 6px rgba(243,156,18,0.4)"
        led_color  = "#f9ca24"
        desc       = "Nivel de CO en rango moderado"
    else:
        status_txt = "🔴 ALERTA"
        bar_color  = "#c0392b"
        status_col = "#ff7979"
        border     = "#c0392b"
        led_glow   = "0 0 8px 3px rgba(255,51,51,0.9),0 0 20px 6px rgba(255,51,51,0.4)"
        led_color  = "#ff3333"
        desc       = "Nivel de CO elevado — ventilar"

    tendencia_col = "#ff7979" if tendencia == "↑" else ("#55efc4" if tendencia == "↓" else "#888")

    return f"""
<div style="width:540px;border-radius:14px;overflow:hidden;
    border:2px solid {border};box-shadow:0 8px 32px rgba(0,0,0,0.5);
    background:#12121e;font-family:'Courier New',monospace;">
  <div style="background:#0a0a14;padding:10px 18px;
      display:flex;justify-content:space-between;align-items:center;
      border-bottom:1px solid rgba(255,255,255,0.05);">
    <span style="color:#ddd;font-size:14px;font-weight:700;letter-spacing:2px;">
      💨 CALIDAD DEL AIRE — MQ7
    </span>
    <div style="display:flex;align-items:center;gap:10px;">
      <span style="color:{tendencia_col};font-size:18px;font-weight:700;">{tendencia}</span>
      <div style="width:16px;height:16px;border-radius:50%;
          background:{led_color};box-shadow:{led_glow};"></div>
    </div>
  </div>
  <div style="padding:18px 24px;display:flex;align-items:center;gap:28px;">
    <div style="text-align:center;min-width:100px;">
      <div style="font-size:52px;font-weight:700;color:{status_col};line-height:1;">
        {co_raw}
      </div>
      <div style="color:#555;font-size:11px;margin-top:4px;letter-spacing:1px;">ADC RAW</div>
    </div>
    <div style="flex:1;">
      <div style="display:flex;justify-content:space-between;
          margin-bottom:8px;align-items:center;">
        <span style="color:{status_col};font-size:16px;font-weight:700;">{status_txt}</span>
        <span style="color:#555;font-size:12px;">{pct:.1f}%</span>
      </div>
      <div style="background:#1e1e2e;border-radius:8px;height:14px;
          overflow:hidden;border:1px solid rgba(255,255,255,0.06);">
        <div style="width:{pct}%;height:100%;border-radius:8px;
            background:linear-gradient(90deg,{bar_color}99,{bar_color});
            transition:width 0.4s ease;"></div>
      </div>
      <div style="display:flex;justify-content:space-between;
          margin-top:5px;color:#444;font-size:10px;">
        <span>0</span>
        <span style="color:#27ae60;">▲{CO_UMBRAL_NORMAL} Normal</span>
        <span style="color:#f39c12;">▲{CO_UMBRAL_MODERADO} Alerta</span>
        <span>{CO_MAX_RAW}</span>
      </div>
      <div style="color:#666;font-size:12px;margin-top:8px;">{desc}</div>
    </div>
  </div>
</div>"""


def _render_occupancy_banner(n_ocupados: int, total: int = 4) -> str:
    n_libres = total - n_ocupados
    pct_ocupado = round(n_ocupados / total * 100)
    if pct_ocupado == 0:
        color = "#27ae60"; bg = "rgba(39,174,96,0.12)"; border = "#27ae60"
        icono = "🟢"
    elif pct_ocupado <= 50:
        color = "#27ae60"; bg = "rgba(39,174,96,0.12)"; border = "#27ae60"
        icono = "🟡"
    elif pct_ocupado < 100:
        color = "#f39c12"; bg = "rgba(243,156,18,0.12)"; border = "#f39c12"
        icono = "🟡"
    else:
        color = "#c0392b"; bg = "rgba(192,57,43,0.18)"; border = "#c0392b"
        icono = "🔴"

    bloques = "".join(
        f'<div style="width:36px;height:36px;border-radius:6px;'
        f'background:{"#c0392b" if i < n_ocupados else "#27ae60"};'
        f'box-shadow:0 0 8px {"rgba(192,57,43,0.6)" if i < n_ocupados else "rgba(39,174,96,0.6)"};">'
        f'</div>'
        for i in range(total)
    )

    return f"""
<div style="border-radius:14px;border:2px solid {border};background:{bg};
    padding:20px 32px;display:flex;align-items:center;justify-content:space-between;
    font-family:'Courier New',monospace;margin-bottom:8px;">
  <div>
    <div style="color:#aaa;font-size:11px;letter-spacing:2px;text-transform:uppercase;
        margin-bottom:4px;">Ocupación del parqueadero</div>
    <div style="color:{color};font-size:36px;font-weight:700;line-height:1;">
      {icono} {n_ocupados} / {total}
      <span style="font-size:16px;color:#888;margin-left:12px;">·  {n_libres} libre{"s" if n_libres != 1 else ""}</span>
    </div>
  </div>
  <div>
    <div style="color:#aaa;font-size:11px;letter-spacing:2px;text-transform:uppercase;
        margin-bottom:8px;text-align:right;">{pct_ocupado}% ocupado</div>
    <div style="display:flex;gap:8px;">{bloques}</div>
  </div>
</div>"""


# ══════════════════════════════════════════════════════════════════════════
# PÁGINA DE AUTENTICACIÓN
# ══════════════════════════════════════════════════════════════════════════

def _auth_page() -> None:
    st.html("""
    <style>
      div[data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #07070f 0%, #0f0f1e 100%);
      }
    </style>
    """)

    _, col, _ = st.columns([1, 1.4, 1])
    with col:
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

        with login_tab:
            with st.form("form_login", clear_on_submit=False):
                username  = st.text_input("Usuario", placeholder="Tu nombre de usuario")
                password  = st.text_input("Contraseña", type="password", placeholder="••••••")
                submitted = st.form_submit_button(
                    "Entrar al sistema", use_container_width=True, type="primary"
                )
            if submitted:
                if not username or not password:
                    st.error("Completa todos los campos.")
                else:
                    ok, msg, role = login_user(username, password)
                    if ok:
                        st.session_state["user"] = username.strip()
                        st.session_state["role"] = role
                        st.session_state["session_start"] = datetime.now().isoformat(
                            timespec="seconds"
                        )
                        st.rerun()
                    else:
                        st.error(msg)

        with reg_tab:
            with st.form("form_register", clear_on_submit=True):
                new_user  = st.text_input("Usuario", placeholder="Mínimo 3 caracteres")
                new_email = st.text_input("Correo electrónico", placeholder="tu@correo.com")
                new_pass  = st.text_input("Contraseña", type="password",
                                          placeholder="Mínimo 6 caracteres")
                confirm   = st.text_input("Confirmar contraseña", type="password",
                                          placeholder="Repite la contraseña")
                new_role  = st.selectbox(
                    "Tipo de cuenta",
                    options=["user", "admin"],
                    format_func=lambda r: "👤 Usuario — solo vista de ocupación y CO"
                                          if r == "user"
                                          else "🔑 Administrador — acceso completo",
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
                    ok, msg = register_user(new_user, new_email, new_pass, new_role)
                    if ok:
                        st.success(msg)
                        st.info("Ya puedes iniciar sesión en la pestaña anterior.")
                    else:
                        st.error(msg)

        st.html("""
        <p style="text-align:center;color:#333;font-size:11px;margin-top:32px;">
          SmartSpot Analytics · ESP32 + HC-SR04 + MQ7
        </p>""")


# ── Gate de autenticación ──────────────────────────────────────────────────
if "user" not in st.session_state:
    _auth_page()
    st.stop()


# ══════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════════════════

if "session_start" not in st.session_state:
    st.session_state["session_start"] = datetime.now().isoformat(timespec="seconds")

_role     = st.session_state.get("role", "user")
_is_admin = _role == "admin"

# ── Cerrar sesión — ANTES de get_reading() para que el click no se bloquee ─
if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True, key="logout"):
    for k in ["user", "role", "session_start", "estado_actual",
              "estado_desde", "entradas", "salidas"]:
        st.session_state.pop(k, None)
    st.rerun()

# ── Leer y persistir ───────────────────────────────────────────────────────
reading = get_reading()
if reading is None:
    # Sin dato válido en este ciclo — reintenta en 0.5 s sin bloquear la UI
    time.sleep(0.5)
    st.rerun()

_ahora = datetime.now()
ts     = reading["timestamp"]
dist_a = reading["puesto_a"]
dist_b = reading["puesto_b"]
dist_c = reading["puesto_c"]
dist_d = reading["puesto_d"]
co_raw = reading["co_raw"]
ocupado_a = dist_a <= UMBRAL_OCUPACION
ocupado_b = dist_b <= UMBRAL_OCUPACION
ocupado_c = dist_c <= UMBRAL_OCUPACION
ocupado_d = dist_d <= UMBRAL_OCUPACION

insert_reading(CELDA_A, dist_a, ts)
insert_reading(CELDA_B, dist_b, ts)
insert_reading(CELDA_C, dist_c, ts)
insert_reading(CELDA_D, dist_d, ts)
insert_co_reading(co_raw, ts)

# ── Tracking de estados y rotación ────────────────────────────────────────
_estado_actual = {
    CELDA_A: ocupado_a, CELDA_B: ocupado_b,
    CELDA_C: ocupado_c, CELDA_D: ocupado_d,
}

if "estado_actual" not in st.session_state:
    st.session_state["estado_actual"] = dict(_estado_actual)
    st.session_state["estado_desde"]  = {k: _ahora for k in _estado_actual}
    st.session_state["entradas"]      = {k: 0 for k in _estado_actual}
    st.session_state["salidas"]       = {k: 0 for k in _estado_actual}

for celda, ocupado in _estado_actual.items():
    if ocupado != st.session_state["estado_actual"][celda]:
        st.session_state["estado_actual"][celda] = ocupado
        st.session_state["estado_desde"][celda]  = _ahora
        if ocupado:
            st.session_state["entradas"][celda] += 1
        else:
            st.session_state["salidas"][celda]  += 1


def _tiempo_en_estado(celda: str) -> str:
    delta = _ahora - st.session_state["estado_desde"][celda]
    return _fmt_time(int(delta.total_seconds()))


# ── Tendencia CO ───────────────────────────────────────────────────────────
_co_rows = get_last_co_readings(20)
if len(_co_rows) >= 6:
    mid     = len(_co_rows) // 2
    avg_old = sum(r[0] for r in _co_rows[:mid]) / mid
    avg_new = sum(r[0] for r in _co_rows[mid:]) / (len(_co_rows) - mid)
    _co_tendencia = "↑" if avg_new > avg_old * 1.05 else ("↓" if avg_new < avg_old * 0.95 else "→")
else:
    _co_tendencia = "—"

# ── Tiempo acumulado en alerta CO (sesión) ─────────────────────────────────
_since = st.session_state["session_start"]
_co_alerta_s = sum(
    1 for r in get_last_co_readings(HISTORICO_N)
    if r[0] >= CO_UMBRAL_MODERADO and r[1] >= _since
)

# ── Sidebar ────────────────────────────────────────────────────────────────
n_ocupados = sum([ocupado_a, ocupado_b, ocupado_c, ocupado_d])

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
        {"🔑" if _is_admin else "👤"} {st.session_state['user']}
      </div>
      <div style="color:#888;font-size:11px;margin-top:3px;background:{"rgba(255,215,0,0.08)" if _is_admin else "rgba(255,255,255,0.04)"};
          padding:3px 8px;border-radius:6px;display:inline-block;">
        {"Administrador" if _is_admin else "Usuario"}
      </div>
      <div style="color:#444;font-size:11px;margin-top:6px;">
        Desde: {st.session_state.get('session_start','—')}
      </div>
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:0 0 16px;">
    <div style="color:#555;font-size:10px;text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px;">Sistema</div>
    <div style="color:#888;font-size:12px;line-height:1.9;">
      {"<span style='color:#f0a500;'>🎭 DEMO — datos simulados</span>" if get_source() == "demo" else "<span style='color:#55efc4;'>🔌 ESP32 — Puerto Serie</span>"}<br>
      📡 Distancia: HC-SR04 × 4<br>
      💨 Aire: MQ7 (CO)<br>
      ⏱ Refresco: {REFRESH_INTERVAL:.0f} s<br>
      🎯 Umbral parqueo: {UMBRAL_OCUPACION} cm
    </div>
    <hr style="border:none;border-top:1px solid rgba(255,255,255,0.08);margin:16px 0;">
    <div style="color:#555;font-size:10px;text-transform:uppercase;
        letter-spacing:1.5px;margin-bottom:8px;">Ahora mismo</div>
    <div style="color:#888;font-size:13px;line-height:2;">
      🚗 Ocupados: <b style="color:#ff7979;">{n_ocupados}/4</b><br>
      🟢 Libres: <b style="color:#55efc4;">{4 - n_ocupados}/4</b><br>
      💨 CO: <b style="color:#f9ca24;">{co_raw} ADC</b>
    </div>
    """)

    st.divider()


# ── Header ─────────────────────────────────────────────────────────────────
st.title("🅿️ SmartSpot Analytics")
st.caption("Sistema de monitoreo IoT en tiempo real · ESP32 + HC-SR04 × 4 + MQ7")
st.divider()

_tabs = (["🅿️ Monitor en Vivo", "📊 Analítica de Ocupación"]
         if _is_admin else ["🅿️ Monitor en Vivo"])
_tab_objects = st.tabs(_tabs)
tab1 = _tab_objects[0]
tab2 = _tab_objects[1] if _is_admin else None


# ══════════════════════════════════════════════════════════════════════════
# TAB 1 — MONITOR EN VIVO
# ══════════════════════════════════════════════════════════════════════════
with tab1:

    # Banner de ocupación global
    st.html(_render_occupancy_banner(n_ocupados))

    st.divider()

    # Celdas 2 × 2 — ahora con tiempo en estado actual
    st.subheader("🚦 Estado de las Celdas")
    st.html(f"""
    <div style="display:flex;flex-direction:column;gap:24px;
                align-items:center;padding:20px 0 10px;">
      <div style="display:flex;gap:40px;justify-content:center;">
        {_render_parking_card(CELDA_A, dist_a, ocupado_a, _tiempo_en_estado(CELDA_A))}
        {_render_parking_card(CELDA_B, dist_b, ocupado_b, _tiempo_en_estado(CELDA_B))}
      </div>
      <div style="display:flex;gap:40px;justify-content:center;">
        {_render_parking_card(CELDA_C, dist_c, ocupado_c, _tiempo_en_estado(CELDA_C))}
        {_render_parking_card(CELDA_D, dist_d, ocupado_d, _tiempo_en_estado(CELDA_D))}
      </div>
    </div>
    """)

    st.divider()

    # Sensor CO con tendencia
    st.subheader("💨 Calidad del Aire — CO (MQ7)")
    st.html(f"""
    <div style="display:flex;justify-content:center;padding:8px 0 20px;">
      {_render_co_card(co_raw, _co_tendencia)}
    </div>
    """)

    if _is_admin:
        st.divider()
        st.subheader("📏 Métricas en Tiempo Real")
        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            st.metric(f"{CELDA_A}", f"{dist_a} cm",
                      delta=f"{'OCUPADO' if ocupado_a else 'LIBRE'}")
            st.caption(f"Estado hace: `{_tiempo_en_estado(CELDA_A)}`")
        with col_b:
            st.metric(f"{CELDA_B}", f"{dist_b} cm",
                      delta=f"{'OCUPADO' if ocupado_b else 'LIBRE'}")
            st.caption(f"Estado hace: `{_tiempo_en_estado(CELDA_B)}`")
        with col_c:
            st.metric(f"{CELDA_C}", f"{dist_c} cm",
                      delta=f"{'OCUPADO' if ocupado_c else 'LIBRE'}")
            st.caption(f"Estado hace: `{_tiempo_en_estado(CELDA_C)}`")
        with col_d:
            st.metric(f"{CELDA_D}", f"{dist_d} cm",
                      delta=f"{'OCUPADO' if ocupado_d else 'LIBRE'}")
            st.caption(f"Estado hace: `{_tiempo_en_estado(CELDA_D)}`")


# ══════════════════════════════════════════════════════════════════════════
# TAB 2 — ANALÍTICA (solo admin)
# ══════════════════════════════════════════════════════════════════════════
if not tab2:
    time.sleep(0.1)
    st.rerun()

with tab2:

    stats = get_occupation_stats(since=st.session_state["session_start"])
    for nombre in NOMBRES_CELDAS:
        stats.setdefault(nombre, {"ocupado": 0, "libre": 0})

    s_a = stats[CELDA_A]; s_b = stats[CELDA_B]
    s_c = stats[CELDA_C]; s_d = stats[CELDA_D]

    # ── Fila 1: Tiempo OCUPADO ─────────────────────────────────────────────
    st.subheader("⏱ KPIs — Sesión Actual")
    ka1, ka2, ka3, ka4 = st.columns(4)
    ka1.metric(f"🔴 {CELDA_A} — Ocupado", _fmt_time(s_a["ocupado"]))
    ka2.metric(f"🔴 {CELDA_B} — Ocupado", _fmt_time(s_b["ocupado"]))
    ka3.metric(f"🔴 {CELDA_C} — Ocupado", _fmt_time(s_c["ocupado"]))
    ka4.metric(f"🔴 {CELDA_D} — Ocupado", _fmt_time(s_d["ocupado"]))

    # ── Fila 2: Tiempo LIBRE ───────────────────────────────────────────────
    kb1, kb2, kb3, kb4 = st.columns(4)
    kb1.metric(f"🟢 {CELDA_A} — Libre", _fmt_time(s_a["libre"]))
    kb2.metric(f"🟢 {CELDA_B} — Libre", _fmt_time(s_b["libre"]))
    kb3.metric(f"🟢 {CELDA_C} — Libre", _fmt_time(s_c["libre"]))
    kb4.metric(f"🟢 {CELDA_D} — Libre", _fmt_time(s_d["libre"]))

    # ── Fila 3: Rotación (entradas / salidas) ──────────────────────────────
    st.divider()
    st.subheader("🔄 Rotación — Entradas y Salidas")
    kc1, kc2, kc3, kc4 = st.columns(4)
    for col, celda in zip([kc1, kc2, kc3, kc4], NOMBRES_CELDAS):
        e = st.session_state["entradas"][celda]
        s = st.session_state["salidas"][celda]
        col.metric(f"🚗 {celda}", f"{e} entrada{'s' if e != 1 else ''}",
                   delta=f"{s} salida{'s' if s != 1 else ''}", delta_color="off")

    # ── Fila 4: CO resumen ─────────────────────────────────────────────────
    st.divider()
    st.subheader("💨 Resumen CO — Sesión")
    co_m1, co_m2, co_m3 = st.columns(3)
    co_m1.metric("Lectura actual", f"{co_raw} ADC")
    co_m2.metric("Tendencia", _co_tendencia)
    co_m3.metric("Tiempo en alerta", _fmt_time(_co_alerta_s))

    st.divider()

    # ── Gráfico serie de tiempo — distancias ───────────────────────────────
    rows = get_last_n_readings(HISTORICO_N)
    if rows:
        df = pd.DataFrame(rows, columns=["Puesto", "Distancia (cm)", "Timestamp"])
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        fig_ts = px.line(
            df, x="Timestamp", y="Distancia (cm)", color="Puesto",
            markers=True,
            title=f"Distancias — últimas {HISTORICO_N} lecturas por celda",
            color_discrete_map={
                CELDA_A: "#3498db", CELDA_B: "#e67e22",
                CELDA_C: "#9b59b6", CELDA_D: "#1abc9c",
            },
        )
        fig_ts.add_hline(
            y=UMBRAL_OCUPACION, line_dash="dash", line_color="red",
            annotation_text=f"Umbral ({UMBRAL_OCUPACION} cm)",
            annotation_position="top left",
        )
        fig_ts.update_layout(
            xaxis_title="Tiempo", yaxis_title="Distancia (cm)",
            legend_title="Celda", height=380,
        )
        st.subheader("📈 Serie de Tiempo — Distancias")
        st.plotly_chart(fig_ts, use_container_width=True, key="chart_ts")

    # ── Gráfico serie de tiempo — CO ───────────────────────────────────────
    if _co_rows:
        df_co = pd.DataFrame(_co_rows, columns=["CO (ADC)", "Timestamp"])
        df_co["Timestamp"] = pd.to_datetime(df_co["Timestamp"])
        fig_co = px.line(
            df_co, x="Timestamp", y="CO (ADC)",
            title=f"Calidad del Aire (MQ7) — últimas {len(_co_rows)} lecturas  |  tendencia {_co_tendencia}",
            color_discrete_sequence=["#f39c12"],
            markers=True,
        )
        fig_co.add_hline(
            y=CO_UMBRAL_NORMAL, line_dash="dot", line_color="#27ae60",
            annotation_text="Normal", annotation_position="top left",
        )
        fig_co.add_hline(
            y=CO_UMBRAL_MODERADO, line_dash="dot", line_color="#c0392b",
            annotation_text="Alerta", annotation_position="top left",
        )
        fig_co.update_layout(xaxis_title="Tiempo", yaxis_title="CO (ADC raw)", height=320)
        st.subheader("💨 Serie de Tiempo — CO (MQ7)")
        st.plotly_chart(fig_co, use_container_width=True, key="chart_co")

    # ── Distribución OCUPADO / LIBRE ───────────────────────────────────────
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
            xaxis_title="Porcentaje (%)", yaxis_title="", height=250, legend_title="Estado",
        )
        st.subheader("📊 Distribución de Estados")
        st.plotly_chart(fig_dist, use_container_width=True, key="chart_dist")


# ── Refresco automático ────────────────────────────────────────────────────
time.sleep(0.1)   # ventana mínima para que Streamlit procese clicks
st.rerun()

