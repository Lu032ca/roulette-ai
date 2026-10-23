
from datetime import datetime
from collections import Counter
import secrets

import streamlit as st
from supabase import create_client

st.set_page_config(
    page_title="Roulette AI",
    page_icon="🎯",
    layout="wide"
)

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


# DATABASE
try:
    db = create_client(
        st.secrets["SUPABASE_URL"],
        st.secrets["SUPABASE_PUBLISHABLE_KEY"]
    )
except Exception as e:
    st.error(f"Errore database: {type(e).__name__}: {e}")
    st.stop()


# AUTENTICAZIONE
if "access_token" not in st.session_state:
    st.session_state.access_token = None
    st.session_state.refresh_token = None

current_user = None

if st.session_state.access_token and st.session_state.refresh_token:
    try:
        db.auth.set_session(
            st.session_state.access_token,
            st.session_state.refresh_token
        )
        auth_session = db.auth.get_session()

        if auth_session:
            st.session_state.access_token = auth_session.access_token
            st.session_state.refresh_token = auth_session.refresh_token

        current_user = db.auth.get_user(
            st.session_state.access_token
        ).user
    except Exception:
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        current_user = None


if current_user is None:
    st.title("🎯 ROULETTE AI")
    st.caption("Accedi al tuo account personale")

    tab_login, tab_register = st.tabs(["Accedi", "Crea account"])

    with tab_login:
        with st.form("login"):
            email = st.text_input("Email")
            password = st.text_input("Password", type="password")
            login_submit = st.form_submit_button(
                "ENTRA", use_container_width=True
            )

        if login_submit:
            try:
                result = db.auth.sign_in_with_password({
                    "email": email.strip(),
                    "password": password
                })
                if not result.session:
                    st.error("Accesso non riuscito.")
                else:
                    st.session_state.access_token = result.session.access_token
                    st.session_state.refresh_token = result.session.refresh_token
                    st.rerun()
            except Exception:
                st.error("Accesso non riuscito. Controlla email e password.")

    with tab_register:
        with st.form("register"):
            new_email = st.text_input("La tua email", key="register_email")
            new_password = st.text_input(
                "Crea una password",
                type="password",
                key="register_password"
            )
            confirm_password = st.text_input(
                "Ripeti la password", type="password"
            )
            register_submit = st.form_submit_button(
                "CREA ACCOUNT", use_container_width=True
            )

        if register_submit:
            if not new_email.strip():
                st.error("Inserisci un'email.")
            elif len(new_password) < 8:
                st.error("La password deve contenere almeno 8 caratteri.")
            elif new_password != confirm_password:
                st.error("Le password non coincidono.")
            else:
                try:
                    result = db.auth.sign_up({
                        "email": new_email.strip(),
                        "password": new_password
                    })
                    if result.session:
                        st.session_state.access_token = result.session.access_token
                        st.session_state.refresh_token = result.session.refresh_token
                        st.rerun()
                    else:
                        st.success(
                            "Account creato. Se richiesto, conferma "
                            "l'email e poi accedi."
                        )
                except Exception:
                    st.error("Registrazione non riuscita. Controlla l'email.")

    st.stop()


user_id = str(current_user.id)


# ROULETTE EUROPEA
ROSSI = {
    1, 3, 5, 7, 9, 12, 14, 16, 18,
    19, 21, 23, 25, 27, 30, 32, 34, 36
}


def colore(n):
    if n == 0:
        return "Verde"
    return "Rosso" if n in ROSSI else "Nero"


def simbolo(n):
    if n == 0:
        return "🟢"
    return "🔴" if n in ROSSI else "⚫"


def percentuale(n, totale):
    return 100 * n / totale if totale else 0


def esito_preso(mercato, scelta, numero):
    """Confronta un consiglio con il numero uscito."""
    if mercato == "Rosso/Nero":
        return colore(numero) == scelta

    if mercato == "Dozzina":
        if numero == 0:
            return False
        if scelta == "1ª dozzina":
            return 1 <= numero <= 12
        if scelta == "2ª dozzina":
            return 13 <= numero <= 24
        if scelta == "3ª dozzina":
            return 25 <= numero <= 36

    if mercato == "Colonna":
        if numero == 0:
            return False
        colonna = (numero - 1) % 3 + 1
        return scelta == f"{colonna}ª colonna"

    return False


def registra_numero(numero, session_id):
    """Registra un giro e valuta i consigli in attesa."""
    try:
        db.table("spins").insert({
            "session_id": session_id,
            "number": int(numero)
        }).execute()

        pending = (
            db.table("roulette_tips")
            .select("id")
            .eq("session_id", session_id)
            .is_("result_number", "null")
            .execute()
            .data or []
        )

        if pending:
            now = datetime.now().astimezone().isoformat()
            for tip in pending:
                db.table("roulette_tips").update({
                    "result_number": int(numero),
                    "evaluated_at": now
                }).eq("id", tip["id"]).eq(
                    "session_id", session_id
                ).execute()

        st.rerun()

    except Exception as e:
        st.error(f"Errore durante la registrazione: {e}")


# INTESTAZIONE
titolo_col, logout_col = st.columns([4, 1])

with titolo_col:
    st.title("🎯 ROULETTE AI")
    st.caption("ROULETTE EUROPEA · STATISTICHE E ANALISI")
    st.caption(f"Account: {current_user.email}")

with logout_col:
    if st.button("ESCI", use_container_width=True):
        try:
            db.auth.sign_out()
        except Exception:
            pass
        st.session_state.access_token = None
        st.session_state.refresh_token = None
        st.rerun()

st.divider()


# CARICAMENTO SESSIONI ACCESSIBILI
try:
    sessions = (
        db.table("sessions")
        .select("id, name, created_at, user_id")
        .order("id", desc=True)
        .execute()
        .data or []
    )

    memberships = (
        db.table("session_members")
        .select("session_id, role")
        .eq("user_id", user_id)
        .execute()
        .data or []
    )
except Exception as e:
    st.error(
        "Non riesco a caricare le sessioni. "
        "Se hai appena sostituito il codice, potrebbe mancare "
        f"l'aggiornamento del database Supabase. Dettaglio: {e}"
    )
    st.stop()


ruoli = {int(m["session_id"]): m["role"] for m in memberships}

def ruolo_sessione(s):
    if str(s["user_id"]) == user_id:
        return "owner"
    return ruoli.get(int(s["id"]), "viewer")


# CREA SESSIONE PERSONALE
with st.expander("➕ Crea sessione", expanded=not sessions):
    with st.form("new_session"):
        nome = st.text_input(
            "Nome",
            value=f"Sessione {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        )
        crea = st.form_submit_button("CREA")

    if crea:
        if nome.strip():
            try:
                db.table("sessions").insert({
                    "name": nome.strip(),
                    "user_id": user_id
                }).execute()
                st.rerun()
            except Exception as e:
                st.error(f"Errore creazione sessione: {e}")
        else:
            st.warning("Inserisci un nome.")


# AGGIORNA SESSIONI
try:
    sessions = (
        db.table("sessions")
        .select("id, name, created_at, user_id")
        .order("id", desc=True)
        .execute()
        .data or []
    )
except Exception as e:
    st.error(f"Errore caricamento sessioni: {e}")
    st.stop()

if not sessions:
    st.info("Non hai ancora sessioni. Creane una per cominciare.")
    st.stop()

opzioni = {
    f"{s['name']} — {s['created_at']}": int(s["id"])
    for s in sessions
}
sessione = st.selectbox("SESSIONE ATTIVA", list(opzioni.keys()))
sid = opzioni[sessione]
sessione_attiva = next(s for s in sessions if int(s["id"]) == sid)
ruolo = ruolo_sessione(sessione_attiva)
puo_inserire = ruolo in ("owner", "editor")
proprietario = ruolo == "owner"

st.caption({
    "owner": "👑",
    "editor": "🎲",
    "viewer": "👁️"
}.get(ruolo, "Tavolo condiviso"))


# CONDIVISIONE TAVOLO
with st.expander("👥 Condivisione e accessi"):
    st.write(
        "Condividi solo questa sessione. Le altre sessioni "
        "rimangono private."
    )

    with st.form("join_by_code"):
        codice = st.text_input("Codice d'invito")
        entra = st.form_submit_button("UNISCITI AL TAVOLO")

    if entra:
        if codice.strip():
            try:
                db.rpc(
                    "join_session_by_code",
                    {"p_code": codice.strip()}
                ).execute()
                st.success("Richiesta completata. Aggiorno i tavoli...")
                st.rerun()
            except Exception as e:
                st.error(f"Codice non valido o non utilizzabile: {e}")
        else:
            st.warning("Inserisci un codice d'invito.")

    if proprietario:
        st.markdown("#### Crea un invito")
        with st.form("create_invite"):
            ruolo_invito = st.selectbox(
    "Permessi dell'invitato",
    ["viewer", "editor"],
    format_func=lambda x: (
        "👁️ Viewer" if x == "viewer"
        else "✏️ Editor"
    )
)
            genera = st.form_submit_button("GENERA CODICE")

        if genera:
            try:
                codice_nuovo = secrets.token_urlsafe(9)
                db.table("session_invites").insert({
                    "session_id": sid,
                    "code": codice_nuovo,
                    "role": ruolo_invito,
                    "created_by": user_id,
                    "active": True
                }).execute()
                st.session_state["ultimo_invito"] = codice_nuovo
                st.session_state["ultimo_invito_ruolo"] = ruolo_invito
                st.rerun()
            except Exception as e:
                st.error(f"Errore creazione invito: {e}")

        if st.session_state.get("ultimo_invito"):
            st.success(
                "Codice creato: "
                + st.session_state["ultimo_invito"]
            )
            st.caption(
                "Permessi: "
                + (
                    "solo visualizzazione"
                    if st.session_state.get("ultimo_invito_ruolo") == "viewer"
                    else "inserimento numeri"
                )
            )
            if st.button("Copia codice invito"):
                st.code(st.session_state["ultimo_invito"])

        st.markdown("#### Membri del tavolo")
        try:
            membri = (
                db.table("session_members")
                .select("user_id, role")
                .eq("session_id", sid)
                .execute()
                .data or []
            )

            if membri:
                for membro in membri:
                    uid = str(membro["user_id"])
                    riga1, riga2 = st.columns([3, 1])
                    riga1.write(f"{uid} — {membro['role']}")

                    if uid != user_id:
                        with riga2:
                            if st.button(
                                "Revoca",
                                key=f"revoca_{sid}_{uid}"
                            ):
                                db.table("session_members").delete().eq(
                                    "session_id", sid
                                ).eq("user_id", uid).execute()
                                st.rerun()
            else:
                st.info("Non ci sono ancora membri invitati.")
        except Exception as e:
            st.error(f"Errore caricamento membri: {e}")

        st.markdown("#### Revoca codici d'invito")
        try:
            inviti = (
                db.table("session_invites")
                .select("id, code, role, active")
                .eq("session_id", sid)
                .eq("active", True)
                .execute()
                .data or []
            )

            for invito in inviti:
                c1, c2 = st.columns([3, 1])
                c1.write(
                    f"{invito['code']} — {invito['role']}"
                )
                with c2:
                    if st.button(
                        "Disattiva",
                        key=f"disattiva_{invito['id']}"
                    ):
                        db.table("session_invites").update({
                            "active": False
                        }).eq("id", invito["id"]).execute()
                        st.rerun()
        except Exception as e:
            st.error(f"Errore caricamento inviti: {e}")


# STORICO SESSIONE
def carica():
    return (
        db.table("spins")
        .select("id, number, created_at")
        .eq("session_id", sid)
        .order("id", desc=True)
        .limit(1000)
        .execute()
        .data or []
    )


try:
    rows = carica()
except Exception as e:
    st.error(f"Errore storico: {e}")
    st.stop()


# TASTIERINO 0-36
st.subheader("🎲 Registra il numero uscito")
st.caption("Tocca un numero per registrarlo.")

if puo_inserire:
    for start in range(0, 37, 3):
        cols = st.columns(3)
        for j, n in enumerate(range(start, min(start + 3, 37))):
            with cols[j]:
                if st.button(
                    f"{simbolo(n)}  {n}",
                    key=f"num_{sid}_{n}",
                    use_container_width=True
                ):
                    registra_numero(n, sid)
else:
    st.info("Hai accesso in sola visualizzazione: non puoi inserire numeri.")


# ANNULLA ULTIMO NUMERO
st.divider()
if rows:
    ultimo = rows[0]
    st.write(
        f"Ultimo inserimento: **{ultimo['number']}** "
        f"{simbolo(ultimo['number'])}"
    )

    if puo_inserire and st.button("↩️ ANNULLA ULTIMO NUMERO"):
        try:
            db.table("spins").delete().eq(
                "id", ultimo["id"]
            ).eq("session_id", sid).execute()
            st.rerun()
        except Exception as e:
            st.error(f"Errore annullamento: {e}")


# STATISTICHE
try:
    rows = list(reversed(carica()))
except Exception as e:
    st.error(f"Errore statistiche: {e}")
    st.stop()

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


# ANALISI ULTIMI GIRI
st.divider()
st.subheader("⏱️ Analisi degli ultimi giri")

periodo = st.selectbox("Intervallo", [20, 50, 100], index=0)
recenti = numbers[-periodo:]
nr = len(recenti)

x, y, z = st.columns(3)
x.metric(
    "Rossi",
    f"{percentuale(sum(colore(n) == 'Rosso' for n in recenti), nr):.2f}%",
    f"{sum(colore(n) == 'Rosso' for n in recenti)} uscite"
)
y.metric(
    "Neri",
    f"{percentuale(sum(colore(n) == 'Nero' for n in recenti), nr):.2f}%",
    f"{sum(colore(n) == 'Nero' for n in recenti)} uscite"
)
z.metric(
    "Zero",
    f"{percentuale(sum(n == 0 for n in recenti), nr):.2f}%",
    f"{sum(n == 0 for n in recenti)} uscite"
)


# FREQUENZE NUMERI
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
    c1.write(", ".join(
        str(n) for n in range(37)
        if frequenze.get(n, 0) == max_freq
    ))
    c1.caption(f"{max_freq} uscite")

    c2.markdown("**Meno usciti**")
    c2.write(", ".join(
        str(n) for n in range(37)
        if frequenze.get(n, 0) == min_freq
    ))
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
    sum(n != 0 and (n - 1) % 3 == i for n in numbers)
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


# ANALISI DELLE PUNTATE - SENZA PROBABILITA' TEORICHE
st.divider()
st.subheader("🧠 Analisi delle puntate")

mercato = st.selectbox(
    "Mercato da analizzare",
    ["Rosso / Nero", "Pari / Dispari", "Basso / Alto", "Dozzine", "Colonne"]
)

if mercato == "Rosso / Nero":
    gruppi = {
        "Rosso": sum(colore(n) == "Rosso" for n in recenti),
        "Nero": sum(colore(n) == "Nero" for n in recenti)
    }
elif mercato == "Pari / Dispari":
    gruppi = {
        "Pari": sum(n != 0 and n % 2 == 0 for n in recenti),
        "Dispari": sum(n % 2 == 1 for n in recenti)
    }
elif mercato == "Basso / Alto":
    gruppi = {
        "Basso (1–18)": sum(1 <= n <= 18 for n in recenti),
        "Alto (19–36)": sum(19 <= n <= 36 for n in recenti)
    }
elif mercato == "Dozzine":
    gruppi = {
        "1ª dozzina": sum(1 <= n <= 12 for n in recenti),
        "2ª dozzina": sum(13 <= n <= 24 for n in recenti),
        "3ª dozzina": sum(25 <= n <= 36 for n in recenti)
    }
else:
    gruppi = {
        f"{i + 1}ª colonna": sum(
            n != 0 and (n - 1) % 3 == i for n in recenti
        )
        for i in range(3)
    }

if nr:
    st.write("**Risultati osservati nell'intervallo scelto:**")
    for label, value in gruppi.items():
        st.write(
            f"{label}: {value}/{nr} ({percentuale(value, nr):.2f}%)"
        )

    massimo = max(gruppi.values())
    minimo = min(gruppi.values())
    st.info(
        "Più frequente nei dati: "
        + ", ".join(k for k, v in gruppi.items() if v == massimo)
    )
    st.write(
        "Meno frequente nei dati: "
        + ", ".join(k for k, v in gruppi.items() if v == minimo)
    )

else:
    st.info("Registra qualche giro per analizzare i risultati.")


# NUMERI CALDI E FREDDI
st.divider()
st.subheader("🔥 Numeri caldi e freddi")

if nr:
    freq_recenti = Counter(recenti)
    caldi = sorted(
        range(37), key=lambda n: (-freq_recenti.get(n, 0), n)
    )[:5]
    freddi = sorted(
        range(37), key=lambda n: (freq_recenti.get(n, 0), n)
    )[:5]

    col_caldi, col_freddi = st.columns(2)
    with col_caldi:
        st.markdown("#### 🔥 Più usciti")
        for n in caldi:
            st.write(f"{simbolo(n)} **{n}** — {freq_recenti.get(n, 0)} uscite")
    with col_freddi:
        st.markdown("#### ❄️ Meno usciti")
        for n in freddi:
            st.write(f"{simbolo(n)} **{n}** — {freq_recenti.get(n, 0)} uscite")


# CONSIGLIO PUNTATA E STORICO
st.divider()
st.subheader("🎯 Consiglio della prossima puntata")

mercato_consiglio = st.selectbox(
    "Tipo di puntata",
    ["Rosso/Nero", "Dozzina", "Colonna"],
    key="mercato_consiglio"
)

importo = st.number_input(
    "Importo (€)",
    min_value=0.10,
    max_value=100.0,
    value=1.0,
    step=0.10,
    key="importo_consiglio"
)

if nr < 20:
    st.info("Registra almeno 20 giri nell'intervallo selezionato.")
else:
    if mercato_consiglio == "Rosso/Nero":
        gruppi_cons = {
            "Rosso": sum(colore(n) == "Rosso" for n in recenti),
            "Nero": sum(colore(n) == "Nero" for n in recenti)
        }
    elif mercato_consiglio == "Dozzina":
        gruppi_cons = {
            "1ª dozzina": sum(1 <= n <= 12 for n in recenti),
            "2ª dozzina": sum(13 <= n <= 24 for n in recenti),
            "3ª dozzina": sum(25 <= n <= 36 for n in recenti)
        }
    else:
        gruppi_cons = {
            f"{i + 1}ª colonna": sum(
                n != 0 and (n - 1) % 3 == i for n in recenti
            )
            for i in range(3)
        }

    massimo = max(gruppi_cons.values())
    scelte = [
        nome for nome, conteggio in gruppi_cons.items()
        if conteggio == massimo
    ]

    scelta = st.selectbox(
        "Consiglio basato sulle frequenze",
        scelte,
        key="scelta_consiglio"
    )

    st.write(f"**Consiglio attuale: {scelta}**")

    if puo_inserire:
        if st.button("💾 SALVA CONSIGLIO", key="salva_consiglio"):
            try:
                db.table("roulette_tips").insert({
                    "user_id": user_id,
                    "session_id": sid,
                    "market": mercato_consiglio,
                    "suggestion": scelta,
                    "stake": importo
                }).execute()
                st.success("Consiglio salvato. Verrà confrontato con il prossimo numero inserito.")
                st.rerun()
            except Exception as e:
                st.error(f"Errore salvataggio consiglio: {e}")
    else:
        st.caption("Solo chi può inserire numeri può salvare un consiglio.")

st.divider()
st.subheader("📚 Storico dei consigli")

try:
    consigli = (
        db.table("roulette_tips")
        .select("id, market, suggestion, stake, created_at, result_number, evaluated_at")
        .eq("session_id", sid)
        .order("id", desc=True)
        .limit(100)
        .execute()
        .data or []
    )

    if consigli:
        dati = []
        for tip in consigli:
            numero_esito = tip["result_number"]
            if numero_esito is None:
                esito = "In attesa"
            else:
                esito = (
                    "✅ Preso"
                    if esito_preso(
                        tip["market"],
                        tip["suggestion"],
                        int(numero_esito)
                    )
                    else "❌ Non preso"
                )

            dati.append({
                "Data": tip["created_at"],
                "Mercato": tip["market"],
                "Consiglio": tip["suggestion"],
                "Esito": esito,
                "Numero uscito": (
                    numero_esito if numero_esito is not None else "—"
                )
            })

        st.dataframe(
            dati,
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Non ci sono ancora consigli salvati.")
except Exception as e:
    st.error(f"Errore caricamento storico consigli: {e}")


# ULTIMI RISULTATI
st.divider()
st.subheader("🕘 Ultimi risultati")

if numbers:
    st.write(" → ".join(
        f"{simbolo(n)} {n}" for n in numbers[-20:][::-1]
    ))
else:
    st.info("Nessun risultato registrato.")


# STORICO DETTAGLIATO
with st.expander("📚 Storico dettagliato"):
    if rows:
        st.dataframe(
            [
                {
                    "Numero": r["number"],
                    "Colore": colore(r["number"]),
                    "Data e ora": r["created_at"]
                }
                for r in rows[-200:][::-1]
            ],
            use_container_width=True,
            hide_index=True
        )
