# CLEARPASS AI

### Detection of Split Parcels in Cross-Border E-Commerce

CLEARPASS AI is a prototype designed to help customs officers identify potentially fragmented e-commerce purchases distributed across multiple parcels and recipients.

A single parcel may appear normal on its own. However, several parcels can form a suspicious pattern when they share similar recipient information, contain repetitive products, arrive at regular intervals, or contain unusually high quantities.

## Problem

Online purchases from platforms such as Shein, Temu and AliExpress may sometimes be divided into several small parcels.

Looking at each parcel individually can make the activity appear normal. CLEARPASS AI explores the relationship between multiple parcels to identify potentially suspicious groups for human review.

## How it works

The prototype uses two stages:

### Stage A — Identity matching

The system compares:

* Recipient names
* Addresses
* Phone numbers

Fuzzy matching is used to detect variations such as spelling differences or abbreviated addresses.

This stage creates candidate groups of related parcels.

### Stage B — Behavioral analysis

Each candidate group receives a score from 0 to 100 based on:

| Factor              | Weight |
| ------------------- | -----: |
| Content homogeneity |    30% |
| Temporal regularity |    25% |
| Quantity anomaly    |    20% |
| Identity confidence |    15% |
| Value deviation     |    10% |

The resulting score is used to prioritize groups for investigation.

### Alert thresholds

* **Below 40:** Ignore
* **40–59:** Monitor
* **60 or above:** Alert for human review

A minimum of 3 parcels is required to form a candidate group.

## Human-in-the-loop

CLEARPASS AI does not automatically declare fraud.

The system only proposes groups that may deserve attention. A customs officer remains responsible for reviewing the evidence and making the final decision.

## Data

This repository uses **synthetic/anonymized demonstration data**.

It does not contain real personal information or real customs records.

For a real deployment, the system would require an authorized and secure data feed from the relevant customs/postal infrastructure.

The current prototype simulates one postal flow and does not connect to private data from La Poste, DHL, Aramex, or other providers.

## Technology

* Python
* Streamlit
* Pandas
* NumPy
* Fuzzy matching
* Rule-based behavioral scoring

## Run locally

Install the dependencies:

```bash
pip install -r requirements.txt
```

Start the application:

```bash
streamlit run app.py
```

The application will open in your browser.

## Project structure

```text
CLEARPASS-AI/
│
├── app.py
├── parcels.csv
├── requirements.txt
└── README.md
```

## Prototype limitations

This is a hackathon prototype.

The scoring weights are illustrative and have not been calibrated on a real historical fraud dataset.

The prototype does not make an automatic customs decision.

Future versions could integrate authorized real-world data sources, improve natural-language product matching, calibrate the scoring model using historical cases, and support additional logistics providers subject to the appropriate legal framework.

## Objective

The objective is to provide customs officers with an additional analytical tool capable of detecting relationships between parcels that may not be visible when declarations are examined individually.
