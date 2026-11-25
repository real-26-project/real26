# Distribuído sob a licença MIT. Consulte COPYING.
"""Textos da interface da carteira e preferência de idioma por usuário."""

import os
from pathlib import Path
from tempfile import NamedTemporaryFile


IDIOMAS = {"pt-BR": "Português (Brasil)", "en": "English", "es": "Español"}
PREFERENCIA = Path(os.environ["LOCALAPPDATA"]) / "REAL-26" / "idioma.txt"


def carregar_idioma():
    try:
        codigo = PREFERENCIA.read_text(encoding="utf-8").strip()
    except (OSError, UnicodeError):
        codigo = ""
    return codigo if codigo in IDIOMAS else "pt-BR"


def salvar_idioma(codigo):
    PREFERENCIA.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=PREFERENCIA.parent, mode="w", encoding="utf-8", delete=False) as arquivo:
        temporario = Path(arquivo.name)
        arquivo.write(codigo + "\n")
    try:
        temporario.replace(PREFERENCIA)
    finally:
        temporario.unlink(missing_ok=True)


# Cada linha contém o texto em português, inglês e espanhol, nessa ordem.
_TEXTOS = r"""
Idioma¦Language¦Idioma
Alterar idioma¦Change language¦Cambiar idioma
Idioma salvo. Feche e reabra a carteira para aplicar.¦Language saved. Close and reopen the wallet to apply it.¦Idioma guardado. Cierra y vuelve a abrir la cartera para aplicarlo.
Falha ao salvar idioma¦Could not save language¦No se pudo guardar el idioma
REAL-26 | Carteira nativa¦REAL-26 | Native wallet¦REAL-26 | Cartera nativa
REAL-26 | Carteira¦REAL-26 | Wallet¦REAL-26 | Cartera
Cancelar¦Cancel¦Cancelar
CARTEIRA¦WALLET¦CARTERA
Criar carteira¦Create wallet¦Crear cartera
Abrir carteira¦Open wallet¦Abrir cartera
Receber¦Receive¦Recibir
Enviar¦Send¦Enviar
Fazer backup¦Back up wallet¦Crear copia de seguridad
Restaurar backup¦Restore backup¦Restaurar copia
Sair da carteira¦Close wallet¦Cerrar cartera
Conectar à testnet¦Connect to testnet¦Conectar a la testnet
Adicionar nó¦Add node¦Añadir nodo
Endereço do nó (host:porta)¦Node address (host:port)¦Dirección del nodo (host:puerto)
Teste compartilhado¦Shared test¦Prueba compartida
Endereço do nó recebido no convite¦Node address from your invitation¦Dirección del nodo de tu invitación
Informe um endereço de nó ou IP válido.¦Enter a valid node address or IP address.¦Introduce una dirección de nodo o IP válida.
Teste isolado¦Isolated test¦Prueba aislada
Falha ao abrir o perfil de teste¦Could not open test profile¦No se pudo abrir el perfil de prueba
Moedas de teste sem valor. A rede pode ser reiniciada.¦Test coins have no value. The network may be reset.¦Las monedas de prueba no tienen valor. La red puede reiniciarse.
Teste compartilhado · ASERT¦Shared test · ASERT¦Prueba compartida · ASERT
Bloco {0}  ·  Pares: {1}¦Block {0}  ·  Peers: {1}¦Bloque {0}  ·  Pares: {1}
Sincronizando  ·  Pares: {1}¦Syncing  ·  Peers: {1}¦Sincronizando  ·  Pares: {1}
Aguardando primeiro bloco  ·  Pares: {1}¦Waiting for first block  ·  Peers: {1}¦Esperando el primer bloque  ·  Pares: {1}
A mineração compartilhada exige conexão com um par e sincronização.¦Shared mining requires a connected peer and a synchronized node.¦La minería compartida requiere un par conectado y un nodo sincronizado.
Visão geral¦Overview¦Vista general
Conectando ao nó¦Connecting to node¦Conectando al nodo
Teste isolado · Ativo¦Isolated test · Active¦Prueba aislada · Activa
SALDO DISPONÍVEL¦AVAILABLE BALANCE¦SALDO DISPONIBLE
Aguardando confirmação¦Awaiting confirmation¦Pendiente de confirmación
Recompensas a amadurecer¦Immature mining rewards¦Recompensas en maduración
Mineração¦Mining¦Minería
Modo¦Mode¦Modo
Automático¦Automatic¦Automático
Threads de CPU¦CPU threads¦Hilos de CPU
Escolha de 1 a {0} threads de CPU.¦Choose between 1 and {0} CPU threads.¦Elige entre 1 y {0} hilos de CPU.
Preparando mineração…¦Preparing mining…¦Preparando la minería…
GPU indisponível. Preparando a CPU…¦GPU unavailable. Preparing the CPU…¦GPU no disponible. Preparando la CPU…
Minerando · {0}¦Mining · {0}¦Minando · {0}
Parada¦Stopped¦Detenida
Encerrar¦Stop¦Detener
Iniciar¦Start¦Iniciar
Pausada¦Paused¦En pausa
Pausar¦Pause¦Pausar
Retomar¦Resume¦Reanudar
Encerrando…¦Stopping…¦Deteniendo…
Falha na mineração¦Mining failed¦Error de minería
{0} bloco¦{0} block¦{0} bloque
{0} blocos¦{0} blocks¦{0} bloques
Atividade¦Activity¦Actividad
Atualizar¦Refresh¦Actualizar
Operação¦Type¦Operación
Valor (REAL-26)¦Amount (REAL-26)¦Importe (REAL-26)
Confirmações¦Confirmations¦Confirmaciones
Identificador¦Transaction ID¦Identificador
Carregar anteriores¦Load older activity¦Cargar actividad anterior
Consultando o nó local…¦Contacting the local node…¦Consultando el nodo local…
A operação falhou.¦The operation failed.¦La operación falló.
Verifique o nó local¦Check the local node¦Comprueba el nodo local
Nó local conectado  ·  Bloco {0}¦Local node connected  ·  Block {0}¦Nodo local conectado  ·  Bloque {0}
bloqueada¦locked¦bloqueada
desbloqueada¦unlocked¦desbloqueada
Nenhuma carteira aberta¦No wallet open¦Ninguna cartera abierta
Enviado¦Sent¦Enviado
Recebido¦Received¦Recibido
Minerado¦Mined¦Minado
Recompensa¦Reward¦Recompensa
Bloco órfão¦Orphan block¦Bloque huérfano
Abra uma carteira, crie outra ou restaure um backup.¦Open, create or restore a wallet.¦Abre, crea o restaura una cartera.
{0} atividades  ·  Clique duplo para copiar o ID.¦{0} entries  ·  Double-click to copy the ID.¦{0} registros  ·  Haz doble clic para copiar el identificador.
Nenhuma transação nesta carteira.¦No transactions in this wallet.¦Esta cartera no tiene transacciones.
Identificador copiado.¦Transaction ID copied.¦Identificador copiado.
Nome da nova carteira¦New wallet name¦Nombre de la nueva cartera
Senha da nova carteira (mínimo de {0} caracteres)¦New wallet password (at least {0} characters)¦Contraseña de la nueva cartera (mínimo de {0} caracteres)
Senha muito curta¦Password too short¦Contraseña demasiado corta
Use pelo menos {0} caracteres. Uma frase longa e exclusiva é mais fácil de guardar.¦Use at least {0} characters. A long, unique passphrase is easier to remember.¦Usa al menos {0} caracteres. Una frase larga y única es más fácil de recordar.
Repita a senha¦Repeat the password¦Repite la contraseña
Senhas diferentes¦Passwords differ¦Las contraseñas son distintas
As senhas precisam coincidir.¦The passwords must match.¦Las contraseñas deben coincidir.
Nenhuma carteira encontrada. Crie uma ou restaure um backup.¦No wallets found. Create one or restore a backup.¦No se encontraron carteras. Crea una o restaura una copia.
Senha da carteira {0}¦Password for wallet {0}¦Contraseña de la cartera {0}
Senha incorreta¦Incorrect password¦Contraseña incorrecta
Falha ao abrir a carteira¦Could not open wallet¦No se pudo abrir la cartera
Receber REAL-26¦Receive REAL-26¦Recibir REAL-26
Endereço de recebimento¦Receiving address¦Dirección de recepción
Copiar endereço¦Copy address¦Copiar dirección
Endereço de teste disponível.¦Test address ready.¦Dirección de prueba disponible.
Enviar REAL-26¦Send REAL-26¦Enviar REAL-26
Endereço do destinatário¦Recipient's address¦Dirección del destinatario
Valor¦Amount¦Importe
Senha da carteira¦Wallet password¦Contraseña de la cartera
Confirmar envio de teste¦Confirm test payment¦Confirmar pago de prueba
Rede de teste isolada¦Isolated test network¦Red de prueba aislada
Rede de teste compartilhada¦Shared test network¦Red de prueba compartida
{0}\n\nValor  {1} REAL-26\nTaxa automática  {2} REAL-26\n\nDestino\n{3}¦{0}\n\nAmount  {1} REAL-26\nAutomatic fee  {2} REAL-26\n\nRecipient\n{3}¦{0}\n\nImporte  {1} REAL-26\nComisión automática  {2} REAL-26\n\nDestinatario\n{3}
Falha ao calcular a taxa¦Could not calculate the fee¦No se pudo calcular la comisión
Falha no envio¦Payment failed¦No se pudo enviar el pago
Conferir envio¦Review payment¦Revisar pago
Identificador da transação:\n{0}¦Transaction ID:\n{0}¦Identificador de la transacción:\n{0}
Pagamento submetido¦Payment submitted¦Pago enviado
Salvar backup criptografado¦Save encrypted backup¦Guardar copia cifrada
Backup salvo¦Backup saved¦Copia guardada
O backup criptografado passou pela verificação de integridade.¦The encrypted backup passed the integrity check.¦La copia cifrada pasó la comprobación de integridad.
Falha ao salvar backup¦Could not save backup¦No se pudo guardar la copia
Abrir backup REAL-26¦Open REAL-26 backup¦Abrir copia de REAL-26
Nome para a carteira restaurada¦Name for the restored wallet¦Nombre de la cartera restaurada
Backup restaurado. Informe a senha original para abrir a carteira.¦Backup restored. Enter the original password to open the wallet.¦Copia restaurada. Introduce la contraseña original para abrir la cartera.
A senha da carteira está incorreta. Digite-a novamente.¦The wallet password is incorrect. Enter it again.¦La contraseña de la cartera es incorrecta. Introdúcela otra vez.
Saldo confirmado e maduro insuficiente para o valor e a taxa.¦Insufficient confirmed, mature funds for the amount and fee.¦Saldo confirmado y maduro insuficiente para el importe y la comisión.
Informe um endereço ML-DSA-65 válido da rede selecionada.¦Enter a valid ML-DSA-65 address for the selected network.¦Introduce una dirección ML-DSA-65 válida de la red seleccionada.
Informe um valor positivo com até oito casas decimais.¦Enter a positive amount with up to eight decimal places.¦Introduce un importe positivo con un máximo de ocho decimales.
Informe uma senha válida em uma única linha.¦Enter a valid password on one line.¦Introduce una contraseña válida en una sola línea.
O estado do envio ficou incerto. Confira a Atividade antes de tentar novamente.¦Payment status is uncertain. Check Activity before trying again.¦El estado del pago es incierto. Consulta Actividad antes de volver a intentarlo.
O pagamento foi submetido. O desbloqueio do nó expira automaticamente.¦The payment was submitted. The node will lock the wallet automatically.¦Se envió el pago. El nodo bloqueará la cartera automáticamente.
Já existe um arquivo nesse local. Escolha outro nome para o backup.¦A file already exists there. Choose a different backup name.¦Ya existe un archivo en esa ubicación. Elige otro nombre para la copia.
O arquivo de backup falhou na verificação de integridade.¦The backup failed the integrity check.¦La copia no pasó la comprobación de integridad.
Use de 1 a 32 letras sem acento, números, hífens ou sublinhados.¦Use 1 to 32 unaccented letters, digits, hyphens or underscores.¦Usa de 1 a 32 letras sin acentos, números, guiones o guiones bajos.
Saia da carteira ativa e escolha um nome ainda não usado.¦Close the active wallet and choose an unused name.¦Cierra la cartera activa y elige un nombre sin usar.
Abra uma carteira primeiro.¦Open a wallet first.¦Abre una cartera primero.
A interface requer uma carteira criptografada.¦This app requires an encrypted wallet.¦Esta aplicación requiere una cartera cifrada.
A interface só gera backups de carteiras criptografadas.¦Only encrypted wallets can be backed up in this app.¦Esta aplicación solo crea copias de carteras cifradas.
O nó local não respondeu.¦The local node did not respond.¦El nodo local no respondió.
O gênese do nó difere do gênese do perfil selecionado.¦The node's genesis block differs from the selected profile's.¦El bloque génesis del nodo difiere del perfil seleccionado.
Falha ao restaurar backup¦Could not restore backup¦No se pudo restaurar la copia
"""

CATALOGO = {}
for linha in _TEXTOS.strip().splitlines():
    original, ingles, espanhol = (parte.replace(r"\n", "\n") for parte in linha.split("¦"))
    CATALOGO[original] = {"en": ingles, "es": espanhol}


def traducao(idioma, texto, *valores):
    resultado = CATALOGO.get(texto, {}).get(idioma, texto)
    return resultado.format(*valores) if valores else resultado
