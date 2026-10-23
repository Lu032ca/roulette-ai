from datetime import datetime
from collections import Counter
import secrets
import re

import streamlit as st
from supabase import create_client


# CONFIGURAZIONE
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
div[data-testid="stButton"] button {
    border: 1px solid #8d7745;
    border-radius: 8px;
    min-height: 34px;
    height: 34px;
    padding: 0.1rem 0.2rem;
    font-size: 13px;
}
[data-testid="stMetricValue"] {
    color: #d8b66a;
}
</style>
""", unsafe_allow_html=True)


# DATABASE
try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_PUBLISHABLE_KEY = st.secrets["SUPABASE_PUBLISHABLE_KEY"]
    SUPABASE_SECRET_KEY = st.secrets["supabase_key"]

    # Client normale: usa la chiave pubblica e la sessione dell'utente.
    db = create_client(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY)

    # Client amministrativo: resta sul server Streamlit e usa il Secret Key.
    # Serve soltanto per associare username e account Supabase Auth.
    admin_db = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)

except Exception as e:
    st.error(
        "Configurazione database incompleta. Controlla i Secrets di Streamlit "
        "(SUPABASE_URL, SUPABASE_PUBLISHABLE_KEY e supabase_key). "
        f"Dettaglio: {type(e).__name__}"
    )
    st.stop()


# AUTENTICAZIONE CON USERNAME E PASSWORD
# Supabase Auth richiede un'email o un telefono. Per non chiedere l'email
# all'utente viene usato un indirizzo tecnico interno, mai mostrato nel sito.
EMAIL_SUFFIX = "@roulette-ai.invalid"
USERNAME_PATTERN = re.compile(r"^[A-Za-z0-9_]{3,20}$")


def username_valido(username):
    return bool(USERNAME_PATTERN.fullmatch(username.strip()))


def email_tecnica(username):
    return username.strip().lower() + EMAIL_SUFFIX


def trova_username(user_id):
    try:
        result = (
            admin_db.table("usernames")
            .select("username")
            .eq("user_id", str(user_id))
            .limit(1)
            .execute()
        )
        if result.data:
            return result.data[0]["username"]
    except Exception:
        pass
    return "utente"


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
    st.caption("Accedi al tuo account")

    tab_login, tab_register = st.tabs(["Accedi", "Crea account"])

    with tab_login:
        with st.form("login"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            login_submit = st.form_submit_button(
                "ENTRA",
                use_container_width=True
            )

        if login_submit:
            clean_username = username.strip().lower()

            if not username_valido(clean_username):
                st.error(
                    "Lo username deve avere 3–20 caratteri: "
                    "solo lettere, numeri e underscore."
                )
            elif not password:
                st.error("Inserisci la password.")
            else:
                try:
                    # Verifica che lo username sia registrato.
                    lookup = (
                        admin_db.table("usernames")
                        .select("user_id")
                        .eq("username", clean_username)
                        .limit(1)
                        .execute()
                    )

                    if not lookup.data:
                        st.error("Username o password non corretti.")
                    else:
                        result = db.auth.sign_in_with_password({
                            "email": email_tecnica(clean_username),
                            "password": password
                        })

                        if not result.session:
                            st.error("Username o password non corretti.")
                        else:
                            st.session_state.access_token = result.session.access_token
                            st.session_state.refresh_token = result.session.refresh_token
                            st.rerun()

                except Exception:
                    st.error("Username o password non corretti.")

    with tab_register:
        with st.form("register"):
            new_username = st.text_input(
                "Scegli uno username",
                max_chars=20,
                key="register_username"
            )
            new_password = st.text_input(
                "Crea una password",
                type="password",
                key="register_password"
            )
            confirm_password = st.text_input(
                "Ripeti la password",
                type="password"
            )
            register_submit = st.form_submit_button(
                "CREA ACCOUNT",
                use_container_width=True
            )

        if register_submit:
            clean_username = new_username.strip().lower()

            if not username_valido(clean_username):
                st.error(
                    "Lo username deve avere 3–20 caratteri: "
                    "solo lettere, numeri e underscore."
                )
            elif len(new_password) < 8:
                st.error("La password deve contenere almeno 8 caratteri.")
            elif new_password != confirm_password:
                st.error("Le password non coincidono.")
            else:
                created_user_id = None
                try:
                    # Controllo preventivo dello username.
                    existing = (
                        admin_db.table("usernames")
                        .select("user_id")
                        .eq("username", clean_username)
                        .limit(1)
                        .execute()
                    )

                    if existing.data:
                        st.error("Questo username è già utilizzato.")
                    else:
                        # Crea l'account senza inviare email di conferma.
                        result = admin_db.auth.admin.create_user({
                            "email": email_tecnica(clean_username),
                            "password": new_password,
                            "email_confirm": True
                        })

                        new_user = getattr(result, "user", None)
                        if new_user is None:
                            new_user = result

                        created_user_id = str(new_user.id)

                        # Salva l'associazione tra username e utente Auth.
                        admin_db.table("usernames").insert({
                            "user_id": created_user_id,
                            "username": clean_username
                        }).execute()

                        # Accesso automatico dopo la registrazione.
                        login_result = db.auth.sign_in_with_password({
                            "email": email_tecnica(clean_username),
                            "password": new_password
                        })

                        if login_result.session:
                            st.session_state.access_token = login_result.session.access_token
                            st.session_state.refresh_token = login_result.session.refresh_token
                            st.success("Account creato!")
                            st.rerun()
                        else:
                            st.success(
                                "Account creato. Ora puoi accedere con username e password."
                            )

                except Exception:
                    # Se l'account Auth è stato creato ma la mappatura non è
                    # riuscita, prova a rimuovere l'account incompleto.
                    if created_user_id:
                        try:
                            admin_db.auth.admin.delete_user(created_user_id)
                        except Exception:
                            pass
                    st.error(
                        "Registrazione non riuscita. Lo username potrebbe "
                        "essere già utilizzato; controlla anche i Secrets "
                        "di Supabase."
                    )

    st.caption(
        "Username: 3–20 caratteri, lettere, numeri o underscore. "
        "Password: almeno 8 caratteri."
    )
    st.stop()


user_id = str(current_user.id)
current_username = trova_username(user_id)


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


def risultato_mercato(numero, mercato):
    if numero == 0:
        return "Zero"

    if mercato == "Rosso/Nero":
        return colore(numero)

    if mercato == "Dozzina":
        return f"{(numero - 1) // 12 + 1}ª dozzina"

    if mercato == "Colonna":
        return f"{(numero - 1) % 3 + 1}ª colonna"

    return None


def categorie_mercato(mercato):
    if mercato == "Rosso/Nero":
        return ["Rosso", "Nero"]

    if mercato == "Dozzina":
        return ["1ª dozzina", "2ª dozzina", "3ª dozzina"]

    if mercato == "Colonna":
        return ["1ª colonna", "2ª colonna", "3ª colonna"]

    return []


# MOTORE DEI PATTERN
def analizza_pattern(numeri, mercato, minimo_casi=3, soglia_vantaggio=0.05):
    """
    Cerca sequenze finali di 2-5 risultati e controlla gli esiti
    successivi a sequenze uguali nello storico precedente.

    Restituisce una scelta soltanto quando ci sono abbastanza esempi
    e una differenza osservata rispetto alla frequenza di base.
    """

    categorie = categorie_mercato(mercato)

    if len(numeri) < 10 or not categorie:
        return None

    sequenza = [
        risultato_mercato(int(n), mercato)
        for n in numeri
    ]

    lunghezza = len(sequenza)
    candidati = []

    for lung_pattern in range(2, min(5, lunghezza // 2) + 1):
        inizio_pattern = lunghezza - lung_pattern
        pattern = sequenza[inizio_pattern:]
        storico_precedente = sequenza[:inizio_pattern]

        if len(storico_precedente) < lung_pattern + 1:
            continue

        successivi = Counter()
        occorrenze = 0

        for i in range(
            0,
            len(storico_precedente) - lung_pattern
        ):
            if storico_precedente[i:i + lung_pattern] == pattern:
                esito_successivo = storico_precedente[i + lung_pattern]
                successivi[esito_successivo] += 1
                occorrenze += 1

        if occorrenze < minimo_casi:
            continue

        frequenze_base = Counter(storico_precedente)
        totale_base = len(storico_precedente)

        for categoria in categorie:
            frequenza_pattern = successivi[categoria] / occorrenze
            frequenza_base = (
                frequenze_base[categoria] / totale_base
                if totale_base else 0
            )

            candidati.append({
                "scelta": categoria,
                "lunghezza": lung_pattern,
                "occorrenze": occorrenze,
                "vantaggio": frequenza_pattern - frequenza_base
            })

    if not candidati:
        return None

    candidati.sort(
        key=lambda c: (
            c["vantaggio"],
            c["occorrenze"],
            c["lunghezza"]
        ),
        reverse=True
    )

    migliore = candidati[0]

    if migliore["vantaggio"] < soglia_vantaggio:
        return None

    return migliore


def scegli_consiglio(numeri, mercato):
    """
    Restituisce sempre una scelta quando esistono risultati.
    Prima tenta l'analisi dei pattern; se non trova un candidato,
    usa il gruppo meno frequente nella finestra recente.
    """

    if not numeri:
        return None

    analisi = analizza_pattern(
        numeri,
        mercato,
        minimo_casi=3,
        soglia_vantaggio=0.05
    )

    if analisi:
        return analisi["scelta"]

    categorie = categorie_mercato(mercato)

    conteggi = {
        categoria: sum(
            risultato_mercato(n, mercato) == categoria
            for n in numeri
        )
        for categoria in categorie
    }

    minimo = min(conteggi.values())
    alternative = [
        categoria
        for categoria, conteggio in conteggi.items()
        if conteggio == minimo
    ]

    if len(alternative) == 1:
        return alternative[0]

    return alternative[len(numeri) % len(alternative)]


def registra_numero(numero, session_id):
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
    st.caption(f"Account: {current_username}")

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


# SESSIONI ACCESSIBILI
try:
    sessions = (
        db.table("sessions")
        .select("id, name, user_id")
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
    st.error(f"Errore caricamento sessioni: {e}")
    st.stop()


ruoli = {
    int(m["session_id"]): m["role"]
    for m in memberships
}


def ruolo_sessione(s):
    if str(s["user_id"]) == user_id:
        return "owner"
    return ruoli.get(int(s["id"]), "viewer")


# CREA SESSIONE
with st.expander("＋ Crea sessione", expanded=not sessions):
    with st.form("new_session"):
        nome = st.text_input("Nome sessione", value="Nuova sessione")
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
        .select("id, name, user_id")
        .order("id", desc=True)
        .execute()
        .data or []
    )
except Exception as e:
    st.error(f"Errore caricamento sessioni: {e}")
    st.stop()

if not sessions:
    st.info("Crea una sessione per cominciare.")
    st.stop()


sessioni_per_id = {
    int(s["id"]): s for s in sessions
}

sid = st.selectbox(
    "SESSIONE ATTIVA",
    list(sessioni_per_id.keys()),
    format_func=lambda session_id: sessioni_per_id[session_id]["name"]
)

sessione_attiva = sessioni_per_id[sid]
ruolo = ruolo_sessione(sessione_attiva)
puo_inserire = ruolo in ("owner", "editor")
proprietario = ruolo == "owner"

st.caption({
    "owner": "👑 Proprietario",
    "editor": "🎲 Puoi inserire numeri",
    "viewer": "👁️ Sola visualizzazione"
}.get(ruolo, "Tavolo condiviso"))


# CONDIVISIONE
with st.expander("👥 Condivisione e accessi"):
    st.caption("La condivisione riguarda soltanto la sessione attiva.")

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
                st.success("Accesso al tavolo completato.")
                st.rerun()
            except Exception as e:
                st.error(f"Codice non valido o non utilizzabile: {e}")
        else:
            st.warning("Inserisci un codice.")

    if proprietario:
        st.markdown("#### Crea invito")

        with st.form("create_invite"):
            ruolo_invito = st.selectbox(
                "Permessi",
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
            st.code(st.session_state["ultimo_invito"])
            st.caption(
                "Permessi: "
                + (
                    "sola visualizzazione"
                    if st.session_state.get("ultimo_invito_ruolo") == "viewer"
                    else "inserimento numeri"
                )
            )

        st.markdown("#### Membri")

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
                    c1, c2 = st.columns([3, 1])

                    c1.write(f"{uid} — {membro['role']}")

                    if uid != user_id:
                        with c2:
                            if st.button(
                                "Revoca",
                                key=f"revoca_{sid}_{uid}"
                            ):
                                db.table("session_members").delete().eq(
                                    "session_id", sid
                                ).eq("user_id", uid).execute()
                                st.rerun()
            else:
                st.caption("Nessun membro invitato.")

        except Exception as e:
            st.error(f"Errore caricamento membri: {e}")

        st.markdown("#### Inviti attivi")

        try:
            inviti = (
                db.table("session_invites")
                .select("id, code, role")
                .eq("session_id", sid)
                .eq("active", True)
                .execute()
                .data or []
            )

            for invito in inviti:
                c1, c2 = st.columns([3, 1])
                c1.write(f"{invito['code']} — {invito['role']}")

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


# CARICAMENTO NUMERI
def carica():
    return (
        db.table("spins")
        .select("id, number")
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


# TASTIERINO COMPATTO
st.divider()
st.subheader("🎲 Registra numero")
st.caption("Tocca il numero uscito.")

if puo_inserire:
    numeri = list(range(37))
    colonne_tastierino = st.columns(6, gap="small")

    for i, n in enumerate(numeri):
        with colonne_tastierino[i % 6]:
            if st.button(
                f"{simbolo(n)} {n}",
                key=f"num_{sid}_{n}",
                use_container_width=True
            ):
                registra_numero(n, sid)
else:
    st.info("Accesso in sola visualizzazione.")


# ANNULLA ULTIMO NUMERO
st.divider()

if rows:
    ultimo = rows[0]

    st.write(
        f"Ultimo numero: **{ultimo['number']}** "
        f"{simbolo(int(ultimo['number']))}"
    )

    if puo_inserire and st.button("↩️ ANNULLA ULTIMO"):
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
st.subheader("📊 Statistiche")

a, b, c = st.columns(3)
a.metric("Giri", totale)
b.metric("Rossi", sum(colore(n) == "Rosso" for n in numbers))
c.metric("Neri", sum(colore(n) == "Nero" for n in numbers))

red = sum(colore(n) == "Rosso" for n in numbers)
black = sum(colore(n) == "Nero" for n in numbers)
zero = sum(n == 0 for n in numbers)

st.markdown("#### Percentuali")

a, b, c = st.columns(3)
a.metric("🔴 Rosso", f"{percentuale(red, totale):.2f}%")
b.metric("⚫ Nero", f"{percentuale(black, totale):.2f}%")
c.metric("🟢 Zero", f"{percentuale(zero, totale):.2f}%")


# ANALISI ULTIMI GIRI
st.divider()
st.subheader("⏱️ Ultimi giri")

periodo = st.selectbox(
    "Intervallo",
    [20, 50, 100],
    index=0
)

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


# FREQUENZA NUMERI
st.divider()
st.subheader("🔢 Frequenza numeri")
st.caption(f"Totale: {totale} giri.")

st.bar_chart({
    "Uscite": {
        str(n): numbers.count(n)
        for n in range(37)
    }
})

if totale:
    frequenze = Counter(numbers)
    max_freq = max(frequenze.values())
    min_freq = min(frequenze.get(n, 0) for n in range(37))

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Più usciti**")
        st.write(", ".join(
            str(n) for n in range(37)
            if frequenze.get(n, 0) == max_freq
        ))
        st.caption(f"{max_freq} uscite")

    with c2:
        st.markdown("**Meno usciti**")
        st.write(", ".join(
            str(n) for n in range(37)
            if frequenze.get(n, 0) == min_freq
        ))
        st.caption(f"{min_freq} uscite")


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
        st.write(
            f"{i}ª: {val} ({percentuale(val, totale):.2f}%)"
        )

with r:
    st.markdown("**Colonne**")
    for i, val in enumerate(colonne, 1):
        st.write(
            f"{i}ª: {val} ({percentuale(val, totale):.2f}%)"
        )


# ANALISI DELLE PUNTATE
st.divider()
st.subheader("🧠 Analisi puntate")

mercato = st.selectbox(
    "Mercato",
    [
        "Rosso / Nero",
        "Pari / Dispari",
        "Basso / Alto",
        "Dozzine",
        "Colonne"
    ]
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
            n != 0 and (n - 1) % 3 == i
            for n in recenti
        )
        for i in range(3)
    }

if nr:
    for label, value in gruppi.items():
        st.write(
            f"{label}: {value}/{nr} "
            f"({percentuale(value, nr):.2f}%)"
        )
else:
    st.caption("Registra qualche giro per vedere le statistiche.")


# NUMERI CALDI E FREDDI
st.divider()
st.subheader("🔥 Numeri caldi e freddi")

if nr:
    freq_recenti = Counter(recenti)

    caldi = sorted(
        range(37),
        key=lambda n: (-freq_recenti.get(n, 0), n)
    )[:5]

    freddi = sorted(
        range(37),
        key=lambda n: (freq_recenti.get(n, 0), n)
    )[:5]

    col_caldi, col_freddi = st.columns(2)

    with col_caldi:
        st.markdown("**🔥 Più usciti**")
        for n in caldi:
            st.write(
                f"{simbolo(n)} {n} · {freq_recenti.get(n, 0)}"
            )

    with col_freddi:
        st.markdown("**❄️ Meno usciti**")
        for n in freddi:
            st.write(
                f"{simbolo(n)} {n} · {freq_recenti.get(n, 0)}"
            )


# CONSIGLIO AUTOMATICO
st.divider()
st.subheader("🎯 Consiglio")

mercato_consiglio = st.selectbox(
    "Tipo di puntata",
    ["Rosso/Nero", "Dozzina", "Colonna"],
    key="mercato_consiglio"
)

if nr:
    scelta = scegli_consiglio(
        recenti,
        mercato_consiglio
    )

    if scelta:
        st.markdown(f"### {scelta}")

        if puo_inserire:
            if st.button("💾 SALVA CONSIGLIO", key="salva_consiglio"):
                try:
                    db.table("roulette_tips").insert({
                        "user_id": user_id,
                        "session_id": sid,
                        "market": mercato_consiglio,
                        "suggestion": scelta,
                        "stake": 1.0
                    }).execute()

                    st.success("Consiglio salvato.")
                    st.rerun()

                except Exception as e:
                    st.error(f"Errore salvataggio consiglio: {e}")


# STORICO CONSIGLI COMPATTO
st.divider()
st.subheader("📚 Storico consigli")

try:
    consigli = (
        db.table("roulette_tips")
        .select("id, market, suggestion, result_number")
        .eq("session_id", sid)
        .order("id", desc=True)
        .limit(10)
        .execute()
        .data or []
    )

    if consigli:
        for tip in consigli:
            numero_esito = tip["result_number"]

            if numero_esito is None:
                esito = "⏳ In attesa"
            else:
                preso = esito_preso(
                    tip["market"],
                    tip["suggestion"],
                    int(numero_esito)
                )
                esito = "✅ Preso" if preso else "❌ Non preso"

            c1, c2 = st.columns([3, 2])

            c1.markdown(f"**{tip['suggestion']}**")
            c1.caption(tip["market"])
            c2.write(esito)

            if numero_esito is not None:
                c2.caption(
                    f"{simbolo(int(numero_esito))} {numero_esito}"
                )

            st.divider()

    else:
        st.caption("Nessun consiglio salvato.")

except Exception as e:
    st.error(f"Errore caricamento storico: {e}")


# ULTIMI RISULTATI
st.subheader("🕘 Ultimi risultati")

if numbers:
    st.write(" → ".join(
        f"{simbolo(n)} {n}"
        for n in numbers[-10:][::-1]
    ))

    if len(numbers) > 10:
        if "mostra_altri_risultati" not in st.session_state:
            st.session_state.mostra_altri_risultati = False

        if st.button(
            "⌄ Mostra altri"
            if not st.session_state.mostra_altri_risultati
            else "⌃ Mostra meno",
            key="toggle_risultati"
        ):
            st.session_state.mostra_altri_risultati = (
                not st.session_state.mostra_altri_risultati
            )
            st.rerun()

        if st.session_state.mostra_altri_risultati:
            st.write(" → ".join(
                f"{simbolo(n)} {n}"
                for n in numbers[-50:-10][::-1]
            ))
else:
    st.caption("Nessun risultato.")