import pickle
import pandas as pd
import json
from datetime import datetime
from logitRegression15 import predict_race_outcomes
import numpy as np

def load_upcoming_races(filepath, features):
    """Load upcoming races data and filter out non-runners"""
    with open(filepath, "r") as f:
        raw_data = json.load(f)
    
    df = pd.DataFrame(raw_data)
    df['race_id'] = df['race_id'].astype(str).str.strip()
    
    # Identify and filter out non-runners (logOdds <= -13.8)
    df = df[df['logOdds'] > -13.8]
    
    # Drop rows with missing essential data
    required_columns = features + ['logOdds']
    df = df.dropna(subset=required_columns)
    
    # Verify we have at least some data for each race
    race_counts = df.groupby('race_id').size()
    if (race_counts < 2).any():
        print(f"Warning: {len(race_counts[race_counts < 2])} races have <2 runners after filtering")
    
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
    min_prob = 0
):
    """Generate betting recommendations for upcoming races"""
    # Load model
    with open(model_path, 'rb') as f:
        model_data = pickle.load(f)
    
    # Load upcoming races
    races_df = load_upcoming_races(input_file, model_data['features'])
    
    # Prepare results
    recommendations = []
    current_bankroll = initial_bankroll
    
    # Process each race
    for race_id, race_data in races_df.groupby('race_id'):
        if len(race_data) < 2:
            continue  # Skip races with <2 runners
            
        try:
            # Get model predictions
            predictions = predict_race_outcomes(
                new_race=race_data[model_data['features']].to_dict('list'),
                beta_hat=model_data['beta_hat'],
                scaler=model_data['scaler'],
                features=model_data['features'],
                n_samples=5000
            )
            
            # Calculate cumulative probabilities for top 2 and top 3
            model_prob_top2 = predictions['rank_1'] + predictions['rank_2']
            model_prob_top3 = model_prob_top2 + predictions['rank_3']
            
            # Prepare race data
            race_data = race_data.assign(
                model_prob_win=predictions['rank_1'].values,
                model_prob_top2=model_prob_top2.values,
                model_prob_top3=model_prob_top3.values,
                decimal_odds=np.exp(race_data['logOdds']) + 1
            )
            
            # Calculate market overround for win market
            market_probs = 1 / race_data['decimal_odds']
            market_total = market_probs.sum()
            
            # Calculate edge for win market
            race_data['edge'] = race_data.apply(
                lambda x: ((x.model_prob_win * x.decimal_odds) - 1),
                axis=1
            )
            
            # Filter value bets for win market
            value_bets = race_data[
                (race_data['edge'].between(min_edge, max_edge)) &
                (race_data['decimal_odds'].between(min_odds, max_odds)) &
                (race_data['model_prob_win'] > min_prob)
            ]
            
            if not value_bets.empty:
                # Calculate Kelly stakes for win bets
                stakes = (
                    (value_bets['model_prob_win'] * value_bets['decimal_odds'] - 1) /
                    (value_bets['decimal_odds'] - 1)
                ).clip(0, max_stake)

                # Filter out bets with zero stakes
                value_bets = value_bets[stakes > 0]
                stakes = stakes[stakes > 0]
                
                # Calculate absolute stake amounts
                stake_amounts = [min(stake * current_bankroll, max_real_stake) for stake in stakes]
                
                # Record recommendations
                for idx, (_, bet) in enumerate(value_bets.iterrows()):
                    # Calculate minimum odds for top 2 and top 3 to be more profitable than win
                    min_odds_top2 = ((bet['decimal_odds'] - 1) * bet['model_prob_win']) / bet['model_prob_top2'] + 1
                    min_odds_top3 = ((bet['decimal_odds'] - 1) * bet['model_prob_win']) / bet['model_prob_top3'] + 1
                    
                    recommendations.append({
                        #'date': datetime.now().strftime('%Y-%m-%d'),
                        'race_id': race_id,
                        'horse_id': bet['horse_id'],
                        'edge_pct': round((bet['model_prob_win'] * bet["decimal_odds"] - 1) * 100, 1),
                        'decimal_odds': round(bet['decimal_odds'], 2),
                        'model_prob_win': bet['model_prob_win'],
                        'model_prob_top2': bet['model_prob_top2'],
                        'model_prob_top3': bet['model_prob_top3'],
                        'min_odds_top2_more_profitable': round(min_odds_top2, 2),
                        'min_odds_top3_more_profitable': round(min_odds_top3, 2),
                        #'kelly_stake_pct': round(stakes.iloc[idx] * 100, 1),
                        'recommended_stake': round(stake_amounts[idx], 2),
                        #'current_bankroll': round(current_bankroll, 2),
                        #'track': bet.get('track', 'Unknown')
                    })
                
                # Simulate bankroll update (uncomment if needed)
                # total_staked = sum(stake_amounts)
                # current_bankroll -= total_staked
        
        except Exception as e:
            print(f"Error processing race {race_id}: {str(e)}")
    
    # Save recommendations
    if recommendations:
        pd.DataFrame(recommendations).to_csv(output_file, index=False)
        print(f"Generated {len(recommendations)} bets to {output_file}")
    else:
        print("No recommended bets found")
        pd.DataFrame(recommendations).to_csv(output_file, index=False)
    
    return recommendations

def main(minEdge=0.1, maxEdge=100, minOdds=1, maxOdds=100, bankroll=100, minProb=0):
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