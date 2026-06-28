from __future__ import annotations

import pandas as pd
import streamlit as st

from veikkaus_odds_monitor.arb_monitor import scan_world_cup_arbitrage
from veikkaus_odds_monitor.config import load_settings
from veikkaus_odds_monitor.db import get_recent_quotes, init_db
from veikkaus_odds_monitor.diagnostics import diagnose_veikkaus_pipeline
from veikkaus_odds_monitor.outrights import scan_world_cup_outrights

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
    st.write(f"Ottelumarkkina: `{settings.the_odds_markets}`")
    st.write(f"Turnausvoittajamarkkina: `{settings.the_odds_outright_markets}`")
    st.write(f"Veikkaus mukana vertailussa: `{settings.include_veikkaus_in_arbitrage}`")
    st.write(f"Minimi-ROI: `{settings.min_arbitrage_roi * 100:.2f} %`")
    notify = st.checkbox("Lähetä Telegram-hälytykset otteluarbitraaseista", value=False)

st.info(
    "Käyttöliittymä on jaettu kahteen eri markkinatyyppiin. Otteluarbitraasit vertaavat 1X2/h2h-ottelukertoimia. "
    "Turnausvoittajaosio vertailee outright/winner-kertoimia erillisenä markkinana. Näitä ei voi sekoittaa samaan arbitraasilaskuun."
)

tab_matches, tab_outrights, tab_veikkaus, tab_recent = st.tabs(
    ["Otteluarbitraasit", "Turnausvoittaja", "Veikkaus-diagnostiikka", "Veikkaus-tietokanta"]
)

with tab_matches:
    st.subheader("Otteluarbitraasit: 1X2 / h2h")
    st.write(
        "Tämä hakee ulkoiset World Cup -ottelukertoimet ja yrittää lisätä mukaan Veikkauksen ottelukohtaiset 1/X/2-kertoimet, "
        "jos Veikkauksen julkinen rajapinta palauttaa niitä."
    )
    scan_arb = st.button("Päivitä ottelukertoimet ja etsi arbitraasit", type="primary")

    if scan_arb:
        with st.spinner("Haetaan Veikkaus + ulkoiset World Cup -ottelukertoimet ja lasketaan arbitraasit..."):
            summary, opportunities = scan_world_cup_arbitrage(settings, notify=notify)

        st.success(f"Valmis: {summary.as_dict()}")

        metric_cols = st.columns(5)
        metric_cols[0].metric("Ulkoisia ottelukertoimia", summary.external_prices)
        metric_cols[1].metric("Veikkaus ottelukertoimia", summary.veikkaus_prices)
        metric_cols[2].metric("Yhteensä", summary.combined_prices)
        metric_cols[3].metric("Arbitraaseja", summary.opportunities)
        metric_cols[4].metric("Virheitä", summary.errors)

        if summary.veikkaus_prices == 0:
            st.warning(
                "Veikkauksen ottelukohtaisia 1X2-kertoimia ei tullut mukaan vertailuun. "
                "Tarkista Veikkaus-diagnostiikka-välilehti: usein syy on, että Veikkaus tarjoaa tässä vaiheessa vain turnausvoittajamarkkinan eikä yksittäisiä MM-otteluita."
            )

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
            st.subheader("Löydetyt otteluarbitraasit")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Otteluarbitraaseja ei löytynyt nykyisillä asetuksilla.")

with tab_outrights:
    st.subheader("Turnausvoittaja: outright / winner")
    st.write(
        "Tämä osio vertailee FIFA World Cup -turnausvoittajakertoimia. "
        "Veikkaukselta löytynyt `Jalkapallon MM-kisat` kuuluu tähän markkinatyyppiin, ei ottelukohtaiseen 1X2-markkinaan."
    )
    st.warning(
        "Turnausvoittaja-arbitraasi on tiukempi kuin otteluarbitraasi: lasku on mielekäs vain, jos kertoimissa on mukana riittävä määrä mahdollisia mestareita. "
        f"Nykyinen vähimmäismäärä on {settings.outright_min_outcomes} lopputulosta."
    )
    scan_outrights = st.button("Päivitä turnausvoittajakertoimet", type="primary")

    if scan_outrights:
        with st.spinner("Haetaan World Cup -turnausvoittajakertoimet ja tarkistetaan mahdolliset arbitraasit..."):
            summary, prices, opportunities = scan_world_cup_outrights(settings)

        st.success(f"Valmis: {summary.as_dict()}")
        metric_cols = st.columns(6)
        metric_cols[0].metric("Ulkoisia winner-kertoimia", summary.external_prices)
        metric_cols[1].metric("Veikkaus winner-kertoimia", summary.veikkaus_prices)
        metric_cols[2].metric("Yhteensä", summary.combined_prices)
        metric_cols[3].metric("Eri lopputuloksia", summary.outcomes)
        metric_cols[4].metric("Arbitraaseja", summary.opportunities)
        metric_cols[5].metric("Virheitä", summary.errors)
        st.info(summary.note)

        if prices:
            rows = [
                {
                    "outcome": p.outcome,
                    "bookmaker": p.bookmaker,
                    "odds": p.odds,
                    "source": p.source,
                    "market": p.market,
                }
                for p in sorted(prices, key=lambda item: (item.outcome_key or item.outcome, -item.odds))
            ]
            st.subheader("Turnausvoittajakertoimet")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("Turnausvoittajakertoimia ei löytynyt. Tarkista, tukeeko The Odds API -tilauksesi `outrights`-markkinaa.")

        if opportunities:
            rows = []
            for item in opportunities:
                for leg in item.legs:
                    rows.append(
                        {
                            "market": item.market,
                            "roi_%": round(item.roi * 100, 2),
                            "profit": round(item.guaranteed_profit, 2),
                            "outcome": leg.outcome,
                            "bookmaker": leg.bookmaker,
                            "odds": round(leg.odds, 3),
                            "stake": round(leg.stake, 2),
                        }
                    )
            st.subheader("Mahdollinen turnausvoittaja-arbitraasi")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with tab_veikkaus:
    st.subheader("Veikkaus-diagnostiikka")
    st.info(
        "Tämä kertoo miksi Veikkaus-kertoimia voi olla otteluarbitraasien vertailussa 0. "
        "Jos World Cup -kohteita löytyy vain WINNER-pelistä, kyse on turnausvoittajamarkkinasta eikä yksittäisistä 1X2-otteluista."
    )
    diagnose_veikkaus = st.button("Diagnosoi Veikkaus-data")

    if diagnose_veikkaus:
        with st.spinner("Tarkistetaan Veikkauksen dataketju: avoimet kohteet → World Cup -suodatus → kertoimet → 1X2-muunnos..."):
            diag = diagnose_veikkaus_pipeline(settings)

        dcols = st.columns(6)
        dcols[0].metric("Raakakohteita", diag.raw_draws)
        dcols[1].metric("World Cup -kohteita", diag.world_cup_draws)
        dcols[2].metric("Haettuja kertoimia", diag.fetched_quotes)
        dcols[3].metric("DB-kertoimia", diag.recent_db_quotes)
        dcols[4].metric("1X2-vertailukelpoisia", diag.comparable_prices)
        dcols[5].metric("Virheitä", diag.errors)

        if diag.notes:
            for note in diag.notes:
                st.warning(note)

        game_rows = []
        for game in diag.games:
            game_rows.append(
                {
                    "game": game.game,
                    "raw_draws": game.raw_draws,
                    "world_cup_draws": game.world_cup_draws,
                    "quotes_from_selected_draws": game.quotes_from_selected_draws,
                    "errors": game.errors,
                    "sample_raw_titles": " | ".join(game.sample_raw_titles[:3]),
                    "sample_world_cup_titles": " | ".join(game.sample_world_cup_titles[:3]),
                    "sample_quote_outcomes": " | ".join(game.sample_quote_outcomes[:3]),
                }
            )
        st.dataframe(pd.DataFrame(game_rows), use_container_width=True, hide_index=True)

with tab_recent:
    st.subheader("Viimeksi tallennetut Veikkaus-kertoimet")
    recent = get_recent_quotes(settings.db_path, limit=500)
    if recent:
        df = pd.DataFrame([dict(row) for row in recent])
        show_cols = [
            col
            for col in ["fetched_at", "game", "title", "draw_id", "market", "outcome", "odds", "closes_at"]
            if col in df.columns
        ]
        st.dataframe(df[show_cols], use_container_width=True, hide_index=True)
    else:
        st.info("Ei vielä Veikkaus-kerroindataa. Diagnostiikka tai arbitraasihaku yrittää hakea Veikkaus-dataa osana vertailua.")
