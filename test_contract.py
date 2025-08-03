
import pytest
from web3 import Web3
import json
import os
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv(encoding='utf-8', override=True)

# --- Fixtures de Pytest ---

@pytest.fixture(scope="module")
def w3():
    """Fixture para inicializar la conexión a Ganache."""
    _w3 = Web3(Web3.HTTPProvider('http://127.0.0.1:8545'))
    if not _w3.is_connected():
        pytest.fail("No se pudo conectar a Ganache. Asegúrate de que esté corriendo.")
    return _w3

@pytest.fixture(scope="module")
def deployer_account(w3):
    """Fixture para obtener la cuenta de despliegue desde la clave privada."""
    private_key = os.getenv("PRIVATE_KEY")
    if not private_key:
        pytest.fail("La variable de entorno PRIVATE_KEY no está configurada.")
    return w3.eth.account.from_key(private_key)

@pytest.fixture(scope="module")
def compiled_contract():
    """Fixture para cargar el ABI y el bytecode del contrato."""
    try:
        with open("TicketManager.abi", "r") as f:
            abi = json.load(f)
        with open("TicketManager.bin", "r") as f:
            bytecode = f.read()
    except FileNotFoundError:
        pytest.fail("ABI o Bytecode no encontrados. Compila el contrato primero.")
    return {"abi": abi, "bytecode": bytecode}

@pytest.fixture(scope="module")
def deployed_contract(w3, deployer_account, compiled_contract):
    """Fixture para desplegar el contrato TicketManager."""
    TicketManager = w3.eth.contract(
        abi=compiled_contract['abi'],
        bytecode=compiled_contract['bytecode']
    )
    
    # Estimar gas antes de construir la transacción
    constructor_tx = TicketManager.constructor().build_transaction({
        'from': deployer_account.address,
        'nonce': w3.eth.get_transaction_count(deployer_account.address),
        'gasPrice': w3.eth.gas_price,
    })
    
    # Estimar el gas necesario y añadir un margen
    estimated_gas = w3.eth.estimate_gas(constructor_tx)
    constructor_tx['gas'] = estimated_gas + 50000

    signed_txn = w3.eth.account.sign_transaction(constructor_tx, private_key=deployer_account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    
    contract_instance = w3.eth.contract(
        address=tx_receipt.contractAddress,
        abi=compiled_contract['abi']
    )
    return contract_instance

# --- Tests del Contrato ---

def test_contract_deployment(deployed_contract):
    """Verifica que el contrato se haya desplegado correctamente."""
    assert deployed_contract.address is not None
    assert len(deployed_contract.address) == 42

def test_safe_mint(w3, deployed_contract, deployer_account):
    """Prueba la función safeMint para crear un nuevo ticket."""
    # Parámetros para el nuevo ticket
    recipient_address = w3.eth.accounts[1]  # Usar otra cuenta de Ganache como destinatario
    token_id = 1
    token_uri = f"https://api.ticketera.com/metadata/tickets/{token_id}"

    # Construir la transacción para llamar a safeMint
    mint_tx = deployed_contract.functions.safeMint(
        recipient_address,
        token_uri
    ).build_transaction({
        'from': deployer_account.address,
        'nonce': w3.eth.get_transaction_count(deployer_account.address),
        'gasPrice': w3.eth.gas_price,
    })

    mint_tx['gas'] = 500000

    # Firmar y enviar la transacción
    signed_mint_tx = w3.eth.account.sign_transaction(mint_tx, private_key=deployer_account.key)
    tx_hash = w3.eth.send_raw_transaction(signed_mint_tx.raw_transaction)
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    # Procesar el evento Transfer para obtener el tokenId
    transfer_event = deployed_contract.events.Transfer().process_receipt(tx_receipt)
    assert len(transfer_event) == 1, "Debería haberse emitido un solo evento Transfer"
    token_id = transfer_event[0]['args']['tokenId']

    # Verificar que el dueño del nuevo token es el destinatario
    owner = deployed_contract.functions.ownerOf(token_id).call()
    assert owner == recipient_address

    # Verificar que el tokenURI se haya establecido correctamente
    uri = deployed_contract.functions.tokenURI(token_id).call()
    assert uri == token_uri
