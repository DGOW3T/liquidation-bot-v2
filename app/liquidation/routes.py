"""Module for handling API routes"""
from flask import Blueprint, make_response, jsonify, request
import math

from .liquidation_bot import logger
from .bot_manager import ChainManager

liquidation = Blueprint("liquidation", __name__)

chain_manager = None

def start_monitor(chain_ids=None):
    """Start monitoring for specified chains, defaults to mainnet if none specified"""
    global chain_manager
    if chain_ids is None:
        chain_ids = [1] # Default to Ethereum mainnet

    chain_manager = ChainManager(chain_ids, notify=True)

    chain_manager.start()

    return chain_manager

@liquidation.route("/allPositions", methods=["GET"])
def get_all_positions():
    chain_id = int(request.args.get("chainId", 1))  # Default to mainnet if not specified
    
    if not chain_manager or chain_id not in chain_manager.monitors:
        return jsonify({"error": f"Monitor not initialized for chain {chain_id}"}), 500

    logger.info("API: Getting all positions for chain %s", chain_id)
    monitor = chain_manager.monitors[chain_id]
    sorted_accounts = monitor.get_accounts_by_health_score()

    response = []
    for (address, owner, sub_account, health_score, value_borrowed, vault_name, vault_symbol) in sorted_accounts:
        if math.isinf(health_score):
            continue
        response.append({
            "address": owner,
            "account_address": address,
            "sub_account": sub_account,
            "health_score": health_score,
            "value_borrowed": value_borrowed,
            "vault_name": vault_name,
            "vault_symbol": vault_symbol
        })

    return make_response(jsonify(response))

@liquidation.route("/positions", methods=["POST"])
def get_accounts_positions():
    """Get positions by their addresses"""
    chain_id = int(request.args.get("chainId", 1))  # Default to mainnet if not specified
    
    if not chain_manager or chain_id not in chain_manager.monitors:
        return jsonify({"error": f"Monitor not initialized for chain {chain_id}"}), 500

    # Get the list of addresses from the request body
    data = request.get_json()
    if not data or 'addresses' not in data:
        return jsonify({"error": "Missing 'addresses' in request body"}), 400

    addresses = data['addresses']
    if not isinstance(addresses, list):
        return jsonify({"error": "'addresses' must be a list"}), 400

    logger.info("API: Getting positions for %d accounts on chain %s", len(addresses), chain_id)
    monitor = chain_manager.monitors[chain_id]
    
    # Find all accounts that match the provided addresses
    accounts_positions = []
    for address in addresses:
        account = monitor.accounts.get(address)
        if account:
            if not math.isinf(account.current_health_score):
                accounts_positions.append({
                    "address": account.address,
                    "owner": account.owner,
                    "sub_account": account.subaccount_number,
                    "health_score": account.current_health_score,
                    "value_borrowed": account.value_borrowed,
                    "balance": account.balance,
                    "next_update_time": account.time_of_next_update,
                    "vault_name": account.controller.vault_name,
                    "vault_address": account.controller.address,
                    "vault_symbol": account.controller.vault_symbol
                })
    
    # Sort by health score ascending (most risky first)
    accounts_positions.sort(key=lambda x: x["health_score"])
    
    return make_response(jsonify(accounts_positions))