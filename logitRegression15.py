import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import logsumexp
import json
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import KFold
import pickle
import math
from numba import njit
from concurrent.futures import ProcessPoolExecutor
from collections import defaultdict

# ----------------------------
# 1. Optimized Data Preparation
# ----------------------------

def load_and_preprocess_data(filepath, features):
    """Vectorized data loading and preprocessing"""
    with open(filepath, "r") as f:
        data = json.load(f)
    
    df = pd.DataFrame(data)
    
    # Clean race_id
    df['race_id'] = df['race_id'].astype(str).str.replace('\n', ' ').str.strip()
    
    # Validate complete ranking sequences
    valid_races = df.groupby('race_id').filter(lambda g: 
        (g['rank'].nunique() == len(g)) and 
        (g['rank'].min() == 1) and 
        (g['rank'].max() == len(g))
    )
    
    # Create race indices
    race_ids = valid_races['race_id'].unique()
    valid_races['race_idx'] = valid_races['race_id'].map(
        {rid: i for i, rid in enumerate(race_ids)}
    )
    
    # Standardize features
    scaler = StandardScaler()
    valid_races[features] = scaler.fit_transform(valid_races[features])
    
    return valid_races, scaler, race_ids

# ----------------------------
# 2. Numba-accelerated Likelihood
# ----------------------------

@njit
def fast_log_likelihood(beta, X, race_indices, ranks, lambda_reg):
    """Numba-optimized likelihood calculation"""
    ll = 0.0
    full_beta = beta
    
    for i in np.unique(race_indices):
        mask = race_indices == i
        X_race = X[mask]
        ranks_race = ranks[mask]
        order = np.argsort(ranks_race)
        V = X_race[order] @ full_beta
        
        k = 0
        while k < len(V):
            current_rank = ranks_race[order[k]]
            same_rank = ranks_race[order[k:]] == current_rank
            group_size = np.sum(same_rank)
            
            group = V[k:k+group_size]
            remaining = V[k:]
            
            max_rem = np.max(remaining)
            ll += np.log(np.sum(np.exp(group - max_rem)))
            ll -= np.log(np.sum(np.exp(remaining - max_rem)))
            
            if group_size > 1:
                ll -= math.lgamma(group_size + 1)
            
            k += group_size
    
    # Regularization (exclude reference feature)
    ll -= lambda_reg * np.sum(beta**2)
    return -ll

# ----------------------------
# 3. Parallel Cross-Validation
# ----------------------------

def parallel_cv(args):
    """Parallel CV execution with error handling"""
    train_idx, val_idx, λ, X, race_indices, ranks, features = args
    try:
        # Training data
        X_train = X[train_idx]
        ri_train = race_indices[train_idx]
        rk_train = ranks[train_idx]
        
        # Validation data
        X_val = X[val_idx]
        ri_val = race_indices[val_idx]
        rk_val = ranks[val_idx]

        # Optimize model
        res = minimize(
            lambda p: fast_log_likelihood(p, X_train, ri_train, rk_train, λ),
            np.zeros(len(features)),
            method='L-BFGS-B',
            options={'maxiter': 50, 'disp': False}
        )
        
        if res.success:
            score = fast_log_likelihood(res.x, X_val, ri_val, rk_val, 0)
            return (λ, score)
    except Exception as e:
        print(f"λ={λ} error: {str(e)}")
    return None

# ----------------------------
# 4. Prediction Function
# ----------------------------

def predict_race_outcomes(new_race, beta_hat, scaler, features, n_samples=10000):
    """Efficient prediction with proper feature name handling"""
    # Convert input to DataFrame with correct feature order
    input_df = pd.DataFrame(new_race, columns=features)
    
    # Scale features with preserved names
    X_scaled = scaler.transform(input_df)
    strengths = X_scaled @ beta_hat
    
    # Gumbel sampling
    np.random.seed(42)
    noise = np.random.gumbel(0, 1, (n_samples, len(strengths)))
    samples = np.argsort(-(strengths + noise), axis=1)
    
    # Calculate probabilities
    prob_matrix = np.zeros((len(strengths), len(strengths)))
    np.add.at(prob_matrix, (samples, np.arange(len(strengths))[None,:]), 1)
    prob_matrix /= n_samples
    
    return pd.DataFrame(
        np.around(prob_matrix, 3),
        columns=[f'rank_{i+1}' for i in range(len(strengths))],
        index=[f'horse_{i+1}' for i in range(len(strengths))]
    )
# ----------------------------
# 5. Main Execution
# ----------------------------

if __name__ == "__main__":
    # Configuration
    features = ['Hwinper', 'wt.carried', 'rating', 'Jwinper', 'age', 'logOdds', 'wdproduct', "form"]
    
    # Load data
    df, scaler, race_ids = load_and_preprocess_data("testRaceData.json", features)
    X = df[features].values
    race_indices = df['race_idx'].values
    ranks = df['rank'].values

    # Cross-validation setup
    lambdas = [0.001, 0.01, 0.1, 1]
    n_folds = 3
    cv_args = [
        (train_idx, val_idx, λ, X, race_indices, ranks, features)
        for λ in lambdas
        for train_idx, val_idx in KFold(n_folds).split(X)
    ]

    # Execute CV
    with ProcessPoolExecutor() as executor:
        results = list(executor.map(parallel_cv, cv_args))

    # Process results
    lambda_scores = defaultdict(list)
    for result in results:
        if result: lambda_scores[result[0]].append(result[1])
    
    # Select best lambda
    best_lambda = min(
        ( (λ, np.mean(scores)) for λ, scores in lambda_scores.items() ),
        key=lambda x: x[1]
    )[0]
    
    print(f"Best lambda: {best_lambda}")

    # Final training
    result = minimize(
        lambda p: fast_log_likelihood(p, X, race_indices, ranks, best_lambda),
        np.zeros(len(features)),
        method='L-BFGS-B',
        options={'maxiter': 100}
    )
    
    if not result.success:
        raise RuntimeError(f"Optimization failed: {result.message}")
    
    beta_hat = result.x
    print("\nTrained Coefficients:")
    print(pd.DataFrame({
        'feature': features,
        'coefficient': beta_hat
    }))
    
    # Save model
    with open('model2.pkl', 'wb') as f:
        pickle.dump({
            'beta_hat': beta_hat,
            'scaler': scaler,
            'features': features,
            'lambda': best_lambda
        }, f)

    # Example prediction
    new_race = {
        'Hwinper': [25, 18, 32, 15, 21],
        'wt.carried': [58, 55, 60, 57, 62],
        'rating': [115, 105, 122, 98, 108],
        'Jwinper': [14, 12, 18, 9, 15],
        'age': [5, 6, 4, 7, 5],
        'logOdds': [1.1, 0.7, 2.0, 0.3, 1.4],
        'wdproduct': [85000, 72000, 92000, 68000, 88000],
        "form": [3, 5, 4, 8]
    }
    
    predictions = predict_race_outcomes(
        new_race=new_race,
        beta_hat=beta_hat,
        scaler=scaler,
        features=features,
        n_samples=100000
    )
    
    print("\nPredicted Probabilities:")
    print(predictions)