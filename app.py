
from datetime import datetime
from collections import Counter

import streamlit as st
from supabase import create_client

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

# Accesso protetto da password
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🎯 ROULETTE AI")
    st.subheader("Accesso")
    with st.form("login"):
        password = st.text_input("Password", type="password")
        login = st.form_submit_button("Entra")

        if login:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password non corretta.")
    st.stop()

# Collegamento al database Supabase
try:
    db = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )
except Exception:
    st.error("Errore di configurazione del database. Controlla i Secrets.")
    st.stop()


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

try:
    sessions = (
        db.table("sessions")
        .select("id, name, created_at")
        .order("id", desc=True)
        .execute()
        .data or []
    )

    with st.expander(
        "➕ Crea una nuova sessione",
        expanded=not sessions
    ):
        with st.form("new_session"):
            session_name = st.text_input(
                "Nome della sessione",
                value=f"Sessione {datetime.now().strftime('%d/%m/%Y %H:%M')}"
            )
            create = st.form_submit_button("Crea sessione")

            if create:
                if session_name.strip():
                    db.table("sessions").insert({
                        "name": session_name.strip()
                    }).execute()
                    st.rerun()
                else:
                    st.warning("Inserisci un nome.")

    sessions = (
        db.table("sessions")
        .select("id, name, created_at")
        .order("id", desc=True)
        .execute()
        .data or []
    )

    if not sessions:
        st.info("Crea la tua prima sessione per iniziare.")
        st.stop()

    labels = {
        f"{s['name']} — {s['created_at']}": s["id"]
        for s in sessions
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
            db.table("spins").insert({
                "session_id": session_id,
                "number": int(number)
            }).execute()
            st.rerun()

    rows = (
        db.table("spins")
        .select("number, created_at")
        .eq("session_id", session_id)
        .order("id")
        .execute()
        .data or []
    )

    numbers = [row["number"] for row in rows]

    st.divider()
    st.subheader("📊 Analisi della sessione")

    a, b, c = st.columns(3)
    a.metric("Giri registrati", len(numbers))
    b.metric("Rossi", sum(color(n) == "Rosso" for n in numbers))
    c.metric("Neri", sum(color(n) == "Nero" for n in numbers))

    st.markdown("### Probabilità teoriche per il prossimo giro")
    x, y, z = st.columns(3)
    x.metric("Rosso", "48,65%")
    y.metric("Nero", "48,65%")
    z.metric("Zero", "2,70%")

    st.caption(
        "I risultati precedenti non cambiano le probabilità "
        "del prossimo giro su una roulette regolare."
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
                    "Numero": row["number"],
                    "Colore": color(row["number"]),
                    "Data e ora": row["created_at"]
                }
                for row in reversed(rows[-100:])
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Registra il primo numero per vedere le statistiche.")

    st.divider()
    st.subheader("📚 Tutte le sessioni")

    for s in sessions:
        result = (
            db.table("spins")
            .select("id", count="exact")
            .eq("session_id", s["id"])
            .execute()
        )
        count = result.count if result.count is not None else 0
        st.write(
            f"**{s['name']}** · {count} giri · {s['created_at']}"
        )

    st.caption(
        "Analisi statistica: non è possibile prevedere con certezza "
        "i risultati casuali della roulette."
    )

except Exception:
    st.error(
        "Si è verificato un errore nel database. "
        "Controlla le tabelle Supabase e i Secrets di Streamlit."
    )
