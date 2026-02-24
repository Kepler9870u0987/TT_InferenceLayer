**Pipeline di Triage Email con LLM**

Design, Ottimizzazione Prompt e Thread Tracking

Documento tecnico --- Febbraio 2025

**1. Architettura Ollama: generate vs chat**

Ollama espone due endpoint distinti per interagire con i modelli. Scegliere quello giusto impatta la qualità dell\'output, il consumo di token e la manutenibilità del codice.

**1.1 Differenze fondamentali**

|                   |                                       |
|-------------------|---------------------------------------|
| **Aspetto**       | **/api/generate**                     |
| Input             | prompt (stringa unica)                |
| Chat template     | Non applicato                         |
| Controllo formato | Totale --- testo grezzo               |
| Uso tipico        | Pipeline custom, prompt pre-costruiti |
| format: json      | Supportato (meno affidabile)          |

|                     |                                |
|---------------------|--------------------------------|
| **Aspetto**         | **/api/generate vs /api/chat** |
| Stringa unica       | Array messages\[\]             |
| No chat template    | Chat template automatico       |
| Controllo totale    | Gestito da Ollama              |
| Pipeline RAG custom | Chatbot multi-turn             |

**1.2 /api/generate --- formato stringa singola**

> POST /api/generate
>
> {
>
> \"model\": \"llama3\",
>
> \"prompt\": \"Sei un assistente. Analizza questa email: \...\"
>
> }

Il modello riceve tutto come un unico blocco di testo. Nessuna struttura conversazionale --- il developer assembla manualmente system + storia + domanda in un\'unica stringa.

**1.3 /api/chat --- formato messaggi strutturati**

> POST /api/chat
>
> {
>
> \"model\": \"llama3\",
>
> \"messages\": \[
>
> { \"role\": \"system\", \"content\": \"Sei un assistente specializzato.\" },
>
> { \"role\": \"user\", \"content\": \"Analizza questa email\...\" }
>
> \],
>
> \"format\": \"json\"
>
> }

Ollama applica internamente il chat template corretto per il modello (es. \[INST\]\...\[/INST\] per Mistral, \<\|im_start\|\> per Qwen).

**2. Scelta dell\'endpoint per la pipeline email**

|                                                                                                            |
|------------------------------------------------------------------------------------------------------------|
| Conclusione: per analisi email stateless con output JSON strutturato, usare /api/chat con format: \"json\" |

**2.1 Motivazioni**

Con Jinja2 come sistema di templating, la separazione tra system e user message è naturale e leggibile. I template rimangono file distinti, più facili da versionare e mantenere.

L\'opzione format: \"json\" di Ollama forza il modello a rispondere con JSON valido a livello di sampling --- non solo tramite prompt. Questo è critico quando l\'output viene validato programmaticamente.

Con /api/generate si dovrebbero gestire manualmente i separatori specifici per ogni modello. Con /api/chat + Jinja2 questo è completamente trasparente.

**2.2 Setup consigliato**

**system_prompt.j2**

> Sei un assistente che analizza email aziendali italiane.
>
> Rispondi SEMPRE in JSON con questa struttura:
>
> {
>
> \"classificazione\": \"\...\",
>
> \"tag\": \[\...\],
>
> \"riassunto\": \"\...\",
>
> \"risposta_suggerita\": \"\...\"
>
> }

**user_message.j2**

> Analizza questa email:
>
> Mittente: {{ email.from }}
>
> Oggetto: {{ email.subject }}
>
> Corpo:
>
> {{ email.body }}

**Request Ollama**

> {
>
> \"model\": \"llama3\",
>
> \"messages\": \[
>
> { \"role\": \"system\", \"content\": \"\<rendered system_prompt.j2\>\" },
>
> { \"role\": \"user\", \"content\": \"\<rendered user_message.j2\>\" }
>
> \],
>
> \"format\": \"json\"
>
> }

**3. Valutazione del Prompt di Triage**

**3.1 Struttura attuale**

Il prompt analizzato è composto da due parti: un system prompt (\~2400 caratteri) e un user prompt (\~4800 caratteri). Il sistema istruisce il modello ad analizzare email italiane e produrre un JSON strutturato con topic, keyword, sentiment e priority.

**3.2 Punti di forza**

- Chiarezza delle regole --- CRITICAL RULES numerate e in grassetto. Il modello capisce immediatamente cosa è vincolante.

- Grounding sui candidati --- forzare i keyword a referenziare un candidate_id elimina allucinazioni e rende l\'output validabile programmaticamente.

- Schema JSON esplicito nel prompt con valori ammessi (es. positive\|neutral\|negative) riduce drasticamente gli errori di formato.

- dictionaryversion --- ottima pratica per il versioning: permette di rilevare response cachate o generate con dizionari obsoleti.

- Evidence quotes --- chiedere citazioni esatte forza il modello a giustificare la classificazione, riducendo risultati arbitrari.

**3.3 Aree di miglioramento**

**Struttura system/user ridondante**

Il blocco INSTRUCTIONS e lo schema JSON sono statici ma compaiono nel user message. Tutto ciò che non cambia tra una chiamata e l\'altra dovrebbe stare nel system prompt. Nel user message devono comparire solo email, topic ammessi e keyword candidate.

**Keyword list verbosa**

Ogni candidato viene passato con Term, Lemma, Count e Score. Il modello ha bisogno solo di ID e termine per referenziarlo --- gli altri campi vengono usati lato codice dopo aver ricevuto il JSON.

Formato attuale (costoso):

> \- ID: L4CD0keGl10i4l43 \| Term: \"contratto\" \| Lemma: \"contrattare\" \| Count: 1 \| Score: 0.46

Formato ottimizzato:

> L4CD0keGl10i4l43:contratto

**Distinzione high vs urgent**

Senza una regola esplicita il modello tende ad overclassificare come urgent. Aggiungere nel system prompt la distinzione: high = deadline esistente con tono neutro; urgent = deadline + tono pressante/emotivo.

**UNKNOWNTOPIC senza esempi**

Il topic di escape viene usato raramente perché il modello non ha esempi di quando applicarlo. Aggiungere nel system prompt 2-3 esempi (spam, OOO, newsletter) migliora la precisione.

**3.4 Giudizio complessivo**

|                       |            |                           |            |
|-----------------------|------------|---------------------------|------------|
| **Aspetto**           | **Voto**   | **Aspetto**               | **Voto**   |
| Chiarezza regole      | ⭐⭐⭐⭐⭐ | Prevenzione allucinazioni | ⭐⭐⭐⭐⭐ |
| Struttura system/user | ⭐⭐⭐     | Robustezza schema         | ⭐⭐⭐⭐   |
| Token efficiency      | ⭐⭐⭐     | Versioning dizionario     | ⭐⭐⭐⭐⭐ |

**4. Ottimizzazione del Prompt (Risorse Limitate)**

|                                                                                                             |
|-------------------------------------------------------------------------------------------------------------|
| Obiettivo: ridurre il consumo di token senza perdere qualità classificatoria, in ambienti con RAM limitata. |

**4.1 Livelli di ottimizzazione**

**Livello 1 --- Elimina ridondanze (-30% token, facile)**

Rimuovere il blocco REMEMBER finale e le spiegazioni verbose nelle CRITICAL RULES. Mantenere solo valori ammessi ed esempi minimi, eliminando le descrizioni narrative delle regole.

**Livello 2 --- Separa statico da dinamico (-20% token nel user)**

Spostare nel system prompt: INSTRUCTIONS, schema JSON, tutte le regole fisse. Mantenere nel user message solo i tre blocchi variabili per chiamata: email, topic list, keyword list.

**Livello 3 --- Comprimi formato keyword (impatto alto)**

Passare solo ID e termine, senza lemma, count e score. Il risparmio è significativo su email con molti candidati.

**Livello 4 --- Pre-filtra le keyword candidate**

Passare solo le top 8-10 keyword per score, eliminando varianti sovrapposte (\"contratto\", \"informazioni contratto\", \"contratto abc\" sono varianti dello stesso concetto). Il pre-filtro avviene lato codice prima della chiamata LLM.

**Livello 5 --- Modello quantizzato + prompt minimale**

Usare un modello Q4_K_M e ridurre il system prompt all\'essenziale. Con validazione programmatica del JSON e retry su malformazione, le istruzioni verbose non sono strettamente necessarie.

**4.2 Stima risparmio token**

|                    |                   |
|--------------------|-------------------|
| **Configurazione** | **Token stimati** |
| Prompt attuale     | \~1800 token      |
| Dopo Livello 1+2   | \~1200 token      |
| Dopo Livello 3+4   | \~700 token       |
| Dopo Livello 5     | \~400 token       |

|                                                                                                                                                |
|------------------------------------------------------------------------------------------------------------------------------------------------|
| Raccomandazione: iniziare dal Livello 3 (compressione formato keyword). Miglior rapporto effort/risparmio senza toccare la logica del sistema. |

**5. Thread Tracking --- Architettura**

La pipeline attuale è completamente stateless: ogni email viene analizzata in isolamento. Questo comporta classificazioni subottimali su thread lunghi, riclassificazioni ridondanti e nessuna visibilità sui cambi di topic nel tempo.

**5.1 Diagnosi del sistema attuale**

- Input singolo per chiamata --- nessun campo thread history nel modello di input

- Prompt costruito solo sull\'email corrente --- nessun contesto delle email precedenti

- Il pre-processing rimuove attivamente il thread --- le quote (\> \...) vengono eliminate upstream

- Redis salva i risultati ma non li re-inietta nelle chiamate successive

- Chiamata Ollama come singolo generate --- nessuna memoria inter-request

**5.2 Struttura dati Redis**

Ogni thread avrà una chiave dedicata che accumula i risultati di triage precedenti con TTL rolling di 7 giorni.

> thread:{thread_id} → JSON con TTL 7 giorni (rolling)
>
> {
>
> \"messages\": \[
>
> {
>
> \"message_id\": \"abc123\",
>
> \"timestamp\": \"2024-01-10T10:00:00Z\",
>
> \"from\": \"mario@example.com\",
>
> \"subject_canonical\": \"contratto fornitura\",
>
> \"keywords\": \[\"contratto\", \"fornitura\"\],
>
> \"category\": \"CONTRATTO\",
>
> \"priority\": \"high\",
>
> \"summary\": \"Richiesta revisione clausola 4b\"
>
> }
>
> \],
>
> \"thread_category\": \"CONTRATTO\",
>
> \"topic_drift_detected\": false,
>
> \"last_updated\": \"2024-01-10T10:00:00Z\"
>
> }

**5.3 Modifiche ai layer**

**input_models.py**

> class EmailDocument(BaseModel):
>
> thread_id: str \# nuovo campo obbligatorio
>
> message_id: str
>
> subject_canonical: str
>
> body_text_canonical: str
>
> from_addr_redacted: str
>
> removed_sections: list\[str\]
>
> candidate_keywords: list\[str\]

**repository.py --- ThreadRepository (nuovo)**

> class ThreadRepository:
>
> THREAD_PREFIX = \"thread:\"
>
> TTL_SECONDS = 7 \* 24 \* 3600 \# 7 giorni rolling
>
> def get_thread_context(self, thread_id: str) -\> dict \| None:
>
> raw = self.redis.get(f\"{self.THREAD_PREFIX}{thread_id}\")
>
> return json.loads(raw) if raw else None
>
> def append_message_result(self, thread_id, result) -\> dict:
>
> context = self.get_thread_context(thread_id) or {\"messages\": \[\]}
>
> context\[\"messages\"\].append(result.to_thread_entry())
>
> context\[\"topic_drift_detected\"\] = self.\_detect_drift(context\[\"messages\"\])
>
> context\[\"thread_category\"\] = self.\_dominant_category(context\[\"messages\"\])
>
> self.redis.setex(f\"{self.THREAD_PREFIX}{thread_id}\",
>
> self.TTL_SECONDS, json.dumps(context))
>
> return context
>
> def is_duplicate(self, thread_id: str, message_id: str) -\> bool:
>
> ctx = self.get_thread_context(thread_id)
>
> return ctx and any(m\[\"message_id\"\] == message_id for m in ctx\[\"messages\"\])
>
> def \_detect_drift(self, messages: list) -\> bool:
>
> if len(messages) \< 2: return False
>
> cats = \[m\[\"category\"\] for m in messages\]
>
> dominant = max(set(cats\[:-1\]), key=cats\[:-1\].count)
>
> return cats\[-1\] != dominant

**triage_service.py --- orchestrazione aggiornata**

> async def triage(self, email: EmailDocument) -\> TriageResult:
>
> \# 1. Deduplication --- skip se gia classificata
>
> if self.thread_repo.is_duplicate(email.thread_id, email.message_id):
>
> return self.triage_repo.get_cached_result(email.message_id)
>
> \# 2. Carica contesto thread
>
> thread_context = self.thread_repo.get_thread_context(email.thread_id)
>
> \# 3. Build prompt con contesto
>
> prompt = self.prompt_builder.build(email, thread_context=thread_context)
>
> \# 4. Chiama LLM
>
> result = await self.llm_client.generate(prompt)
>
> \# 5. Salva risultato singolo (audit, TTL 24h)
>
> self.triage_repo.save(email.message_id, result)
>
> \# 6. Aggiorna memoria thread (TTL 7gg rolling)
>
> thread_state = self.thread_repo.append_message_result(email.thread_id, result)
>
> \# 7. Arricchisci result con stato aggregato
>
> result.thread_summary = thread_state
>
> result.topic_drift = thread_state\[\"topic_drift_detected\"\]
>
> return result

**user_prompt_template.txt --- sezione thread opzionale**

> {% if thread_context and thread_context.messages %}
>
> === THREAD CONTEXT ({{ thread_context.messages \| length }} messaggi precedenti) ===
>
> {% for msg in thread_context.messages\[-3:\] %}
>
> \- \[{{ msg.timestamp }}\] {{ msg.from }} \| category: {{ msg.category }} \| \"{{ msg.summary }}\"
>
> {% endfor %}
>
> Thread dominant category: {{ thread_context.thread_category }}
>
> {% if thread_context.topic_drift_detected %}
>
> ⚠️ Topic drift rilevato in questo thread.
>
> {% endif %}
>
> === END THREAD CONTEXT ===
>
> {% endif %}
>
> Classifica la seguente email tenendo conto del contesto sopra:
>
> \...

**5.4 Flusso completo**

|                                                          |
|----------------------------------------------------------|
| Email in arrivo (con thread_id)                          
 │                                                         
 ▼                                                         
 Già classificata? ──YES──► ritorna cached result (dedup)  
 │ NO                                                      
 ▼                                                         
 Carica thread context da Redis                            
 │                                                         
 ▼                                                         
 Build prompt + thread context (ultimi 3 msg)              
 │                                                         
 ▼                                                         
 LLM classify                                              
 │                                                         
 ├──► Redis: salva risultato singolo (TTL 24h, audit)      
 └──► Redis: aggiorna thread state (TTL 7gg rolling)       |

**5.5 Priorità di implementazione**

Rollout graduale con feature flag per ogni step:

|                                                           |                                                  |
|-----------------------------------------------------------|--------------------------------------------------|
| **Step**                                                  | **Obiettivo**                                    |
| Step 1 --- ThreadRepository.is_duplicate                  | Deduplication immediata, zero rischio            |
| Step 2 --- ThreadRepository.append_message_result         | Accumula contesto senza ancora usarlo nel prompt |
| Step 3 --- Inject thread context nel prompt               | Migliora la classificazione                      |
| Step 4 --- Topic drift + aggregated category nel response | Analytics e monitoraggio                         |

**6. Riepilogo Decisioni Architetturali**

|                           |                                                    |
|---------------------------|----------------------------------------------------|
| **Decisione**             | **Scelta**                                         |
| Endpoint Ollama           | /api/chat con format: json                         |
| Templating                | Jinja2 --- system e user come template separati    |
| Output strutturato        | JSON validato programmaticamente                   |
| Keyword grounding         | candidate_id con formato compresso                 |
| Memoria thread            | Redis con TTL rolling 7 giorni                     |
| Deduplication             | is_duplicate su message_id                         |
| Contesto nel prompt       | Ultimi 3 messaggi del thread (jinja2 opzionale)    |
| Gestione risorse limitate | Livello 3+4: keyword compresse + pre-filtro top 10 |

*Documento generato con Claude --- Febbraio 2025*
