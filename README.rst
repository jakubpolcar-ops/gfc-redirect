GFC Redirect
============

Google Cloud Function pro přesměrování s maskováním osobních údajů v URL.

Adresa ``https://form.tulak.org/{jotform_id}/{hash}`` se přeloží
na JotForm URL s předvyplněnými osobními údaji, aniž by byly viditelné
v původním odkazu. Data se načítají z Google Sheets ve sdílené složce na
Google Drive. Každý sheet odpovídá jednomu formuláři — ``jotform_id`` se
extrahuje z posledního čísla v názvu souboru (např.
``Velikonoční výprava - 02.-05.04. 2026 - 260482905363055``).

Příklad::

    GET /260482905363055/53AVL
    → 302 https://form.jotform.com/260482905363055?parent_name[first]=Michal&parent_name[last]=Sýkora&kid_name[first]=Karel&kid_name[last]=Sýkora


Prerekvizity
------------

- ``nix-shell`` nebo ``direnv`` pro nastavení vývojového prostředí
- Google Cloud projekt s aktivovanými API
- ``gcloud`` CLI (součást nix prostředí)
- ``uv`` pro správu Python závislostí (součást nix prostředí)
- Složka na Google Drive s Google Sheets (sdílená se service accountem Cloud Function)


Lokální vývoj
-------------

Vstup do prostředí::

    direnv allow
    # nebo
    nix-shell

Konfigurace prostředí — vytvoř soubor ``.env`` v kořenu projektu::

    DRIVE_FOLDER_ID=1vBgyZvoaEGr7M0GzFsu5ANAH7NyFhGDD

Soubor ``.env`` je načítán automaticky přes ``direnv`` (funkce ``dotenv_if_exists``).

Aktivace Google Sheets API a Drive API (nutné i pro lokální vývoj)::

    gcloud services enable sheets.googleapis.com
    gcloud services enable drive.googleapis.com

Nastavení Application Default Credentials pro přístup ke Google Sheets a Drive
(Workspace API vyžadují explicitní scopes)::

    gcloud auth application-default login \
        --scopes="openid,https://www.googleapis.com/auth/userinfo.email,https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/spreadsheets.readonly,https://www.googleapis.com/auth/drive.readonly"

.. note::

   Na Cloud Functions se autentizace řeší automaticky přes service account.
   Kroky výše (aktivace API a ADC login) jsou potřeba **pouze pro lokální
   vývoj**. Nezapomeň se přihlásit účtem, který má přístup ke složce
   na Google Drive.

Instalace závislostí::

    uv sync

Spuštění lokálního serveru::

    make run

Server poběží na ``http://localhost:8080``.

::

    curl -v http://localhost:8080/260482905363055/53AVL


CLI rozhraní
~~~~~~~~~~~~

Pro rychlé testování bez spuštění serveru je k dispozici CLI, které vrací
JSON se záznamem příjemce::

    uv run python main.py --jotform-id 260482905363055 --hash-code 53AVL
    uv run python main.py --jotform-id 260475821739061 --hash-code 4S25T

Příklad výstupu::

    {
      "parent_first": "Michal",
      "parent_last": "Sýkora",
      "child_first": "Karel",
      "child_last": "Sýkora",
      "address": "Masarykova 12, Brno",
      "phone": "+420 723 127 217"
    }


Google Sheets
-------------

Data příjemců se načítají z Google Sheets umístěných ve sdílené složce na
Google Drive. Každý soubor ve složce musí mít v názvu ``jotform_id`` jako
poslední číslo oddělené pomlčkou, např.::

    Velikonoční výprava - 02.-05.04. 2026 - 260482905363055
    Podzimní výprava - 25.10.2025 - 29.10.2025 - 260475821739061

Soubory bez čísla v názvu (např. ``Hlavní seznam``) se přeskočí.

Každý sheet musí mít následující strukturu (první řádek = hlavičky):

======  ==============  ================  ================  ==============  ================  ==============
ID      Jméno rodiče    Příjmení rodiče   Adresa bydliště   Jméno dítěte   Příjmení dítěte   Telefon rodiče
======  ==============  ================  ================  ==============  ================  ==============
53AVL   Michal          Sýkora            Masarykova 12     Karel           Sýkora            \+420 723 ...
4S25T   Lenka           Vlčková           Veveří 45         Marie           Vlčková           \+420 608 ...
======  ==============  ================  ================  ==============  ================  ==============

Sloupec **ID** slouží jako unikátní identifikátor (hash) pro vyhledání záznamu.

Data se cachují v paměti po dobu 5 minut (``CACHE_TTL_SECONDS``), aby se
minimalizoval počet API volání.

Nastavení přístupu
~~~~~~~~~~~~~~~~~~

1. Aktivuj Google Sheets API a Drive API v GCP projektu::

    gcloud services enable sheets.googleapis.com
    gcloud services enable drive.googleapis.com

2. Zjisti email service accountu Cloud Function::

    gcloud iam service-accounts list

   Typicky ``PROJECT_ID@appspot.gserviceaccount.com`` nebo
   ``PROJECT_NUMBER-compute@developer.gserviceaccount.com``.

3. Sdílej složku na Google Drive s tímto emailem jako **Viewer** (čtenář):

   - Otevři složku na Drive → **Sdílet** → přidej email service accountu


Deployment
----------

1. Vytvoření GCP projektu a přihlášení
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    gcloud auth login

    gcloud projects create gfc-redirect-prod --name="GFC Redirect"
    gcloud config set project gfc-redirect-prod

    # Aktivace billing účtu (nutné pro Cloud Functions)
    gcloud billing accounts list
    gcloud billing projects link gfc-redirect-prod --billing-account=BILLING_ACCOUNT_ID

2. Aktivace potřebných API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    gcloud services enable cloudfunctions.googleapis.com
    gcloud services enable run.googleapis.com
    gcloud services enable cloudbuild.googleapis.com
    gcloud services enable artifactregistry.googleapis.com
    gcloud services enable sheets.googleapis.com
    gcloud services enable drive.googleapis.com

3. Deploy
~~~~~~~~~

::

    make deploy

Deploy automaticky nastaví proměnnou ``DRIVE_FOLDER_ID`` z prostředí na
Cloud Function (``--set-env-vars``).

Nebo ručně::

    gcloud functions deploy gfc-redirect \
        --gen2 \
        --runtime python312 \
        --region europe-west1 \
        --trigger-http \
        --allow-unauthenticated \
        --entry-point handle_redirect \
        --source . \
        --memory 256Mi \
        --max-instances 2 \
        --set-env-vars DRIVE_FOLDER_ID=<ID složky na Google Drive>


Custom doména (DNS)
-------------------

Po deployi získej URL Cloud Run služby::

    gcloud run services describe gfc-redirect \
        --region europe-west1 \
        --format 'value(status.url)'

    curl -v https://gfc-redirect-t4m2ndmelq-ew.a.run.app/260482905363055/53AVL

Namapuj vlastní doménu na Cloud Run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    gcloud beta run domain-mappings create \
        --service gfc-redirect \
        --domain form.tulak.org \
        --region europe-west1

Smazání mapování domény
~~~~~~~~~~~~~~~~~~~~~~~

Pokud potřebuješ odebrat starou doménu::

    gcloud beta run domain-mappings delete \
        --domain gfc-redirect.gaussalgo.com \
        --region europe-west1

DNS CNAME záznam
~~~~~~~~~~~~~~~~

Vytvoř v DNS zóně ``tulak.org`` následující CNAME záznam::

    form.tulak.org.  CNAME  ghs.googlehosted.com.

.. note::

   Přesný CNAME target ověř ve výstupu příkazu ``domain-mappings create``.
   Provisioning SSL certifikátu může trvat až 24 hodin (typicky 15–30 minut).


Logy
----

Zobrazení posledních logů::

    make logs

Streaming logů v reálném čase::

    gcloud beta run services logs tail gfc-redirect \
        --region europe-west1

Logy v Cloud Console:

    https://console.cloud.google.com/run/detail/europe-west1/gfc-redirect/logs


Testování (curl)
----------------

Lokálně
~~~~~~~

::

    # Úspěšné přesměrování — vrátí 302 + Location header
    curl -v http://localhost:8080/260482905363055/53AVL

    # Neexistující hash — vrátí 404
    curl -v http://localhost:8080/260482905363055/NEEXISTUJE

    # Chybný formát URL — vrátí 400
    curl -v http://localhost:8080/bad-request

Po deployi
~~~~~~~~~~

::

    # Přes Cloud Run URL
    curl -v https://gfc-redirect-XXXXXXX-lm.a.run.app/260482905363055/53AVL

    # Přes vlastní doménu (po nastavení DNS)
    curl -v https://form.tulak.org/260482905363055/53AVL

    # Sledování přesměrování (-L)
    curl -L https://form.tulak.org/260482905363055/53AVL


Statická kontrola kódu
-----------------------

::

    make lint       # Ruff linter
    make format     # Ruff formatter
    make check      # Lint + mypy type checking

