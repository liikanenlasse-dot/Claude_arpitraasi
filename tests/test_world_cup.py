from veikkaus_odds_monitor.parser import Draw
from veikkaus_odds_monitor.world_cup import draw_is_world_cup, infer_teams_from_title, outcome_matches_team


def test_world_cup_draw_filter_matches_title():
    draw = Draw(
        game="WINNER",
        draw_id="1",
        list_index=None,
        title="FIFA World Cup: Brazil - Japan",
        closes_at=None,
        raw={},
    )
    assert draw_is_world_cup(draw, ("fifa world cup", "world cup"))


def test_world_cup_draw_filter_rejects_other_competition():
    draw = Draw(
        game="WINNER",
        draw_id="2",
        list_index=None,
        title="Premier League: Arsenal - Chelsea",
        closes_at=None,
        raw={},
    )
    assert not draw_is_world_cup(draw, ("fifa world cup", "world cup"))


def test_infer_teams_from_title():
    assert infer_teams_from_title("Brazil - Japan") == ("Brazil", "Japan")
    assert infer_teams_from_title("France vs Sweden") == ("France", "Sweden")


def test_outcome_matches_team_with_minor_name_variation():
    assert outcome_matches_team("United States", "USA United States")
