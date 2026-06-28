# Claude_arpitraasi / FIFA World Cup arbitrage monitor

Read-only Python-työkalu FIFA World Cup -kertoimien seuraamiseen ja arbitraasien etsimiseen.

Tämä projekti:

- hakee Veikkauksen avoimia pelikohteita JSON-rajapinnasta
- suodattaa Veikkaus-haun oletuksena vain FIFA World Cup / MM-kisat -kohteisiin
- hakee ulkoiset World Cup -kertoimet API-pohjaisesta odds-aggregaatista
- vertailee useiden bookkereiden h2h/1X2-kertoimia
- laskee arbitraasit eli surebet-mahdollisuudet
- tallentaa Veikkaus-kohteet ja kertoimet SQLite-tietokantaan
- tunnistaa Veikkauksen kerroinmuutokset
- voi lähettää Telegram-hälytyksen kerroinmuutoksista ja arbitraaseista
- sisältää Streamlit-dashboardin

Tämä projekti **ei**:

- kirjaudu Veikkauksen tilille
- kirjaudu muille vedonlyöntisivuille
- lähetä pelikupongin tarkistuspyyntöjä
- jätä vetoja
- kierrä bottisuojauksia
- raavi HTML-sivuja selaimella

## Tausta ja rajaus

Veikkauksen oma `sport-games-robot`-referenssitoteutus kuvaa JSON/REST-rajapintaa ja edellyttää automaattisilta ohjelmilta headeria:

```http
X-ESA-API-Key: ROBOT
Accept: application/json
Content-Type: application/json
```

Referenssitoteutuksessa kerrotaan myös, että kiinteäkertoimisen vedonlyönnin ohjelmallinen pelaaminen on kielletty. Siksi tämä repo on toteutettu read-only-monitoriksi.

Ulkoiset kertoimet haetaan ensimmäisessä versiossa The Odds API -palvelusta. Oletuksena käytetään sport key -arvoa:

```text
soccer_fifa_world_cup
```

ja markkinaa:

```text
h2h
```

## Asennus Windowsissa

Avaa PowerShell repossa:

```powershell
git clone https://github.com/liikanenlasse-dot/Claude_arpitraasi.git
cd Claude_arpitraasi
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dashboard,test]"
copy .env.example .env
```

## Asennus macOS/Linuxissa

```bash
git clone https://github.com/liikanenlasse-dot/Claude_arpitraasi.git
cd Claude_arpitraasi
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e '.[dashboard,test]'
cp .env.example .env
```

## API-avain ulkoisiin bookkereihin

Arbitraasin etsiminen useiden bookkereiden välillä vaatii ulkoisen odds-datalähteen. Lisää `.env`-tiedostoon:

```env
THE_ODDS_API_KEY=oma_api_avaimesi_tähän
```

Ilman tätä avainta Veikkaus-monitori toimii, mutta `arbitrage`-komento ei hae muiden bookkereiden kertoimia.

## Käyttö

### 1. Veikkaus World Cup -kohteiden haku

Yksittäinen haku:

```bash
veikkaus-monitor scan --games SCORE,WINNER,SPORT
```

Jatkuva monitorointi:

```bash
veikkaus-monitor loop --games SCORE,WINNER,SPORT
```

Oletuksena `WORLD_CUP_ONLY=true`, jolloin Veikkaus-kohteista pidetään mukana vain sellaiset, joiden nimi tai raakadatan teksti viittaa FIFA World Cupiin / MM-kisoihin.

### 2. FIFA World Cup -arbitraasien haku muilta bookkereilta

```bash
veikkaus-monitor arbitrage
```

Lyhyt alias:

```bash
veikkaus-monitor arb
```

Komento hakee The Odds API:n kautta FIFA World Cup -kertoimet, valitsee parhaan kertoimen jokaiselle lopputulokselle ja laskee, syntyykö arbitraasi:

```text
1 / paras_kerroin_1 + 1 / paras_kerroin_2 + ... < 1
```

Jos arbitraasi löytyy, työkalu näyttää:

- ottelun
- markkinan
- ROI:n
- suositellun panosjaon
- taatun palautuksen
- taatun voiton
- bookkerin jokaiselle vedon osalle

### 3. Dashboard

```bash
streamlit run app.py
```

Dashboardissa voit:

- hakea Veikkauksen World Cup -kohteet
- etsiä World Cup -arbitraasit
- katsoa tallennetut Veikkaus-kertoimet
- katsoa valitut Veikkaus-kohteet

## Asetukset

Muokkaa `.env`-tiedostoa:

```env
# Read-only Veikkaus monitor settings
VEIKKAUS_BASE_URL=https://www.veikkaus.fi
VEIKKAUS_API_KEY=ROBOT
VEIKKAUS_GAMES=SCORE,WINNER,SPORT,MULTISCORE
VEIKKAUS_POLL_SECONDS=120
VEIKKAUS_DB_PATH=data/veikkaus_odds.sqlite3
VEIKKAUS_MIN_ODDS_CHANGE=0.05

# Only keep Veikkaus draws that explicitly look like FIFA World Cup / MM-kisat.
WORLD_CUP_ONLY=true
TOURNAMENT_KEYWORDS=fifa world cup,world cup,fifa mm,mm-kisat,mm kisat,jalkapallon mm

# External multi-bookmaker odds provider. Required for arbitrage scanning.
THE_ODDS_API_KEY=
THE_ODDS_API_BASE_URL=https://api.the-odds-api.com
THE_ODDS_SPORT_KEY=soccer_fifa_world_cup
THE_ODDS_REGIONS=eu,uk
THE_ODDS_MARKETS=h2h
THE_ODDS_ODDS_FORMAT=decimal

# Arbitrage thresholds
MIN_ARBITRAGE_ROI=0.005
ARBITRAGE_TOTAL_STAKE=1000

# Optional Telegram alerts
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

`MIN_ARBITRAGE_ROI=0.005` tarkoittaa, että arbitraasihälytys syntyy vasta, jos laskennallinen ROI on vähintään 0.5 %.

`ARBITRAGE_TOTAL_STAKE=1000` tarkoittaa, että panosjako lasketaan 1000 yksikön kokonaispanokselle. Yksikkö voi olla euro, mutta työkalu ei käsittele rahansiirtoja eikä vetoja.

## Telegram-hälytys

1. Luo botti Telegramissa `@BotFather`-botilla.
2. Kopioi bot token `.env`-tiedoston kohtaan `TELEGRAM_BOT_TOKEN`.
3. Selvitä oma chat ID esimerkiksi `@userinfobot`-botilla tai Telegram API:n `getUpdates`-kutsulla.
4. Lisää `TELEGRAM_CHAT_ID`.
5. Aja:

```bash
veikkaus-monitor loop
```

tai:

```bash
veikkaus-monitor arbitrage
```

## Tuetut pelityypit Veikkauksella

Oletuksena haetaan:

```text
SCORE, WINNER, SPORT, MULTISCORE
```

Veikkauksen referenssidokumentaatiossa mainittuja pelejä ovat esimerkiksi:

```text
MULTISCORE  Moniveto
SCORE       Tulosveto
SPORT       Vakio
WINNER      Voittajaveto
PICKTWO     Päivän pari
PICKTHREE   Päivän trio
PERFECTA    Superkaksari
TRIFECTA    Supertripla
```

Kaikki pelit eivät välttämättä palauta kertoimia samalla rakenteella tai samalla endpointilla. Työkalu tallentaa kohdetiedot ja yrittää kerätä kertoimet geneerisellä parserilla.

## Mitä "muilta sivuilta" tarkoittaa tässä työkalussa?

Työkalu ei avaa bet365:n, Unibetin, Paf:n tai muiden sivustojen HTML-sivuja eikä kierrä niiden suojauksia. Muiden bookkereiden kertoimet tulevat odds-aggregaatin API:n kautta. Tämä on teknisesti vakaampi ja käyttöehtojen kannalta turvallisempi tapa.

Ensimmäinen tuettu aggregaatti:

```text
The Odds API
```

Seuraavaksi voidaan lisätä muita API-adaptereita, esimerkiksi `Odds-API.io`, `OpticOdds` tai muu lisensoitu datalähde, jos sinulla on niihin API-avain.

## Tietokantarakenne

SQLite-tietokanta syntyy automaattisesti polkuun:

```text
data/veikkaus_odds.sqlite3
```

Taulut:

```text
draws        avoimet Veikkaus-pelikohteet
odds_quotes  yksittäiset Veikkaus-kerroinsnapshotit
latest_odds  näkymä viimeisimmistä Veikkaus-kertoimista
```

Arbitraasit lasketaan tällä hetkellä lennossa ulkoisesta API-datasta. Niitä ei vielä tallenneta omaan tauluun.

## Testit

```bash
pytest
```

## GitHubiin vieminen

Jos latasit tämän zip-paketin, pura se paikallisesti ja aja:

```bash
git init
git remote add origin https://github.com/liikanenlasse-dot/Claude_arpitraasi.git
git add .
git commit -m "Add FIFA World Cup arbitrage monitor"
git branch -M main
git push -u origin main
```

Jos repo on jo kloonattu, kopioi tiedostot sen sisään ja aja:

```bash
git add .
git commit -m "Add FIFA World Cup arbitrage monitor"
git push
```

Voit käyttää myös mukana olevia skriptejä:

```powershell
.\push_to_github.ps1
```

tai:

```bash
./push_to_github.sh
```

## Vastuullinen käyttö

Pidä hakuväli maltillisena, esimerkiksi 60–300 sekuntia. Älä lisää tähän kirjautumista tai automaattista vetojen lähettämistä. Tarkista aina Veikkauksen, odds-datalähteen ja mahdollisten bookkereiden ajantasaiset ehdot ja rajapinnan käyttöä koskevat rajoitukset.
