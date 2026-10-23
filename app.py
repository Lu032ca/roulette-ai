
import sqlite3
from pathlib import Path
from datetime import datetime
from collections import Counter

import streamlit as st

DB_PATH = Path(__file__).with_name("roulette.db")

st.set_page_config(
    page_title="Roulette AI",
    page_icon="🎯",
    layout="wide"
)

st.markdown("""
<style>
.stApp {
    background: #101510;
    color: #f3ead5;
}
h1, h2, h3 {
    color: #d8b66a !important;
}
div.stButton > button {
    border: 1px solid #b99a52;
    border-radius: 10px;
}
</style>
""", unsafe_allow_html=True)


def connect():
    con = sqlite3.connect(DB_PATH)
    con.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS spins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id INTEGER NOT NULL,
            number INTEGER NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY(session_id) REFERENCES sessions(id)
        )
    """)
    con.commit()
    return con


def get_sessions(con):
    return con.execute(
        "SELECT id, name, created_at FROM sessions ORDER BY id DESC"
    ).fetchall()


def color(number):
    reds = {
        1, 3, 5, 7, 9, 12, 14, 16, 18,
        19, 21, 23, 25, 27, 30, 32, 34, 36
    }
    if number == 0:
        return "Verde"
    return "Rosso" if number in reds else "Nero"


st.title("🎯 ROULETTE AI")
st.caption("ROULETTE EUROPEA · ANALISI STATISTICA")

con = connect()
sessions = get_sessions(con)

with st.expander("➕ Crea una nuova sessione", expanded=not sessions):
    with st.form("new_session"):
        session_name = st.text_input(
            "Nome della sessione",
            value=f"Sessione {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        create = st.form_submit_button("Crea sessione")

        if create:
            if session_name.strip():
                con.execute(
                    "INSERT INTO sessions (name, created_at) VALUES (?, ?)",
                    (session_name.strip(), datetime.now().isoformat(timespec="seconds"))
                )
                con.commit()
                st.rerun()
            else:
                st.warning("Inserisci un nome.")

sessions = get_sessions(con)

if not sessions:
    st.info("Crea la tua prima sessione per iniziare.")
    con.close()
    st.stop()

labels = {
    f"{name} — {created}": sid
    for sid, name, created in sessions
}

selected_label = st.selectbox(
    "Sessione attiva",
    list(labels.keys())
)
session_id = labels[selected_label]

st.divider()
st.subheader("Inserisci il numero uscito")

with st.form("add_spin", clear_on_submit=True):
    number = st.number_input(
        "Numero della roulette (0–36)",
        min_value=0,
        max_value=36,
        value=0,
        step=1
    )
    add = st.form_submit_button("REGISTRA NUMERO")

    if add:
        con.execute(
            "INSERT INTO spins (session_id, number, created_at) VALUES (?, ?, ?)",
            (
                session_id,
                int(number),
                datetime.now().isoformat(timespec="seconds")
            )
        )
        con.commit()
        st.rerun()

rows = con.execute(
    "SELECT number, created_at FROM spins "
    "WHERE session_id = ? ORDER BY id ASC",
    (session_id,)
).fetchall()

numbers = [row[0] for row in rows]
total = len(numbers)

st.divider()
st.subheader("📊 Analisi della sessione")

a, b, c = st.columns(3)
a.metric("Giri registrati", total)
b.metric("Rossi", sum(color(n) == "Rosso" for n in numbers))
c.metric("Neri", sum(color(n) == "Nero" for n in numbers))

st.markdown("### Probabilità teoriche per il prossimo giro")
x, y, z = st.columns(3)
x.metric("Rosso", "48,65%")
y.metric("Nero", "48,65%")
z.metric("Zero", "2,70%")

st.caption(
    "Su una roulette europea regolare, i risultati precedenti "
    "non cambiano le probabilità del prossimo giro."
)

if numbers:
    st.markdown("### Frequenze dei numeri")
    counts = Counter(numbers)
    st.bar_chart({
        "Uscite": {
            str(n): counts[n] for n in range(37)
        }
    })

    st.markdown("### Ultimi risultati")
    st.write(" → ".join(map(str, numbers[-20:][::-1])))

    st.markdown("### Dettaglio storico")
    st.dataframe(
        [
            {
                "Numero": n,
                "Colore": color(n),
                "Data e ora": timestamp
            }
            for n, timestamp in reversed(rows[-100:])
        ],
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("Registra il primo numero per vedere le statistiche.")

st.divider()
st.subheader("📚 Tutte le sessioni")

for sid, name, created in sessions:
    count = con.execute(
        "SELECT COUNT(*) FROM spins WHERE session_id = ?",
        (sid,)
    ).fetchone()[0]
    st.write(f"**{name}** · {count} giri · {created}")

con.close()

st.caption(
    "Versione iniziale: analisi descrittiva, non previsione dei risultati."
)
