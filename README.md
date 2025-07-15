# ✚ Suggeritore di Canti per la Messa

Script Python per generare automaticamente un file JSON contenente:

- le **letture liturgiche** della domenica
- le **antifone**
- i **canti suggeriti** per ogni momento della Messa

---

## 🧠 Come funziona

Lo script `liturgia_messa_builder.py` lavora in 6 fasi principali:

1. **Input della data**
   - Inserisci una data nel formato `YYYY-MM-DD`
   - Se lasci vuoto, usa **automaticamente la prossima domenica**

2. **Calcolo del tempo liturgico**
   - Determina stagione liturgica (Avvento, Quaresima, ecc.)
   - Calcola il numero della domenica e l’anno liturgico (A, B, C)

3. **Download delle letture**
   - Scarica dal sito ufficiale [chiesacattolica.it](https://www.chiesacattolica.it/liturgia-del-giorno)
   - Estrae le letture, salmi e antifone del giorno

4. **Suggerimento dei canti**
   - Confronta semanticamente le letture con il testo dei canti nel file `canti.json`
   - Suggerisce un canto per: ingresso, offertorio, comunione, finale

5. **Creazione del file JSON**
   - Costruisce un dizionario con tutti i testi liturgici e i canti suggeriti

6. **Salvataggio del file**
   - Il file viene salvato sul **Desktop** con nome:
     ```
     messa_YYYYMMDD.json
     ```

---

## 💾 Requisiti

Assicurati di avere Python 3.9 o superiore installato.

Installa i pacchetti necessari con:

```bash
pip install -r requirements.txt
```

Facoltativo: puoi usare un ambiente virtuale per tenere tutto isolato
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

# ⚙️ Tecnologie & Tecniche utilizzate

## 1 · Linguaggio & Ambiente

| Tecnologia | Ruolo |
|------------|-------|
| **Python 3.11+** | Linguaggio principale dello script |
| **Virtual Env / Conda** | Ambiente isolato per gestire dipendenze (facoltativo ma consigliato) |

---

## 2 · Librerie di Terze Parti

| Libreria | Perché viene usata |
|----------|--------------------|
| `requests` | Effettua la richiesta HTTP al sito CEI |
| `beautifulsoup4` | **Web scraping**: parse del DOM e estrazione dei testi liturgici |
| `pandas` | Gestione tabellare di `canti.json` (filtri, explode, ecc.) |
| `sentence-transformers` | Embedding semantici multilingua (modello SBERT **distiluse-base-multilingual-cased**) |
| `scikit-learn` | Funzione `cosine_similarity` per il matching letture-canti |

---

## 3 · Algoritmi & Logica

### 3.1 · Calcolo del calendario liturgico  
- **Algoritmo di Computus**: determina la data di Pasqua (funzione `pasqua`)  
- Mapping dinamico delle domeniche tramite **calcolo di offset** e `timedelta`  
- Classificazione “Anno A/B/C” secondo la prima domenica di Avvento

### 3.2 · Web Scraping  
- Viene interrogata l’URL:  
  `https://www.chiesacattolica.it/liturgia-del-giorno/?data-liturgia=YYYYMMDD`  
- **BeautifulSoup** cerca i blocchi `div.cci-liturgia-giorno-dettagli-content` per ogni sezione (prima lettura, salmo, ecc.)  

### 3.3 · Natural Language Processing  
1. **Embeddings SBERT**  
   - Ogni canto nel file `canti.json` viene vettorializzato **una sola volta** e memorizzato in `df["embedding"]`.  
2. **Similarity Matching**  
   - Per la data richiesta si genera un embedding “riassunto” delle letture ↔ si confronta con quelli dei canti  
   - Si usa **coseno di similitudine** (`scikit-learn`) per ordinare i canti, scegliendo il più vicino (per momento liturgico)

### 3.4 · Gestione File  
- Salvataggio del JSON sul Desktop (`Path.home() / "Desktop"`)  
- Naming robusto: `messa_YYYYMMDD.json`  
- Supporto a output opzionale (disabilitabile con `save=False`)

---

## 4 · Design Patterns adottati

| Pattern | Dove/Perché |
|---------|-------------|
| **Lazy Singleton** | Funzione `get_model()` carica il modello SBERT **solo alla prima chiamata**, evitando overhead |
| **DataFrame cache** | `get_canti_df()` costruisce e ri-usa il DataFrame dei canti (evita riletture/ricomputazioni) |
| **CLI fail-safe** | Se l’utente non fornisce la data, viene calcolata **automaticamente** la prossima domenica |

---

## 5 · Performance & Robustezza

- Richieste HTTP con **timeout** di 10 s → evita blocchi permanenti  
- Embedding pre-calcolati → riduce drasticamente il tempo di esecuzione (≈ 1-2 s dopo il primo run)  
- Gestione delle eccezioni con messaggio d’errore colorato (ANSI) e `sys.exit(1)`  