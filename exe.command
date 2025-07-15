#!/bin/bash
cd "$(dirname "$0")"

# Inizializza Conda correttamente
eval "$(/Users/francescolindiner/anaconda3/bin/conda shell.bash hook)"

# Attiva l’ambiente (sostituisci con il nome giusto se serve)
conda activate PythonEnv

# Avvia lo script
python3 liturgia_messa_builder.py

# Mantieni la finestra aperta
read -p "Premi INVIO per uscire..."