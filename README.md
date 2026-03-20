# Olympic Figure Skating Judge Bias Analysis

A statistical case study investigating potential national bias in figure skating judging at the Olympic and international level. The analysis covers competitions from 2017–2026 across Grand Prix, European Championship, Four Continents, and Olympic events.

## Project Overview

This project examines whether figure skating judges exhibit systematic score inflation toward skaters from their own country (or allied nations), using detailed component and element scores from ISU competitions. Key analyses include mixed-effects models, machine learning regressors, and classification of judge nationalities against scoring patterns.

## Repository Structure

```
OlympicFigureSkating/
├── analysis.ipynb          # Main analysis notebook
├── kyle/                   # Scraped/processed competition data (CSV per event)
│   ├── judge_nationalities.csv
│   ├── judges_nationalities_v2.csv
│   └── <competition>/      # Per-event score CSVs (ec, fc, gp, owg, wc series)
├── OWG10_ScoresCSV_SOV/    # 2010 Winter Olympics raw SOV score CSVs
├── misc/                   # Exploratory notebooks and intermediate data
├── images/                 # Output plots
├── report_docs/            # Report/writeup materials
├── environment.yml         # Conda environment specification
└── README.md
```

## Data

- **Source:** ISU judging system (scraped via `kyle/data_pull.ipynb` and `kyle/query.R`)
- **Coverage:** Men's Singles, Ladies' Singles, Pairs — Short Program and Free Skate
- **Competitions:** Grand Prix series (CAN, FRA, USA), Grand Prix Final, European Championships, Four Continents, World Championships, Olympic Winter Games (2018, 2022, 2026)
- **Features:** Per-judge GOE and PCS scores, skater nationality, judge nationality, season, segment

## Setup

### Conda (recommended)

```bash
conda env create -f environment.yml
conda activate figure-skating
jupyter lab
```

### Manual pip install

```bash
pip install pandas numpy polars scipy seaborn matplotlib statsmodels scikit-learn lightgbm xgboost optuna imbalanced-learn plotly
```

## Usage

Open and run `analysis.ipynb` from the repo root. The notebook expects data to be present under `./data/`.
