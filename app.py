from __future__ import annotations

import pandas as pd
import streamlit as st

from veikkaus_odds_monitor.arb_monitor import scan_world_cup_arbitrage
from veikkaus_odds_monitor.config import load_settings
from veikkaus_odds_monitor.db import get_draws, get_recent_quotes, init_db
from veikkaus_odds_monitor.monitor import scan_once

st.set_page_config(page_title="World Cup arbitrage monitor", layout="wide")
st.title("FIFA World Cup arbitrage monitor")
st.caption("Read-only kerroinseuranta: ei kirjautumista, ei vetojen lähettämistä, ei HTML-scrapetusta.")

settings = load_settings()
init_db(settings.db_path)

with st.sidebar:
    st.header("Asetukset")
    st.write(f"Tietokanta: `{settings.db_path}`")
    st.write(f"World Cup -suodatus: `{settings.world_cup_only}`")
    st.write(f"External sport key: `{settings.the_odds_sport_key}`")
    games_raw = st.text_input("Veikkaus-pelit", ",".join(settings.games))
    notify = st.checkbox("Lähetä Telegram-hälytykset", value=False)
    scan_veikkaus = st.button("Hae Veikkaus-kertoimet nyt")
    scan_arb = st.button("Etsi World Cup -arbitraasit")

if scan_veikkaus:
    games = tuple(item.strip().upper() for item in games_raw.split(",") if item.strip())
    with st.spinner("Haetaan Veikkauksen World Cup -dataa..."):
        summary = scan_once(settings, games=games, notify=notify)
    st.success(f"Valmis: {summary}")

if scan_arb:
    with st.spinner("Haetaan ulkoiset World Cup -kertoimet ja lasketaan arbitraasit..."):
        summary, opportunities = scan_world_cup_arbitrage(settings, notify=notify)
    st.success(f"Valmis: {summary.as_dict()}")
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
        st.info("Arbitraaseja ei löytynyt nykyisillä asetuksilla.")

recent = get_recent_quotes(settings.db_path, limit=500)
draws = get_draws(settings.db_path, limit=500)

left, right = st.columns(2)
with left:
    st.subheader("Viimeisimmät Veikkaus-kertoimet")
    if recent:
        df = pd.DataFrame([dict(row) for row in recent])
        show_cols = [
            col
            for col in ["fetched_at", "game", "title", "draw_id", "market", "outcome", "odds", "closes_at"]
            if col in df.columns
        ]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Ei vielä Veikkaus-kerroindataa.")

with right:
    st.subheader("Valitut Veikkaus-kohteet")
    if draws:
        df_draws = pd.DataFrame([dict(row) for row in draws])
        show_cols = [col for col in ["updated_at", "game", "draw_id", "title", "closes_at"] if col in df_draws.columns]
        st.dataframe(df_draws[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Ei vielä kohdedataa.")
