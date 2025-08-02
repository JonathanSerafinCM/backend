from fastapi import FastAPI, HTTPException, Depends
from web3 import Web3
import json
import os
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- Configuración de Web3 ---
ALCHEMY_API_KEY = os.environ.get("ALCHEMY_API_KEY")
if not ALCHEMY_API_KEY:
    raise ValueError("No se ha configurado la ALCHEMY_API_KEY en las variables de entorno.")

w3 = Web3(Web3.HTTPProvider(f"https://polygon-amoy.g.alchemy.com/v2/{ALCHEMY_API_KEY}"))

with open("TicketManager.abi", "r") as f:
    abi = json.load(f)

with open("TicketManager.bin", "r") as f:
    bytecode = f.read()

def get_contract_address():
    contract_address = os.environ.get("CONTRACT_ADDRESS")
    if not contract_address:
        raise HTTPException(status_code=500, detail="La dirección del contrato no está configurada.")
    return contract_address

PRIVATE_KEY = os.environ.get("PRIVATE_KEY", "0x59c6995e998f97a5a0044966f0945389dc9e86dae88c7a8412f4603b6b78690d") # Clave de prueba de Hardhat - ¡NO USAR EN PRODUCCIÓN!
ACCOUNT_ADDRESS = "0x70997970C51812dc3A010C7d01b50e0d17dc79C8" # Dirección de prueba de Hardhat


@app.post("/deploy")
def deploy_contract():
    if not PRIVATE_KEY:
        raise HTTPException(status_code=500, detail="La clave privada no está configurada.")

    TicketManagerContract = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)
    
    # Estimar gas dinámicamente
    constructor = TicketManagerContract.constructor()
    gas_estimate = constructor.estimate_gas({'from': ACCOUNT_ADDRESS, 'nonce': nonce})

    transaction = constructor.build_transaction({
        'chainId': 80002,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })
    
    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    return {"message": "Contrato desplegado", "contract_address": tx_receipt.contractAddress}


@app.post("/tickets")
def create_ticket_endpoint(owner_address: str, contract_address: str = Depends(get_contract_address)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)

    # Estimar gas dinámicamente
    create_ticket_function = contract.functions.createTicket(owner_address)
    gas_estimate = create_ticket_function.estimate_gas({'from': ACCOUNT_ADDRESS, 'nonce': nonce})

    tx_data = create_ticket_function.build_transaction({
        'chainId': 80002,
        'gas': gas_estimate,
        'gasPrice': w3.eth.gas_price,
        'nonce': nonce,
    })

    signed_tx = w3.eth.account.sign_transaction(tx_data, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    # El ID del ticket se puede obtener de los logs del evento, si se implementan.
    # Por ahora, devolvemos el hash de la transacción.
    return {"message": "Ticket creado exitosamente", "transaction_hash": tx_hash.hex()}


@app.get("/tickets/{ticket_id}")
def get_ticket_owner(ticket_id: int, contract_address: str = Depends(get_contract_address)):
    contract = w3.eth.contract(address=contract_address, abi=abi)
    owner = contract.functions.ticketOwners(ticket_id).call()
    return {"ticket_id": ticket_id, "owner": owner}


@app.get("/events/recommendations")
def get_event_recommendations():
    return {
        "events": [
            {"id": 1, "name": "Concierto de Rock", "category": "Música"},
            {"id": 2, "name": "Obra de Teatro", "category": "Teatro"},
            {"id": 3, "name": "Festival de Jazz", "category": "Música"},
        ]
    }
