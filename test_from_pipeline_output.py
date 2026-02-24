"""
Test script: uses pipeline_last_output.json as candidate keywords source.

- Loads 'pipeline_last_output.json' produced by the keyword-extraction layer.
- Maps the 'candidates' array to the CandidateKeyword format expected by /triage.
- Calls Ollama /api/chat DIRECTLY (bypasses FastAPI layer) with:
    * role=system  → config/prompts/system_prompt.txt
    * role=user    → config/prompts/user_prompt_template.txt (Jinja2-rendered)
    * format       → config/schema/email_triage_v2.json (JSON Schema)
- Model: gemma3:4b-it-q8_0 via Ollama localhost:11434
"""

import json
import sys
import asyncio
import time
from pathlib import Path

import httpx
from jinja2 import Environment, FileSystemLoader

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]

# ── Load pipeline_last_output.json ────────────────────────────────────────────
PIPELINE_OUTPUT = Path("pipeline_last_output.json")

with PIPELINE_OUTPUT.open(encoding="utf-8") as f:
    pipeline_data = json.load(f)

# Map candidates → CandidateKeyword
# pipeline_last_output fields : candidateid, source, term, lemma, count, embeddingscore, score
# CandidateKeyword fields      : candidate_id, source, term, lemma, count, score  (extra="forbid")
# Candidates are already sorted by score desc; take the top-N best ones.
# Sending all 97 with a 15k-token prompt is too heavy for CPU inference.
TOP_N = 20
raw_candidates = pipeline_data["candidates"][:TOP_N]
candidate_keywords = [
    {
        "candidate_id": c["candidateid"],
        "term":         c["term"],
        "lemma":        c["lemma"],
        "count":        c["count"],
        "source":       c["source"],
        "score":        c["score"],
    }
    for c in raw_candidates
]

# dictionary_version comes from pipeline metadata
dictionary_version: int = (
    pipeline_data.get("metadata", {})
    .get("pipeline_version", {})
    .get("dictionaryversion", 1)
)

# ── Email document (matches the message_id in pipeline_last_output.json) ──────
email_document = {
    "uid": "12345",
    "uidvalidity": "987654321",
    "mailbox": "INBOX",
    "message_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv@example.it",
    "fetched_at": "2024-02-15T14:31:00Z",
    "size": 3456,
    "from_addr_redacted": "Mario Rossi mario.rossi@example.it",
    "to_addrs_redacted": ["supporto@azienda.it", "info@azienda.it"],
    "subject_canonical": "Re: Richiesta informazioni contratto n. 2024/ABC/123",
    "date_parsed": "Thu, 15 Feb 2024 14:30:45 +0100",
    "headers_canonical": {
        "return-path": "mario.rossi@example.it",
        "received": "from mail.example.it ([192.168.1.100]) by mailserver.azienda.it",
        "from": "Mario Rossi mario.rossi@example.it",
        "to": "supporto@azienda.it, info@azienda.it",
        "subject": "Re: Richiesta informazioni contratto n. 2024/ABC/123",
        "date": "Thu, 15 Feb 2024 14:30:45 +0100",
        "message-id": "abcd1234-5678-90ef-ghij-klmnopqrstuv@example.it",
        "in-reply-to": "previous-message-id@azienda.it",
        "references": "previous-message-id@azienda.it",
        "mime-version": "1.0",
        "content-type": "multipart/mixed; boundary=\"----=_Part_12345\"",
        "x-mailer": "Outlook 16.0",
        "x-priority": "3",
    },
    "body_text_canonical": (
        "Buongiorno,\n\n"
        "grazie per la vostra risposta rapida.\n\n"
        "Volevo confermare che i dati sono corretti:\n"
        "- Codice Fiscale: RSSMRA80A01H501U\n"
        "- Telefono: +39 335 1234567\n"
        "- Email: mario.rossi@example.it\n\n"
        "Vorrei procedere con la stipula del contratto n. 2024/ABC/123 come discusso. "
        "Ho verificato tutti i dettagli e sono d'accordo con i termini proposti: "
        "durata 24 mesi, canone mensile di 250\u20ac + IVA, assistenza tecnica inclusa H24, "
        "penali per ritardi di attivazione entro 48 ore dalla firma. "
        "In particolare, confermo l'interesse per l'opzione di pagamento anticipato con sconto del 10%, "
        "come indicato nell'offerta allegata alla vostra precedente mail. "
        "Potete inviarmi il contratto definitivo in formato PDF editabile per apporre la firma digitale? "
        "Ho bisogno di firmarlo entro fine settimana per rispettare le scadenze interne della mia azienda.\n\n"
        "Inoltre, riguardo al contratto precedente (ref. 2023/XYZ/456), che scade a marzo, "
        "vorrei discutere un rinnovo con upgrade al piano premium, includendo il modulo di "
        "fatturazione elettronica integrata con il nostro ERP. "
        "Potete fornirmi un preventivo aggiornato con le nuove tariffe 2024?\n\n"
        "In allegato trovate il documento firmato e i dati aggiuntivi richiesti "
        "(IBAN per domiciliazione, delega amministrativa).\n\n"
        "Restando in attesa di riscontro urgente,\n\n"
        "Mario Rossi\n\n"
        "Mario Rossi\nResponsabile Vendite\nAzienda Example S.r.l.\n"
        "Via Roma 123, 20100 Milano\nTel: +39 02 12345678\nEmail: mario.rossi@example.it\n\n"
        "---\n"
        "Questa email e gli allegati sono confidenziali e destinati esclusivamente\n"
        "ai destinatari indicati. Se avete ricevuto questo messaggio per errore,\n"
        "vi preghiamo di eliminarlo e informarci immediatamente."
    ),
    "body_html_canonical": "",
    "body_original_hash": "e440d55d98d17e941d36467b6a67b6335aacbe80bc20c340a4d022b23b130d23",
    "removed_sections": [
        {"type": "quote_standard",      "span_start": 402, "span_end": 457,
         "content_preview": "\n> Il 14/02/2024 10:23, [supporto@azienda.it ha scritto:", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 458, "span_end": 459,
         "content_preview": ">", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 460, "span_end": 478,
         "content_preview": "> Gentile Cliente,", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 479, "span_end": 480,
         "content_preview": ">", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 481, "span_end": 542,
         "content_preview": "> Abbiamo ricevuto la sua richiesta e la prendiamo in carico.", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 543, "span_end": 600,
         "content_preview": "> Il contratto verrà elaborato entro 3 giorni lavorativi.", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 601, "span_end": 602,
         "content_preview": ">", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 603, "span_end": 620,
         "content_preview": "> Cordiali saluti", "confidence": 1.0},
        {"type": "quote_standard",      "span_start": 621, "span_end": 636,
         "content_preview": "> Team Supporto", "confidence": 1.0},
        {"type": "signature_separator", "span_start": 264, "span_end": 267,
         "content_preview": "\n--", "confidence": 1.0},
        {"type": "closing_formal",      "span_start": 235, "span_end": 252,
         "content_preview": "Cordiali saluti,\n", "confidence": 0.9},
    ],
    "pii_entities": [
        {"type": "CF",       "original_hash": "db3b314a23e8cfe4", "redacted": "RSSMRA80A01H501U",
         "span_start": 114, "span_end": 130, "confidence": 1.0,  "detection_method": "regex"},
        {"type": "PHONE_IT", "original_hash": "d78d127dbfd50fa8", "redacted": "+39 335 1234567",
         "span_start": 143, "span_end": 158, "confidence": 1.0,  "detection_method": "regex"},
        {"type": "EMAIL",    "original_hash": "251fd3c8fb631861", "redacted": "mario.rossi@example.it",
         "span_start": 168, "span_end": 190, "confidence": 1.0,  "detection_method": "regex"},
        {"type": "NAME",     "original_hash": "0673b6b1b193d30c", "redacted": "Mario Rossi",
         "span_start": 235, "span_end": 246, "confidence": 0.81, "detection_method": "ner"},
        {"type": "NAME",     "original_hash": "0673b6b1b193d30c", "redacted": "Mario Rossi",
         "span_start": 248, "span_end": 259, "confidence": 0.81, "detection_method": "ner"},
        {"type": "ORG",      "original_hash": "b01a734e20616f08", "redacted": "Responsabile Vendite",
         "span_start": 260, "span_end": 280, "confidence": 0.90, "detection_method": "ner"},
        {"type": "ORG",      "original_hash": "e2b9728baef8415d", "redacted": "Azienda Example S.r.l",
         "span_start": 281, "span_end": 302, "confidence": 0.90, "detection_method": "ner"},
        {"type": "PHONE_IT", "original_hash": "7d59c1dc01f11001", "redacted": "+39 02 1234567",
         "span_start": 336, "span_end": 350, "confidence": 1.0,  "detection_method": "regex"},
        {"type": "EMAIL",    "original_hash": "251fd3c8fb631861", "redacted": "mario.rossi@example.it",
         "span_start": 359, "span_end": 381, "confidence": 1.0,  "detection_method": "regex"},
    ],
    "pipeline_version": {
        "parser_version":           "email-parser-1.3.0",
        "canonicalization_version": "1.3.0",
        "ner_model_version":        "it_core_news_lg-3.8.2",
        "pii_redaction_version":    "1.0.0",
    },
    "processing_timestamp": "2026-02-18T15:33:36.787857+00:00",
    "processing_duration_ms": 0,
}

# ── Config paths (relative to project root) ───────────────────────────────────
PROJECT_ROOT   = Path(__file__).parent
PROMPTS_DIR    = PROJECT_ROOT / "config" / "prompts"
SCHEMA_PATH    = PROJECT_ROOT / "config" / "schema" / "email_triage_v2.json"

OLLAMA_URL     = "http://localhost:11434"
MODEL          = "gemma3:4b-it-q8_0"
TEMPERATURE    = 0.1
MAX_TOKENS     = 2048
BODY_LIMIT     = 1500  # chars — keep prompt small for CPU inference

# ── Load config files ─────────────────────────────────────────────────────────
jinja_env    = Environment(loader=FileSystemLoader(str(PROMPTS_DIR)), trim_blocks=True, lstrip_blocks=True)
system_tmpl  = jinja_env.get_template("system_prompt.txt")
user_tmpl    = jinja_env.get_template("user_prompt_template.txt")

with SCHEMA_PATH.open(encoding="utf-8") as f:
    json_schema = json.load(f)

# Allowed topics from schema enum
allowed_topics: list[str] = (
    json_schema["properties"]["topics"]["items"]
    ["properties"]["labelid"]["enum"]
)

# ── Build prompts ─────────────────────────────────────────────────────────────
system_prompt = system_tmpl.render().strip()

# Truncate body to keep prompt small
body = email_document["body_text_canonical"][:BODY_LIMIT]

user_prompt = user_tmpl.render(
    dictionary_version = dictionary_version,
    subject            = email_document["subject_canonical"],
    from_addr          = email_document["from_addr_redacted"],
    body               = body,
    allowed_topics     = allowed_topics,
    candidate_keywords = [
        {
            "candidate_id": kw["candidate_id"],
            "term":         kw["term"],
            "lemma":        kw["lemma"],
            "count":        kw["count"],
            "score":        round(kw["score"], 2),
        }
        for kw in candidate_keywords
    ],
).strip()

# ── Ollama /api/chat payload ───────────────────────────────────────────────────
chat_payload = {
    "model":  MODEL,
    "stream": False,
    "messages": [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ],
    "format": json_schema,       # structured output — JSON Schema constraint
    "options": {
        "temperature": TEMPERATURE,
        "num_predict": MAX_TOKENS,
    },
}


async def run_test() -> None:
    ollama_url = f"{OLLAMA_URL}/api/chat"

    print("=" * 80)
    print("  LLM Inference Layer — direct Ollama /api/chat test")
    print("=" * 80)
    print(f"  Input file   : {PIPELINE_OUTPUT}")
    print(f"  Candidates   : {len(candidate_keywords)} (top-{TOP_N} of {len(pipeline_data['candidates'])} total)")
    print(f"  Dict version : {dictionary_version}")
    print(f"  Subject      : {email_document['subject_canonical']}")
    print(f"  Model        : {MODEL}")
    print(f"  Endpoint     : {ollama_url}")
    print(f"  System msg   : {len(system_prompt)} chars")
    print(f"  User msg     : {len(user_prompt)} chars")
    print("=" * 80)

    try:
        async with httpx.AsyncClient(timeout=600.0) as client:
            print("\nSending /api/chat request to Ollama …", flush=True)
            t0 = time.time()
            response = await client.post(ollama_url, json=chat_payload)
            elapsed_ms = int((time.time() - t0) * 1000)

            print(f"HTTP status : {response.status_code}  ({elapsed_ms} ms)")

            if response.status_code == 200:
                raw = response.json()

                # /api/chat response: {"message": {"role": "assistant", "content": "..."}, ...}
                content_str = raw.get("message", {}).get("content", "")
                prompt_tokens     = raw.get("prompt_eval_count")
                completion_tokens = raw.get("eval_count")

                print(f"Tokens      : prompt={prompt_tokens}  completion={completion_tokens}")

                # Parse structured JSON from model output
                try:
                    triage_response = json.loads(content_str)
                except json.JSONDecodeError as exc:
                    print(f"\nERROR: model returned invalid JSON — {exc}")
                    print("Raw content (first 500 chars):")
                    print(content_str[:500])
                    return

                # ── Topics ────────────────────────────────────────────────────
                topics = triage_response.get("topics", [])
                print(f"\n[TOPICS] ({len(topics)})")
                for t in topics:
                    ev_preview = ""
                    for ev in t.get("evidence", [])[:1]:
                        ev_preview = f"  ev=\"{ev.get('quote','')[:80]}\""
                    print(f"  {t.get('labelid','?'):30s}  conf={t.get('confidence',0):.2f}{ev_preview}")

                # ── Sentiment ─────────────────────────────────────────────────
                sentiment = triage_response.get("sentiment", {})
                print(f"\n[SENTIMENT]  {sentiment.get('value','N/A'):10s}  conf={sentiment.get('confidence',0):.2f}")

                # ── Priority ──────────────────────────────────────────────────
                priority = triage_response.get("priority", {})
                print(f"\n[PRIORITY ]  {priority.get('value','N/A'):10s}  conf={priority.get('confidence',0):.2f}")
                for sig in priority.get("signals", [])[:3]:
                    print(f"  signal: {sig}")

                # ── Keywords (flattened across all topics) ────────────────────
                all_kw: dict[str, dict] = {}
                for t in topics:
                    for kw in t.get("keywordsintext", []):
                        cid = kw.get("candidateid", "?")
                        if cid not in all_kw:
                            # look up original term from candidates list
                            term = next(
                                (c["term"] for c in candidate_keywords if c["candidate_id"] == cid),
                                kw.get("lemma", "?")
                            )
                            all_kw[cid] = {"term": term, **kw}
                print(f"\n[KEYWORDS] ({len(all_kw)} unique across all topics)")
                for kw in list(all_kw.values())[:15]:
                    print(f"  {kw.get('term','?'):35s}  id={kw.get('candidateid','?')}")

                # ── Ollama timing metadata ────────────────────────────────────
                total_ns = raw.get("total_duration", 0)
                eval_ns  = raw.get("eval_duration", 0)
                print(f"\n[TIMING]  total={total_ns//1_000_000} ms  eval={eval_ns//1_000_000} ms  (wall={elapsed_ms} ms)")

                # ── Save full result ───────────────────────────────────────────
                out = {
                    "model":              raw.get("model"),
                    "created_at":         raw.get("created_at"),
                    "triage_response":    triage_response,
                    "prompt_tokens":      prompt_tokens,
                    "completion_tokens":  completion_tokens,
                    "total_duration_ms":  total_ns // 1_000_000,
                    "messages_sent": [
                        {"role": "system", "content_length": len(system_prompt)},
                        {"role": "user",   "content_length": len(user_prompt)},
                    ],
                }
                out_file = Path("triage_result_gemma.json")
                out_file.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
                print(f"\nFull result saved to: {out_file}")

            else:
                print(f"\nERROR {response.status_code}:")
                print(response.text[:2000])

    except httpx.ConnectError:
        print(f"\nERROR: cannot connect to {OLLAMA_URL}")
        print("  Make sure Ollama is running:  ollama serve")
    except httpx.TimeoutException:
        print("\nERROR: request timed out (600 s)")
    except Exception as exc:
        print(f"\nERROR: {type(exc).__name__}: {exc}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(run_test())
