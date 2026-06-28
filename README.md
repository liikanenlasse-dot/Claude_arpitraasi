# Claude_arpitraasi / FIFA World Cup arbitrage monitor

Read-only Python-työkalu FIFA World Cup -kertoimien vertailuun ja arbitraasien etsimiseen.

Tämä versio on rakennettu niin, että **Veikkaus ei ole erillinen irrallinen kertoimien katselunäkymä**. Veikkaus haetaan vain osana arbitraasivertailua, jossa sitä verrataan ulkoiseen odds-API-dataan.

Työkalu ei kirjaudu vedonlyöntisivuille, ei ohita bottisuojauksia, ei scrapeta HTML-sivuja eikä lähetä vetoja.

## Mitä työkalu tekee?

- hakee FIFA World Cup -kertoimet The Odds API:n kautta
- hakee Veikkauksen World Cup -kohteita read-only-mallilla
- yrittää yhdistää Veikkauksen 1/X/2-kertoimet samaan h2h/1X2-markkinaan
- laskee arbitraasit parhaiden kertoimien perusteella
- näyttää tulokset Streamlit-dashboardissa
- voi lähettää Telegram-hälytyksen, jos arbitraasi löytyy

## Asennus

```powershell
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass -Force
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dashboard,test]"
```

## .env

Kopioi esimerkkitiedosto:

```powershell
copy .env.example .env
notepad .env
```

Lisää ainakin The Odds API -avain:

```env
THE_ODDS_API_KEY=oma_api_avain_tähän
THE_ODDS_SPORT_KEY=soccer_fifa_world_cup
THE_ODDS_REGIONS=eu,uk
THE_ODDS_MARKETS=h2h
INCLUDE_VEIKKAUS_IN_ARBITRAGE=true
MIN_ARBITRAGE_ROI=0.005
ARBITRAGE_TOTAL_STAKE=1000
```

Älä lisää `.env`-tiedostoa GitHubiin.

## Käyttö komentoriviltä

```powershell
veikkaus-monitor arb
```

tai:

```powershell
python -m veikkaus_odds_monitor.cli arb
```

## Dashboard

```powershell
python -m streamlit run app.py
```

Avaa selainosoite:

```text
http://localhost:8501
```

Dashboardissa on yksi päätoiminto:

```text
Päivitä kertoimet ja etsi arbitraasit
```

Se hakee ulkoiset World Cup -kertoimet, hakee Veikkauksen tuoreet World Cup -kertoimet ja laskee arbitraasit yhdistetystä datasta.

## Automaattinen haku

PowerShellissä:

```powershell
while ($true) {
    veikkaus-monitor arb
    Start-Sleep -Seconds 120
}
```

## Telegram-hälytykset

Lisää `.env`-tiedostoon:

```env
TELEGRAM_BOT_TOKEN=oma_bot_token
TELEGRAM_CHAT_ID=oma_chat_id
```

Kun arbitraasi löytyy, työkalu lähettää Telegram-viestin.

## Huomio Veikkaus-täsmäytyksestä

Veikkaus voidaan ottaa arbitraasivertailuun vain silloin, kun tapahtuma ja 1/X/2-lopputulokset voidaan yhdistää luotettavasti ulkoisen API:n World Cup -otteluun. Jos dashboardissa näkyy `Veikkaus-kertoimia vertailussa = 0`, syy on yleensä jokin näistä:

- Veikkauksella ei ole tuoretta World Cup -kohdetta kyseisessä markkinassa
- Veikkauksen tapahtumanimi poikkeaa ulkoisen API:n nimestä
- Veikkauksen outcome-labelit eivät olleet tunnistettavissa 1/X/2-muotoon
- Veikkaus-quote oli vanhempi kuin `VEIKKAUS_QUOTE_MAX_AGE_SECONDS`

## Testit

```powershell
pytest
```
