import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import psycopg2
from decouple import config
import os

# Configuração do logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Função de conexão com o Neon (PostgreSQL)
def conectar():
    return psycopg2.connect(config("DATABASE_URL"))

# Funções de banco de dados (salvar_gasto, salvar_entrada, etc.) permanecem as mesmas
# (copie do código anterior que enviei)

# Comando /start, /gasto, /entrada, etc., permanecem os mesmos
# (copie do código anterior que enviei)

# Função principal com bloqueio
def main():
    lock_file = 'bot.lock'
    try:
        # Tenta adquirir o bloqueio criando ou verificando o arquivo
        if os.path.exists(lock_file):
            logger.error("Outra instância do bot está rodando. Encerrando.")
            return
        with open(lock_file, 'w') as f:
            f.write(str(os.getpid()))  # Escreve o PID para rastreamento

        application = Application.builder().token(config("TELEGRAM_TOKEN")).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("gasto", gasto))
        application.add_handler(CommandHandler("entrada", entrada))
        application.add_handler(CommandHandler("resumo", resumo))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("editar", editar))
        application.add_handler(CommandHandler("remover", remover))
        logger.info("Bot iniciado com sucesso.")
        application.run_polling()
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")
    finally:
        if os.path.exists(lock_file):
            os.remove(lock_file)  # Remove o arquivo de bloqueio ao encerrar

if __name__ == "__main__":
    main()
