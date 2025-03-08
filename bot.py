import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import psycopg2
from decouple import config

# Configuração do logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configurações de conexão com o SQL Server usando Autenticação do Windows
conn_str = (
    f'DRIVER={{ODBC Driver 17 for SQL Server}};'
    f'SERVER={config("DB_SERVER")};'
    f'DATABASE=ChatbotFinanceiro;'
    f'Trusted_Connection=Yes;'
)

# Estrutura sugerida do banco de dados (execute no SQL Server antes de rodar o bot):
"""
CREATE TABLE gastos (
    id INT IDENTITY(1,1) PRIMARY KEY,
    usuario VARCHAR(50),
    valor DECIMAL(10, 2),
    categoria VARCHAR(50),
    data DATE
);
"""

# Função para salvar um gasto
def salvar_gasto(usuario, valor, categoria, data):
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            INSERT INTO gastos (usuario, valor, categoria, data)
            VALUES (?, ?, ?, ?)
            ''', (usuario, valor, categoria, data))
            conn.commit()
        logger.info(f"Gasto salvo: R${valor} em {categoria} por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao salvar gasto: {e}")
        raise

# Função para obter gastos mensais
def obter_gastos_mensais(usuario, mes, ano):
    try:
        with pyodbc.connect(conn_str) as conn:
            cursor = conn.cursor()
            cursor.execute('''
            SELECT categoria, SUM(valor) as total
            FROM gastos
            WHERE usuario = ? AND MONTH(data) = ? AND YEAR(data) = ?
            GROUP BY categoria
            ''', (usuario, mes, ano))
            gastos = cursor.fetchall()
        return gastos
    except Exception as e:
        logger.error(f"Erro ao obter gastos: {e}")
        raise

# Função para o comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou seu assistente de gastos. Use os comandos:\n"
        "1. /gasto VALOR CATEGORIA\n"
        "2. /resumo [MES ANO] (ex: /resumo 03 2025, opcional)"
    )

# Função para o comando /gasto
async def gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) != 3:
        await update.message.reply_text("Formato inválido. Use: /gasto VALOR CATEGORIA")
        return
    try:
        _, valor, categoria = args
        valor = float(valor)
        if valor <= 0:
            await update.message.reply_text("O valor deve ser positivo.")
            return
        data = datetime.now().strftime('%Y-%m-%d')
        salvar_gasto(str(update.message.chat.id), valor, categoria, data)
        await update.message.reply_text(f"Gasto de R${valor:.2f} na categoria '{categoria}' salvo com sucesso!")
    except ValueError:
        await update.message.reply_text("O valor deve ser numérico. Use: /gasto VALOR CATEGORIA")
    except Exception:
        await update.message.reply_text("Erro ao salvar o gasto. Tente novamente.")

# Função para o comando /resumo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) == 3:
        try:
            mes, ano = map(int, args[1:])
            if not (1 <= mes <= 12 and 2000 <= ano <= 9999):
                await update.message.reply_text("Mês deve ser 1-12 e ano válido (ex: 2025).")
                return
        except ValueError:
            await update.message.reply_text("Use: /resumo MES ANO (ex: /resumo 03 2025)")
            return
    else:
        mes = datetime.now().month
        ano = datetime.now().year

    try:
        gastos = obter_gastos_mensais(str(update.message.chat.id), mes, ano)
        if gastos:
            resumo = f"Gastos de {mes:02d}/{ano}:\n"
            for categoria, total in gastos:
                resumo += f"- {categoria}: R${total:.2f}\n"
            recomendacao = gerar_recomendacao(gastos)
            resumo += f"\nRecomendação: {recomendacao}"
            await update.message.reply_text(resumo)
        else:
            await update.message.reply_text(f"Nenhum gasto registrado em {mes:02d}/{ano}.")
    except Exception:
        await update.message.reply_text("Erro ao gerar o resumo. Tente novamente.")

# Função para gerar recomendações mais inteligentes
def gerar_recomendacao(gastos):
    total_gastos = sum(total for _, total in gastos)
    for categoria, total in gastos:
        if total > 1000 and categoria.lower() in ['lazer', 'compras', 'entretenimento']:
            return f"Considere reduzir gastos com '{categoria}' (R${total:.2f})."
    if total_gastos > 3000:
        return "Você está gastando muito! Reduza despesas gerais."
    elif total_gastos > 1500:
        return "Seus gastos estão moderados. Tente economizar um pouco mais."
    return "Seus gastos estão sob controle. Parabéns!"

# Função principal
def main():
    try:
        application = Application.builder().token(config("TELEGRAM_TOKEN")).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("gasto", gasto))
        application.add_handler(CommandHandler("resumo", resumo))
        logger.info("Bot iniciado com sucesso.")
        application.run_polling()
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")

if __name__ == "__main__":
    main()
