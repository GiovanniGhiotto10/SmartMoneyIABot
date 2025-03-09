import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from datetime import datetime
import psycopg2
from decouple import config
import os
import asyncio

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
        "3. /editar ID [VALOR] [CATEGORIA] [FORMA_PAGAMENTO]\n"
        "4. /remover ID\n"
        "5. /powerbi (veja seu relatório no Power BI)\n"
        "6. /listar (Ver o ID)\n"
        "7. /grafico [MES ANO] (veja um gráfico simples)"
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

# Comando /grafico (atualizado para as mesmas informações do /resumo, sem IDs)
async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = update.message.text.split()
    if len(args) == 3:
        try:
            mes, ano = map(int, args[1:])
            if not (1 <= mes <= 12 and 2000 <= ano <= 9999):
                await update.message.reply_text("Mês deve ser 1-12 e ano válido.")
                return
        except ValueError:
            await update.message.reply_text("Use: /grafico MES ANO")
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
            emojis = ["🟦", "🟩", "🟪", "🟥", "🟧"]  # Cores diferentes para cada categoria
            max_valor = max(total for _, total in gastos)  # Para normalizar o tamanho das barras
            for i, (categoria, total) in enumerate(gastos):
                emoji = emojis[i % len(emojis)]
                bar_length = int((total / max_valor) * 10) if max_valor > 0 else 0
                bar = "▬" * bar_length  # Usando '▬' para compatibilidade
                resumo += f"{emoji} {categoria}: R${total:.2f} {bar}\n"
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
    except Exception as e:
        logger.error(f"Erro ao gerar gráfico: {e}")
        await update.message.reply_text("Erro ao gerar o gráfico.")

# Comando /powerbi
POWER_BI_BASE_LINK = "https://app.powerbi.com/links/vv8SkpDKaL?filter=public%20gastos/usuario%20eq%20'"
async def send_powerbi_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    filtered_link = f"{POWER_BI_BASE_LINK}'{user_id}'"
    await update.message.reply_text(f"Veja seu relatório (faça login no Power BI): {filtered_link}")

# Função principal assíncrona com webhooks
async def main():
    try:
        # Crie a aplicação
        application = Application.builder().token(config("TELEGRAM_TOKEN")).build()

        # Adicione os handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("gasto", gasto))
        application.add_handler(CommandHandler("entrada", entrada))
        application.add_handler(CommandHandler("listar", listar))
        application.add_handler(CommandHandler("editar", editar))
        application.add_handler(CommandHandler("remover", remover))
        application.add_handler(CommandHandler("powerbi", send_powerbi_link))
        application.add_handler(CommandHandler("grafico", grafico))

        # Configure o webhook
        port = int(os.environ.get("PORT", 8443))
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
        await application.bot.set_webhook(url=webhook_url)

        # Inicialize a aplicação
        await application.initialize()

        # Inicie a aplicação
        await application.start()

        # Inicie o webhook
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/webhook",
            webhook_url=webhook_url
        )
        logger.info(f"Bot iniciado com sucesso via webhook on port {port}.")

        # Mantenha o bot rodando
        while True:
            await asyncio.sleep(10)
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")
        if application and application.updater:
            await application.updater.stop()
        if application:
            await application.stop()
            await application.shutdown()
        raise

if __name__ == "__main__":
    asyncio.run(main())
