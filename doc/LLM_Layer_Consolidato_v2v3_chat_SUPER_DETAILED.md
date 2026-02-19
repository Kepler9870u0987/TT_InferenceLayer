# LLM Layer (Tool Calling / Structured Outputs) — Specifica *super dettagliata* (PDF v2 + v3 + chat)

> Documento di riferimento per implementare e operare **il layer LLM** della pipeline “Thread Classificator Mail”.
>
> Consolidato da:
> - Brainstorming v2: schema JSON strict, prompting, validazione multi-stadio, retry, esempi di codice e guardrail. [file:1]
> - Brainstorming v3: invarianti (determinismo statistico), architettura 2026, versioning, checklist operativa e stack suggerito. [file:2]
> - Decisioni in chat: demo con **Ollama** (structured outputs JSON) e piano futuro per **SGLang** (structured outputs/guided decoding), mantenendo **FastAPI** come orchestratore/validator. [file:1][file:2][web:120][web:121][web:106]

---

## 0) Scopo, confini, principi

### 0.1 Scopo
Questo layer trasforma una email (già canonicalizzata) in un output **strutturato e auditabile** che contiene classificazioni e spiegazioni minime: topics multi-label + sentiment + priority, e per ogni topic una lista di keyword “ancorate” ai candidati e brevi evidenze testuali. [file:1][file:2]

### 0.2 Confini (cosa NON fa)
- Non fa parsing MIME/RFC5322: quello è Ingestion/Canonicalization. [file:2]
- Non decide *in modo finale* `customerstatus`: per i PDF deve restare deterministico via CRM lookup. [file:1]
- Non aggiorna direttamente dizionari: produce segnali (`keywordsintext`) che alimentano observation storage e promoter notturno. [file:2]

### 0.3 Principi non negoziabili
- **Tassonomia chiusa** (`TOPICSENUM`) + `UNKNOWNTOPIC`. [file:1][file:2]
- **No keyword inventate**: `keywordsintext[].candidateid` deve puntare a candidati forniti in input. [file:1]
- **Output tipizzato** con JSON Schema strict, più validazione deterministica multi-stadio e retry. [file:1]
- **Determinismo statistico**: a parità di versioni/config, stesso input → stesso output (o variabilità controllata e tracciata). [file:2]

---

## 1) Input del layer (contratto)

### 1.1 Email canonicalizzata
Il layer lavora su un documento email già normalizzato/canonicalizzato (testo pulito, firme/quote eventualmente rimosse, PII redaction se prevista). [file:2]

Campi tipici passati nel payload LLM (v2):
- `subject`
- `from`
- `body` (troncato, es. `bodycanonical[:8000]`) [file:1]

**Raccomandazione operativa**: troncare il body e non inviare l’intera email se non necessario, per stabilità, latenza e compliance. [file:1][file:2]

### 1.2 Candidate keywords deterministiche (fondamentali)
L’LLM non “estrae keyword dal nulla”: seleziona keyword *solo* dalla lista candidati generata upstream. [file:1]

#### 1.2.1 Generazione deterministica candidati (sintesi tecnica)
Nel v2 è descritta una pipeline deterministica basata su tokenizzazione semplice e n-gram (uni/bi/tri), contatori e stable id. [file:1]

Punti chiave:
- `stableid(source, term)` (hash) per ottenere `candidateid` stabile. [file:1]
- Ordinamento stabile dei candidati (es. per source, count desc, term). [file:1]

#### 1.2.2 Arricchimento semantico (opzionale ma raccomandato)
Il v2 propone di arricchire i candidati con uno score semantico via KeyBERT + sentence-transformers (version pinned) e usare uno score composito per ranking. [file:1]

#### 1.2.3 Filtri hard (anti-rumore)
Il v2 include stoplist italiana versionata + blacklist pattern per evitare inquinamento (es. saluti, “re”, “fwd”, numeri isolati). [file:1]

#### 1.2.4 Top-N candidati
Nel prompt/payload v2 viene limitato il set inviato all’LLM (es. top 100 per score) per non saturare contesto e migliorare aderenza allo schema. [file:1]

**Bug logico comune e fix**:
- Se invii troppi candidati, aumenti la probabilità che il modello:
  - non rispetti vincoli min/max,
  - selezioni keyword marginali,
  - produca output troppo lungo o più fragile.
- Fix: top-N + tronchi body + temperature bassa (e retry). [file:1]

---

## 2) Output del layer (contratto JSON)

### 2.1 Assi e semantica
Il layer produce:
- **Topics multi-label**: 1–5 topic da enum chiuso. [file:1]
- **Sentiment**: `positive|neutral|negative`. [file:1]
- **Priority**: `low|medium|high|urgent` + `signals` per audit. [file:1]
- **Keywords in text** per topic: selezionate dai candidati via `candidateid`. [file:1]
- **Evidence** per topic: 1–2 quote brevi (≤200 char). [file:1]

### 2.2 JSON Schema strict (estratto “completo” ricostruito dai vincoli v2)
Nota: lo schema qui sotto è una versione “operativa” coerente con i vincoli del v2 (strict, additionalProperties false, min/max). [file:1]

```json
{
  "name": "emailtriagev2",
  "strict": true,
  "schema": {
    "type": "object",
    "additionalProperties": false,
    "required": ["dictionaryversion", "sentiment", "priority", "topics"],
    "properties": {
      "dictionaryversion": {"type": "integer"},
      "sentiment": {
        "type": "object",
        "additionalProperties": false,
        "required": ["value", "confidence"],
        "properties": {
          "value": {"type": "string", "enum": ["positive", "neutral", "negative"]},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1}
        }
      },
      "priority": {
        "type": "object",
        "additionalProperties": false,
        "required": ["value", "confidence", "signals"],
        "properties": {
          "value": {"type": "string", "enum": ["low", "medium", "high", "urgent"]},
          "confidence": {"type": "number", "minimum": 0, "maximum": 1},
          "signals": {"type": "array", "maxItems": 6, "items": {"type": "string"}}
        }
      },
      "topics": {
        "type": "array",
        "minItems": 1,
        "maxItems": 5,
        "items": {
          "type": "object",
          "additionalProperties": false,
          "required": ["labelid", "confidence", "keywordsintext", "evidence"],
          "properties": {
            "labelid": {"type": "string", "enum": ["FATTURAZIONE", "ASSISTENZATECNICA", "RECLAMO", "INFOCOMMERCIALI", "DOCUMENTI", "APPUNTAMENTO", "CONTRATTO", "GARANZIA", "SPEDIZIONE", "UNKNOWNTOPIC"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "keywordsintext": {
              "type": "array",
              "minItems": 1,
              "maxItems": 15,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["candidateid", "lemma", "count"],
                "properties": {
                  "candidateid": {"type": "string"},
                  "lemma": {"type": "string"},
                  "count": {"type": "integer", "minimum": 1},
                  "spans": {
                    "type": "array",
                    "items": {
                      "type": "array",
                      "minItems": 2,
                      "maxItems": 2,
                      "items": {"type": "integer"}
                    }
                  }
                }
              }
            },
            "evidence": {
              "type": "array",
              "minItems": 1,
              "maxItems": 2,
              "items": {
                "type": "object",
                "additionalProperties": false,
                "required": ["quote"],
                "properties": {
                  "quote": {"type": "string", "maxLength": 200},
                  "span": {"type": "array", "minItems": 2, "maxItems": 2, "items": {"type": "integer"}}
                }
              }
            }
          }
        }
      }
    }
  }
}
```

**Nota**: i PDF includono `customerstatus` nello schema di esempio, ma raccomandano di calcolarlo deterministically via CRM lookup; in produzione è preferibile non farlo produrre all’LLM (vedi sezione 6). [file:1]

---

## 3) Prompting: cosa dire al modello (pattern v2)

### 3.1 System prompt (idea)
Il v2 usa un system prompt molto esplicito: JSON conforme allo schema, niente keyword/label/campi inventati, keyword solo dalla lista candidati, ecc. [file:1]

### 3.2 User payload (idea)
Il payload include:
- `dictionaryversion`
- `subject`, `from`, `body` troncato
- `allowedtopics` (= enum)
- `candidatekeywords` top-N ordinati con `candidateid/term/lemma/count/source/score`
- `instructions` testuali operative (topics/sentiment/priority/keywords/evidence). [file:1]

### 3.3 Parametri di generazione
- `temperature` bassa (es. 0.1) per ridurre variabilità. [file:1]
- `stream: false` per semplificare validazione (ricevi output completo). [file:1]

---

## 4) Validazione multi-stadio (guardrail) e retry (v2)

Questa sezione è “la parte production” fondamentale, indipendente dal modello. [file:1]

### 4.1 Perché serve anche con output strutturato
Anche se l’inference server ti aiuta a ottenere JSON valido, devi comunque applicare:
- controlli deterministici su candidateid/enum,
- dedup e warning,
- retry/fallback e audit. [file:1][file:2]

### 4.2 Definizione degli stadi (v2)
- **Stage 1: JSON parse** → errore hard se fallisce. [file:1]
- **Stage 2: JSON Schema validation** → errore hard se fallisce. [file:1]
- **Stage 3: Business rules** → errore hard se:
  - `labelid` non è in enum,
  - `candidateid` non è tra i candidati input (invenzione). [file:1]
- **Stage 4: Quality checks** → warning (non hard fail) se:
  - confidence topic < 0.2,
  - topic senza keyword/evidence,
  - duplicati (dedup deterministico). [file:1]

### 4.3 Retry
Il v2 prevede retry fino a max tentativi (es. 3) in caso di fallimenti hard. [file:1]

### 4.4 Miglioramenti (fix logici emersi in chat)
Aggiungere due verifier deterministici riduce “JSON valido ma poco affidabile”:
- **Evidence presence check**: `quote` deve esistere nel testo canonicalizzato (substring o match controllato). [file:1]
- **Keyword presence check**: keyword selezionata deve apparire nel testo (term/lemma) o avere spans coerenti. [file:1]

E aggiungere un fallback “shrink request”:
- se fallisce validazione, ritenta con body più corto e top-N candidati più piccolo (es. 50). [file:1]

---

## 5) Customer status: cosa fare davvero

Il v2 è esplicito: non delegare `new vs existing` all’LLM; farlo con CRM lookup deterministico (match exact/domain/none) + segnali testuali come fallback. [file:1]

**Regola operativa**:
- L’LLM può al massimo riportare evidenze (“ho già un contratto”), ma la decisione finale deve essere ripetibile e versionata. [file:1]

---

## 6) Determinismo statistico e versioning (v3)

### 6.1 Invariante
Il v3 definisce l’invariante: a parità di `dictionaryversion`, `modelversion`, `parserversion`, `stoplistversion`, `nermodelversion`, `schemaversion`, `toolcallingversion`, lo stesso input produce lo stesso output (determinismo statistico). [file:2]

### 6.2 PipelineVersion (contratto metadati)
Il v3 propone una `PipelineVersion` (dataclass frozen) da salvare nei metadati per audit/backtesting. [file:2]

**Checklist pratica**:
- logga sempre PipelineVersion insieme all’output LLM,
- “freeze” dictionaryversion durante il run: aggiornamenti dizionari solo a fine batch con nuova versione. [file:2]

---

## 7) Architettura consigliata (demo e produzione)

### 7.1 Pattern a servizi separati (deciso in chat, coerente con v3)
- **FastAPI** = orchestratore e validatore. [file:2]
- **Inference server** = esecuzione modello (stateless), scalabile indipendentemente. [file:2]
- **Queue/worker** (Redis + Celery) per batch e resilienza (retry/backoff, DLQ). [file:2]

Il v3 suggerisce stack: Python 3.11 + FastAPI, PostgreSQL, Redis, Celery; monitoring Prometheus/Grafana con alert su validation error rate, collision rate, drift, under-triage. [file:2]

### 7.2 Politiche di fallback (production-ready)
- Retry standard su fallimento hard (schema/business rules). [file:1]
- Retry “request più facile” (meno candidati + body più corto). [file:1]
- Fallback su modello/istanza alternativa (stesso schema) quando necessario. [file:2]
- DLQ + human review per casi che non si risolvono automaticamente. [file:2]

---

## 8) Self-hosting: due strade operative (richiesta chat)

> In tutti i casi: **FastAPI resta l’orchestratore**, e la multi-validazione dei PDF resta invariata. [file:1][file:2]

### 8.1 Soluzione DEMO (MVP): Ollama con output strutturato JSON

Decisione: per la demo partire con Ollama, perché consente output JSON e structured outputs. [web:120][web:121]

Requisiti:
- Usare `format: "json"` quando basta avere JSON valido, oppure `format: <JSON Schema>` per structured outputs vincolati. [web:120][web:121]
- Applicare comunque validazione multi-stadio (Stage 1–4) e business rules su enum/candidateid. [file:1]

**Regola di sicurezza**:
- mai fidarsi del solo “format”: se il modello sbaglia un `candidateid` o una label, deve fallire Stage 3 e andare in retry/fallback. [file:1]

### 8.2 Soluzione FUTURA (produzione): SGLang (e/o vLLM) con structured outputs

Decisione: per produzione/scalabilità migrare a un inference server come SGLang (o vLLM) che supporta structured outputs/guided decoding. [file:2][web:106]

Requisiti:
- mantenere lo stesso schema strict,
- mantenere lo stesso validator multi-stadio,
- mantenere PipelineVersion e audit invarianti,
- scalare repliche via Docker/Kubernetes quando l’hardware è definito. [file:2]

---

## 9) Metriche, monitoraggio, valutazione (v3)

Il v3 propone un piano di valutazione con metriche per:
- topics multilabel (micro/macro F1, Hamming loss), [file:2]
- priority ordinale (kappa, under/over-triage), [file:2]
- sentiment (accuracy, F1), [file:2]
- drift detection (test chi-quadro su distribuzioni label a 7/14 giorni). [file:2]

Operativamente, il v3 raccomanda alert su:
- validation error rate,
- collision rate dei dizionari,
- under-triage rate,
- quota UNKNOWNTOPIC. [file:2]

---

## 10) Runbook per istruire un agent (dettagliato)

### 10.1 Compiti dell’agent (sequenza end-to-end del layer LLM)

1) **Input**: ricevi `EmailDocument` canonicalizzato + `dictionaryversion` + candidati deterministici. [file:2][file:1]
2) **Prepara payload**:
   - tronca `body` (es. 8000 char), [file:1]
   - ordina candidati per score composito, [file:1]
   - limita top-N (50/100), [file:1]
   - includi `allowedtopics` e `candidatekeywords` con `candidateid`. [file:1]
3) **Invoca LLM self-hosted**:
   - Demo: Ollama con `format` JSON o schema. [web:120][web:121]
   - Futuro: SGLang (structured outputs). [web:106]
4) **Validazione multi-stadio**:
   - parse JSON, [file:1]
   - validate schema, [file:1]
   - business rules (candidateid exists; labelid in enum), [file:1]
   - quality warnings + dedup. [file:1]
5) **Retry** fino a max (es. 3) se invalid. [file:1]
6) **Verifier extra**:
   - evidence quote presente nel testo, [file:1]
   - keyword presente nel testo/spans coerenti. [file:1]
7) **Persistenza**:
   - salva output validato,
   - salva PipelineVersion completa. [file:2]
8) **Downstream (fuori layer ma collegato)**:
   - calcola `customerstatus` deterministico (CRM lookup), [file:1]
   - priority scoring e confidence adjust (se implementati). [file:1][file:2]

### 10.2 Criteri di accettazione (hard requirements)
- Output sempre validabile (schema strict). [file:1]
- Nessun `candidateid` inventato. [file:1]
- Nessuna label fuori enum. [file:1]
- Almeno un topic (anche UNKNOWNTOPIC). [file:1]
- Evidence presente e corta (≤200 char). [file:1]
- Tracciabilità: PipelineVersion salvata e log completo. [file:2]

### 10.3 Policy di fallback (definitiva)
- Retry N volte.
- Se fallisce: shrink request (top-N più basso + body più corto).
- Se fallisce: fallback su modello/istanza alternativa.
- Se fallisce: DLQ + review. [file:1][file:2]

---

## 11) Bug logici tipici e fix (riassunto operativo)

- **Delegare customerstatus all’LLM** → vietato: deve essere deterministico via CRM. [file:1]
- **Keyword non ancorate ai candidati** → hard fail (Stage 3). [file:1]
- **Evidence inventata** → aggiungere evidence presence check (verifier). [file:1]
- **Troppi candidati/body troppo lungo** → aumentano failure e latenza: top-N e tronco body. [file:1]
- **Output semanticamente debole ma formalmente valido** → usare confidence gating e/o review queue (v3 prevede human review per casi low confidence). [file:2]

