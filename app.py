import streamlit as st
import pandas as pd
from difflib import SequenceMatcher
from itertools import combinations
import re

st.set_page_config(page_title="ParcelShield AI", page_icon="📦", layout="wide")

@st.cache_data
def load_data():
    rows=[
    ["P001","Ahmed Ben Salah","12 Rue Ibn Khaldoun, Ariana","22123456","2026-09-01","Coque iPhone 15 transparente",3,18,"China"],
    ["P002","Ahmed B. Salah","12 Ibn Khaldoun Ariana","22123456","2026-09-04","iPhone 15 phone case",4,23,"China"],
    ["P003","A. Ben Salah","12 Rue Ibn Khaldoun Ariana","22123456","2026-09-08","Coques pour iPhone 15",5,27,"China"],
    ["P004","Ahmed Ben Salah","12 Rue Ibn Khaldoun, Ariana","22123456","2026-09-12","Etuis téléphone iPhone 15",4,22,"China"],
    ["P005","Sonia Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-02","Faux cils cosmétiques",8,31,"China"],
    ["P006","Sonia T. Trabelsi","8 Rue Marseille Tunis","55112233","2026-09-06","Cils artificiels",10,39,"China"],
    ["P007","S. Trabelsi","8 Rue de Marseille, Tunis","55112233","2026-09-11","Lot de faux cils",9,35,"China"],
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
    ]
    return pd.DataFrame(rows,columns=["parcel_id","name","address","phone","date","description","quantity","value_tnd","origin"]).assign(date=lambda x:pd.to_datetime(x.date))

df=load_data()

def norm(s):
    return re.sub(r"\s+"," ",re.sub(r"[^a-z0-9àâäéèêëîïôöùûüç\s]"," ",str(s).lower())).strip()

def sim(a,b): return SequenceMatcher(None,norm(a),norm(b)).ratio()

def jaccard(a,b):
    A=set(norm(a).split()); B=set(norm(b).split())
    return len(A&B)/len(A|B) if A and B else 0

def product_sim(a,b):
    j=jaccard(a,b)
    if j>=.35: return max(j,sim(a,b))
    families=[
      ["iphone","coque","case","étui","etui"],
      ["cils","faux","cosmetique","cosmétiques"],
      ["bracelet","bijou","métallique","metallique","acier"]
    ]
    aa,bb=norm(a),norm(b)
    for f in families:
        if any(x in aa for x in f) and any(x in bb for x in f): return .86
    return sim(a,b)*.8

def identity(a,b):
    name=sim(a.name,b.name)
    addr=sim(a.address,b.address)
    phone=1 if str(a.phone)==str(b.phone) else 0
    return .25*name+.35*addr+.40*phone

def groups():
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
        if identity(df.iloc[i],df.iloc[j])>=.72: union(i,j)
    out={}
    for i in range(len(df)): out.setdefault(find(i),[]).append(i)
    return [x for x in out.values() if len(x)>=3]

def score(g):
    x=df.iloc[g].sort_values("date")
    ids=[identity(x.iloc[i],x.iloc[j]) for i,j in combinations(range(len(x)),2)]
    ps=[product_sim(x.iloc[i].description,x.iloc[j].description) for i,j in combinations(range(len(x)),2)]
    ident=sum(ids)/len(ids); content=sum(ps)/len(ps)
    span=(x.date.max()-x.date.min()).days
    temporal=max(0,min(1,(21-span)/21))
    qty=max(0,min(1,(x.quantity.sum()-2)/12))
    value=max(0,min(1,(100-x.value_tnd.mean())/100))
    total=100*(.30*content+.25*temporal+.20*qty+.15*ident+.10*value)
    return dict(group=g,identity=ident,content=content,temporal=temporal,quantity=qty,value=value,score=total,total_qty=int(x.quantity.sum()),span=span)

gs=groups()
results=sorted([score(g) for g in gs],key=lambda r:r["score"],reverse=True)

st.title("📦 ParcelShield AI")
st.subheader("Détection des colis fractionnés — Prototype")
st.caption("Hackathon • flux postal simulé • aucune décision automatique de fraude")

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
"Signal":["Homogénéité du contenu","Régularité temporelle","Anomalie de quantité","Confiance d'identité","Écart de valeur (secondaire)"],
"Poids":["30%","25%","20%","15%","10%"],
"Valeur":[f"{r['content']*100:.0f}%",f"{r['temporal']*100:.0f}%",f"{r['quantity']*100:.0f}%",f"{r['identity']*100:.0f}%",f"{r['value']*100:.0f}%"]}),use_container_width=True,hide_index=True)

st.markdown("### 📦 Colis liés")
st.dataframe(g,use_container_width=True,hide_index=True)

st.markdown("### 🤖 Explication")
if r["score"]>=60:
    st.info(f"Pris individuellement, ces colis peuvent sembler compatibles avec des achats personnels. Leur regroupement révèle toutefois un schéma répétitif : produits similaires, commandes rapprochées, quantité cumulée de {r['total_qty']} unités et forte corrélation d'identité. Vérification humaine recommandée.")
elif r["score"]>=40:
    st.info("Plusieurs signaux existent, mais leur combinaison reste insuffisante pour une alerte forte. Le groupe est conservé pour surveillance.")
else:
    st.info("Les signaux observés ne justifient pas une alerte.")

st.caption("⚠️ Prototype : données simulées et pondérations illustratives, conformément au caractère démonstratif du prototype.")

