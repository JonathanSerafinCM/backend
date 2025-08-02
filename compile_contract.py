from solcx import compile_source, install_solc, get_installed_solc_versions
import json

# Instalar solc 0.8.0 si no está instalado
if '0.8.0' not in get_installed_solc_versions():
    print("Instalando solc v0.8.0...")
    install_solc('0.8.0')
    print("solc instalado.")

with open("TicketManager.sol", "r") as f:
    contract_source_code = f.read()

# Permitir importaciones desde la carpeta 'contracts'
allowed_paths = [
    "D:/Ruben/ticketera-ia-blockchain/backend/contracts"
]

compiled_sol = compile_source(
    contract_source_code,
    output_values=['abi', 'bin'],
    solc_version='0.8.0',
    allow_paths=allowed_paths
)

contract_interface = compiled_sol["<stdin>:TicketManager"]

# Guardar ABI
with open("TicketManager.abi", "w") as f:
    json.dump(contract_interface['abi'], f)

# Guardar bytecode
with open("TicketManager.bin", "w") as f:
    f.write(contract_interface['bin'])

print("Contrato compilado exitosamente. ABI y bytecode guardados.")