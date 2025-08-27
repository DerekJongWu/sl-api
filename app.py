from flask import Flask, jsonify, request
import os
from datetime import datetime
import numpy as np
from sl_package import Game
from sl_package.sampling import sample_from_distribution

app = Flask(__name__)

def evaluate_formula(formula, sampled_values, player_suffix, variables_data):
    """
    Evaluate a formula string using the sampled values.
    
    Args:
        formula (str): Formula string like "v1_Val+v2_Val" or "v1_Stnd"
        sampled_values (dict): Dictionary of sampled variable values
        player_suffix (str): Player suffix ('A' or 'B') for variable lookup
        variables_data (list): List of variable definitions with min, max, desiredEffect
        
    Returns:
        float: Calculated result
    """
    try:
        # Create a safe evaluation environment with only the sampled values
        # Replace formula variables with actual sampled values
        eval_formula = formula
        
        # Handle different variable formats in the formula
        # Replace v1_Val with v1_A, v2_Val with v2_A, etc.
        for var_name, value in sampled_values.items():
            if var_name.endswith(f"_{player_suffix}"):
                # Extract the base variable name (e.g., "v1" from "v1_A")
                base_var = var_name.replace(f"_{player_suffix}", "")
                
                # Check if this variable needs standardization
                if f"{base_var}_Stnd" in formula:
                    # Find the variable definition to get min, max, and desiredEffect
                    var_def = None
                    for var in variables_data:
                        if var['variableNumber'] == base_var:
                            var_def = var
                            break
                    
                    if var_def:
                        min_val = float(var_def['min'])
                        max_val = float(var_def['max'])
                        desired_effect = var_def['desiredEffect']
                        
                        # Apply standardization based on desired effect
                        if desired_effect.lower() == 'positive':
                            # Positive: (val - min) / (max - min)
                            standardized_val = (value - min_val) / (max_val - min_val)
                        elif desired_effect.lower() == 'negative':
                            # Negative: (max - val) / (max - min)
                            standardized_val = (max_val - value) / (max_val - min_val)
                        else:
                            # Default to positive if desiredEffect is not specified
                            standardized_val = (value - min_val) / (max_val - min_val)
                        
                        # Replace the _Stnd variable with the standardized value
                        eval_formula = eval_formula.replace(f"{base_var}_Stnd", str(standardized_val))
                    else:
                        # If variable definition not found, use original value
                        eval_formula = eval_formula.replace(f"{base_var}_Stnd", str(value))
                else:
                    # Replace _Val variables with original sampled values
                    eval_formula = eval_formula.replace(f"{base_var}_Val", str(value))
                    eval_formula = eval_formula.replace(f"{base_var}", str(value))
        
        # Evaluate the formula safely
        # Only allow basic arithmetic operations
        allowed_chars = set('0123456789+-*/(). ')
        if all(c in allowed_chars for c in eval_formula):
            result = eval(eval_formula)
            return float(result)
        else:
            raise ValueError(f"Formula contains invalid characters: {formula}")
            
    except Exception as e:
        raise Exception(f"Error evaluating formula '{formula}': {str(e)}")

def create_game(outcomes):
    # Create a new game where "China" is the root player
    game = Game()
    
    # Add moves: China chooses between "Tariff" or "No Tariff"
    game.add_moves(player="Player A", actions=["Tariff", "No Tariff"])
    
    # Add moves: The US responds to China's move
    game.add_moves(player="Player B", actions=["Tariff", "No Tariff"])
    
    game.add_outcomes(outcomes)

    return game

def process_game_info(game_data):
    """
    Process the received game info data using custom software package logic.
    
    Args:
        game_data (dict): The received game info data
        
    Returns:
        dict: Processed results from the custom software package
    """
    try:
        # Extract player data
        playerA = game_data['playerA']
        playerB = game_data['playerB']
        
        # Number of simulation runs
        n = 1000
        
        # Dictionary to store outcome values for each run
        run_outcomes = {}
        
        # Lists to store aggregated results for each scenario
        scenario_results = {
            'NT_NT': [],  # No Tariff - No Tariff
            'T_NT': [],   # Tariff - No Tariff  
            'NT_T': [],   # No Tariff - Tariff
            'T_T': []     # Tariff - Tariff
        }
        
        # Run simulation n times
        for run in range(n):
            run_outcomes[run] = {}
            
            # Process each scenario
            for i, scenario in enumerate(playerA['scenarios']):
                # Extract mean and stdev for each variable in this scenario
                playerA_vars = playerA['variables']
                playerB_vars = playerB['variables']
                
                # Get scenario values (mean values for this scenario)
                playerA_scenario_vals = [float(x) for x in playerA['scenarioValues'][i]]
                playerB_scenario_vals = [float(x) for x in playerB['scenarioValues'][i]]
                
                # Sample from distributions for each variable
                sampled_values = {}
                
                # Sample Player A variables
                for j, var in enumerate(playerA_vars):
                    var_name = var['variableNumber']
                    # Use scenario value as mean, variable stdev as standard deviation
                    mean = playerA_scenario_vals[j]  # Mean from scenarioValues
                    stdev = float(var['stdev'])      # Stdev from variables
                    sampled_val = sample_from_distribution(mean, stdev, 1)[0]
                    sampled_values[f"{var_name}_A"] = sampled_val
                
                # Sample Player B variables  
                for j, var in enumerate(playerB_vars):
                    var_name = var['variableNumber']
                    # Use scenario value as mean, variable stdev as standard deviation
                    mean = playerB_scenario_vals[j]  # Mean from scenarioValues
                    stdev = float(var['stdev'])      # Stdev from variables
                    sampled_val = sample_from_distribution(mean, stdev, 1)[0]
                    sampled_values[f"{var_name}_B"] = sampled_val
                
                # Calculate scenario values using the formulas
                # Player A formula: dynamically parse from game_data
                playerA_result = evaluate_formula(playerA['formula'], sampled_values, 'A', playerA['variables'])
                
                # Player B formula: dynamically parse from game_data
                playerB_result = evaluate_formula(playerB['formula'], sampled_values, 'B', playerB['variables'])
                
                # Store results for this run and scenario
                run_outcomes[run][scenario] = {
                    'playerA_result': playerA_result,
                    'playerB_result': playerB_result,
                    'sampled_values': sampled_values
                }
                
                # Add to scenario results for aggregation
                scenario_results[scenario].append({
                    'playerA': playerA_result,
                    'playerB': playerB_result
                })
        
        # Calculate aggregated outcomes for each scenario
        # These will be the final outcomes used in the game
        final_outcomes = []
        
        # Create the game with the calculated outcomes
        game = create_game(final_outcomes)
        
        # Prepare the response
        processed_results = {
            'status': 'processed',
            'input_data': game_data,
            'processing_timestamp': datetime.now().isoformat(),
            'simulation_runs': n,
            'final_outcomes': final_outcomes,
            'scenario_breakdown': {},
            'run_details': run_outcomes,  # Detailed results for each run
            'game_created': True
        }
        
        return processed_results
        
    except Exception as e:
        # Handle any errors from your custom software package
        raise Exception(f"Error in custom software processing: {str(e)}")

@app.route('/')
def hello_world():
    """Main endpoint that returns hello world"""
    return jsonify({
        'message': 'Hello World!',
        'status': 'success'
    })

@app.route('/health')
def health_check():
    """Health check endpoint for monitoring"""
    return jsonify({
        'status': 'healthy',
        'message': 'API is running'
    })

@app.route('/api/game-info', methods=['POST'])
def receive_game_info():
    """Endpoint to receive game results data from frontend"""
    try:
        # Get JSON data from request
        data = request.get_json()
        
        if not data:
            return jsonify({
                'error': 'No JSON data received',
                'status': 'error'
            }), 400
        
        # Validate required fields
        required_fields = ['playerA', 'playerB', 'summary']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'error': f'Missing required field: {field}',
                    'status': 'error'
                }), 400
        
        # Add timestamp if not provided
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        
        # Process the data using custom software package
        processed_results = process_game_info(data)
        
        return jsonify({
            'message': 'Game info processed successfully',
            'status': 'success',
            'input_timestamp': data['timestamp'],
            'processing_timestamp': processed_results['processing_timestamp'],
            'results': processed_results
        }), 200
        
    except Exception as e:
        return jsonify({
            'error': f'Error processing request: {str(e)}',
            'status': 'error'
        }), 500

@app.route('/api/game-info', methods=['GET'])
def get_game_info():
    """Endpoint to retrieve game info (placeholder for now)"""
    return jsonify({
        'message': 'Game info endpoint - use POST to submit data',
        'status': 'info'
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
