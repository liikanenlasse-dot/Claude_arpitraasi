from __future__ import annotations

import pandas as pd
import streamlit as st

from veikkaus_odds_monitor.arb_monitor import scan_world_cup_arbitrage
from veikkaus_odds_monitor.config import load_settings
from veikkaus_odds_monitor.db import get_recent_quotes, init_db

st.set_page_config(page_title="World Cup arbitrage monitor", layout="wide")
st.title("FIFA World Cup arbitrage monitor")
st.caption(
    "Read-only kerroinvertailu: Veikkaus + ulkoiset bookmaker-kertoimet API:n kautta. "
    "Ei kirjautumista, ei vetojen lähettämistä, ei HTML-scrapetusta."
)

settings = load_settings()
init_db(settings.db_path)

with st.sidebar:
    st.header("Asetukset")
    st.write(f"Tietokanta: `{settings.db_path}`")
    st.write(f"World Cup -suodatus: `{settings.world_cup_only}`")
    st.write(f"External sport key: `{settings.the_odds_sport_key}`")
    st.write(f"External markets: `{settings.the_odds_markets}`")
    st.write(f"Veikkaus mukana vertailussa: `{settings.include_veikkaus_in_arbitrage}`")
    notify = st.checkbox("Lähetä Telegram-hälytykset", value=False)
    scan_arb = st.button("Päivitä kertoimet ja etsi arbitraasit", type="primary")

st.info(
    "Tämä näkymä ei hae Veikkausta erillisenä irrallisena listana. "
    "Kun painat hakupainiketta, työkalu hakee ulkoiset World Cup -kertoimet, "
    "hakee Veikkauksen tuoreet World Cup -kertoimet ja yrittää verrata ne samaan 1X2/h2h-markkinaan."
)

if scan_arb:
    with st.spinner("Haetaan Veikkaus + ulkoiset World Cup -kertoimet ja lasketaan arbitraasit..."):
        summary, opportunities = scan_world_cup_arbitrage(settings, notify=notify)

    st.success(f"Valmis: {summary.as_dict()}")

    metric_cols = st.columns(5)
    metric_cols[0].metric("Ulkoisia kertoimia", summary.external_prices)
    metric_cols[1].metric("Veikkaus-kertoimia vertailussa", summary.veikkaus_prices)
    metric_cols[2].metric("Yhteensä", summary.combined_prices)
    metric_cols[3].metric("Arbitraaseja", summary.opportunities)
    metric_cols[4].metric("Virheitä", summary.errors)

    if opportunities:
        rows = []
        for item in opportunities:
            for leg in item.legs:
                rows.append(
                    {
                        "event": item.event_name,
                        "kickoff": item.commence_time,
                        "market": item.market,
                        "roi_%": round(item.roi * 100, 2),
                        "profit": round(item.guaranteed_profit, 2),
                        "outcome": leg.outcome,
                        "bookmaker": leg.bookmaker,
                        "odds": round(leg.odds, 3),
                        "stake": round(leg.stake, 2),
                    }
                )
        st.subheader("Löydetyt arbitraasit")
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info(
            "Arbitraaseja ei löytynyt nykyisillä asetuksilla. Jos Veikkaus-kertoimia vertailussa = 0, "
            "Veikkauksen tapahtuma- tai 1/X/2-nimet eivät täsmänneet ulkoiseen dataan tai tuoreita World Cup -kohteita ei ollut saatavilla."
        )

recent = get_recent_quotes(settings.db_path, limit=500)
st.subheader("Viimeksi tallennetut Veikkaus-kertoimet, joita voidaan käyttää vertailuun")
if recent:
    df = pd.DataFrame([dict(row) for row in recent])
    show_cols = [
        col
        for col in ["fetched_at", "game", "title", "draw_id", "market", "outcome", "odds", "closes_at"]
        if col in df.columns
    ]
    st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
else:
    st.info("Ei vielä Veikkaus-kerroindataa. Paina ylhäältä arbitraasihakua, jolloin Veikkaus-data haetaan osana vertailua.")
