import os
import json
from web3 import Web3
from solcx import compile_source, install_solc
from dotenv import load_dotenv

load_dotenv(encoding='utf-8')

def compile_and_deploy():
    # Instalar y seleccionar la versión del compilador de Solidity
    install_solc('0.8.0')

    # Leer el código fuente del contrato
    with open("TicketManager.sol", "r") as f:
        source = f.read()

    # Compilar el contrato
    compiled_sol = compile_source(
        source,
        output_values=["abi", "bin"],
        solc_version='0.8.0'
    )

    contract_interface = compiled_sol["<stdin>:TicketManager"]
    abi = contract_interface["abi"]
    bytecode = contract_interface["bin"]

    # Guardar ABI
    with open("TicketManager.abi", "w") as f:
        json.dump(abi, f)

    # Conectar a Ganache
    w3 = Web3(Web3.HTTPProvider("http://127.0.0.1:8545"))
    if not w3.is_connected():
        raise ConnectionError("No se pudo conectar a Ganache.")

    # Usar la primera cuenta de Ganache
    w3.eth.default_account = w3.eth.accounts[0]

    # Crear instancia del contrato
    TicketManager = w3.eth.contract(abi=abi, bytecode=bytecode)

    # Desplegar
    tx_hash = TicketManager.constructor().transact()
    tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    contract_address = tx_receipt.contractAddress
    print(f"Contrato desplegado en: {contract_address}")

    # Actualizar .env
    # Leer el archivo .env existente
    if os.path.exists('.env'):
        with open('.env', 'r') as f:
            lines = f.readlines()
    else:
        lines = []

    # Eliminar la línea CONTRACT_ADDRESS existente si la hay
    lines = [line for line in lines if not line.strip().startswith('CONTRACT_ADDRESS=')]

    # Añadir la nueva dirección del contrato
    lines.append(f'CONTRACT_ADDRESS={contract_address}\n')

    # Escribir el archivo .env actualizado
    with open('.env', 'w') as f:
        f.writelines(lines)

    print("Archivo .env actualizado con la nueva dirección del contrato.")

if __name__ == "__main__":
    compile_and_deploy()