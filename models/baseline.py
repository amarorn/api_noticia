from schemas.models import BolaoFeature, BolaoLabel

HOME_ADVANTAGE = 0.15


def predict_baseline(features: BolaoFeature) -> tuple[BolaoLabel, float, str]:
    """
    Previsão heurística combinando estatísticas + sentimento + notícias.
    Retorna (palpite, confiança 0-1, motivo).
    """
    score_home = HOME_ADVANTAGE
    score_away = 0.0
    reasons: list[str] = []

    if features.home_position and features.away_position:
        pos_diff = features.away_position - features.home_position
        score_home += pos_diff * 0.02
        if pos_diff > 3:
            reasons.append(f"{features.home_team} {features.home_position}º vs {features.away_team} {features.away_position}º")
        elif pos_diff < -3:
            reasons.append(f"{features.away_team} melhor na tabela ({features.away_position}º vs {features.home_position}º)")

    if features.home_points is not None and features.away_points is not None:
        pts_diff = features.home_points - features.away_points
        score_home += pts_diff * 0.008

    if features.home_form and features.away_form and features.home_form != "N/A":
        home_wins = features.home_form.count("V")
        away_wins = features.away_form.count("V")
        score_home += (home_wins - away_wins) * 0.05

    if features.h2h_home_wins is not None and features.h2h_away_wins is not None:
        h2h_diff = features.h2h_home_wins - features.h2h_away_wins
        score_home += h2h_diff * 0.06

    if features.sentiment_home is not None and features.sentiment_away is not None:
        sent_diff = features.sentiment_home - features.sentiment_away
        score_home += sent_diff * 0.2
        if abs(sent_diff) > 0.2:
            reasons.append("sentimento das notícias")

    if features.injury_mentions_home > features.injury_mentions_away + 1:
        score_home -= 0.1
        reasons.append(f"desfalques {features.home_team}")
    elif features.injury_mentions_away > features.injury_mentions_home + 1:
        score_home += 0.1
        reasons.append(f"desfalques {features.away_team}")

    if features.news_count_home + features.news_count_away > 0:
        news_ratio = features.news_count_home / max(features.news_count_home + features.news_count_away, 1)
        score_home += (news_ratio - 0.5) * 0.1

    if score_home > 0.12:
        prediction: BolaoLabel = "1"
    elif score_home < -0.12:
        prediction = "2"
    else:
        prediction = "X"

    confidence = min(abs(score_home) + 0.3, 0.85)
    reason = "; ".join(reasons) if reasons else "equilíbrio entre os times"
    return prediction, confidence, reason
