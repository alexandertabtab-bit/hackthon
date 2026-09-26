import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
from itertools import combinations
import re

st.set_page_config(page_title="ParcelShield AI", page_icon="📦", layout="wide")

CANDIDATE_LINK_THRESHOLD = 0.45
GROUP_MIN_SIZE = 3

# Official weights -- matches the six-indicator table exactly (sums to 100%)
WEIGHTS = {
    "Frequency": 0.25,
    "Product Repetition": 0.20,
    "Commercial Volume": 0.20,
    "Network Linkage": 0.15,
    "Declared Business Status": 0.10,
    "Value Pattern": 0.10,
}
assert abs(sum(WEIGHTS.values()) - 1.0) < 1e-9, "Weights must sum to 100%"

# ==============================================================================
# DATA (synthetic, for hackathon demonstration only)
# One flagship HIGH-RISK case (12 parcels / 3 weeks -- a realistic splitting
# scale), plus MONITOR and LOW examples so the demo shows the full spectrum.
# ==============================================================================

@st.cache_data
def load_data():
    rows=[]

    # --- Flagship case: Ahmed, 12 split iPhone-case parcels over 3 weeks ---
    flagship_desc=['Coque iPhone 15 transparente','iPhone 15 phone case','Coques pour iPhone 15',
        'Etuis téléphone iPhone 15','Housse iPhone 15 silicone','iPhone 15 protective case',
        'Coque de protection iPhone','Etui iPhone antichoc','iPhone 15 back cover',
        'Coques iPhone lot de 2','Housse transparente iPhone','iPhone case bulk']
    flagship_names=['Ahmed Ben Salah','Ahmed B. Salah','A. Ben Salah','Ahmed Ben Salah','A.B. Salah',
        'Ahmed Ben Salah','Ben Salah Ahmed','A. Ben Salah','Ahmed B Salah','Ahmed Ben Salah',
        'A. Ben Salah','Ahmed Ben Salah']
    for i in range(12):
        rows.append([f"P{i+1:03d}",flagship_names[i],"12 Rue Ibn Khaldoun, Ariana","22123456",
            (pd.Timestamp("2026-09-01")+pd.Timedelta(days=i*2)).strftime("%Y-%m-%d"),
            flagship_desc[i],3+i%3,18+i,"China","No"])
    n0=len(rows)

    # --- Monitor-tier case: Sonia, false eyelashes, moderate signals ---
    rows += [
    [f"P{n0+1:03d}","Sonia Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-02","Faux cils cosmétiques",8,31,"Turkey","No"],
    [f"P{n0+2:03d}","Sonia T. Trabelsi","8 Rue Marseille Tunis","55112233","2026-09-06","Cils artificiels",10,39,"Turkey","No"],
    [f"P{n0+3:03d}","S. Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-11","Lot de faux cils",9,35,"Turkey","No"],
    ]
    n1=len(rows)

    # --- Registered-business case: Youssef, bracelets -- demonstrates that a
    # declared business is never penalized on that indicator, even if other
    # signals still keep the case in view for monitoring ---
    rows += [
    [f"P{n1+1:03d}","Youssef Gharbi","21 Avenue Habib Bourguiba, Sousse","98112233","2026-09-03","Bracelets acier fantaisie",6,29,"China","Yes"],
    [f"P{n1+2:03d}","Y. Gharbi","21 Av Habib Bourguiba Sousse","98112233","2026-09-09","Bracelets métalliques fantaisie",7,34,"China","Yes"],
    [f"P{n1+3:03d}","Youssef Gharbi","21 Avenue Habib Bourguiba, Sousse","98112233","2026-09-15","Bijoux fantaisie bracelets",6,30,"China","Yes"],
    ]
    n2=len(rows)

    # --- Singles: normal personal deliveries, not grouped (too few links) ---
    singles = [
    ["Mariem Jaziri","4 Rue des Jasmins, Nabeul","20123456","2026-09-01","Lampe de bureau LED",1,48,"Turkey","No"],
    ["Karim Mejri","16 Rue Carthage, Tunis","50111222","2026-09-02","Sac à dos scolaire",1,62,"China","No"],
    ["Nour Ben Amor","7 Rue du Lac, Tunis","29123455","2026-09-03","Écouteurs Bluetooth",1,74,"China","No"],
    ["Hatem Khelifi","2 Rue El Amal, Sfax","97112244","2026-09-04","Mug isotherme",1,35,"China","No"],
    ["Amira Saidi","10 Rue Farhat Hached, Monastir","23117890","2026-09-05","Robe femme",1,91,"Turkey","No"],
    ["Walid Nasri","19 Rue de la République, Bizerte","54119988","2026-09-07","Clavier mécanique",1,120,"China","No"],
    ["Sarra Ayari","5 Rue Ibn Sina, Ariana","98117766","2026-09-08","Livre de cuisine",2,44,"France","No"],
    ["Rami Ben Salem","13 Rue du Stade, Sousse","27114567","2026-09-10","Chargeur USB-C",1,27,"China","No"],
    ["Ines Mansour","22 Rue de l'Université, Tunis","55116789","2026-09-12","Chaussures femme",1,83,"Turkey","No"],
    ["Omar Haddad","3 Rue 18 Janvier, Sfax","20119876","2026-09-14","T-shirt homme",2,52,"Turkey","No"],
    ]
    for i,s in enumerate(singles):
        rows.append([f"P{n2+i+1:03d}",*s])
    n3=len(rows)

    # --- Low/borderline case: Leila, weak signals across the board ---
    rows += [
    [f"P{n3+1:03d}","Leila Fendri","30 Rue de la Liberté, Tunis","24556677","2026-09-01","Sac a main simili cuir",2,65,"France","No"],
    [f"P{n3+2:03d}","Leila F.","30 Rue Liberte, Tunis","24556677","2026-09-15","Petit sac femme",1,70,"France","No"],
    [f"P{n3+3:03d}","L. Fendri","30 Rue de la Liberte Tunis","24556677","2026-09-28","Pochette accessoire mode",1,60,"France","No"],
    ]
    n4=len(rows)

    # --- Identity-gap case: same household, DIFFERENT phone per order --
    # exercises why identity must be a soft scoring signal, not a hard gate.
    rows += [
    [f"P{n4+1:03d}","Fatma Kortli","Cite Ennasr 2, Ariana","21556677","2026-09-02","Robe soirée sequins",1,140,"Turkey","No"],
    [f"P{n4+2:03d}","Mohamed Kortli","Cite Ennasr 2, Ariana","98223344","2026-09-05","Robes de soirée femme",2,150,"Turkey","No"],
    [f"P{n4+3:03d}","M. Kortli","Cite Ennasr 2, Ariana","98223344","2026-09-09","Robe habillée femme",1,145,"Turkey","No"],
    ]

    return pd.DataFrame(rows,columns=["parcel_id","name","address","phone","date","description",
        "quantity","value_tnd","origin","declared_business_status"]).assign(date=lambda x:pd.to_datetime(x.date))

df=load_data()

# ==============================================================================
# TEXT SIMILARITY HELPERS
# ==============================================================================

def norm(s):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç\s]"," ",str(s).lower())).strip()

def sim(a,b): return SequenceMatcher(None,norm(a),norm(b)).ratio()

def jaccard(a,b):
    A=set(norm(a).split()); B=set(norm(b).split())
    return len(A&B)/len(A|B) if A and B else 0

# PROTOTYPE lexicon of product families (French/English synonyms). Chosen as
# an explainable placeholder over a black-box embedding model, since every
# match must be justifiable to a human officer. PRODUCTION UPGRADE PATH: real
# postal parcels carry a customs tariff/HS code on the CN22/CN23 declaration
# -- matching on that structured code instead of free-text description
# removes this limitation entirely.
PRODUCT_FAMILIES = [
    ["iphone","coque","case","étui","etui","housse"],
    ["cils","faux","cosmetique","cosmétiques","maquillage"],
    ["bracelet","bijou","métallique","metallique","acier","bijoux"],
    ["casque","ecouteur","écouteur","headphone","earphone","audio","bluetooth"],
    ["sac","pochette","handbag","cabas"],
    ["robe","dress","habillée","habille","soirée","soiree"],
    ["montre","watch","smartwatch","connectee","connectée"],
    ["chargeur","cable","câble","usb","adaptateur"],
]

def product_sim(a,b):
    j=jaccard(a,b)
    if j>=.35: return max(j,sim(a,b))
    aa,bb=norm(a),norm(b)
    for f in PRODUCT_FAMILIES:
        if any(x in aa for x in f) and any(x in bb for x in f): return .86
    return sim(a,b)*.8

def identity(a,b):
    """
    Identity confidence (0-1): name 25% + address 35% + phone 40%.
    Used both for candidate grouping (loose threshold) and, precisely, as
    the Network Linkage indicator (15% weight) in the final score.
    """
    name=sim(a["name"],b["name"])
    addr=sim(a["address"],b["address"])
    phone=1 if str(a["phone"])==str(b["phone"]) else 0
    return .25*name+.35*addr+.40*phone

# ==============================================================================
# GROUPING (candidate linking)
# ==============================================================================

def groups():
    """
    Union-find candidate grouping using identity() at a LOW threshold (0.45),
    deliberately looser than a strict confirmation bar. Grouping is a
    recall-oriented "is this worth looking at together" step; the precise,
    weighted identity score (15%) is what actually drives the risk number.
    Keeping these separate means a same-address/same-surname/different-phone
    pattern can still be grouped and scored instead of being silently
    dropped before scoring ever runs.
    """
    parent=list(range(len(df)))
    def find(x):
        while parent[x]!=x:
            parent[x]=parent[parent[x]]
            x=parent[x]
        return x
    def union(a,b):
        a,b=find(a),find(b)
        if a!=b: parent[b]=a
    for i,j in combinations(range(len(df)),2):
        if identity(df.iloc[i],df.iloc[j])>=CANDIDATE_LINK_THRESHOLD: union(i,j)
    out={}
    for i in range(len(df)): out.setdefault(find(i),[]).append(i)
    return [x for x in out.values() if len(x)>=GROUP_MIN_SIZE]

# ==============================================================================
# SIX INDICATORS -- matches the official table exactly
# ==============================================================================

def calc_frequency_score(n_parcels, span_days):
    """
    Frequency (25% weight): 'how often activity occurs'. Measured as a rate
    (parcels per week) rather than a raw monthly-transaction count, because
    the unit of analysis here is a short-window parcel CLUSTER (already
    pre-filtered to a few weeks), not a whole seller profile observed over a
    month. Reusing month-scale bins on a week-scale cluster would silently
    under-score genuine splitting patterns (verified while building this:
    it dropped a real positive from HIGH-RISK to MONITOR for no real-world
    reason). PROTOTYPE bins: <1/week -> 10 | <2 -> 35 | <3 -> 55 | <5 -> 75 | >=5 -> 100
    """
    rate = n_parcels / max(span_days, 1) * 7
    if rate < 1: return 10
    elif rate < 2: return 35
    elif rate < 3: return 55
    elif rate < 5: return 75
    else: return 100

def calc_commercial_volume_score(total_qty):
    """Commercial Volume (20%): PROTOTYPE bins <=5->10 | <=15->30 | <=35->60 | <=60->80 | >60->100"""
    if total_qty<=5: return 10
    elif total_qty<=15: return 30
    elif total_qty<=35: return 60
    elif total_qty<=60: return 80
    else: return 100

def calc_declared_status_score(is_registered, n_parcels, total_value):
    """
    Declared Business Status (10%): registered -> 0. Unregistered activity is
    scaled by strength (per the brief: "high activity, no declared business
    = high signal"), not a flat switch.
    """
    if is_registered: return 0
    if n_parcels>=20 or total_value>=2000: return 100
    elif n_parcels>=10 or total_value>=800: return 70
    elif n_parcels>=5 or total_value>=200: return 40
    else: return 15

def calc_value_pattern_score(total_value):
    """
    Value Pattern (10%): HIGH cumulative value = higher signal, matching the
    official table ("high cumulative value inconsistent with declared
    profile"). PROTOTYPE bins: <=200->10 | <=800->30 | <=2000->60 | <=5000->80 | >5000->100
    """
    if total_value<=200: return 10
    elif total_value<=800: return 30
    elif total_value<=2000: return 60
    elif total_value<=5000: return 80
    else: return 100

def score(g):
    x=df.iloc[g].sort_values("date")
    ids=[identity(x.iloc[i],x.iloc[j]) for i,j in combinations(range(len(x)),2)]
    ps=[product_sim(x.iloc[i].description,x.iloc[j].description) for i,j in combinations(range(len(x)),2)]
    ident_pct=sum(ids)/len(ids)*100
    content_pct=sum(ps)/len(ps)*100
    span=(x.date.max()-x.date.min()).days
    n_parcels=len(x)
    total_qty=int(x.quantity.sum())
    total_value=float(x.value_tnd.sum())
    is_registered=(x["declared_business_status"]=="Yes").any()

    indicators={
        "Frequency": calc_frequency_score(n_parcels, span),
        "Product Repetition": content_pct,
        "Commercial Volume": calc_commercial_volume_score(total_qty),
        "Network Linkage": ident_pct,
        "Declared Business Status": calc_declared_status_score(is_registered, n_parcels, total_value),
        "Value Pattern": calc_value_pattern_score(total_value),
    }
    final=round(sum(indicators[k]*WEIGHTS[k] for k in WEIGHTS),2)
    return dict(group=g, score=final, indicators=indicators, n_parcels=n_parcels,
                total_qty=total_qty, total_value=total_value, span=span, is_registered=is_registered)

gs=groups()
results=sorted([score(g) for g in gs],key=lambda r:r["score"],reverse=True)

# ==============================================================================
# LLM EXPLANATION (real call if an API key is configured, honest fallback otherwise)
# ==============================================================================

def build_llm_prompt(label, r):
    high=[k for k,v in r["indicators"].items() if v>=60]
    return f"""[SYSTEM INSTRUCTION]
Tu es un assistant IA pour les finances publiques evaluant des schemas de transactions
pouvant etre compatibles avec une activite commerciale non declaree (colis fractionnes).
Explique les signaux clairement et neutralement pour un agent humain.

REGLES:
1. Ne formule aucune accusation de fraude ou d'acte illegal.
2. Mets en avant uniquement les signaux dominants.
3. Rappelle explicitement qu'une verification humaine est obligatoire avant toute action.

[DONNEES DU CAS]
Groupe: {label}
Score composite: {r['score']:.0f}/100
Colis lies: {r['n_parcels']}
Quantite cumulee: {r['total_qty']}
Valeur cumulee: {r['total_value']:.0f} TND
Statut declare: {'Entreprise declaree' if r['is_registered'] else 'Non declare'}
Signaux forts (>=60): {', '.join(high) if high else 'aucun'}

[INDICATEURS]
- Frequence (25%): {r['indicators']['Frequency']:.0f}/100
- Repetition produit (20%): {r['indicators']['Product Repetition']:.0f}/100
- Volume commercial (20%): {r['indicators']['Commercial Volume']:.0f}/100
- Reseau/identite (15%): {r['indicators']['Network Linkage']:.0f}/100
- Statut declare (10%): {r['indicators']['Declared Business Status']:.0f}/100
- Motif de valeur (10%): {r['indicators']['Value Pattern']:.0f}/100

TACHE: Redige 3 points expliquant les signaux les plus determinants pour l'agent.
"""

def get_llm_explanation(label, r):
    prompt=build_llm_prompt(label, r)
    api_key = st.secrets.get("ANTHROPIC_API_KEY") if hasattr(st,"secrets") else None
    if api_key:
        try:
            import anthropic
            client=anthropic.Anthropic(api_key=api_key)
            msg=client.messages.create(model="claude-sonnet-4-6", max_tokens=300,
                messages=[{"role":"user","content":prompt}])
            return "".join(b.text for b in msg.content if hasattr(b,"text")), True
        except Exception as e:
            return f"[Appel LLM impossible ({e}). Voici le prompt seul :]\n\n{prompt}", False

    high=[k for k,v in r["indicators"].items() if v>=60]
    if r["score"]>=60:
        text=(f"- Ce groupe obtient {r['score']:.0f}/100, tire principalement par "
              f"{', '.join(high) if high else 'plusieurs signaux combines'}.\n"
              f"- Ce schema reflete uniquement des donnees comportementales -- il n'etablit "
              f"ni intention ni faute.\n"
              f"- Verification humaine requise avant toute action.")
    elif r["score"]>=40:
        text=("- Plusieurs signaux existent mais restent insuffisants pour une alerte forte.\n"
              "- Le dossier est conserve pour suivi, sans action immediate.\n"
              "- A reevaluer si de nouveaux colis lies apparaissent.")
    else:
        text=("- Les signaux observes ne justifient pas une alerte a ce stade.\n"
              "- Aucune action necessaire pour l'instant.")
    return f"[EXEMPLE STATIQUE -- aucune cle API live utilisee]\n\n{text}", False

# ==============================================================================
# UI
# ==============================================================================

st.title("📦 ParcelShield AI")
st.subheader("Détection de fractionnement de colis — Prototype")
st.caption("Hackathon • flux postal simulé • aucune décision automatique de fraude")

with st.expander("ℹ️ Méthodologie & limites du prototype"):
    st.markdown("""
**Un seul modèle à six indicateurs, appliqué ici au niveau d'un cluster de colis**
(plutôt qu'à un profil vendeur global) : Fréquence 25%, Répétition produit 20%,
Volume commercial 20%, Réseau/identité 15%, Statut déclaré 10%, Motif de valeur 10%.
Les poids sont identiques à notre modèle de profil vendeur ; seule l'unité
d'analyse change (un cluster de colis détecté vs. un profil sur une période).

**L'origine du colis n'entre dans aucun calcul de score** — affichée à titre
informatif uniquement, pour éviter tout profilage par pays d'origine.

**La similarité de produit est un lexique explicable, pas un modèle sémantique.**
Une version de production s'appuierait sur le code tarifaire douanier (CN22/CN23)
plutôt que sur le texte libre.

**Tous les poids et seuils sont des hypothèses de prototype**, à calibrer sur des
données réelles labellisées avant tout déploiement.

**Aucune décision n'est automatisée.** Le score priorise ; la vérification
humaine reste obligatoire avant toute action.
""")

st.sidebar.header("Prototype")
st.sidebar.info("Les données sont synthétiques. Elles servent à démontrer le pipeline de détection.")
if st.sidebar.checkbox("Afficher les données",True):
    st.markdown("### 1. Flux de colis simulé")
    st.dataframe(df,use_container_width=True,hide_index=True)

st.divider()
st.markdown("### 2. Analyse multi-colis")
a,b,c,d=st.columns(4)
a.metric("Colis analysés",len(df))
b.metric("Groupes candidats",len(results))
alerts=sum(r["score"]>=60 for r in results)
watch=sum(40<=r["score"]<60 for r in results)
c.metric("Alertes",alerts)
d.metric("À surveiller",watch)

table=[]
for i,r in enumerate(results,1):
    table.append([f"#{i:02d}",r["n_parcels"],r["total_qty"],r["span"],
                  "Oui" if r["is_registered"] else "Non",
                  f"{r['indicators']['Network Linkage']:.0f}%",
                  f"{r['indicators']['Product Repetition']:.0f}%",
                  f"{r['score']:.0f}/100",
                  "🔴 Vérification humaine" if r["score"]>=60 else ("🟠 À surveiller" if r["score"]>=40 else "🟢 Ignoré")])
st.dataframe(pd.DataFrame(table,columns=["Groupe","Colis","Qté cumulée","Période (j)","Entreprise déclarée","Identité","Produits","Score","Statut"]),use_container_width=True,hide_index=True)

labels=[f"Groupe #{i:02d} — {r['score']:.0f}/100" for i,r in enumerate(results,1)]
choice=st.selectbox("🔎 Examiner un groupe",labels)
r=results[labels.index(choice)]
g=df.iloc[r["group"]].sort_values("date")

st.divider()
if r["score"]>=60:
    st.error(f"🔴 ALERTE — {choice}\n\nLe système recommande une vérification humaine. Le score est un signal, pas une décision automatique de fraude.")
elif r["score"]>=40: st.warning("🟠 À surveiller — plusieurs signaux sont présents.")
else: st.success("🟢 Aucun signal suffisamment fort.")

x,y,z=st.columns(3)
x.metric("Score composite",f"{r['score']:.0f}/100")
y.metric("Réseau/identité",f"{r['indicators']['Network Linkage']:.0f}%")
z.metric("Répétition produit",f"{r['indicators']['Product Repetition']:.0f}%")

st.markdown("### 🔬 Décomposition du score (six indicateurs officiels)")
st.dataframe(pd.DataFrame({
"Indicateur":["Fréquence","Répétition produit","Volume commercial","Réseau/identité","Statut déclaré","Motif de valeur"],
"Poids":["25%","20%","20%","15%","10%","10%"],
"Valeur":[f"{r['indicators']['Frequency']:.0f}%",f"{r['indicators']['Product Repetition']:.0f}%",
          f"{r['indicators']['Commercial Volume']:.0f}%",f"{r['indicators']['Network Linkage']:.0f}%",
          f"{r['indicators']['Declared Business Status']:.0f}%",f"{r['indicators']['Value Pattern']:.0f}%"]}),
use_container_width=True,hide_index=True)

st.markdown("### 📦 Colis liés")
st.dataframe(g,use_container_width=True,hide_index=True)


