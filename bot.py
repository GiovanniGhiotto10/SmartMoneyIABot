import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
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

# Função para obter o total de gastos mensais
def obter_total_gastos_mensais(usuario, mes, ano):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT SUM(valor) as total
                FROM gastos
                WHERE usuario = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
                ''', (usuario, mes, ano))
                resultado = cursor.fetchone()
                return resultado[0] if resultado[0] is not None else 0
    except Exception as e:
        logger.error(f"Erro ao obter total de gastos: {e}")
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

# Função para obter o limite do usuário
def obter_limite(usuario):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT limite
                FROM limites
                WHERE usuario = %s
                ''', (usuario,))
                resultado = cursor.fetchone()
                return resultado[0] if resultado else None
    except Exception as e:
        logger.error(f"Erro ao obter limite: {e}")
        raise

# Função para definir ou atualizar o limite do usuário
def definir_limite(usuario, limite):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                INSERT INTO limites (usuario, limite)
                VALUES (%s, %s)
                ON CONFLICT (usuario)
                DO UPDATE SET limite = EXCLUDED.limite
                ''', (usuario, limite))
                conn.commit()
        logger.info(f"Limite de R${limite} definido para o usuário {usuario}")
    except Exception as e:
        logger.error(f"Erro ao definir limite: {e}")
        raise

# Função para verificar se o limite foi excedido
async def verificar_limite(update: Update, usuario, mes, ano):
    try:
        limite = obter_limite(usuario)
        if limite is None:
            return
        
        total_gastos = obter_total_gastos_mensais(usuario, mes, ano)
        if total_gastos > limite:
            await update.message.reply_text(
                f"⚠️ Alerta: Você ultrapassou seu limite de gastos mensal de R${limite:.2f}! "
                f"Seu total de gastos em {mes:02d}/{ano} é R${total_gastos:.2f}."
            )
    except Exception as e:
        logger.error(f"Erro ao verificar limite: {e}")

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

# Função para listar os gastos no Telegram
async def listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = str(update.callback_query.message.chat.id) if update.callback_query else str(update.message.chat.id)
    try:
        gastos = listar_gastos(usuario)
        if not gastos:
            await update.message.reply_text("Nenhum gasto registrado.") if update.message else await update.callback_query.message.reply_text("Nenhum gasto registrado.")
            return
        
        mensagem = "Seus gastos:\n"
        for gasto in gastos:
            id_gasto, valor, categoria, forma_pagamento, data = gasto
            mensagem += f"ID: {id_gasto} | R${valor:.2f} | {categoria} | {forma_pagamento} | {data}\n"
        
        await update.message.reply_text(mensagem) if update.message else await update.callback_query.message.reply_text(mensagem)
    except Exception as e:
        logger.error(f"Erro ao listar gastos para o usuario {usuario}: {str(e)}")
        await update.message.reply_text("Erro ao listar os gastos.") if update.message else await update.callback_query.message.reply_text("Erro ao listar os gastos.")

# Comando /start (menu interativo)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("GASTO", callback_data="start_gasto")],
        [InlineKeyboardButton("ENTRADA", callback_data="start_entrada")],
        [InlineKeyboardButton("LISTAR", callback_data="start_listar")],
        [InlineKeyboardButton("EDITAR", callback_data="start_editar")],
        [InlineKeyboardButton("REMOVER", callback_data="start_remover")],
        [InlineKeyboardButton("POWER BI", callback_data="start_powerbi")],
        [InlineKeyboardButton("GRÁFICO", callback_data="start_grafico")],
        [InlineKeyboardButton("DEFINIR LIMITE", callback_data="start_definirlimite")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha uma opção:", reply_markup=reply_markup)

# Handler para o menu inicial
async def button_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_gasto":
        await query.message.reply_text("Por favor, insira o valor que você gastou (ex.: 100):")
        context.user_data['state'] = 'awaiting_gasto_valor'
    elif query.data == "start_entrada":
        await query.message.reply_text("Por favor, insira o valor da entrada (ex.: 100) e a descrição (ex.: 'Salário'):")
        context.user_data['state'] = 'awaiting_entrada'
    elif query.data == "start_listar":
        await listar(update, context)
    elif query.data == "start_editar":
        await query.message.reply_text("Por favor, insira o ID do gasto a editar (ex.: /editar 1):")
        context.user_data['state'] = 'awaiting_editar_id'
    elif query.data == "start_remover":
        await query.message.reply_text("Por favor, insira o ID do gasto a remover (ex.: /remover 1):")
        context.user_data['state'] = 'awaiting_remover_id'
    elif query.data == "start_powerbi":
        await send_powerbi_link(update, context)
    elif query.data == "start_grafico":
        await grafico(update, context)
    elif query.data == "start_definirlimite":
        await query.message.reply_text("Por favor, insira o valor do limite (ex.: 1000):")
        context.user_data['state'] = 'awaiting_definirlimite'

# Handler para processar mensagens de texto (fluxo interativo)
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = context.user_data.get('state')
    if not state:
        return

    usuario = str(update.message.chat.id)
    mes = datetime.now().month
    ano = datetime.now().year

    if state == 'awaiting_gasto_valor':
        try:
            valor = float(update.message.text)
            if valor <= 0:
                await update.message.reply_text("O valor deve ser positivo. Tente novamente.")
                return
            context.user_data['gasto_valor'] = valor
            # Mostrar botões de categoria
            categorias = ["Alimentação", "Lazer", "Transporte", "Saúde", "Outros", "Escrever Categoria"]
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"gasto_categoria_{cat}") for cat in categorias[i:i+2]]
                for i in range(0, len(categorias), 2)
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Escolha a categoria do gasto ou escreva uma personalizada:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_categoria'
        except ValueError:
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 100).")

    elif state == 'awaiting_gasto_categoria':
        if update.message.text:
            context.user_data['gasto_categoria'] = update.message.text
            # Mostrar botões de forma de pagamento
            formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
            keyboard = [
                [InlineKeyboardButton(fp, callback_data=f"gasto_forma_{fp}") for fp in formas_pagamento[i:i+2]]
                for i in range(0, len(formas_pagamento), 2)
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Escolha a forma de pagamento:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_forma'
        else:
            await update.message.reply_text("Por favor, escreva uma categoria ou escolha uma das opções.")

    elif state == 'awaiting_entrada':
        try:
            parts = update.message.text.split(maxsplit=1)
            if len(parts) != 2:
                await update.message.reply_text("Formato inválido. Use: VALOR DESCRICAO (ex.: 100 Salário).")
                return
            valor = float(parts[0])
            if valor <= 0:
                await update.message.reply_text("O valor deve ser positivo. Tente novamente.")
                return
            descricao = parts[1]
            data = datetime.now().strftime('%Y-%m-%d')
            salvar_entrada(usuario, valor, descricao, data)
            await update.message.reply_text(f"Entrada de R${valor:.2f} - {descricao} salva!")
            context.user_data.pop('state', None)
            await verificar_limite(update, usuario, mes, ano)
        except ValueError:
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 100 Salário).")

    elif state == 'awaiting_editar_id':
        try:
            gasto_id = int(update.message.text.split()[1]) if update.message.text.startswith('/editar') else int(update.message.text)
            context.user_data['editar_id'] = gasto_id
            await update.message.reply_text("Insira o novo valor (opcional), categoria (opcional) e forma de pagamento (opcional), separados por espaço (ex.: 200 Alimentação Cartão):")
            context.user_data['state'] = 'awaiting_editar_dados'
        except ValueError:
            await update.message.reply_text("ID inválido. Insira um número (ex.: /editar 1).")

    elif state == 'awaiting_editar_dados':
        try:
            parts = update.message.text.split(maxsplit=3)
            valor = float(parts[0]) if len(parts) > 0 and parts[0] else None
            categoria = parts[1] if len(parts) > 1 and parts[1] else None
            forma_pagamento = parts[2] if len(parts) > 2 and parts[2] else None
            if valor is not None and valor <= 0:
                await update.message.reply_text("O valor deve ser positivo.")
                return
            gasto_id = context.user_data['editar_id']
            editar_gasto(usuario, gasto_id, valor, categoria, forma_pagamento)
            await update.message.reply_text(f"Gasto ID {gasto_id} editado! Use /listar para verificar.")
            context.user_data.pop('state', None)
            context.user_data.pop('editar_id', None)
        except ValueError:
            await update.message.reply_text("Dados inválidos. Use: VALOR CATEGORIA FORMA (ex.: 200 Alimentação Cartão).")
        except Exception:
            await update.message.reply_text("Erro ao editar o gasto ou ID não encontrado.")

    elif state == 'awaiting_remover_id':
        try:
            gasto_id = int(update.message.text.split()[1]) if update.message.text.startswith('/remover') else int(update.message.text)
            remover_gasto(usuario, gasto_id)
            await update.message.reply_text(f"Gasto ID {gasto_id} removido!")
            context.user_data.pop('state', None)
        except ValueError:
            await update.message.reply_text("ID inválido. Insira um número (ex.: /remover 1).")
        except Exception:
            await update.message.reply_text("Erro ao remover o gasto ou ID não encontrado.")

    elif state == 'awaiting_definirlimite':
        try:
            limite = float(update.message.text)
            if limite <= 0:
                await update.message.reply_text("O limite deve ser positivo. Tente novamente.")
                return
            definir_limite(usuario, limite)
            await update.message.reply_text(f"Limite de R${limite:.2f} definido com sucesso!")
            context.user_data.pop('state', None)
        except ValueError:
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 1000).")

# Handler para botões de gasto
async def button_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data.startswith("gasto_categoria_"):
        categoria = query.data[len("gasto_categoria_"):]
        if categoria == "Escrever Categoria":
            await query.message.reply_text("Por favor, escreva a categoria personalizada:")
            context.user_data['state'] = 'awaiting_gasto_categoria'
        else:
            context.user_data['gasto_categoria'] = categoria
            # Mostrar botões de forma de pagamento
            formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
            keyboard = [
                [InlineKeyboardButton(fp, callback_data=f"gasto_forma_{fp}") for fp in formas_pagamento[i:i+2]]
                for i in range(0, len(formas_pagamento), 2)
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text("Escolha a forma de pagamento:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_forma'

    elif query.data.startswith("gasto_forma_"):
        forma_pagamento = query.data[len("gasto_forma_"):]
        valor = context.user_data.get('gasto_valor')
        categoria = context.user_data.get('gasto_categoria')
        data = datetime.now().strftime('%Y-%m-%d')

        try:
            usuario = str(query.message.chat.id)
            salvar_gasto(usuario, valor, categoria, forma_pagamento, data)
            msg = f"Gasto de R${valor:.2f} na categoria '{categoria}' ({forma_pagamento}) salvo com sucesso!"
            await query.message.reply_text(msg)
            context.user_data.pop('state', None)
            context.user_data.pop('gasto_valor', None)
            context.user_data.pop('gasto_categoria', None)

            # Verificar o limite após salvar o gasto
            mes = datetime.now().month
            ano = datetime.now().year
            await verificar_limite(query, usuario, mes, ano)
        except Exception as e:
            logger.error(f"Erro ao salvar o gasto: {str(e)} - Dados: usuario={usuario}, valor={valor}, categoria={categoria}, forma_pagamento={forma_pagamento}, data={data}")
            await query.message.reply_text(f"Erro ao salvar o gasto: {str(e)}")

# Comando /grafico
async def grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mes = datetime.now().month
    ano = datetime.now().year
    context.user_data['grafico_mes'] = mes
    context.user_data['grafico_ano'] = ano
    await mostrar_grafico(update, context, mes, ano)

# Função para mostrar o gráfico com botões
async def mostrar_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE, mes, ano):
    usuario = str(update.message.chat.id) if update.message else str(update.callback_query.message.chat.id)
    try:
        gastos = obter_gastos_mensais(usuario, mes, ano)
        entradas = obter_entradas_mensais(usuario, mes, ano)
        resumo = f"Resumo de {mes:02d}/{ano}:\n"
        
        if gastos:
            resumo += "Gastos:\n"
            emojis = ["🟦", "🟩", "🟪", "🟥", "🟧"]
            max_valor = max(total for _, total in gastos)
            for i, (categoria, total) in enumerate(gastos):
                emoji = emojis[i % len(emojis)]
                bar_length = int((total / max_valor) * 10) if max_valor > 0 else 0
                bar = "▬" * bar_length
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

        keyboard = [
            [
                InlineKeyboardButton("⬅️ Mês Anterior", callback_data="grafico_prev"),
                InlineKeyboardButton("Mês Próximo ➡️", callback_data="grafico_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(resumo, reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text(resumo, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Erro ao gerar gráfico: {e}")
        if update.message:
            await update.message.reply_text("Erro ao gerar o gráfico.")
        else:
            await update.callback_query.message.edit_text("Erro ao gerar o gráfico.")

# Handler para botões de navegação do /grafico
async def button_grafico(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    mes = context.user_data.get('grafico_mes', datetime.now().month)
    ano = context.user_data.get('grafico_ano', datetime.now().year)

    if query.data == "grafico_prev":
        mes -= 1
        if mes < 1:
            mes = 12
            ano -= 1
    elif query.data == "grafico_next":
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    context.user_data['grafico_mes'] = mes
    context.user_data['grafico_ano'] = ano

    await mostrar_grafico(update, context, mes, ano)

# Comando /powerbi
POWER_BI_BASE_LINK = "https://app.powerbi.com/links/vv8SkpDKaL?filter=public%20gastos/usuario%20eq%20'"
async def send_powerbi_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        filtered_link = f"{POWER_BI_BASE_LINK}'{user_id}'"
        await query.message.reply_text(f"Veja seu relatório (faça login no Power BI): {filtered_link}")
    except Exception as e:
        logger.error(f"Erro ao gerar link do Power BI: {str(e)}")
        await query.message.reply_text("Erro ao gerar o link do Power BI.")

# Função principal assíncrona com webhooks
async def main():
    try:
        application = Application.builder().token(config("TELEGRAM_TOKEN")).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_start, pattern="^start_"))
        application.add_handler(CallbackQueryHandler(button_gasto, pattern="^gasto_"))
        application.add_handler(CallbackQueryHandler(button_grafico, pattern="^grafico_"))
        application.add_handler(CommandHandler("grafico", grafico))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

        port = int(os.environ.get("PORT", 8443))
        webhook_url = f"https://{os.environ.get('RENDER_EXTERNAL_HOSTNAME')}/webhook"
        await application.bot.set_webhook(url=webhook_url)
        await application.initialize()
        await application.start()
        await application.updater.start_webhook(
            listen="0.0.0.0",
            port=port,
            url_path="/webhook",
            webhook_url=webhook_url
        )
        logger.info(f"Bot iniciado com sucesso via webhook on port {port}.")
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
