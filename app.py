import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
from itertools import combinations
import re

st.set_page_config(page_title="ParcelShield AI", page_icon="📦", layout="wide")

CANDIDATE_LINK_THRESHOLD = 0.45   # loose net for grouping (recall-oriented) -- see identity()
GROUP_MIN_SIZE = 3

# ==============================================================================
# DATA (synthetic, for hackathon demonstration only)
# ==============================================================================

@st.cache_data
def load_data():
    rows=[
    ["P001","Ahmed Ben Salah","12 Rue Ibn Khaldoun, Ariana","22123456","2026-09-01","Coque iPhone 15 transparente",3,18,"China"],
    ["P002","Ahmed B. Salah","12 Ibn Khaldoun Ariana","22123456","2026-09-04","iPhone 15 phone case",4,23,"China"],
    ["P003","A. Ben Salah","12 Rue Ibn Khaldoun Ariana","22123456","2026-09-08","Coques pour iPhone 15",5,27,"China"],
    ["P004","Ahmed Ben Salah","12 Rue Ibn Khaldoun, Ariana","22123456","2026-09-12","Etuis téléphone iPhone 15",4,22,"China"],
    ["P005","Sonia Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-02","Faux cils cosmétiques",8,31,"Turkey"],
    ["P006","Sonia T. Trabelsi","8 Rue Marseille Tunis","55112233","2026-09-06","Cils artificiels",10,39,"Turkey"],
    ["P007","S. Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-11","Lot de faux cils",9,35,"Turkey"],
    ["P008","Youssef Gharbi","21 Avenue Habib Bourguiba, Sousse","98112233","2026-09-03","Bracelets acier fantaisie",6,29,"China"],
    ["P009","Y. Gharbi","21 Av Habib Bourguiba Sousse","98112233","2026-09-09","Bracelets métalliques fantaisie",7,34,"China"],
    ["P010","Youssef Gharbi","21 Avenue Habib Bourguiba, Sousse","98112233","2026-09-15","Bijoux fantaisie bracelets",6,30,"China"],
    ["P011","Mariem Jaziri","4 Rue des Jasmins, Nabeul","20123456","2026-09-01","Lampe de bureau LED",1,48,"Turkey"],
    ["P012","Karim Mejri","16 Rue Carthage, Tunis","50111222","2026-09-02","Sac à dos scolaire",1,62,"China"],
    ["P013","Nour Ben Amor","7 Rue du Lac, Tunis","29123455","2026-09-03","Écouteurs Bluetooth",1,74,"China"],
    ["P014","Hatem Khelifi","2 Rue El Amal, Sfax","97112244","2026-09-04","Mug isotherme",1,35,"China"],
    ["P015","Amira Saidi","10 Rue Farhat Hached, Monastir","23117890","2026-09-05","Robe femme",1,91,"Turkey"],
    ["P016","Walid Nasri","19 Rue de la République, Bizerte","54119988","2026-09-07","Clavier mécanique",1,120,"China"],
    ["P017","Sarra Ayari","5 Rue Ibn Sina, Ariana","98117766","2026-09-08","Livre de cuisine",2,44,"France"],
    ["P018","Rami Ben Salem","13 Rue du Stade, Sousse","27114567","2026-09-10","Chargeur USB-C",1,27,"China"],
    ["P019","Ines Mansour","22 Rue de l'Université, Tunis","55116789","2026-09-12","Chaussures femme",1,83,"Turkey"],
    ["P020","Omar Haddad","3 Rue 18 Janvier, Sfax","20119876","2026-09-14","T-shirt homme",2,52,"Turkey"],
    # Genuine "monitor"-tier example: weaker signals across the board, so the
    # demo actually exercises all three tiers instead of only alert/ignored.
    ["P021","Leila Fendri","30 Rue de la Liberté, Tunis","24556677","2026-09-01","Sac a main simili cuir",2,65,"France"],
    ["P022","Leila F.","30 Rue Liberte, Tunis","24556677","2026-09-15","Petit sac femme",1,70,"France"],
    ["P023","L. Fendri","30 Rue de la Liberte Tunis","24556677","2026-09-28","Pochette accessoire mode",1,60,"France"],
    # Same household, DIFFERENT phone per order, names related but not string-
    # similar: exercises the identity structural gap directly (see identity()).
    ["P024","Fatma Kortli","Cite Ennasr 2, Ariana","21556677","2026-09-02","Robe soirée sequins",1,140,"Turkey"],
    ["P025","Mohamed Kortli","Cite Ennasr 2, Ariana","98223344","2026-09-05","Robes de soirée femme",2,150,"Turkey"],
    ["P026","M. Kortli","Cite Ennasr 2, Ariana","98223344","2026-09-09","Robe habillée femme",1,145,"Turkey"],
    ]
    return pd.DataFrame(rows,columns=["parcel_id","name","address","phone","date","description","quantity","value_tnd","origin"]).assign(date=lambda x:pd.to_datetime(x.date))

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
# match must be justifiable to a human officer in a government-review
# context. PRODUCTION UPGRADE PATH: real postal parcels carry a customs
# tariff/HS code on the CN22/CN23 declaration -- matching on that structured
# code instead of free-text description removes this limitation entirely and
# is the recommended next step beyond this prototype.
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
    Weighted identity confidence (0-1): name 25% + address 35% + phone 40%.
    BUGFIX: the previous version read a.name / b.name. On a pandas Series,
    .name is a RESERVED attribute holding the row's index label, not a way
    to access a column called "name" -- so name-similarity was silently
    comparing row index numbers (almost always 0.0) instead of actual
    customer names, for every single score ever produced by this app.
    Fixed here with dict-style column access: a["name"], b["name"].
    """
    name=sim(a["name"],b["name"])
    addr=sim(a["address"],b["address"])
    phone=1 if str(a["phone"])==str(b["phone"]) else 0
    return .25*name+.35*addr+.40*phone

# ==============================================================================
# GROUPING (candidate linking) & SCORING
# ==============================================================================

def groups():
    """
    Union-find candidate grouping using the SAME identity() function used for
    scoring, but at a LOWER threshold (0.45) than before (0.72). This is
    deliberate: identity is meant to be a soft 15%-weight signal in the final
    score, not a hard gate that silently drops real splitting patterns before
    they are ever scored (e.g. a household ordering under different phone
    numbers). 0.45 sits in the natural gap on this dataset between real (if
    weak) identity links (0.52+) and coincidental stranger overlap (<=0.36).
    On real data this cutoff should be re-validated against a labeled sample.
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

def score(g):
    x=df.iloc[g].sort_values("date")
    ids=[identity(x.iloc[i],x.iloc[j]) for i,j in combinations(range(len(x)),2)]
    ps=[product_sim(x.iloc[i].description,x.iloc[j].description) for i,j in combinations(range(len(x)),2)]
    ident=sum(ids)/len(ids); content=sum(ps)/len(ps)
    span=(x.date.max()-x.date.min()).days
    # Renamed from "Régularité temporelle": this measures how TIGHTLY the
    # dates cluster (a short span), not the periodicity of the intervals
    # between them. The old label overclaimed what the metric measures.
    temporal_concentration=max(0,min(1,(21-span)/21))
    qty=max(0,min(1,(x.quantity.sum()-2)/12))
    # LOWER average declared value -> HIGHER signal, by design: this module
    # targets customs de-minimis threshold evasion (splitting one shipment
    # into several low-value parcels to dodge duties) -- the OPPOSITE
    # value-direction assumption from a general "high cumulative revenue"
    # undeclared-business detector (see methodology note below).
    value=max(0,min(1,(100-x.value_tnd.mean())/100))
    total=100*(.30*content+.25*temporal_concentration+.20*qty+.15*ident+.10*value)
    return dict(group=g,identity=ident,content=content,temporal=temporal_concentration,
                quantity=qty,value=value,score=total,total_qty=int(x.quantity.sum()),span=span)

gs=groups()
results=sorted([score(g) for g in gs],key=lambda r:r["score"],reverse=True)

# ==============================================================================
# LLM EXPLANATION (real call if an API key is configured, honest fallback otherwise)
# ==============================================================================

def build_llm_prompt(label, r):
    return f"""[SYSTEM INSTRUCTION]
Tu es un assistant IA pour les finances publiques qui évalue des schémas de transactions
pouvant être compatibles avec un fractionnement de colis pour éviter des seuils douaniers.
Explique les signaux de façon claire et neutre pour un agent humain.

RÈGLES:
1. Ne formule aucune accusation de fraude ou d'acte illégal.
2. Mets en avant uniquement les signaux comportementaux dominants.
3. Rappelle explicitement qu'une vérification humaine est obligatoire avant toute action.

[DONNÉES DU CAS]
Groupe: {label}
Score composite: {r['score']:.0f}/100
Colis liés: {len(r['group'])}
Quantité cumulée: {r['total_qty']}
Période: {r['span']} jours

[SIGNAUX]
- Homogénéité du contenu (30%): {r['content']*100:.0f}%
- Concentration temporelle (25%): {r['temporal']*100:.0f}%
- Anomalie de quantité (20%): {r['quantity']*100:.0f}%
- Confiance d'identité (15%): {r['identity']*100:.0f}%
- Écart de valeur (10%): {r['value']*100:.0f}%

TÂCHE: Rédige 3 points expliquant les signaux les plus déterminants pour l'agent de vérification.
"""

def get_llm_explanation(label, r):
    """Uses a real Claude call if an API key is available in st.secrets;
    otherwise returns a clearly-labeled static example so the app stays
    demonstrable without any external dependency."""
    prompt = build_llm_prompt(label, r)
    api_key = st.secrets.get("ANTHROPIC_API_KEY") if hasattr(st, "secrets") else None
    if api_key:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-6", max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in msg.content if hasattr(b, "text")), True
        except Exception as e:
            return f"[Appel LLM impossible ({e}). Voici uniquement le prompt.]\n\n{prompt}", False

    if r["score"]>=60:
        text = (f"- Ce groupe obtient {r['score']:.0f}/100, tiré principalement par une forte homogénéité "
                f"des produits et une identité récurrente sur {len(r['group'])} colis.\n"
                f"- Ce schéma reflète uniquement des données comportementales (contenu, calendrier, "
                f"quantité, identité, valeur) -- il n'établit ni intention ni faute.\n"
                f"- Une vérification humaine est requise avant toute action ; un agent doit examiner "
                f"les colis sous-jacents avant que ce dossier ne soit traité davantage.")
    else:
        text = (f"- Ce groupe obtient {r['score']:.0f}/100 : plusieurs signaux existent mais restent "
                f"insuffisants pour une alerte forte.\n"
                f"- Le dossier est conservé pour suivi, sans déclencher d'action immédiate.\n"
                f"- Toute évolution (nouveaux colis, signaux renforcés) devrait être réévaluée par le système.")
    return f"[EXEMPLE STATIQUE -- aucune clé API live utilisée]\n\n{text}", False

# ==============================================================================
# UI
# ==============================================================================

st.title("📦 ParcelShield AI")
st.subheader("Détection des colis fractionnés — Prototype")
st.caption("Hackathon • flux postal simulé • aucune décision automatique de fraude")

with st.expander("ℹ️ Méthodologie & limites du prototype (à lire avant la démo)"):
    st.markdown("""
**Deux modules complémentaires, pas un seul.** Cet outil (*ParcelShield*) cible un
schéma précis : le **fractionnement de colis pour éviter un seuil douanier** (petits
colis répétés, même expéditeur/destinataire, faible valeur déclarée). C'est un cas
particulier du problème plus général de "l'activité commerciale non déclarée" —
notre second module (profil vendeur, fréquence/valeur cumulée) couvre ce cas
général. Les deux utilisent des poids et un module `identité/réseau` cohérents,
mais des indicateurs différents adaptés à chaque schéma (ex : ici une **valeur
déclarée basse** est le signal, alors que pour un profil vendeur, une **valeur
cumulée élevée** l'est — ce sont deux fraudes différentes, pas une contradiction).

**L'origine du colis (Chine, Turquie, France...) n'entre dans aucun calcul de
score.** Elle est affichée à titre informatif uniquement.

**La similarité de produit est un lexique explicable, pas un modèle sémantique.**
Une version de production devrait s'appuyer sur le code tarifaire douanier
(déclaration CN22/CN23) plutôt que sur le texte libre, ce qui est plus robuste.

**Aucune décision n'est automatisée.** Le score est un signal de priorisation ;
la vérification humaine reste obligatoire avant toute action.
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
    table.append([f"#{i:02d}",len(r["group"]),r["total_qty"],r["span"],f"{r['identity']*100:.0f}%",f"{r['content']*100:.0f}%",f"{r['score']:.0f}/100",
                  "🔴 Vérification humaine" if r["score"]>=60 else ("🟠 À surveiller" if r["score"]>=40 else "🟢 Ignoré")])
st.dataframe(pd.DataFrame(table,columns=["Groupe","Colis","Qté cumulée","Période","Identité","Produits","Score","Statut"]),use_container_width=True,hide_index=True)

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
y.metric("Confiance identité",f"{r['identity']*100:.0f}%")
z.metric("Similarité produits",f"{r['content']*100:.0f}%")

st.markdown("### 🔬 Décomposition du score")
st.dataframe(pd.DataFrame({
"Signal":["Homogénéité du contenu","Concentration temporelle","Anomalie de quantité","Confiance d'identité","Écart de valeur (secondaire)"],
"Poids":["30%","25%","20%","15%","10%"],
"Valeur":[f"{r['content']*100:.0f}%",f"{r['temporal']*100:.0f}%",f"{r['quantity']*100:.0f}%",f"{r['identity']*100:.0f}%",f"{r['value']*100:.0f}%"]}),use_container_width=True,hide_index=True)

st.markdown("### 📦 Colis liés")
st.dataframe(g,use_container_width=True,hide_index=True)

st.markdown("### 🤖 Explication")
explanation, is_live = get_llm_explanation(choice, r)
if is_live:
    st.info(explanation)
else:
    st.info(explanation)
    st.caption("Configurez `ANTHROPIC_API_KEY` dans les secrets Streamlit pour une explication générée en direct.")

st.caption("⚠️ Prototype : données simulées et pondérations illustratives, conformément au caractère démonstratif du prototype.")
