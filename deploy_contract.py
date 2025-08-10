
from web3 import Web3
import json
import os
from dotenv import load_dotenv


# Cargar variables de entorno
load_dotenv(encoding='utf-8', override=True)

# Conectar a la red (Testnet o Local)
rpc_url = os.getenv("TESTNET_RPC_URL", "http://127.0.0.1:8545")
w3 = Web3(Web3.HTTPProvider(rpc_url))

if not w3.is_connected():
    raise Exception(f"No se pudo conectar a la red en {rpc_url}. Asegúrate de que la URL sea correcta y la red esté disponible.")

print(f"Conectado a la red: {rpc_url}")

# Cargar ABI y Bytecode del contrato TicketManager
try:
    with open("TicketManager.abi", "r") as f:
        abi = json.load(f)
    with open("TicketManager.bin", "r") as f:
        bytecode = f.read()
except FileNotFoundError:
    print("ABI o Bytecode no encontrados. Asegúrate de haber compilado el contrato con compile_contract.py")
    exit()


# Obtener la clave privada y derivar la dirección pública
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
deployer_account = w3.eth.account.from_key(PRIVATE_KEY).address
print(f"Usando la cuenta de despliegue: {deployer_account}")

# Crear el objeto contrato
TicketManager = w3.eth.contract(abi=abi, bytecode=bytecode)

# Construir la transacción de despliegue
# Si tu constructor de TicketManager.sol requiere argumentos, pásalos aquí:
# Por ejemplo: constructor_args = [arg1, arg2]
# transaction = TicketManager.constructor(*constructor_args).build_transaction({
transaction = TicketManager.constructor().build_transaction({
    'from': deployer_account,
    'nonce': w3.eth.get_transaction_count(deployer_account),
    'gasPrice': w3.to_wei('30', 'gwei'), # Precio de gas ajustado a 30 Gwei para asegurar el minado
    'gas': 2500000  # Límite de gas ajustado para asegurar el despliegue en Amoy
})


# Firmar la transacción
signed_txn = w3.eth.account.sign_transaction(transaction, private_key=PRIVATE_KEY)

# Enviar la transacción
tx_hash = w3.eth.send_raw_transaction(signed_txn.raw_transaction)
print(f"Transacción de despliegue enviada. Hash: {tx_hash.hex()}")

# Esperar a que la transacción sea minada y obtener el recibo
tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=240) # Aumentamos el tiempo de espera a 240s
contract_address = tx_receipt.contractAddress
print(f"Contrato desplegado en la dirección: {contract_address}")

# Guardar la dirección del contrato para usarla en main.py o en tests futuros
# Puedes guardar esto en un archivo .env o directamente en una variable de entorno
# Por ahora, lo imprimimos y puedes copiarlo
print(f"Por favor, guarda esta dirección del contrato en tu .env como CONTRACT_ADDRESS: {contract_address}")

# Interactuar con el contrato (ejemplo: llamar a una función)
# Asegúrate de que tu contrato TicketManager.sol tenga una función `name()` o `symbol()` si es ERC721
# contract_instance = w3.eth.contract(address=contract_address, abi=abi)
# try:
#     contract_name = contract_instance.functions.name().call()
#     contract_symbol = contract_instance.functions.symbol().call()
#     print(f"Nombre del contrato: {contract_name}")
#     print(f"Símbolo del contrato: {contract_symbol}")
# except Exception as e:
#     print(f"Error al llamar a funciones del contrato (¿ERC721?): {e}")

print("\nDespliegue y prueba básica completados.")
