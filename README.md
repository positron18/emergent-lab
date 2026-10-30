# Emergent Lab — MVP 0.1

Un esperimento piccolo e verificabile per osservare **eventuali** comportamenti sociali spontanei in una popolazione di agenti indipendenti che affrontano problemi FinQA.

## Cosa fa davvero

- Gestisce identità agentiche separate, ciascuna con uno spazio privato e un archivio comune.
- Offre azioni minime: elenco file comuni, lettura, scrittura, risposta e annotazione.
- Distribuisce questioni finanziarie FinQA, senza passare le risposte di riferimento ai modelli.
- Conserva un registro SQLite delle azioni, delle letture e delle scritture.
- Confronta risposte numeriche con tolleranza indicativa dell'1% (non è lo scorer ufficiale FinQA).
- Funziona in modalità **demo**, puramente scripted, o **llm** tramite API chat completions compatibili.

**Importante:** la demo non è una simulazione convincente dell'emergenza sociale: è soltanto un test dell'infrastruttura. Questo MVP inoltre registra l'accesso ai documenti ma non dimostra automaticamente che il contenuto venga riutilizzato. I task del benchmark pubblico possono essere già noti ai modelli: non usare i risultati come prova di generalizzazione.

## Requisiti

macOS, Python 3.10+ e accesso Internet per scaricare FinQA e utilizzare un provider LLM. Nessuna libreria Python esterna. Nessun Docker richiesto per questo MVP, **perché non viene eseguito codice prodotto dagli agenti**: le azioni sono soltanto operazioni limitate sui file testuali virtuali.

## Avvio, senza costi API

```bash
cd emergent-lab
python3 lab.py --mode demo --agents 3 --tasks 3 --turns 3
```

Viene creato `runs/<timestamp>/`, con `events.sqlite3`, `metadata.json`, cartelle `private/` e `shared/`.

Per esaminare i risultati, sostituire il percorso visualizzato:

```bash
python3 report.py runs/20260101-120000
```

## Avvio con agenti LLM reali

Scarica lo split di sviluppo ufficiale FinQA (solo per il benchmark; i dati di riferimento non vengono inviati ai modelli):

```bash
python3 lab.py --fetch-dev
```

Definisci le credenziali per il tuo provider con endpoint chat-completions compatibile:

```bash
export LAB_API_KEY='LA_TUA_CHIAVE'
export LAB_MODEL='nome-modello-del-provider'
export LAB_ENDPOINT='https://api.tuo-provider.example/v1/chat/completions'
python3 lab.py --mode llm --dataset finqa_dev.json --agents 3 --tasks 6 --turns 5
```

Per OpenAI, l'endpoint predefinito è `https://api.openai.com/v1/chat/completions`; scegli un modello disponibile sulla tua chiave e compatibile con l'API. Non incorporare chiavi in file o repository. Per un primo test reale suggerisco **3 agenti, 6 task e 5 turni** con budget provider molto piccolo.

**Nota privacy/sicurezza:** le chiamate ai provider includono contenuto FinQA pubblico e gli artefatti che l'agente decide di leggere. Non usare credenziali, dati privati o segreti negli artefatti. Questo MVP non concede agli agenti shell, scrittura fuori dalla cartella del run o navigazione Internet diretta; limita i nomi file e le dimensioni degli artefatti. Usa soltanto endpoint HTTPS o HTTP locale.

## Limiti intenzionali e prossimi passi

1. I turni sono sequenziali e i task vengono distribuiti in ordine mescolato. Per comportamenti sociali più profondi andrebbe introdotta una scheduler a round-robin *dentro* ogni task (interleaving agenti) e una memoria di sessione più ricca.
2. `report.py` presenta i log grezzi: non esiste ancora una dashboard né inferenza automatica delle relazioni.
3. Lo scorer è un'approssimazione per numeri e percentuali: casi con unità, scale o formule devono essere verificati separatamente.
4. Non viene eseguito codice generato dagli agenti: per consentire strumenti Python creati autonomamente serve una vera sandbox senza rete, con limite di risorse.
5. Serve una condizione sperimentale senza spazio condiviso, per distinguere la collaborazione dagli effetti del modello e del benchmark.
6. In questa versione il prompt rivela la presenza di un archivio comune, ma non di altri agenti né di un obbligo a collaborare.

Fonte dati: [FinQA ufficiale](https://github.com/czyssrs/FinQA) (Chen et al., EMNLP 2021). Controlla e rispetta le licenze delle fonti prima di ridistribuire dati o derivati.
