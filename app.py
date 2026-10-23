
from datetime import datetime
from collections import Counter

import streamlit as st
from supabase import create_client

st.set_page_config(page_title="Roulette AI", page_icon="🎯", layout="wide")

st.markdown("""
<style>
.stApp {background:#101510;color:#f3ead5}
h1,h2,h3 {color:#d8b66a !important}
div.stButton > button {
    border:1px solid #b99a52;
    border-radius:10px;
    min-height:42px;
}
[data-testid="stMetricValue"] {color:#d8b66a}
</style>
""", unsafe_allow_html=True)

# DATABASE E ACCESSO PERSONALE
try:
    db = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_PUBLISHABLE_KEY"]
    )
except Exception as e:
    st.error(f"Errore di collegamento: {type(e).__name__}: {e}")
    st.stop()

if "access_token" not in st.session_state:
    st.session_state.access_token = None
    st.session_state.refresh_token = None

if st.session_state.access_token and st.session_state.refresh_token:
    try:
        db.auth.set_session(
            st.session_state.access_token,
            st.session_state.refresh_token
        )
        session = db.auth.get_session()
        if session:
            st.session_state.access_token = session.access_token
            st.session_state.refresh_token = session.refresh_token
    except Exception:
        st.session_state.access_token = None
        st.session_state.refresh_token = None

if not st.session_state.access_token:
    st.title("🎯 ROULETTE AI")
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("ENTRA"):
            try:
                result = db.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password
                })
                st.session_state.access_token = result.session.access_token
                st.session_state.refresh_token = result.session.refresh_token
                st.rerun()
            except Exception:
                st.error("Email o password non corretti.")
    st.stop()

ROSSI = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36
}

def colore(n):
    if n == 0:
        return "Verde"
    return "Rosso" if n in ROSSI else "Nero"

def simbolo(n):
    return "🟢" if n == 0 else ("🔴" if n in ROSSI else "⚫")

def percentuale(n, totale):
    return 100 * n / totale if totale else 0

st.title("🎯 ROULETTE AI")
st.caption("ROULETTE EUROPEA · STATISTICHE E ANALISI")
st.divider()

# SESSIONI
try:
    sessions = (
        db.table("sessions")
        .select("id, name, created_at")
        .order("id", desc=True)
        .execute().data or []
    )
except Exception as e:
    st.error(f"Errore sessioni: {e}")
    st.stop()

with st.expander("➕ Crea sessione", expanded=not sessions):
    with st.form("new_session"):
        nome = st.text_input(
            "Nome",
            value=f"Sessione {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        if st.form_submit_button("CREA"):
            if nome.strip():
                db.table("sessions").insert(
                    {"name": nome.strip()}
                ).execute()
                st.rerun()
            else:
                st.warning("Inserisci un nome.")

sessions = (
    db.table("sessions")
    .select("id, name, created_at")
    .order("id", desc=True)
    .execute().data or []
)

if not sessions:
    st.info("Crea una sessione per cominciare.")
    st.stop()

opzioni = {f"{s['name']} — {s['created_at']}": s["id"] for s in sessions}
sessione = st.selectbox("SESSIONE ATTIVA", list(opzioni.keys()))
sid = opzioni[sessione]

# CARICAMENTO STORICO: ultimi 1000 giri della sessione
def carica():
    return (
        db.table("spins")
        .select("id, number, created_at")
        .eq("session_id", sid)
        .order("id", desc=True)
        .limit(1000)
        .execute().data or []
    )

try:
    rows = carica()
except Exception as e:
    st.error(f"Errore storico: {e}")
    st.stop()

# TASTIERA
st.subheader("🎲 Registra il numero uscito")
st.caption("Tocca un numero per registrarlo direttamente.")

for start in range(0, 37, 3):
    cols = st.columns(3)
    for j, n in enumerate(range(start, min(start + 3, 37))):
        with cols[j]:
            if st.button(
                f"{simbolo(n)}  {n}",
                key=f"num_{sid}_{n}",
                use_container_width=True
            ):
                try:
                    db.table("spins").insert({
                        "session_id": sid,
                        "number": n
                    }).execute()
                    st.rerun()
                except Exception as e:
                    st.error(f"Errore salvataggio: {e}")

# AGGIUNTA MANUALE OPZIONALE
with st.expander("Inserimento manuale"):
    with st.form("manuale"):
        n_manual = st.number_input(
            "Numero da 0 a 36", 0, 36, 0, 1
        )
        if st.form_submit_button("REGISTRA"):
            db.table("spins").insert({
                "session_id": sid,
                "number": int(n_manual)
            }).execute()
            st.rerun()

# ANNULLA ULTIMO
st.divider()
if rows:
    ultimo = rows[0]
    st.write(
        f"Ultimo inserimento: **{ultimo['number']}** "
        f"{simbolo(ultimo['number'])}"
    )
    if st.button("↩️ ANNULLA ULTIMO NUMERO"):
        db.table("spins").delete().eq("id", ultimo["id"]).eq(
            "session_id", sid
        ).execute()
        st.rerun()

# STATISTICHE
rows = list(reversed(carica()))
numbers = [int(r["number"]) for r in rows]
totale = len(numbers)

st.divider()
st.subheader("📊 Statistiche della sessione")
a, b, c = st.columns(3)
a.metric("Giri", totale)
b.metric("Rossi", sum(colore(n) == "Rosso" for n in numbers))
c.metric("Neri", sum(colore(n) == "Nero" for n in numbers))

red = sum(colore(n) == "Rosso" for n in numbers)
black = sum(colore(n) == "Nero" for n in numbers)
zero = sum(n == 0 for n in numbers)

st.markdown("#### Percentuali osservate")
a, b, c = st.columns(3)
a.metric("🔴 Rosso", f"{percentuale(red, totale):.2f}%")
b.metric("⚫ Nero", f"{percentuale(black, totale):.2f}%")
c.metric("🟢 Zero", f"{percentuale(zero, totale):.2f}%")

with st.expander("Probabilità teoriche"):
    st.write("Rosso: **48,65%**")
    st.write("Nero: **48,65%**")
    st.write("Zero: **2,70%**")

# INTERVALLI 20/50/100
st.divider()
st.subheader("⏱️ Analisi degli ultimi giri")
periodo = st.selectbox("Intervallo", [20, 50, 100], index=0)
recenti = numbers[-periodo:]
nr = len(recenti)
cr = Counter(recenti)

x, y, z = st.columns(3)
x.metric("Rossi", f"{percentuale(sum(colore(n)=='Rosso' for n in recenti), nr):.2f}%",
         f"{sum(colore(n)=='Rosso' for n in recenti)} uscite")
y.metric("Neri", f"{percentuale(sum(colore(n)=='Nero' for n in recenti), nr):.2f}%",
         f"{sum(colore(n)=='Nero' for n in recenti)} uscite")
z.metric("Zero", f"{percentuale(sum(n==0 for n in recenti), nr):.2f}%",
         f"{sum(n==0 for n in recenti)} uscite")

# FREQUENZE
st.divider()
st.subheader("🔢 Frequenza dei numeri")
st.caption(f"Conteggi sull'intera sessione ({totale} giri).")
st.bar_chart({
    "Uscite": {str(n): numbers.count(n) for n in range(37)}
})

if totale:
    frequenze = Counter(numbers)
    max_freq = max(frequenze.values())
    min_freq = min(frequenze.get(n, 0) for n in range(37))
    c1, c2 = st.columns(2)
    c1.markdown("**Più usciti**")
    c1.write(", ".join(str(n) for n in range(37)
                       if frequenze.get(n, 0) == max_freq))
    c1.caption(f"{max_freq} uscite")
    c2.markdown("**Meno usciti**")
    c2.write(", ".join(str(n) for n in range(37)
                       if frequenze.get(n, 0) == min_freq))
    c2.caption(f"{min_freq} uscite")

# DOZZINE E COLONNE
st.divider()
st.subheader("📐 Dozzine e colonne")

dozzine = [
    sum(1 <= n <= 12 for n in numbers),
    sum(13 <= n <= 24 for n in numbers),
    sum(25 <= n <= 36 for n in numbers)
]
colonne = [
    sum(n != 0 and (n-1) % 3 == i for n in numbers)
    for i in range(3)
]

l, r = st.columns(2)
with l:
    st.markdown("**Dozzine**")
    for i, val in enumerate(dozzine, 1):
        st.write(f"{i}ª: {val} ({percentuale(val, totale):.2f}%)")
with r:
    st.markdown("**Colonne**")
    for i, val in enumerate(colonne, 1):
        st.write(f"{i}ª: {val} ({percentuale(val, totale):.2f}%)")

# SUGGERIMENTI DI PUNTATA
st.divider()
st.subheader("🧠 Analisi delle puntate")
st.write(
    "Questa sezione confronta i risultati recenti, ma non può "
    "prevedere in modo affidabile il prossimo giro."
)

mercato = st.selectbox(
    "Mercato da analizzare",
    ["Rosso / Nero", "Pari / Dispari", "Basso / Alto",
     "Dozzine", "Colonne"]
)

if mercato == "Rosso / Nero":
    gruppi = {
        "Rosso": sum(colore(n) == "Rosso" for n in recenti),
        "Nero": sum(colore(n) == "Nero" for n in recenti)
    }
    probabilita = "48,65% per ciascun colore"
elif mercato == "Pari / Dispari":
    gruppi = {
        "Pari": sum(n != 0 and n % 2 == 0 for n in recenti),
        "Dispari": sum(n % 2 == 1 for n in recenti)
    }
    probabilita = "48,65% per ciascun esito"
elif mercato == "Basso / Alto":
    gruppi = {
        "Basso (1–18)": sum(1 <= n <= 18 for n in recenti),
        "Alto (19–36)": sum(19 <= n <= 36 for n in recenti)
    }
    probabilita = "48,65% per ciascun esito"
elif mercato == "Dozzine":
    gruppi = {
        "1ª dozzina": sum(1 <= n <= 12 for n in recenti),
        "2ª dozzina": sum(13 <= n <= 24 for n in recenti),
        "3ª dozzina": sum(25 <= n <= 36 for n in recenti)
    }
    probabilita = "32,43% per ciascuna dozzina"
else:
    gruppi = {
        f"{i+1}ª colonna": sum(
            n != 0 and (n-1) % 3 == i for n in recenti
        )
        for i in range(3)
    }
    probabilita = "32,43% per ciascuna colonna"

st.caption(f"Probabilità teorica: {probabilita}.")
if nr:
    st.write("**Risultati osservati nell'intervallo scelto:**")
    for label, value in gruppi.items():
        st.write(f"{label}: {value}/{nr} ({percentuale(value, nr):.2f}%)")

    maxval = max(gruppi.values())
    minval = min(gruppi.values())
    piu = [k for k, v in gruppi.items() if v == maxval]
    meno = [k for k, v in gruppi.items() if v == minval]

    st.info("Più frequente nei dati: " + ", ".join(piu))
    st.write("Meno frequente nei dati: " + ", ".join(meno))
    st.warning(
        "Questi sono dati storici, non consigli predittivi. "
        "Un esito meno uscito non è più probabile al prossimo giro. "
        "Le puntate standard sulla roulette europea hanno valore "
        "atteso negativo."
    )
else:
    st.info("Registra qualche giro per analizzare i risultati.")

# ULTIMI RISULTATI
st.divider()
st.subheader("🕘 Ultimi risultati")
if numbers:
    st.write(" → ".join(
        f"{simbolo(n)} {n}" for n in numbers[-20:][::-1]
    ))
else:
    st.info("Nessun risultato registrato.")

# STORICO
with st.expander("📚 Storico dettagliato"):
    if rows:
        st.dataframe([
            {
                "Numero": r["number"],
                "Colore": colore(r["number"]),
                "Data e ora": r["created_at"]
            }
            for r in reversed(rows[-200:])
        ], use_container_width=True, hide_index=True)

st.caption(
    "Roulette europea: ogni giro è indipendente. "
    "Le statistiche descrivono il passato, non garantiscono vincite."
)
