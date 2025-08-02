import os
import json
from web3 import Web3
from solcx import compile_source, install_solc, get_installed_solc_versions
from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

def deploy():
    """Compila y despliega el contrato TicketManager."""
    # --- 1. Compilación ---
    if '0.8.0' not in get_installed_solc_versions():
        print("Instalando solc v0.8.0...")
        install_solc('0.8.0')

    with open("TicketManager.sol", "r") as f:
        contract_source_code = f.read()

    allowed_paths = ["D:/Ruben/ticketera-ia-blockchain/backend/contracts"]
    compiled_sol = compile_source(
        contract_source_code,
        output_values=['abi', 'bin'],
        solc_version='0.8.0',
        allow_paths=allowed_paths
    )

    contract_interface = compiled_sol["<stdin>:TicketManager"]
    abi = contract_interface['abi']
    bytecode = contract_interface['bin']

    # Guardar ABI para la app
    with open("TicketManager.abi", "w") as f:
        json.dump(abi, f)

    print("Contrato compilado exitosamente.")

    # --- 2. Despliegue ---
    ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")
    PRIVATE_KEY = os.getenv("PRIVATE_KEY")
    ACCOUNT_ADDRESS = os.getenv("ACCOUNT_ADDRESS")

    if not all([ALCHEMY_API_KEY, PRIVATE_KEY, ACCOUNT_ADDRESS]):
        raise ValueError("Por favor, define ALCHEMY_API_KEY, PRIVATE_KEY y ACCOUNT_ADDRESS en tu archivo .env")

    w3 = Web3(Web3.HTTPProvider(f"https://polygon-amoy.g.alchemy.com/v2/{ALCHEMY_API_KEY}"))

    if not w3.is_connected():
        raise ConnectionError("No se pudo conectar con Alchemy.")

    print(f"Conectado a la red. Desplegando desde la cuenta: {ACCOUNT_ADDRESS}")

    TicketManagerContract = w3.eth.contract(abi=abi, bytecode=bytecode)
    nonce = w3.eth.get_transaction_count(ACCOUNT_ADDRESS)
    
    constructor = TicketManagerContract.constructor()
    
    transaction = constructor.build_transaction({
        'from': ACCOUNT_ADDRESS,
        'nonce': nonce,
        'gasPrice': w3.eth.gas_price
    })

    # Estimar gas
    gas_estimate = w3.eth.estimate_gas(transaction)
    transaction['gas'] = gas_estimate

    print(f"Gas estimado: {gas_estimate}")

    signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)

    print(f"Transacción enviada. Hash: {tx_hash.hex()}")
    print("Esperando confirmación...")

    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    contract_address = tx_receipt.contractAddress

    print("-" * 50)
    print(f"¡CONTRATO DESPLEGADO EXITOSAMENTE!")
    print(f"Dirección del Contrato: {contract_address}")
    print("Por favor, guarda esta dirección en tu archivo .env como CONTRACT_ADDRESS")
    print("-" * 50)

if __name__ == "__main__":
    deploy()
