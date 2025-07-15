#!/bin/bash
cd "$(dirname "$0")"

eval "$(/Users/francescolindiner/anaconda3/bin/conda shell.bash hook)"
conda activate PythonEnv

while true; do
  clear
  python3 liturgia_messa_builder.py
  echo
  read -p "Premi Invio per rieseguire, oppure digita q per uscire: " ans
  [[ "$ans" == "q" ]] && break
done