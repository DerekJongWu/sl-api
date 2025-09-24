from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import os
from datetime import datetime
import numpy as np
from sl_package import Game, BackwardInductionSolver
from sl_package.sampling import sample_from_distribution
import pandas as pd
import io

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

def clamp_to_bounds(value, min_val, max_val):
    """
    Clamp a value to the specified min and max bounds.
    
    Args:
        value (float): The value to clamp
        min_val (float): Minimum allowed value
        max_val (float): Maximum allowed value
        
    Returns:
        float: The clamped value
    """
    return max(min_val, min(max_val, value))

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
        # Debug output (commented out for production)
        # print(f"DEBUG: Evaluating formula '{formula}' for player {player_suffix}")
        # print(f"DEBUG: Sampled values: {sampled_values}")
        # print(f"DEBUG: Variables data: {variables_data}")
        # Create a safe evaluation environment with only the sampled values
        # Replace formula variables with actual sampled values
        eval_formula = formula
        
        # Handle different variable formats in the formula
        # First, replace weight variables with actual weight values
        for var in variables_data:
            var_name = var['variableNumber']
            weight = var.get('weight', 0.5)  # Default weight if not specified
            # Handle both uppercase and lowercase variable names
            eval_formula = eval_formula.replace(f"{var_name}_weight", str(weight))
            eval_formula = eval_formula.replace(f"{var_name.lower()}_weight", str(weight))
        
        # print(f"DEBUG: After weight replacement: {eval_formula}")
        
        # Replace v1_Val with v1_A, v2_Val with v2_A, etc.
        for var_name, value in sampled_values.items():
            if var_name.endswith(f"_{player_suffix}"):
                # Extract the base variable name (e.g., "v1" from "v1_A")
                base_var = var_name.replace(f"_{player_suffix}", "")
                
                # Check if this variable needs standardization
                if f"{base_var}_stnd" in formula or f"{base_var}_Stnd" in formula or f"{base_var.lower()}_stnd" in formula:
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
                        
                        # Clamp standardized value to [0, 1] range to avoid extreme values
                        standardized_val = max(0.0, min(1.0, standardized_val))
                        
                        # Replace the _stnd variable with the standardized value
                        eval_formula = eval_formula.replace(f"{base_var}_stnd", str(standardized_val))
                        eval_formula = eval_formula.replace(f"{base_var}_Stnd", str(standardized_val))
                        eval_formula = eval_formula.replace(f"{base_var.lower()}_stnd", str(standardized_val))
                        # print(f"DEBUG: After {base_var} standardization: {eval_formula}")
                    else:
                        # If variable definition not found, use original value
                        eval_formula = eval_formula.replace(f"{base_var}_stnd", str(value))
                        eval_formula = eval_formula.replace(f"{base_var}_Stnd", str(value))
                        eval_formula = eval_formula.replace(f"{base_var.lower()}_stnd", str(value))
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
        dict: Processed results and Excel file data
    """
    try:
        # Extract player data
        playerA = game_data['playerA']
        playerB = game_data['playerB']
        
        # Number of simulation runs
        n = 1000
        
        # Data structures to store simulation results
        playerA_variables = []  # For Excel sheet 1
        playerB_variables = []  # For Excel sheet 2
        payoffs_and_results = []  # For Excel sheet 3
        failed_simulations = []  # Track failed simulation runs
        
        # Run simulation n times
        for run in range(n):
            try:
                run_data_A = {'simulation_run': run + 1}
                run_data_B = {'simulation_run': run + 1}
                
                # Sample from distributions for each variable in each scenario
                scenario_payoffs = {}
                
                for i, scenario in enumerate(playerA['scenarios']):
                    # Sample Player A variables
                    playerA_sampled = {}
                    for j, var in enumerate(playerA['variables']):
                        var_name = var['variableNumber']
                        mean = float(playerA['scenarioValues'][i][j])
                        stdev = float(var['stdev'])
                        sampled_val = sample_from_distribution(mean, stdev, 1)[0]
                        
                        # Apply bounds checking after sampling but before standardization
                        min_val = float(var['min'])
                        max_val = float(var['max'])
                        clamped_val = clamp_to_bounds(sampled_val, min_val, max_val)
                        
                        playerA_sampled[f"{var_name}_A"] = clamped_val
                    
                    # Sample Player B variables  
                    playerB_sampled = {}
                    for j, var in enumerate(playerB['variables']):
                        var_name = var['variableNumber']
                        mean = float(playerB['scenarioValues'][i][j])
                        stdev = float(var['stdev'])
                        sampled_val = sample_from_distribution(mean, stdev, 1)[0]
                        
                        # Apply bounds checking after sampling but before standardization
                        min_val = float(var['min'])
                        max_val = float(var['max'])
                        clamped_val = clamp_to_bounds(sampled_val, min_val, max_val)
                        
                        playerB_sampled[f"{var_name}_B"] = clamped_val
                    
                    # Calculate payoffs using formulas
                    playerA_payoff = evaluate_formula(playerA['formula'], playerA_sampled, 'A', playerA['variables'])
                    playerB_payoff = evaluate_formula(playerB['formula'], playerB_sampled, 'B', playerB['variables'])
                    
                    scenario_payoffs[scenario] = (playerA_payoff, playerB_payoff)
                    
                    # Store variable values for this run and scenario
                    # Player A variables
                    for var_name, value in playerA_sampled.items():
                        run_data_A[f"{var_name}_{scenario}"] = value
                    
                    # Player B variables
                    for var_name, value in playerB_sampled.items():
                        run_data_B[f"{var_name}_{scenario}"] = value
                
                # Store variable values for this run
                playerA_variables.append(run_data_A)
                playerB_variables.append(run_data_B)
                
                # Create game with current scenario payoffs and solve
                outcomes = [
                    scenario_payoffs['NT_NT'],  # No Tariff - No Tariff
                    scenario_payoffs['T_NT'],   # Tariff - No Tariff  
                    scenario_payoffs['NT_T'],   # No Tariff - Tariff
                    scenario_payoffs['T_T']     # Tariff - Tariff
                ]
                
                g = create_game(outcomes)
                solver = BackwardInductionSolver(g)
                solver.solve()
                sim_result = solver.record_equilibrium()
                
                # Store payoff and result data for this run
                payoff_data = {
                    'simulation_run': run + 1,
                    'NT_NT_PlayerA': scenario_payoffs['NT_NT'][0],
                    'NT_NT_PlayerB': scenario_payoffs['NT_NT'][1],
                    'T_NT_PlayerA': scenario_payoffs['T_NT'][0],
                    'T_NT_PlayerB': scenario_payoffs['T_NT'][1],
                    'NT_T_PlayerA': scenario_payoffs['NT_T'][0],
                    'NT_T_PlayerB': scenario_payoffs['NT_T'][1],
                    'T_T_PlayerA': scenario_payoffs['T_T'][0],
                    'T_T_PlayerB': scenario_payoffs['T_T'][1],
                    'equilibrium_result': str(sim_result)
                }
                payoffs_and_results.append(payoff_data)
                
            except Exception as sim_error:
                # Log the failed simulation but continue with the next one
                failed_simulations.append({
                    'simulation_run': run + 1,
                    'error': str(sim_error),
                    'error_type': type(sim_error).__name__
                })
                print(f"Warning: Simulation run {run + 1} failed: {sim_error}")
                continue
        
        # Prepare the response with Excel data
        successful_runs = len(payoffs_and_results)
        failed_count = len(failed_simulations)
        
        processed_results = {
            'status': 'processed',
            'input_data': game_data,
            'processing_timestamp': datetime.now().isoformat(),
            'simulation_runs': n,
            'successful_runs': successful_runs,
            'failed_runs': failed_count,
            'success_rate': f"{(successful_runs/n)*100:.1f}%" if n > 0 else "0%",
            'failed_simulations': failed_simulations if failed_count > 0 else None,
            'excel_data': {
                'playerA_variables': playerA_variables,
                'playerB_variables': playerB_variables,
                'payoffs_and_results': payoffs_and_results
            }
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
        
        # Process the data using custom software package
        processed_results = process_game_info(data)
        
        # Create Excel file with three sheets
        output = io.BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: Player A variable values for each simulation
            df_playerA = pd.DataFrame(processed_results['excel_data']['playerA_variables'])
            df_playerA.to_excel(writer, sheet_name='PlayerA_Variables', index=False)
            
            # Sheet 2: Player B variable values for each simulation
            df_playerB = pd.DataFrame(processed_results['excel_data']['playerB_variables'])
            df_playerB.to_excel(writer, sheet_name='PlayerB_Variables', index=False)
            
            # Sheet 3: Payoffs and results for each simulation
            df_payoffs = pd.DataFrame(processed_results['excel_data']['payoffs_and_results'])
            df_payoffs.to_excel(writer, sheet_name='Payoffs_andResults', index=False)
        
        output.seek(0)
        
        return send_file(
            output, 
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
            as_attachment=True, 
            download_name='game_simulation_results.xlsx'
        )
        
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
