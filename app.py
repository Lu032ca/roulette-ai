
from datetime import datetime
from collections import Counter

import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Roulette AI",
    page_icon="🎯",
    layout="wide"
)

# STILE
st.markdown("""
<style>
.stApp {
    background: #101510;
    color: #f3ead5;
}
h1, h2, h3 {
    color: #d8b66a !important;
}
div.stButton > button,
div.stFormSubmitButton > button {
    border: 1px solid #b99a52;
    border-radius: 10px;
}
[data-testid="stMetricValue"] {
    color: #d8b66a;
}
</style>
""", unsafe_allow_html=True)


# ACCESSO
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("🎯 ROULETTE AI")
    st.caption("STATISTICAL ANALYSIS")

    with st.form("login"):
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("ENTRA")

        if submitted:
            if password == st.secrets["APP_PASSWORD"]:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Password non corretta.")

    st.stop()


# DATABASE
try:
    db = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_KEY"]
    )

    sessions = (
        db.table("sessions")
        .select("id, name, created_at")
        .order("id", desc=True)
        .execute()
        .data or []
    )

except Exception as e:
    st.error(f"Errore di collegamento: {type(e).__name__}: {e}")
    st.stop()


# ROULETTE EUROPEA
RED_NUMBERS = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36
}


def get_color(n):
    if n == 0:
        return "Verde"
    return "Rosso" if n in RED_NUMBERS else "Nero"


def get_dozen(n):
    if n == 0:
        return "Zero"
    return f"{(n - 1) // 12 + 1}ª dozzina"


def get_column(n):
    if n == 0:
        return "Zero"
    return f"{(n - 1) % 3 + 1}ª colonna"


# TESTATA
st.title("🎯 ROULETTE AI")
st.caption("ROULETTE EUROPEA · ANALISI STATISTICA")
st.divider()


# SESSIONI
with st.expander("➕ CREA UNA NUOVA SESSIONE", expanded=not sessions):
    with st.form("new_session"):
        name = st.text_input(
            "Nome sessione",
            value=f"Sessione {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        create = st.form_submit_button("CREA SESSIONE")

        if create:
            if name.strip():
                try:
                    db.table("sessions").insert({
                        "name": name.strip()
                    }).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore: {type(e).__name__}: {e}")
            else:
                st.warning("Inserisci un nome.")

try:
    sessions = (
        db.table("sessions")
        .select("id, name, created_at")
        .order("id", desc=True)
        .execute()
        .data or []
    )
except Exception as e:
    st.error(f"Errore nel caricamento delle sessioni: {e}")
    st.stop()

if not sessions:
    st.info("Crea una sessione per iniziare.")
    st.stop()

labels = {
    f"{s['name']} — {s['created_at']}": s["id"]
    for s in sessions
}

selected = st.selectbox("SESSIONE ATTIVA", list(labels.keys()))
session_id = labels[selected]


# INSERIMENTO NUMERO
st.subheader("🎲 Registra un risultato")

with st.form("add_spin", clear_on_submit=True):
    number = st.number_input(
        "Numero uscito (0–36)",
        min_value=0,
        max_value=36,
        value=0,
        step=1
    )
    add = st.form_submit_button("REGISTRA NUMERO")

    if add:
        try:
            db.table("spins").insert({
                "session_id": session_id,
                "number": int(number)
            }).execute()
            st.success(f"Numero {int(number)} registrato.")
            st.rerun()
        except Exception as e:
            st.error(f"Errore nel salvataggio: {type(e).__name__}: {e}")


# CARICAMENTO STORICO
try:
    rows = (
        db.table("spins")
        .select("id, number, created_at")
        .eq("session_id", session_id)
        .order("id")
        .execute()
        .data or []
    )
except Exception as e:
    st.error(f"Errore nel caricamento dello storico: {e}")
    st.stop()

numbers = [int(r["number"]) for r in rows]
total = len(numbers)


# PERCENTUALI REALI E TEORICHE
st.divider()
st.subheader("📊 Percentuali della sessione")

red = sum(get_color(n) == "Rosso" for n in numbers)
black = sum(get_color(n) == "Nero" for n in numbers)
green = sum(n == 0 for n in numbers)

a, b, c = st.columns(3)
a.metric("🔴 Rossi", f"{red / total * 100:.2f}%" if total else "0,00%",
         f"{red} uscite")
b.metric("⚫ Neri", f"{black / total * 100:.2f}%" if total else "0,00%",
         f"{black} uscite")
c.metric("🟢 Zero", f"{green / total * 100:.2f}%" if total else "0,00%",
         f"{green} uscite")

st.caption(f"Giri registrati: {total}")

with st.expander("Probabilità teoriche della roulette europea"):
    st.write("🔴 Rosso: **48,65%**")
    st.write("⚫ Nero: **48,65%**")
    st.write("🟢 Zero: **2,70%**")
    st.caption(
        "Le percentuali teoriche sono probabilità per singolo giro. "
        "Le percentuali osservate possono discostarsi anche molto "
        "nel breve periodo."
    )


# FREQUENZE NUMERI
st.divider()
st.subheader("🔢 Frequenza dei numeri")

counts = Counter(numbers)

st.bar_chart({
    "Uscite": {str(n): counts[n] for n in range(37)}
})

if total:
    highest = max(counts.values())
    lowest = min(counts.get(n, 0) for n in range(37))

    hot = [n for n in range(37) if counts[n] == highest]
    cold = [n for n in range(37) if counts.get(n, 0) == lowest]

    col1, col2 = st.columns(2)
    col1.markdown("**Più frequenti nella sessione**")
    col1.write(", ".join(map(str, hot)))
    col1.caption(f"{highest} uscite ciascuno")

    col2.markdown("**Meno frequenti nella sessione**")
    col2.write(", ".join(map(str, cold)))
    col2.caption(f"{lowest} uscite ciascuno")


# DOZZINE E COLONNE
st.divider()
st.subheader("📐 Dozzine e colonne")

dozens = {
    "1ª dozzina (1–12)": sum(1 <= n <= 12 for n in numbers),
    "2ª dozzina (13–24)": sum(13 <= n <= 24 for n in numbers),
    "3ª dozzina (25–36)": sum(25 <= n <= 36 for n in numbers),
}

columns = {
    "1ª colonna": sum(n != 0 and (n - 1) % 3 == 0 for n in numbers),
    "2ª colonna": sum(n != 0 and (n - 1) % 3 == 1 for n in numbers),
    "3ª colonna": sum(n != 0 and (n - 1) % 3 == 2 for n in numbers),
}

left, right = st.columns(2)

with left:
    st.markdown("**Dozzine**")
    for label, value in dozens.items():
        pct = value / total * 100 if total else 0
        st.write(f"{label}: **{value}** ({pct:.2f}%)")

with right:
    st.markdown("**Colonne**")
    for label, value in columns.items():
        pct = value / total * 100 if total else 0
        st.write(f"{label}: **{value}** ({pct:.2f}%)")


# ULTIMI RISULTATI
st.divider()
st.subheader("🕘 Ultimi risultati")

if numbers:
    st.write(" → ".join(map(str, numbers[-20:][::-1])))
else:
    st.info("Nessun numero registrato in questa sessione.")


# STORICO DETTAGLIATO
with st.expander("📚 Storico dettagliato"):
    if rows:
        st.dataframe(
            [
                {
                    "Numero": r["number"],
                    "Colore": get_color(r["number"]),
                    "Dozzina": get_dozen(r["number"]),
                    "Colonna": get_column(r["number"]),
                    "Data e ora": r["created_at"]
                }
                for r in reversed(rows[-200:])
            ],
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Lo storico apparirà qui.")


# RIEPILOGO SESSIONI
st.divider()
st.subheader("📁 Riepilogo sessioni")

for s in sessions:
    try:
        result = (
            db.table("spins")
            .select("id", count="exact")
            .eq("session_id", s["id"])
            .execute()
        )
        count = result.count if result.count is not None else 0
        st.write(f"**{s['name']}** · {count} giri · {s['created_at']}")
    except Exception:
        st.write(f"**{s['name']}**")

st.caption(
    "Le frequenze descrivono il passato. Non indicano quale numero "
    "uscirà al prossimo giro: ogni giro regolare è indipendente."
)
