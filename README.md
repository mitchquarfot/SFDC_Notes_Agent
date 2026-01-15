# SFDC Notes Agent (Local)

Local app to upload multiple sales-call transcripts (Gong/Zoom exports like `.txt`, `.vtt`, `.srt`) and generate **concise, tailored notes per opportunity** that you can paste or upload into Salesforce.

## What you get
- Upload **multiple transcripts at once**
- Assign each transcript to an **Opportunity / Account**
- Generate **structured notes** (summary, pain, stakeholders, next steps, risks, etc.)
- Export **CSV** for weekly/twice-weekly Salesforce updates
- Optional: push notes to Salesforce via API (requires credentials)

## Quick start

### 1) Create a venv and install deps
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2) Configure (choose ONE LLM backend)
Copy `env.example` to `.env` and fill in one of:
- **Snowflake Cortex** (recommended for Snowflake employees)
- **OpenAI / Azure OpenAI** (optional)
- Or run **Mock** mode (no LLM; generates a placeholder structure)

```bash
cp env.example .env
```

## Snowflake Cortex auth (recommended: key-pair)
This app supports **Snowflake key-pair authentication** for Cortex calls.

### 1) Generate an RSA key (PKCS8 PEM)
Unencrypted (simplest):

```bash
openssl genrsa 2048 > snowflake_rsa_key.pem
openssl pkcs8 -topk8 -inform PEM -outform PEM -in snowflake_rsa_key.pem -out snowflake_rsa_key.p8 -nocrypt
openssl rsa -in snowflake_rsa_key.pem -pubout -out snowflake_rsa_key.pub
```

Encrypted (recommended if you store it on disk):

```bash
openssl genrsa 2048 > snowflake_rsa_key.pem
openssl pkcs8 -topk8 -inform PEM -outform PEM -in snowflake_rsa_key.pem -out snowflake_rsa_key.p8
openssl rsa -in snowflake_rsa_key.pem -pubout -out snowflake_rsa_key.pub
```

### 2) Register the public key on your Snowflake user
In Snowflake, set the public key on your user (choose RSA_PUBLIC_KEY or RSA_PUBLIC_KEY_2):

```sql
ALTER USER <your_user> SET RSA_PUBLIC_KEY='<paste contents of snowflake_rsa_key.pub without header/footer and newlines>';
```

### 3) Configure `.env`
Set:
- `LLM_BACKEND=snowflake_cortex`
- `SNOWFLAKE_AUTH_METHOD=keypair`
- `SNOWFLAKE_PRIVATE_KEY_PATH=/absolute/path/to/snowflake_rsa_key.p8`
- `SNOWFLAKE_PRIVATE_KEY_PASSPHRASE=...` (only if encrypted)

### 3) Run the app
```bash
streamlit run app/main.py
```

## Notes on transcript formats
- `.txt`: treated as raw text
- `.vtt`: timestamps/headers stripped
- `.srt`: sequence numbers/timestamps stripped

## Salesforce upload options
- **CSV export**: safest default; you can import/update as your org allows
- **API push (optional)**: uses `simple-salesforce` (username/password/token). For this app, we push into **Solution Assessment → Opportunity Comments** (configurable) by:
  - Finding the **Opportunity** by name (and optional Account name)
  - Finding the latest **Solution Assessment** record related to that Opportunity
  - **Appending** the new dated entry to the top of the existing field

### How to find the right SFDC API names
In Salesforce Setup → Object Manager:
- Find the object that backs the **Solution Assessment** section (often a custom object)
- Copy:
  - **Object API Name** (e.g. `Solution_Assessment__c`)
  - The lookup field to Opportunity (often `Opportunity__c`)
  - The **Opportunity Comments** field API name (e.g. `Opportunity_Comments__c`)

Then put those in the UI or `.env` (see `env.example`).

### Strongly recommended: use Opportunity IDs
If you have the **Opportunity Id** (15/18 chars), enter it per transcript in the app. The Salesforce push will use it for **exact matching** (much safer than Opportunity Name).

## Repo layout
- `app/main.py`: Streamlit UI
- `app/core/*`: parsing, prompting, summarizers, export
- `data/`: local saved runs (JSON)
- `outputs/`: exported CSV

