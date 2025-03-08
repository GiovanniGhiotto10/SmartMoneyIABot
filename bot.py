import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import psycopg2  # Substitui pyodbc
from decouple import config

# Configuração do logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuração de conexão com o Neon (PostgreSQL)
def conectar():
    return psycopg2.connect(config("DATABASE_URL"))

# Função para salvar um gasto
def salvar_gasto(usuario, valor, categoria, forma_pagamento, data):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO gastos (usuario, valor, categoria, forma_pagamento, data)
                VALUES (%s, %s, %s, %s, %s)
                ''', (usuario, valor, categoria, forma_pagamento, data))
                conn.commit()
        logger.info(f"Gasto salvo: R${valor} em {categoria} por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao salvar gasto: {e}")
        raise

# Função para salvar uma entrada
def salvar_entrada(usuario, valor, descricao, data):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO entradas (usuario, valor, descricao, data)
                VALUES (%s, %s, %s, %s)
                ''', (usuario, valor, descricao, data))
                conn.commit()
        logger.info(f"Entrada salva: R${valor} - {descricao} por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao salvar entrada: {e}")
        raise

# Função para obter gastos mensais
def obter_gastos_mensais(usuario, mes, ano):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT categoria, SUM(valor) as total
                FROM gastos
                WHERE usuario = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
                GROUP BY categoria
                ''', (usuario, mes, ano))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao obter gastos: {e}")
        raise

# Função para obter entradas mensais
def obter_entradas_mensais(usuario, mes, ano):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT SUM(valor) as total
                FROM entradas
                WHERE usuario = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
                ''', (usuario, mes, ano))
                resultado = cursor.fetchone()
                return resultado[0] if resultado[0] is not None else 0
    except Exception as e:
        logger.error(f"Erro ao obter entradas: {e}")
        raise

# Função para listar gastos
def listar_gastos(usuario):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT id, valor, categoria, forma_pagamento, data
                FROM gastos
                WHERE usuario = %s
                ORDER BY data DESC
                ''', (usuario,))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar gastos: {e}")
        raise

# Função para editar um gasto
def editar_gasto(usuario, gasto_id, valor=None, categoria=None, forma_pagamento=None):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                query = "UPDATE gastos SET "
                params = []
                if valor is not None:
                    query += "valor = %s, "
                    params.append(valor)
                if categoria is not None:
                    query += "categoria = %s, "
                    params.append(categoria)
                if forma_pagamento is not None:
                    query += "forma_pagamento = %s, "
                    params.append(forma_pagamento)
                query = query.rstrip(", ") + " WHERE usuario = %s AND id = %s"
                params.extend([usuario, gasto_id])
                cursor.execute(query, params)
                conn.commit()
        logger.info(f"Gasto ID {gasto_id} editado por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao editar gasto: {e}")
        raise

# Função para remover um gasto
def remover_gasto(usuario, gasto_id):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                DELETE FROM gastos
                WHERE usuario = %s AND id = %s
                ''', (usuario, gasto_id))
                conn.commit()
        logger.info(f"Gasto ID {gasto_id} removido por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao remover gasto: {e}")
        raise

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Olá! Eu sou o SmartMoneyIABot, seu assistente financeiro. Use os comandos:\n"
        "1. /gasto VALOR CATEGORIA [FORMA_PAGAMENTO]\n"
        "2. /entrada VALOR DESCRICAO\n"
        "3. /resumo [MES ANO]\n"
        "4. /editar ID [VALOR] [CATEGORIA] [FORMA_PAGAMENTO]\n"
        "5. /remover ID\n"
        "6. /listar (mostra seus gastos)"
    )

# Comando /gasto
async def gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) < 3 or len(args) > 4:
        await update.message.reply_text("Formato inválido. Use: /gasto VALOR CATEGORIA [FORMA_PAGAMENTO]")
        return
    try:
        _, valor, categoria = args[:3]
        forma_pagamento = args[3] if len(args) == 4 else None
        valor = float(valor)
        if valor <= 0:
            await update.message.reply_text("O valor deve ser positivo.")
            return
        data = datetime.now().strftime('%Y-%m-%d')
        salvar_gasto(str(update.message.chat.id), valor, categoria, forma_pagamento, data)
        msg = f"Gasto de R${valor:.2f} na categoria '{categoria}'"
        if forma_pagamento:
            msg += f" ({forma_pagamento})"
        msg += " salvo com sucesso!"
        await update.message.reply_text(msg)
    except ValueError:
        await update.message.reply_text("O valor deve ser numérico.")
    except Exception:
        await update.message.reply_text("Erro ao salvar o gasto.")

# Comando /entrada
async def entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) != 3:
        await update.message.reply_text("Formato inválido. Use: /entrada VALOR DESCRICAO")
        return
    try:
        _, valor, descricao = args
        valor = float(valor)
        if valor <= 0:
            await update.message.reply_text("O valor deve ser positivo.")
            return
        data = datetime.now().strftime('%Y-%m-%d')
        salvar_entrada(str(update.message.chat.id), valor, descricao, data)
        await update.message.reply_text(f"Entrada de R${valor:.2f} - {descricao} salva!")
    except ValueError:
        await update.message.reply_text("O valor deve ser numérico.")
    except Exception:
        await update.message.reply_text("Erro ao salvar a entrada.")

# Comando /resumo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) == 3:
        try:
            mes, ano = map(int, args[1:])
            if not (1 <= mes <= 12 and 2000 <= ano <= 9999):
                await update.message.reply_text("Mês deve ser 1-12 e ano válido.")
                return
        except ValueError:
            await update.message.reply_text("Use: /resumo MES ANO")
            return
    else:
        mes = datetime.now().month
        ano = datetime.now().year

    try:
        usuario = str(update.message.chat.id)
        gastos = obter_gastos_mensais(usuario, mes, ano)
        entradas = obter_entradas_mensais(usuario, mes, ano)
        resumo = f"Resumo de {mes:02d}/{ano}:\n"
        
        if gastos:
            resumo += "Gastos:\n"
            for categoria, total in gastos:
                resumo += f"- {categoria}: R${total:.2f}\n"
            total_gastos = sum(total for _, total in gastos)
            resumo += f"Total Gasto: R${total_gastos:.2f}\n"
        else:
            resumo += "Nenhum gasto registrado.\n"
            total_gastos = 0
        
        resumo += f"\nEntradas: R${entradas:.2f}\n"
        saldo = entradas - total_gastos
        resumo += f"Saldo: R${saldo:.2f}\n"
        
        if gastos:
            recomendacao = gerar_recomendacao(gastos)
            resumo += f"\nRecomendação: {recomendacao}"
        
        await update.message.reply_text(resumo)
    except Exception:
        await update.message.reply_text("Erro ao gerar o resumo.")

# Comando /listar
async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = str(update.message.chat.id)
    try:
        gastos = listar_gastos(usuario)
        if gastos:
            resposta = "Seus gastos:\n"
            for id, valor, categoria, forma_pagamento, data in gastos:
                fp = f" ({forma_pagamento})" if forma_pagamento else ""
                resposta += f"ID {id}: R${valor:.2f} - {categoria}{fp} ({data})\n"
            await update.message.reply_text(resposta)
        else:
            await update.message.reply_text("Nenhum gasto registrado.")
    except Exception:
        await update.message.reply_text("Erro ao listar gastos.")

# Comando /editar
async def editar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) < 2 or len(args) > 5:
        await update.message.reply_text("Formato inválido. Use: /editar ID [VALOR] [CATEGORIA] [FORMA_PAGAMENTO]")
        return
    try:
        usuario = str(update.message.chat.id)
        gasto_id = int(args[1])
        valor = float(args[2]) if len(args) > 2 else None
        categoria = args[3] if len(args) > 3 else None
        forma_pagamento = args[4] if len(args) > 4 else None
        
        if valor is not None and valor <= 0:
            await update.message.reply_text("O valor deve ser positivo.")
            return
        
        editar_gasto(usuario, gasto_id, valor, categoria, forma_pagamento)
        await update.message.reply_text(f"Gasto ID {gasto_id} editado! Use /listar para verificar.")
    except ValueError:
        await update.message.reply_text("ID e VALOR devem ser numéricos.")
    except Exception:
        await update.message.reply_text("Erro ao editar o gasto ou ID não encontrado.")

# Comando /remover
async def remover(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) != 2:
        await update.message.reply_text("Formato inválido. Use: /remover ID")
        return
    try:
        usuario = str(update.message.chat.id)
        gasto_id = int(args[1])
        remover_gasto(usuario, gasto_id)
        await update.message.reply_text(f"Gasto ID {gasto_id} removido!")
    except ValueError:
        await update.message.reply_text("ID deve ser numérico.")
    except Exception:
        await update.message.reply_text("Erro ao remover o gasto ou ID não encontrado.")

# Função para gerar recomendações
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
        application.add_handler(CommandHandler("entrada", entrada))
        application.add_handler(CommandHandler("resumo", resumo))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("editar", editar))
        application.add_handler(CommandHandler("remover", remover))
        logger.info("Bot iniciado com sucesso.")
        application.run_polling()
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")

if __name__ == "__main__":
    main()
