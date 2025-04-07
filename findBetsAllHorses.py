import pickle
import pandas as pd
import json
from datetime import datetime
from logitRegression15 import predict_race_outcomes
import numpy as np

def load_upcoming_races(filepath, features):
    """Load upcoming races data without outcome information"""
    with open(filepath, "r") as f:
        raw_data = json.load(f)
    
    df = pd.DataFrame(raw_data)
    df['race_id'] = df['race_id'].astype(str).str.strip()
    df = df.dropna(subset=features + ['logOdds'])  # No rank check    
    return df

def generate_betting_recommendations(
    input_file,
    model_path,
    output_file="bets.csv",
    initial_bankroll=100.0,
    min_edge=0.1,
    max_edge=0.3,
    max_stake=0.05,
    max_real_stake=50,
    min_odds=1.0,
    max_odds=7.0,
    min_prob = 0,
    include_all_horses=True  # New flag to include all horses
):
    """Generate betting recommendations for upcoming races"""
    # Load model
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    # Load upcoming races - modified to keep more data
    with open(input_file, "r") as f:
        raw_data = json.load(f)
    
    df = pd.DataFrame(raw_data)
    df['race_id'] = df['race_id'].astype(str).str.strip()
    
    # Only drop rows missing absolutely critical fields
    df = df.dropna(subset=['horse_id', 'logOdds'] + model_data['features'])
    df = df[(df["logOdds"])>-13]  
    
    # Prepare results
    recommendations = []
    
    # Process each race
    for race_id, race_data in df.groupby('race_id'):
        if len(race_data) < 2:
            print(f"Skipping race {race_id} with only {len(race_data)} runners")
            continue
            
        try:
            # Get model predictions for all horses
            predictions = predict_race_outcomes(
                new_race=race_data[model_data['features']].to_dict('list'),
                beta_hat=model_data['beta_hat'],
                scaler=model_data['scaler'],
                features=model_data['features'],
                n_samples=5000
            )
            
            # Calculate probabilities
            model_prob_top2 = predictions['rank_1'] + predictions['rank_2']
            model_prob_top3 = model_prob_top2 + predictions['rank_3']
            
            # Prepare complete race data
            race_data = race_data.assign(
                model_prob_win=predictions['rank_1'].values,
                model_prob_top2=model_prob_top2.values,
                model_prob_top3=model_prob_top3.values,
                decimal_odds=np.exp(race_data['logOdds']) + 1
            )
            
            # Calculate edge for all horses
            market_probs = 1 / race_data['decimal_odds']
            market_total = market_probs.sum()
            race_data['edge'] = race_data.apply(
                lambda x: (x.model_prob_win / ((1/x.decimal_odds)/market_total)) - 1,
                axis=1
            )
            
            # Include ALL horses if flag is True
            value_bets = race_data.copy() if include_all_horses else race_data[
                (race_data['edge'].between(min_edge, max_edge)) &
                (race_data['decimal_odds'].between(min_odds, max_odds)) &
                (race_data['model_prob_win'] > min_prob)
            ]
            
            # Calculate Kelly stakes (even for non-value bets if include_all_horses)
            stakes = (
                (value_bets['model_prob_win'] * value_bets['decimal_odds'] - 1) /
                (value_bets['decimal_odds'] - 1)
            ).clip(0, max_stake)
            
            stake_amounts = [min(stake * initial_bankroll, max_real_stake) for stake in stakes]
            
            # Record ALL horses' data
            for idx, (_, bet) in enumerate(value_bets.iterrows()):
                min_odds_top2 = ((bet['decimal_odds'] - 1) * bet['model_prob_win']) / bet['model_prob_top2'] + 1
                min_odds_top3 = ((bet['decimal_odds'] - 1) * bet['model_prob_win']) / bet['model_prob_top3'] + 1
                
                recommendations.append({
                    #'date': datetime.now().strftime('%Y-%m-%d'),
                    'race_id': race_id,
                    'horse_id': bet['horse_id'],
                    #'track': bet.get('track', 'Unknown'),
                    'edge_pct': round((bet['model_prob_win'] * bet["decimal_odds"] - 1) * 100, 1),
                    'decimal_odds': round(bet['decimal_odds'], 2),
                    'model_prob_win': bet['model_prob_win'],
                    'model_prob_top2': bet['model_prob_top2'],
                    'model_prob_top3': bet['model_prob_top3'],
                    'min_odds_top2': round(1/bet['model_prob_top2'], 2),
                    'min_odds_top3': round(1/bet['model_prob_top3'], 2),
                    'min_odds_top2_more_profitable': round(min_odds_top2, 2),
                    'min_odds_top3_more_profitable': round(min_odds_top3, 2),
                    #'kelly_stake_pct': round(stakes.iloc[idx] * 100, 1),
                    'recommended_stake': round(stake_amounts[idx], 2),
                    #'current_bankroll': round(initial_bankroll, 2),
                    # 'included_in_value_bets': include_all_horses or (
                    #     (min_edge <= bet['edge'] <= max_edge) and
                    #     (min_odds <= bet['decimal_odds'] <= max_odds) and
                    #     (bet['model_prob_win'] > min_prob)
                    # )
                })
                
        except Exception as e:
            print(f"Error processing race {race_id}: {str(e)}")
            continue
    
    # Save all data
    pd.DataFrame(recommendations).to_csv(output_file, index=False)
    print(f"Generated {len(recommendations)} bets to {output_file}")
    return recommendations

def main(minEdge=0.1, maxEdge=1, minOdds=1, maxOdds=7, bankroll=100, minProb=0):
    generate_betting_recommendations(
        input_file="upcomingRaceData.json",
        model_path="model2.pkl",
        output_file="today_bets.csv",
        initial_bankroll=bankroll,
        min_edge=minEdge,
        max_edge=maxEdge,
        max_stake=1,
        max_real_stake=100,
        min_odds=minOdds,
        max_odds=maxOdds,
        min_prob=minProb
    )

if __name__ == "__main__":
    main()