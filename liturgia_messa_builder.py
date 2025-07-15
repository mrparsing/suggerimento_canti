#!/usr/bin/env python3

# ============================================================
#  liturgia_messa_builder.py — build full Mass JSON from a date
#  *Revised 2025‑07‑15 — patch 3 (bug‑fix newline + duplicates)*
# ============================================================
# Input:  ISO date string (YYYY‑MM‑DD)
# Output: JSON file with readings & suggested hymns

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity

# -------------------------------------------------------------
#  GLOBAL CONFIG
# -------------------------------------------------------------
MODEL_NAME = "distiluse-base-multilingual-cased"  # SBERT model
CANTI_PATH = Path("canti.json")                  # JSON repertoire of hymns
SAVE_DIR = Path.home() / "Desktop"              # output folder
SAVE_DIR.mkdir(exist_ok=True)

_model: SentenceTransformer | None = None  # lazy singleton

def get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)
    return _model

# -------------------------------------------------------------
#  CALENDAR / LITURGICAL YEAR UTILITIES
# -------------------------------------------------------------

def pasqua(year: int) -> datetime:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return datetime(year, month, day)

def sunday_before(date: datetime) -> datetime:
    return date - timedelta(days=(date.weekday() + 1) % 7)

def first_sunday_of_advent(year: int) -> datetime:
    christmas = datetime(year, 12, 25)
    offset = 7 if christmas.weekday() == 6 else christmas.weekday()
    fourth = christmas - timedelta(days=offset)
    return fourth - timedelta(weeks=3)

def baptism_sunday(year: int) -> datetime:
    return sunday_before(datetime(year, 1, 13))

def liturgical_year_letter(date: datetime) -> str:
    first_adv = first_sunday_of_advent(date.year)
    ref_year = date.year if date >= first_adv else date.year - 1
    return {0: "A", 1: "B", 2: "C"}[ref_year % 3]

# ---------- Build mapping of Sundays ----------

def build_sunday_map(year: int) -> Dict[datetime, Tuple[str, Any]]:
    p = pasqua(year)
    ash_wed = p - timedelta(days=46)
    palm = p - timedelta(days=7)
    pentecost = p + timedelta(days=49)

    m: Dict[datetime, Tuple[str, Any]] = {}

    # Avvento
    first_adv = first_sunday_of_advent(year)
    for i in range(4):
        m[first_adv + timedelta(weeks=i)] = ("Avvento", i + 1)

    # Ordinario I
    counter = 2
    cur = baptism_sunday(year) + timedelta(weeks=1)
    while cur < ash_wed:
        m[cur] = ("Tempo Ordinario", counter)
        counter += 1
        cur += timedelta(weeks=1)

    # Quaresima
    cur = ash_wed + timedelta(days=(6 - ash_wed.weekday()))
    for i in range(1, 6):
        m[cur] = ("Quaresima", i)
        cur += timedelta(weeks=1)
    m[palm] = ("Quaresima", "Domenica delle Palme")

    # Pasqua ed Easter season
    m[p] = ("Tempo di Pasqua", "Pasqua")
    cur = p + timedelta(weeks=1)
    easter_no = 2
    while cur <= pentecost:
        m[cur] = ("Tempo di Pasqua", easter_no)
        easter_no += 1
        cur += timedelta(weeks=1)

    # Ordinario II
    cur = pentecost + timedelta(weeks=1)
    counter += 2  # salta 8‑9 → 11
    next_first_adv = first_sunday_of_advent(year + 1)
    christ_king = next_first_adv - timedelta(weeks=1)
    while cur <= christ_king:
        m[cur] = ("Tempo Ordinario", counter)
        counter += 1
        cur += timedelta(weeks=1)
    m[christ_king] = ("Tempo Ordinario", "Cristo Re")
    return m

def get_tempo_info(date: datetime) -> Tuple[str, Any, str]:
    sunday = sunday_before(date)
    mapping = build_sunday_map(sunday.year)
    if sunday not in mapping:
        mapping |= build_sunday_map(sunday.year - 1) | build_sunday_map(sunday.year + 1)
    season, num = mapping.get(sunday, ("Tempo Ordinario", 0))
    return season, num, liturgical_year_letter(date)

# -------------------------------------------------------------
#  SCRAPE & FORMAT READINGS
# -------------------------------------------------------------
TITLE_PAIRS = [
    ("Antifona alla comunione", "antifona_comunione"),
    ("Antifona", "antifona"),
    ("Acclamazione al Vangelo", "versetto_vangelo"),
    ("Prima Lettura", "prima_lettura"),
    ("Salmo Responsoriale", "salmo"),
    ("Seconda Lettura", "seconda_lettura"),
    ("Vangelo", "vangelo"),
]
BOLD_FIRST = {"prima_lettura", "seconda_lettura", "vangelo"}


def _fmt(raw: str, bold: bool) -> str:
    txt = raw.strip().replace("\n", "<br>")
    if bold and "<br>" in txt:
        first, rest = txt.split("<br>", 1)
        txt = f"<strong>{first}</strong><br>{rest}"
    return txt


def scrape_readings(date: datetime) -> Dict[str, str]:
    url = f"https://www.chiesacattolica.it/liturgia-del-giorno/?data-liturgia={date.strftime('%Y%m%d')}"
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    out = {dest: "" for _, dest in TITLE_PAIRS}
    for sec in soup.select("div.cci-liturgia-giorno-dettagli-content"):
        title_tag = sec.select_one("h2.cci-liturgia-giorno-section-title")
        cont_tag = sec.select_one("div.cci-liturgia-giorno-section-content")
        if not title_tag or not cont_tag:
            continue
        heading = title_tag.get_text(strip=True)
        for key, dest in TITLE_PAIRS:
            if heading.startswith(key):
                raw = cont_tag.get_text("\n", strip=True)
                out[dest] = _fmt(raw, dest in BOLD_FIRST)
                break
    return out

# -------------------------------------------------------------
#  SUGGEST HYMNS (unchanged)
# -------------------------------------------------------------

def build_canti_df() -> pd.DataFrame:
    data = json.loads(CANTI_PATH.read_text(encoding="utf-8"))
    df = pd.DataFrame(data["canti"])
    df["momento"] = df["tipologia"].fillna("").apply(lambda s: [x.strip().lower() for x in s.split(",")])
    df = df.explode("momento")
    df["tempo_liturgico"] = df["tempo"].fillna("qualsiasi").str.strip().str.lower()
    model = get_model()
    df["embedding"] = df["testo"].fillna("").apply(lambda t: model.encode(BeautifulSoup(t, "html.parser").get_text()))
    return df

_CANTI_DF: pd.DataFrame | None = None

def get_canti_df() -> pd.DataFrame:
    global _CANTI_DF
    if _CANTI_DF is None:
        _CANTI_DF = build_canti_df()
    return _CANTI_DF


def _slug(title: str) -> str:
    import re, unicodedata
    # minuscole, rimuovi apostrofi e virgole, spazi → trattini
    s = title.lower().replace("'", "").replace("’", "").replace(",", "")
    s = re.sub(r"\s+", "-", s.strip())
    # facoltativo: normalizza unicode per caratteri accentati (mantiene le lettere)
    s = unicodedata.normalize("NFC", s)
    return s


def suggerisci_canti(readings: Dict[str, str], season: str, top_n: int = 1) -> Dict[str, str]:
    df = get_canti_df()
    model = get_model()
    picks, used = {}, set()

    for momento in ["ingresso", "offertorio", "comunione", "finale"]:
        base: List[str] = []
        if momento == "ingresso" and readings["antifona"]:
            base.extend([readings["antifona"]] * 3)
        if momento == "comunione" and readings["antifona_comunione"]:
            base.extend([readings["antifona_comunione"]] * 3)
        base.extend(
            readings[k] for k in ("prima_lettura", "salmo", "seconda_lettura", "vangelo") if readings[k]
        )
        ref_emb = model.encode(" ".join(base)) if base else None

        df_m = df[df["momento"] == momento]
        sel = df_m[df_m["tempo_liturgico"] == season.lower()]
        if sel.empty:
            sel = df_m[df_m["tempo_liturgico"] == "qualsiasi"]
        sel = sel[~sel["titolo"].isin(used)].copy()
        if sel.empty:
            continue
        if ref_emb is not None:
            sel["sim"] = sel["embedding"].apply(lambda e: cosine_similarity([e], [ref_emb])[0][0])
            sel = sel.sort_values("sim", ascending=False).head(top_n)
        titolo = sel.iloc[0]["titolo"]
        slug = _slug(titolo)
        html = f"<a href='/../../canti/testo/{slug}' target='_blank'>{titolo}</a>"
        picks[momento] = html
        used.add(titolo)
    return picks

# -------------------------------------------------------------
#  BUILD JSON MASS
# -------------------------------------------------------------

def build_mass(date_str: str, colore: str = "#2a9a5c", save: bool = True) -> Dict[str, Any]:
    date_obj = datetime.strptime(date_str, "%Y-%m-%d")
    season, num, year_letter = get_tempo_info(date_obj)
    r = scrape_readings(date_obj)
    hymns = suggerisci_canti(r, season)

    num_str = str(num) if isinstance(num, str) else f"{num:02d}"
    title = f"{to_roman(int(num_str))} Domenica del {season} - Anno {year_letter}"

    tempo = ""
    if "Quaresima" in season:
        tempo = "quaresima"
    elif "Ordinario" in season:
        tempo = "ordinario"
    elif "Pasqua" in season:
        tempo = "pasqua"
    elif "Avvento" in season:
        tempo = "avvento"

    mass = {
        "title": title,
        "numero": num,
        "anno": year_letter,
        "colore": colore,
        "antifona_ingresso": r["antifona"],
        "canto_ingresso": hymns.get("ingresso", ""),
        "atto_penitenziale": "Confesso a Dio onnipotente e a voi, fratelli e sorelle, che ho molto peccato in pensieri, parole, opere e omissioni, per mia colpa, mia colpa, mia grandissima colpa. E supplico la beata sempre Vergine Maria, gli angeli, i santi e voi, fratelli e sorelle, di pregare per me il Signore Dio nostro.",
        "prima_lettura_testo": r["prima_lettura"],
        "salmo_link": f"../../db/tempi_liturgici/{tempo}/salmi_anno_{year_letter}/{year_letter.lower()} {num} Visconti.pdf",
        "salmo_testo": r["salmo"],
        "seconda_lettura_testo": r["seconda_lettura"],
        "versetto_vangelo": r["versetto_vangelo"],
        "vangelo": r["vangelo"],
        "canto_offertorio": hymns.get("offertorio", ""),
        "canto_comunione": hymns.get("comunione", ""),
        "antifona_alla_comunione": r["antifona_comunione"],
        "canto_finale": hymns.get("finale", "")
    }

    if save:
        fname = SAVE_DIR / f"messa_{date_obj.strftime('%Y%m%d')}.json"
        fname.write_text(json.dumps(mass, ensure_ascii=False, indent=2), encoding="utf-8")
        print("✚ File salvato in", fname)
    return mass

def to_roman(n: int) -> str:
    val = [
        1000, 900, 500, 400,
        100,  90,  50,  40,
        10,   9,   5,   4,  1
    ]
    syms = [
        "M", "CM", "D", "CD",
        "C", "XC", "L", "XL",
        "X", "IX", "V", "IV", "I"
    ]
    roman = ""
    i = 0
    while n > 0:
        for _ in range(n // val[i]):
            roman += syms[i]
            n -= val[i]
        i += 1
    return roman

# -------------------------------------------------------------
#  CLI
# -------------------------------------------------------------
if __name__ == "__main__":
    from datetime import date as _date
    import sys
    banner = r"""
            ╔══════════════════════════════════════════════════════════╗
            ║                                                          ║
            ║   LITURGIA DEL GIORNO - SUGGERIMENTO CANTI PER LA MESSA  ║
            ║                                                          ║
            ║        Costruzione automatica di letture e canti         ║
            ║                                                          ║
            ╚══════════════════════════════════════════════════════════╝
            """
    print(banner)
    # Usa argomento da riga di comando se presente
    cli_arg = sys.argv[1] if len(sys.argv) > 1 else ""
    user_in = cli_arg or input("Data (YYYY-MM-DD) (Vuoto = prossima domenica) > ").strip()

    if not user_in:
        today = _date.today()
        days_ahead = (6 - today.weekday()) % 7  # 0=Mon .. 6=Sun
        days_ahead = 7 if days_ahead == 0 else days_ahead
        target = today + timedelta(days=days_ahead)
        user_in = target.strftime("%Y-%m-%d")
        print(f"Nessuna data inserita: uso la prossima domenica {user_in}")

    try:
        build_mass(user_in)
    except Exception as exc:
        print("[31mErrore:[0m", exc)
        sys.exit(1)
