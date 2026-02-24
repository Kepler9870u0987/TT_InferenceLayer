"""
Test script for LLM Inference Layer with provided Italian email input.
Uses Gemma model via Ollama.
"""

import json
import httpx
import asyncio
import sys
from datetime import datetime

# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Test input data - Italian contract email
test_input = {
    "email": {
        "uid": "12345",
        "uidvalidity": "987654321",
        "mailbox": "INBOX",
        "message_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv@example.it",
        "fetched_at": "2024-02-15T14:31:00Z",
        "size": 3456,
        "from_addr_redacted": "Mario Rossi mario.rossi@example.it",
        "to_addrs_redacted": [
            "supporto@azienda.it",
            "info@azienda.it"
        ],
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
            "x-priority": "3"
        },
        "body_text_canonical": "Buongiorno,\n\ngrazie per la vostra risposta rapida.\n\nVolevo confermare che i dati sono corretti:\n- Codice Fiscale: RSSMRA80A01H501U\n- Telefono: +39 335 1234567\n- Email: mario.rossi@example.it\n\nVorrei procedere con la stipula del contratto n. 2024/ABC/123 come discusso. Ho verificato tutti i dettagli e sono d'accordo con i termini proposti: durata 24 mesi, canone mensile di 250€ + IVA, assistenza tecnica inclusa H24, penali per ritardi di attivazione entro 48 ore dalla firma. In particolare, confermo l'interesse per l'opzione di pagamento anticipato con sconto del 10%, come indicato nell'offerta allegata alla vostra precedente mail. Potete inviarmi il contratto definitivo in formato PDF editabile per apporre la firma digitale? Ho bisogno di firmarlo entro fine settimana per rispettare le scadenze interne della mia azienda.\n\nInoltre, riguardo al contratto precedente (ref. 2023/XYZ/456), che scade a marzo, vorrei discutere un rinnovo con upgrade al piano premium, includendo il modulo di fatturazione elettronica integrata con il nostro ERP. Potete fornirmi un preventivo aggiornato con le nuove tariffe 2024?\n\nIn allegato trovate il documento firmato e i dati aggiuntivi richiesti (IBAN per domiciliazione, delega amministrativa).\n\nRestando in attesa di riscontro urgente,\n\nMario Rossi\n\nMario Rossi\nResponsabile Vendite\nAzienda Example S.r.l.\nVia Roma 123, 20100 Milano\nTel: +39 02 12345678\nEmail: mario.rossi@example.it\n\n---\nQuesta email e gli allegati sono confidenziali e destinati esclusivamente\nai destinatari indicati. Se avete ricevuto questo messaggio per errore,\nvi preghiamo di eliminarlo e informarci immediatamente.",
        "body_html_canonical": "",
        "body_original_hash": "e440d55d98d17e941d36467b6a67b6335aacbe80bc20c340a4d022b23b130d23",
        "removed_sections": [
            {
                "type": "quote_standard",
                "span_start": 402,
                "span_end": 457,
                "content_preview": "\n> Il 14/02/2024 10:23, [supporto@azienda.it ha scritto:",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 458,
                "span_end": 459,
                "content_preview": ">",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 460,
                "span_end": 478,
                "content_preview": "> Gentile Cliente,",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 479,
                "span_end": 480,
                "content_preview": ">",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 481,
                "span_end": 542,
                "content_preview": "> Abbiamo ricevuto la sua richiesta e la prendiamo in carico.",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 543,
                "span_end": 600,
                "content_preview": "> Il contratto verrà elaborato entro 3 giorni lavorativi.",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 601,
                "span_end": 602,
                "content_preview": ">",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 603,
                "span_end": 620,
                "content_preview": "> Cordiali saluti",
                "confidence": 1.0
            },
            {
                "type": "quote_standard",
                "span_start": 621,
                "span_end": 636,
                "content_preview": "> Team Supporto",
                "confidence": 1.0
            },
            {
                "type": "signature_separator",
                "span_start": 264,
                "span_end": 267,
                "content_preview": "\n--",
                "confidence": 1.0
            },
            {
                "type": "closing_formal",
                "span_start": 235,
                "span_end": 252,
                "content_preview": "Cordiali saluti,\n",
                "confidence": 0.9
            }
        ],
        "pii_entities": [
            {
                "type": "CF",
                "original_hash": "db3b314a23e8cfe4",
                "redacted": "RSSMRA80A01H501U",
                "span_start": 114,
                "span_end": 130,
                "confidence": 1.0,
                "detection_method": "regex"
            },
            {
                "type": "PHONE_IT",
                "original_hash": "d78d127dbfd50fa8",
                "redacted": "+39 335 1234567",
                "span_start": 143,
                "span_end": 158,
                "confidence": 1.0,
                "detection_method": "regex"
            },
            {
                "type": "EMAIL",
                "original_hash": "251fd3c8fb631861",
                "redacted": "mario.rossi@example.it",
                "span_start": 168,
                "span_end": 190,
                "confidence": 1.0,
                "detection_method": "regex"
            },
            {
                "type": "NAME",
                "original_hash": "0673b6b1b193d30c",
                "redacted": "Mario Rossi",
                "span_start": 235,
                "span_end": 246,
                "confidence": 0.81,
                "detection_method": "ner"
            },
            {
                "type": "NAME",
                "original_hash": "0673b6b1b193d30c",
                "redacted": "Mario Rossi",
                "span_start": 248,
                "span_end": 259,
                "confidence": 0.81,
                "detection_method": "ner"
            },
            {
                "type": "ORG",
                "original_hash": "b01a734e20616f08",
                "redacted": "Responsabile Vendite",
                "span_start": 260,
                "span_end": 280,
                "confidence": 0.90,
                "detection_method": "ner"
            },
            {
                "type": "ORG",
                "original_hash": "e2b9728baef8415d",
                "redacted": "Azienda Example S.r.l",
                "span_start": 281,
                "span_end": 302,
                "confidence": 0.9,
                "detection_method": "ner"
            },
            {
                "type": "PHONE_IT",
                "original_hash": "7d59c1dc01f11001",
                "redacted": "+39 02 1234567",
                "span_start": 336,
                "span_end": 350,
                "confidence": 1.0,
                "detection_method": "regex"
            },
            {
                "type": "EMAIL",
                "original_hash": "251fd3c8fb631861",
                "redacted": "mario.rossi@example.it",
                "span_start": 359,
                "span_end": 381,
                "confidence": 1.0,
                "detection_method": "regex"
            }
        ],
        "pipeline_version": {
            "parser_version": "email-parser-1.3.0",
            "canonicalization_version": "1.3.0",
            "ner_model_version": "it_core_news_lg-3.8.2",
            "pii_redaction_version": "1.0.0"
        },
        "processing_timestamp": "2026-02-18T15:33:36.787857+00:00",
        "processing_duration_ms": 0
    },
    "candidate_keywords": [
        {"candidate_id": "hash_contratto", "term": "contratto", "lemma": "contratto", "count": 5, "source": "body", "score": 0.95},
        {"candidate_id": "hash_informazioni", "term": "informazioni", "lemma": "informazione", "count": 2, "source": "subject", "score": 0.92},
        {"candidate_id": "hash_stipula", "term": "stipula", "lemma": "stipula", "count": 1, "source": "body", "score": 0.90},
        {"candidate_id": "hash_firma", "term": "firma", "lemma": "firmare", "count": 2, "source": "body", "score": 0.88},
        {"candidate_id": "hash_fatturazione", "term": "fatturazione", "lemma": "fatturazione", "count": 1, "source": "body", "score": 0.85},
        {"candidate_id": "hash_rinnovo", "term": "rinnovo", "lemma": "rinnovo", "count": 1, "source": "body", "score": 0.83},
        {"candidate_id": "hash_pagamento", "term": "pagamento", "lemma": "pagamento", "count": 1, "source": "body", "score": 0.80},
        {"candidate_id": "hash_preventivo", "term": "preventivo", "lemma": "preventivo", "count": 1, "source": "body", "score": 0.78},
        {"candidate_id": "hash_scadenza", "term": "scadenza", "lemma": "scadenza", "count": 1, "source": "body", "score": 0.75},
        {"candidate_id": "hash_assistenza", "term": "assistenza", "lemma": "assistenza", "count": 1, "source": "body", "score": 0.73},
        {"candidate_id": "hash_offerta", "term": "offerta", "lemma": "offerta", "count": 1, "source": "body", "score": 0.70},
        {"candidate_id": "hash_tariffe", "term": "tariffe", "lemma": "tariffa", "count": 1, "source": "body", "score": 0.68},
        {"candidate_id": "hash_upgrade", "term": "upgrade", "lemma": "upgrade", "count": 1, "source": "body", "score": 0.65},
        {"candidate_id": "hash_urgente", "term": "urgente", "lemma": "urgente", "count": 1, "source": "body", "score": 0.63},
        {"candidate_id": "hash_allegato", "term": "allegato", "lemma": "allegato", "count": 1, "source": "body", "score": 0.60},
    ],
    "dictionary_version": 1
}


async def test_triage():
    """Test the triage endpoint with the Italian contract email."""
    
    api_url = "http://localhost:8000/triage"
    
    print("=" * 80)
    print("Testing LLM Inference Layer with Gemma")
    print("=" * 80)
    print(f"\nAPI URL: {api_url}")
    print(f"Email UID: {test_input['email']['uid']}")
    print(f"Subject: {test_input['email']['subject_canonical']}")
    print(f"Candidate Keywords: {len(test_input['candidate_keywords'])}")
    print(f"\nBody preview (first 200 chars):")
    print(test_input['email']['body_text_canonical'][:200] + "...")
    print("\n" + "=" * 80)
    
    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            print("\n🚀 Sending triage request...")
            
            response = await client.post(api_url, json=test_input)
            
            print(f"\n✅ Response Status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                
                print("\n" + "=" * 80)
                print("TRIAGE RESULT")
                print("=" * 80)
                
                # Extract main results
                triage_result = result.get("result", {})
                triage_response = triage_result.get("triage_response", {})
                
                # Topics
                topics = triage_response.get("topics", [])
                print(f"\n📋 Topics ({len(topics)}):")
                for topic in topics:
                    print(f"   - {topic['labelid']} (confidence: {topic['confidence']:.2f})")
                    if 'evidence' in topic:
                        print(f"     Evidence: {topic['evidence'][:100]}...")
                
                # Sentiment
                sentiment = triage_response.get("sentiment", {})
                print(f"\n😊 Sentiment: {sentiment.get('label', 'N/A')} (confidence: {sentiment.get('confidence', 0):.2f})")
                if 'evidence' in sentiment:
                    print(f"   Evidence: {sentiment['evidence'][:100]}...")
                
                # Priority
                priority = triage_response.get("priority", {})
                print(f"\n⚡ Priority: {priority.get('label', 'N/A')} (confidence: {priority.get('confidence', 0):.2f})")
                if 'evidence' in priority:
                    print(f"   Evidence: {priority['evidence'][:100]}...")
                
                # Keywords
                keywords = triage_response.get("keywords", [])
                print(f"\n🔑 Keywords ({len(keywords)}):")
                for kw in keywords[:10]:  # Show first 10
                    print(f"   - {kw['term']} (candidate_id: {kw['candidateid']}, count: {kw.get('count', 'N/A')})")
                
                # Processing info
                print(f"\n⏱️  Processing Duration: {triage_result.get('processing_duration_ms', 0)} ms")
                print(f"🔄 Retries Used: {triage_result.get('retries_used', 0)}")
                
                # Warnings
                warnings = result.get("warnings", [])
                if warnings:
                    print(f"\n⚠️  Warnings ({len(warnings)}):")
                    for warning in warnings:
                        print(f"   - {warning}")
                else:
                    print("\n✓ No validation warnings")
                
                # Save full result to file
                output_file = "triage_result.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(result, f, indent=2, ensure_ascii=False)
                print(f"\n💾 Full result saved to: {output_file}")
                
            else:
                print(f"\n❌ Error: {response.status_code}")
                print(response.text)
                
    except httpx.ConnectError:
        print("\n❌ ERROR: Could not connect to API")
        print("   Make sure the FastAPI server is running on http://localhost:8000")
        print("   Start it with: uvicorn inference_layer.main:app --reload")
    except httpx.TimeoutException:
        print("\n❌ ERROR: Request timed out")
        print("   The LLM might be taking too long to respond")
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
    
    print("\n" + "=" * 80)


if __name__ == "__main__":
    asyncio.run(test_triage())
