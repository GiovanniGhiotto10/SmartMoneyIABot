import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters
from datetime import datetime
import psycopg2
from decouple import config
import os
import asyncio
import pandas as pd
from io import BytesIO
from openpyxl import Workbook
from openpyxl.chart import BarChart, Reference
from openpyxl.chart.label import DataLabelList

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

# Função para obter gastos mensais (para resumo e planilha)
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

# Função para listar gastos de um mês específico
def listar_gastos_mensais(usuario, mes, ano):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT id, valor, categoria, forma_pagamento, data
                FROM gastos
                WHERE usuario = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
                ORDER BY data DESC
                ''', (usuario, mes, ano))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar gastos mensais: {e}")
        raise

# Função para listar entradas de um mês específico
def listar_entradas_mensais(usuario, mes, ano):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                SELECT id, valor, descricao, data
                FROM entradas
                WHERE usuario = %s AND EXTRACT(MONTH FROM data) = %s AND EXTRACT(YEAR FROM data) = %s
                ORDER BY data DESC
                ''', (usuario, mes, ano))
                return cursor.fetchall()
    except Exception as e:
        logger.error(f"Erro ao listar entradas mensais: {e}")
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

# Função para editar uma entrada
def editar_entrada(usuario, entrada_id, valor=None, descricao=None):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                query = "UPDATE entradas SET "
                params = []
                if valor is not None:
                    query += "valor = %s, "
                    params.append(valor)
                if descricao is not None:
                    query += "descricao = %s, "
                    params.append(descricao)
                query = query.rstrip(", ") + " WHERE usuario = %s AND id = %s"
                params.extend([usuario, entrada_id])
                cursor.execute(query, params)
                conn.commit()
        logger.info(f"Entrada ID {entrada_id} editada por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao editar entrada: {e}")
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

# Função para remover uma entrada
def remover_entrada(usuario, entrada_id):
    try:
        with conectar() as conn:
            with conn.cursor() as cursor:
                cursor.execute('''
                DELETE FROM entradas
                WHERE usuario = %s AND id = %s
                ''', (usuario, entrada_id))
                conn.commit()
        logger.info(f"Entrada ID {entrada_id} removida por {usuario}")
    except Exception as e:
        logger.error(f"Erro ao remover entrada: {e}")
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

# Comando /start (menu interativo)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("GASTO", callback_data="start_gasto")],
        [InlineKeyboardButton("VALOR RECEBIDO", callback_data="start_entrada")],
        [InlineKeyboardButton("RESUMO", callback_data="start_resumo")],
        [InlineKeyboardButton("PLANILHA EXCEL", callback_data="start_excel")],
        [InlineKeyboardButton("POWER BI", callback_data="start_powerbi")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Escolha uma opção:", reply_markup=reply_markup)
    context.user_data['navigation_stack'] = []

# Handler para o menu inicial
async def button_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "start_gasto":
        keyboard = [
            [InlineKeyboardButton("GASTO NORMAL", callback_data="gasto_normal")],
            [InlineKeyboardButton("GASTO FIXO", callback_data="gasto_fixo")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha o tipo de gasto:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_entrada":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR VALOR RECEBIDO", callback_data="entrada_adicionar")],
            [InlineKeyboardButton("EDITAR VALOR RECEBIDO", callback_data="editar_entrada")],
            [InlineKeyboardButton("REMOVER VALOR RECEBIDO", callback_data="remover_entrada")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Valor Recebido:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_powerbi":
        await send_powerbi_link(update, context)
        context.user_data['navigation_stack'].append("start")
    elif query.data == "start_resumo":
        await resumo(update, context)
    elif query.data == "start_excel":
        mes = datetime.now().month
        ano = datetime.now().year
        context.user_data['excel_mes'] = mes
        context.user_data['excel_ano'] = ano
        context.user_data['navigation_stack'].append("start")
        await mostrar_selecao_excel(update, context, mes, ano)

# Função para mostrar a seleção de mês/ano para a planilha Excel
async def mostrar_selecao_excel(update: Update, context: ContextTypes.DEFAULT_TYPE, mes, ano):
    usuario = str(update.callback_query.message.chat.id)
    try:
        mensagem = f"Selecione o mês e ano para gerar a planilha:\n\nMês atual: {mes:02d}/{ano}"
        keyboard = [
            [
                InlineKeyboardButton("⬅️ Mês Anterior", callback_data="excel_prev"),
                InlineKeyboardButton("Gerar Planilha", callback_data="excel_gerar"),
                InlineKeyboardButton("Mês Próximo ➡️", callback_data="excel_next")
            ],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text(mensagem, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Erro ao mostrar seleção de mês para Excel: {e}")
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.edit_text("Erro ao mostrar seleção de mês.", reply_markup=reply_markup)

# Handler para botões de navegação da seleção de mês para Excel
async def button_excel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "voltar":
        await handle_voltar(update, context)
        return

    mes = context.user_data.get('excel_mes', datetime.now().month)
    ano = context.user_data.get('excel_ano', datetime.now().year)

    if query.data == "excel_prev":
        mes -= 1
        if mes < 1:
            mes = 12
            ano -= 1
    elif query.data == "excel_next":
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1
    elif query.data == "excel_gerar":
        await gerar_planilha_excel(update, context, mes, ano)
        return

    context.user_data['excel_mes'] = mes
    context.user_data['excel_ano'] = ano
    await mostrar_selecao_excel(update, context, mes, ano)

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
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O valor deve ser positivo. Tente novamente.", reply_markup=reply_markup)
                return
            context.user_data['gasto_valor'] = valor
            categorias = ["Alimentação", "Lazer", "Transporte", "Saúde", "Outros", "Escrever Categoria"]
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"gasto_categoria_{cat}") for cat in categorias[i:i+2]]
                for i in range(0, len(categorias), 2)
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Escolha a categoria do gasto ou escreva uma personalizada:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_categoria'
            context.user_data['navigation_stack'].append("awaiting_gasto_valor")
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 100).", reply_markup=reply_markup)
    elif state == 'awaiting_gasto_categoria':
        if update.message.text:
            context.user_data['gasto_categoria'] = update.message.text
            formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
            keyboard = [
                [InlineKeyboardButton(fp, callback_data=f"gasto_forma_{fp}") for fp in formas_pagamento[i:i+2]]
                for i in range(0, len(formas_pagamento), 2)
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Escolha a forma de pagamento:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_forma'
            context.user_data['navigation_stack'].append("awaiting_gasto_categoria")
        else:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Por favor, escreva uma categoria ou escolha uma das opções.", reply_markup=reply_markup)
    elif state == 'awaiting_entrada':
        try:
            parts = update.message.text.split(maxsplit=1)
            if len(parts) != 2:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("Formato inválido. Use: VALOR DESCRICAO (ex.: 100 Salário).", reply_markup=reply_markup)
                return
            valor = float(parts[0])
            if valor <= 0:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O valor deve ser positivo. Tente novamente.", reply_markup=reply_markup)
                return
            descricao = parts[1]
            data = datetime.now().strftime('%Y-%m-%d')
            salvar_entrada(usuario, valor, descricao, data)
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Entrada de R${valor:.2f} - {descricao} salva!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            await verificar_limite(update, usuario, mes, ano)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 100 Salário).", reply_markup=reply_markup)
    elif state == 'awaiting_gasto_fixo_valor':
        try:
            valor = float(update.message.text)
            if valor <= 0:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O valor deve ser positivo. Tente novamente.", reply_markup=reply_markup)
                return
            context.user_data['gasto_fixo_valor'] = valor
            periodicidade = context.user_data.get('gasto_fixo_periodicidade', 'MENSAL').lower()
            categorias = ["Alimentação", "Lazer", "Transporte", "Saúde", "Outros", "Escrever Categoria"]
            keyboard = [
                [InlineKeyboardButton(cat, callback_data=f"gasto_fixo_categoria_{cat}") for cat in categorias[i:i+2]]
                for i in range(0, len(categorias), 2)
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Escolha a categoria do gasto fixo {periodicidade} ou escreva uma personalizada:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_fixo_categoria'
            context.user_data['navigation_stack'].append("awaiting_gasto_fixo_valor")
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 100).", reply_markup=reply_markup)
    elif state == 'awaiting_gasto_fixo_categoria':
        if update.message.text:
            context.user_data['gasto_fixo_categoria'] = update.message.text
        else:
            # Se a categoria foi escolhida via botão (não texto), o valor será tratado em button_gasto
            return  # Deixa o button_gasto lidar com a escolha de categoria via botão
        formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
        keyboard = [
            [InlineKeyboardButton(fp, callback_data=f"gasto_fixo_forma_{fp}") for fp in formas_pagamento[i:i+2]]
            for i in range(0, len(formas_pagamento), 2)
        ]
        keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Escolha a forma de pagamento do gasto fixo:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_fixo_forma'
        context.user_data['navigation_stack'].append("awaiting_gasto_fixo_categoria")
    elif state == 'awaiting_gasto_fixo_forma':
        forma_pagamento = update.message.text  # Aqui o usuário pode escrever a forma, mas idealmente usa botões
        if forma_pagamento not in ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Forma de pagamento inválida. Escolha uma opção válida.", reply_markup=reply_markup)
            return
        valor = context.user_data.get('gasto_fixo_valor')
        categoria = context.user_data.get('gasto_fixo_categoria')
        periodicidade = context.user_data.get('gasto_fixo_periodicidade', 'MENSAL')
        data = datetime.now().strftime('%Y-%m-%d')
        try:
            usuario = str(update.message.chat.id)
            salvar_gasto(usuario, valor, f"{categoria} ({periodicidade})", forma_pagamento, data)
            msg = f"Gasto fixo de R${valor:.2f} na categoria '{categoria}' ({periodicidade}, {forma_pagamento}) salvo com sucesso!"
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(msg, reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('gasto_fixo_valor', None)
            context.user_data.pop('gasto_fixo_categoria', None)
            context.user_data.pop('gasto_fixo_periodicidade', None)
            await verificar_limite(update, usuario, mes, ano)
        except Exception as e:
            logger.error(f"Erro ao salvar o gasto fixo: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Erro ao salvar o gasto fixo: {str(e)}", reply_markup=reply_markup)
    elif state == 'awaiting_editar_dados_gasto':
        try:
            parts = update.message.text.split(maxsplit=3)
            valor = float(parts[0]) if len(parts) > 0 and parts[0] else None
            categoria = parts[1] if len(parts) > 1 and parts[1] else None
            forma_pagamento = parts[2] if len(parts) > 2 and parts[2] else None
            if valor is not None and valor <= 0:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O valor deve ser positivo.", reply_markup=reply_markup)
                return
            gasto_id = context.user_data['editar_id']
            editar_gasto(usuario, gasto_id, valor, categoria, forma_pagamento)
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Gasto ID {gasto_id} editado com sucesso!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('editar_id', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Dados inválidos. Use: VALOR CATEGORIA FORMA (ex.: 200 Alimentação Cartão).", reply_markup=reply_markup)
        except Exception:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Erro ao editar o gasto ou ID não encontrado.", reply_markup=reply_markup)
    elif state == 'awaiting_editar_dados_entrada':
        try:
            parts = update.message.text.split(maxsplit=2)
            valor = float(parts[0]) if len(parts) > 0 and parts[0] else None
            descricao = parts[1] if len(parts) > 1 and parts[1] else None
            if valor is not None and valor <= 0:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O valor deve ser positivo.", reply_markup=reply_markup)
                return
            entrada_id = context.user_data['editar_id']
            editar_entrada(usuario, entrada_id, valor, descricao)
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Entrada ID {entrada_id} editada com sucesso!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('editar_id', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Dados inválidos. Use: VALOR DESCRICAO (ex.: 200 Salário).", reply_markup=reply_markup)
        except Exception:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Erro ao editar a entrada ou ID não encontrado.", reply_markup=reply_markup)
    elif state == 'awaiting_definirlimite':
        try:
            limite = float(update.message.text)
            if limite <= 0:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("O limite deve ser positivo. Tente novamente.", reply_markup=reply_markup)
                return
            definir_limite(usuario, limite)
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(f"Limite de R${limite:.2f} definido com sucesso!", reply_markup=reply_markup)
            context.user_data.pop('state', None)
        except ValueError:
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Valor inválido. Insira um número (ex.: 1000).", reply_markup=reply_markup)

# Handler para botões de gasto
async def button_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "voltar":
        await handle_voltar(update, context)
        return

    if query.data == "gasto_normal":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR GASTO NORMAL", callback_data="gasto_normal_adicionar")],
            [InlineKeyboardButton("EDITAR GASTO NORMAL", callback_data="editar_gasto")],
            [InlineKeyboardButton("REMOVER GASTO NORMAL", callback_data="remover_gasto_normal")],
            [InlineKeyboardButton("DEFINIR LIMITE DE GASTO", callback_data="definir_limite")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Gasto Normal:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start_gasto")
    elif query.data == "gasto_fixo":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR GASTO FIXO", callback_data="gasto_fixo_adicionar")],
            [InlineKeyboardButton("EDITAR GASTO FIXO", callback_data="editar_gasto_fixo")],
            [InlineKeyboardButton("REMOVER GASTO FIXO", callback_data="remover_gasto_fixo")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Gasto Fixo:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start_gasto")
    elif query.data == "gasto_normal_adicionar":
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Por favor, insira o valor que você gastou (ex.: 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_valor'
        context.user_data['navigation_stack'].append("gasto_normal")
    elif query.data == "gasto_fixo_adicionar":
        keyboard = [
            [InlineKeyboardButton("DIÁRIO", callback_data="gasto_fixo_diario")],
            [InlineKeyboardButton("SEMANAL", callback_data="gasto_fixo_semanal")],
            [InlineKeyboardButton("MENSAL", callback_data="gasto_fixo_mensal")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha a periodicidade do gasto fixo:", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("gasto_fixo")
    elif query.data.startswith("gasto_fixo_"):
        periodicidade = query.data[len("gasto_fixo_"):]
        context.user_data['gasto_fixo_periodicidade'] = periodicidade.upper()
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Insira o valor do gasto fixo {periodicidade.lower()} (ex.: 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_fixo_valor'
        context.user_data['navigation_stack'].append("awaiting_gasto_fixo_periodicidade")
    elif query.data.startswith("gasto_fixo_categoria_"):
        categoria = query.data[len("gasto_fixo_categoria_"):]
        if categoria == "Escrever Categoria":
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Por favor, escreva a categoria personalizada para o gasto fixo:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_fixo_categoria'
        else:
            context.user_data['gasto_fixo_categoria'] = categoria
            formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
            keyboard = [
                [InlineKeyboardButton(fp, callback_data=f"gasto_fixo_forma_{fp}") for fp in formas_pagamento[i:i+2]]
                for i in range(0, len(formas_pagamento), 2)
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Escolha a forma de pagamento do gasto fixo:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_fixo_forma'
            context.user_data['navigation_stack'].append("awaiting_gasto_fixo_categoria")
    elif query.data.startswith("gasto_categoria_"):
        categoria = query.data[len("gasto_categoria_"):]
        if categoria == "Escrever Categoria":
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Por favor, escreva a categoria personalizada:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_categoria'
        else:
            context.user_data['gasto_categoria'] = categoria
            formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
            keyboard = [
                [InlineKeyboardButton(fp, callback_data=f"gasto_forma_{fp}") for fp in formas_pagamento[i:i+2]]
                for i in range(0, len(formas_pagamento), 2)
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Escolha a forma de pagamento:", reply_markup=reply_markup)
            context.user_data['state'] = 'awaiting_gasto_forma'
            context.user_data['navigation_stack'].append("awaiting_gasto_categoria")
    elif query.data.startswith("gasto_forma_"):
        forma_pagamento = query.data[len("gasto_forma_"):]
        valor = context.user_data.get('gasto_valor')
        categoria = context.user_data.get('gasto_categoria')
        data = datetime.now().strftime('%Y-%m-%d')
        try:
            usuario = str(query.message.chat.id)
            salvar_gasto(usuario, valor, categoria, forma_pagamento, data)
            msg = f"Gasto normal de R${valor:.2f} na categoria '{categoria}' ({forma_pagamento}) salvo com sucesso!"
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('gasto_valor', None)
            context.user_data.pop('gasto_categoria', None)
            mes = datetime.now().month
            ano = datetime.now().year
            await verificar_limite(query, usuario, mes, ano)
        except Exception as e:
            logger.error(f"Erro ao salvar o gasto normal: {str(e)} - Dados: usuario={usuario}, valor={valor}, categoria={categoria}, forma_pagamento={forma_pagamento}, data={data}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Erro ao salvar o gasto normal: {str(e)}", reply_markup=reply_markup)
    elif query.data.startswith("gasto_fixo_forma_"):
        forma_pagamento = query.data[len("gasto_fixo_forma_"):]
        valor = context.user_data.get('gasto_fixo_valor')
        categoria = context.user_data.get('gasto_fixo_categoria')
        periodicidade = context.user_data.get('gasto_fixo_periodicidade', 'MENSAL')
        data = datetime.now().strftime('%Y-%m-%d')
        try:
            usuario = str(query.message.chat.id)
            salvar_gasto(usuario, valor, f"{categoria} ({periodicidade})", forma_pagamento, data)
            msg = f"Gasto fixo de R${valor:.2f} na categoria '{categoria}' ({periodicidade}, {forma_pagamento}) salvo com sucesso!"
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('state', None)
            context.user_data.pop('gasto_fixo_valor', None)
            context.user_data.pop('gasto_fixo_categoria', None)
            context.user_data.pop('gasto_fixo_periodicidade', None)
            mes = datetime.now().month
            ano = datetime.now().year
            await verificar_limite(query, usuario, mes, ano)
        except Exception as e:
            logger.error(f"Erro ao salvar o gasto fixo: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Erro ao salvar o gasto fixo: {str(e)}", reply_markup=reply_markup)
    elif query.data == "definir_limite":
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Por favor, insira o valor do limite (ex.: 1000):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_definirlimite'
        context.user_data['navigation_stack'].append("gasto_normal")

# Handler para botões de entrada
async def button_entrada(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "entrada_adicionar":
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Por favor, insira o valor da entrada (ex.: 100) e a descrição (ex.: 'Salário'):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_entrada'
        context.user_data['navigation_stack'].append("start_entrada")

# Handler para botões de edição e remoção
async def button_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    usuario = str(query.message.chat.id)

    if query.data == "voltar":
        await handle_voltar(update, context)
        return

    if query.data == "editar_gasto":  # Para Gasto Normal
        try:
            gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
            gastos_normais = [g for g in gastos if not any(p in g[2] for p in ["(DIÁRIO)", "(SEMANAL)", "(MENSAL)"])]
            if not gastos_normais:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum gasto normal registrado para editar.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}", callback_data=f"editar_gasto_select_{gasto[0]}")]
                for gasto in gastos_normais
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o gasto normal para editar:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("gasto_normal")
        except Exception as e:
            logger.error(f"Erro ao carregar gastos para edição: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os gastos para edição.", reply_markup=reply_markup)
    elif query.data == "editar_gasto_fixo":
        try:
            gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
            gastos_fixos = [g for g in gastos if any(p in g[2] for p in ["(DIÁRIO)", "(SEMANAL)", "(MENSAL)"])]
            if not gastos_fixos:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum gasto fixo registrado para editar.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}", callback_data=f"editar_gasto_select_{gasto[0]}")]
                for gasto in gastos_fixos
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o gasto fixo para editar:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("gasto_fixo")
        except Exception as e:
            logger.error(f"Erro ao carregar gastos fixos para edição: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os gastos fixos para edição.", reply_markup=reply_markup)
    elif query.data == "editar_entrada":
        try:
            entradas = listar_entradas_mensais(usuario, datetime.now().month, datetime.now().year)
            if not entradas:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum valor recebido registrado para editar.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {entrada[0]} - R${entrada[1]:.2f} - {entrada[2]}", callback_data=f"editar_entrada_select_{entrada[0]}")]
                for entrada in entradas
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o valor recebido para editar:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("start_entrada")
        except Exception as e:
            logger.error(f"Erro ao carregar entradas para edição: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os valores recebidos para edição.", reply_markup=reply_markup)
    elif query.data.startswith("editar_gasto_select_"):
        gasto_id = int(query.data[len("editar_gasto_select_"):])
        context.user_data['editar_id'] = gasto_id
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Insira o novo valor (opcional), categoria (opcional) e forma de pagamento (opcional), separados por espaço (ex.: 200 Alimentação Cartão):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_editar_dados_gasto'
        context.user_data['navigation_stack'].append("editar_gasto")
    elif query.data.startswith("editar_entrada_select_"):
        entrada_id = int(query.data[len("editar_entrada_select_"):])
        context.user_data['editar_id'] = entrada_id
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Insira o novo valor (opcional) e descrição (opcional), separados por espaço (ex.: 200 Salário):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_editar_dados_entrada'
        context.user_data['navigation_stack'].append("editar_entrada")
    elif query.data == "remover_gasto_normal":
        try:
            gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
            gastos_normais = [g for g in gastos if not any(p in g[2] for p in ["(DIÁRIO)", "(SEMANAL)", "(MENSAL)"])]
            if not gastos_normais:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum gasto normal registrado para remover.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}", callback_data=f"remover_gasto_normal_select_{gasto[0]}")]
                for gasto in gastos_normais
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o gasto normal para remover:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("gasto_normal")
        except Exception as e:
            logger.error(f"Erro ao carregar gastos normais para remoção: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os gastos normais para remoção.", reply_markup=reply_markup)
    elif query.data == "remover_gasto_fixo":
        try:
            gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
            gastos_fixos = [g for g in gastos if any(p in g[2] for p in ["(DIÁRIO)", "(SEMANAL)", "(MENSAL)"])]
            if not gastos_fixos:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum gasto fixo registrado para remover.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}", callback_data=f"remover_gasto_fixo_select_{gasto[0]}")]
                for gasto in gastos_fixos
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o gasto fixo para remover:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("gasto_fixo")
        except Exception as e:
            logger.error(f"Erro ao carregar gastos fixos para remoção: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os gastos fixos para remoção.", reply_markup=reply_markup)
    elif query.data == "remover_entrada":
        try:
            entradas = listar_entradas_mensais(usuario, datetime.now().month, datetime.now().year)
            if not entradas:
                keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await query.message.edit_text("Nenhum valor recebido registrado para remover.", reply_markup=reply_markup)
                return
            keyboard = [
                [InlineKeyboardButton(f"ID {entrada[0]} - R${entrada[1]:.2f} - {entrada[2]}", callback_data=f"remover_entrada_select_{entrada[0]}")]
                for entrada in entradas
            ]
            keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Selecione o valor recebido para remover:", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("start_entrada")
        except Exception as e:
            logger.error(f"Erro ao carregar entradas para remoção: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao carregar os valores recebidos para remoção.", reply_markup=reply_markup)
    elif query.data.startswith("remover_gasto_normal_select_"):
        gasto_id = query.data[len("remover_gasto_normal_select_"):]
        context.user_data['remover_id'] = gasto_id
        context.user_data['remover_tipo'] = 'gasto_normal'
        gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
        gasto = next((g for g in gastos if str(g[0]) == gasto_id), None)
        if gasto:
            opcao = f"o gasto normal ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}"
            keyboard = [
                [
                    InlineKeyboardButton("SIM", callback_data="confirmar_remover_sim"),
                    InlineKeyboardButton("NÃO", callback_data="confirmar_remover_nao")
                ],
                [InlineKeyboardButton("Voltar", callback_data="voltar")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Você tem certeza que deseja remover {opcao}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remover_gasto_normal")
    elif query.data.startswith("remover_gasto_fixo_select_"):
        gasto_id = query.data[len("remover_gasto_fixo_select_"):]
        context.user_data['remover_id'] = gasto_id
        context.user_data['remover_tipo'] = 'gasto_fixo'
        gastos = listar_gastos_mensais(usuario, datetime.now().month, datetime.now().year)
        gasto = next((g for g in gastos if str(g[0]) == gasto_id), None)
        if gasto:
            opcao = f"o gasto fixo ID {gasto[0]} - R${gasto[1]:.2f} - {gasto[2]} - {gasto[3]}"
            keyboard = [
                [
                    InlineKeyboardButton("SIM", callback_data="confirmar_remover_sim"),
                    InlineKeyboardButton("NÃO", callback_data="confirmar_remover_nao")
                ],
                [InlineKeyboardButton("Voltar", callback_data="voltar")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Você tem certeza que deseja remover {opcao}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remover_gasto_fixo")
    elif query.data.startswith("remover_entrada_select_"):
        entrada_id = query.data[len("remover_entrada_select_"):]
        context.user_data['remover_id'] = entrada_id
        context.user_data['remover_tipo'] = 'entrada'
        entradas = listar_entradas_mensais(usuario, datetime.now().month, datetime.now().year)
        entrada = next((e for e in entradas if str(e[0]) == entrada_id), None)
        if entrada:
            opcao = f"a entrada ID {entrada[0]} - R${entrada[1]:.2f} - {entrada[2]}"
            keyboard = [
                [
                    InlineKeyboardButton("SIM", callback_data="confirmar_remover_sim"),
                    InlineKeyboardButton("NÃO", callback_data="confirmar_remover_nao")
                ],
                [InlineKeyboardButton("Voltar", callback_data="voltar")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(f"Você tem certeza que deseja remover {opcao}?", reply_markup=reply_markup)
            context.user_data['navigation_stack'].append("remover_entrada")
    elif query.data == "confirmar_remover_sim":
        try:
            remover_id = context.user_data.get('remover_id')
            remover_tipo = context.user_data.get('remover_tipo')
            if remover_tipo == 'gasto_normal':
                remover_gasto(usuario, int(remover_id))
                msg = f"Gasto normal ID {remover_id} removido com sucesso!"
            elif remover_tipo == 'gasto_fixo':
                remover_gasto(usuario, int(remover_id))
                msg = f"Gasto fixo ID {remover_id} removido com sucesso!"
            elif remover_tipo == 'entrada':
                remover_entrada(usuario, int(remover_id))
                msg = f"Entrada ID {remover_id} removida com sucesso!"
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text(msg, reply_markup=reply_markup)
            context.user_data.pop('remover_id', None)
            context.user_data.pop('remover_tipo', None)
        except Exception as e:
            logger.error(f"Erro ao remover: {str(e)}")
            keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.edit_text("Erro ao remover o item.", reply_markup=reply_markup)
    elif query.data == "confirmar_remover_nao":
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Remoção cancelada.", reply_markup=reply_markup)

# Função para lidar com o botão "Voltar"
async def handle_voltar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not context.user_data.get('navigation_stack') or len(context.user_data['navigation_stack']) == 0:
        await start(query, context)  # Sempre volta ao menu inicial se a pilha estiver vazia
        context.user_data['state'] = None  # Limpa o estado
        return

    previous_state = context.user_data['navigation_stack'].pop()

    if previous_state == "start":
        await start(query, context)
    elif previous_state == "start_gasto":
        keyboard = [
            [InlineKeyboardButton("GASTO NORMAL", callback_data="gasto_normal")],
            [InlineKeyboardButton("GASTO FIXO", callback_data="gasto_fixo")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha o tipo de gasto:", reply_markup=reply_markup)
    elif previous_state == "start_entrada":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR VALOR RECEBIDO", callback_data="entrada_adicionar")],
            [InlineKeyboardButton("EDITAR VALOR RECEBIDO", callback_data="editar_entrada")],
            [InlineKeyboardButton("REMOVER VALOR RECEBIDO", callback_data="remover_entrada")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Valor Recebido:", reply_markup=reply_markup)
    elif previous_state == "gasto_normal":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR GASTO NORMAL", callback_data="gasto_normal_adicionar")],
            [InlineKeyboardButton("EDITAR GASTO NORMAL", callback_data="editar_gasto")],
            [InlineKeyboardButton("REMOVER GASTO NORMAL", callback_data="remover_gasto_normal")],
            [InlineKeyboardButton("DEFINIR LIMITE DE GASTO", callback_data="definir_limite")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Gasto Normal:", reply_markup=reply_markup)
    elif previous_state == "gasto_fixo":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR GASTO FIXO", callback_data="gasto_fixo_adicionar")],
            [InlineKeyboardButton("EDITAR GASTO FIXO", callback_data="editar_gasto_fixo")],
            [InlineKeyboardButton("REMOVER GASTO FIXO", callback_data="remover_gasto_fixo")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Gasto Fixo:", reply_markup=reply_markup)
    elif previous_state == "editar_gasto":
        await button_action(Update(0, query.message), context, "editar_gasto")
    elif previous_state == "editar_gasto_fixo":
        await button_action(Update(0, query.message), context, "editar_gasto_fixo")
    elif previous_state == "editar_entrada":
        await button_action(Update(0, query.message), context, "editar_entrada")
    elif previous_state == "remover_gasto_normal":
        await button_action(Update(0, query.message), context, "remover_gasto_normal")
    elif previous_state == "remover_gasto_fixo":
        await button_action(Update(0, query.message), context, "remover_gasto_fixo")
    elif previous_state == "remover_entrada":
        await button_action(Update(0, query.message), context, "remover_entrada")
    elif previous_state == "awaiting_gasto_valor":
        keyboard = [
            [InlineKeyboardButton("ADICIONAR GASTO NORMAL", callback_data="gasto_normal_adicionar")],
            [InlineKeyboardButton("EDITAR GASTO NORMAL", callback_data="editar_gasto")],
            [InlineKeyboardButton("REMOVER GASTO NORMAL", callback_data="remover_gasto_normal")],
            [InlineKeyboardButton("DEFINIR LIMITE DE GASTO", callback_data="definir_limite")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha uma ação para Gasto Normal:", reply_markup=reply_markup)
        context.user_data['state'] = None
    elif previous_state == "awaiting_gasto_categoria":
        categorias = ["Alimentação", "Lazer", "Transporte", "Saúde", "Outros", "Escrever Categoria"]
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"gasto_categoria_{cat}") for cat in categorias[i:i+2]]
            for i in range(0, len(categorias), 2)
        ]
        keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha a categoria do gasto ou escreva uma personalizada:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_categoria'
    elif previous_state == "awaiting_gasto_fixo_periodicidade":
        keyboard = [
            [InlineKeyboardButton("DIÁRIO", callback_data="gasto_fixo_diario")],
            [InlineKeyboardButton("SEMANAL", callback_data="gasto_fixo_semanal")],
            [InlineKeyboardButton("MENSAL", callback_data="gasto_fixo_mensal")],
            [InlineKeyboardButton("Voltar", callback_data="voltar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha a periodicidade do gasto fixo:", reply_markup=reply_markup)
    elif previous_state == "awaiting_gasto_fixo_valor":
        periodicidade = context.user_data.get('gasto_fixo_periodicidade', '').lower()
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Insira o valor do gasto fixo {periodicidade} (ex.: 100):", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_fixo_valor'
    elif previous_state == "awaiting_gasto_fixo_categoria":
        categorias = ["Alimentação", "Lazer", "Transporte", "Saúde", "Outros", "Escrever Categoria"]
        keyboard = [
            [InlineKeyboardButton(cat, callback_data=f"gasto_fixo_categoria_{cat}") for cat in categorias[i:i+2]]
            for i in range(0, len(categorias), 2)
        ]
        keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha a categoria do gasto fixo ou escreva uma personalizada:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_fixo_categoria'
    elif previous_state == "awaiting_gasto_fixo_forma":
        formas_pagamento = ["Cartão de Crédito", "Cartão de Débito", "Pix", "Dinheiro"]
        keyboard = [
            [InlineKeyboardButton(fp, callback_data=f"gasto_fixo_forma_{fp}") for fp in formas_pagamento[i:i+2]]
            for i in range(0, len(formas_pagamento), 2)
        ]
        keyboard.append([InlineKeyboardButton("Voltar", callback_data="voltar")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Escolha a forma de pagamento do gasto fixo:", reply_markup=reply_markup)
        context.user_data['state'] = 'awaiting_gasto_fixo_forma'
    elif previous_state == "start_resumo":
        await start(query, context)
    elif previous_state == "start_excel":
        mes = context.user_data.get('excel_mes', datetime.now().month)
        ano = context.user_data.get('excel_ano', datetime.now().year)
        await mostrar_selecao_excel(update, context, mes, ano)

# Comando /resumo
async def resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mes = datetime.now().month
    ano = datetime.now().year
    context.user_data['resumo_mes'] = mes
    context.user_data['resumo_ano'] = ano
    context.user_data['navigation_stack'].append("start")
    await mostrar_resumo(update, context, mes, ano)

# Função para mostrar o resumo com botões
async def mostrar_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE, mes, ano):
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
                InlineKeyboardButton("⬅️ Mês Anterior", callback_data="resumo_prev"),
                InlineKeyboardButton("Voltar", callback_data="voltar"),
                InlineKeyboardButton("Mês Próximo ➡️", callback_data="resumo_next")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if update.message:
            await update.message.reply_text(resumo, reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text(resumo, reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Erro ao gerar resumo: {e}")
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if update.message:
            await update.message.reply_text("Erro ao gerar o resumo.", reply_markup=reply_markup)
        else:
            await update.callback_query.message.edit_text("Erro ao gerar o resumo.", reply_markup=reply_markup)

# Handler para botões de navegação do /resumo
async def button_resumo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "voltar":
        await handle_voltar(update, context)
        return

    mes = context.user_data.get('resumo_mes', datetime.now().month)
    ano = context.user_data.get('resumo_ano', datetime.now().year)

    if query.data == "resumo_prev":
        mes -= 1
        if mes < 1:
            mes = 12
            ano -= 1
    elif query.data == "resumo_next":
        mes += 1
        if mes > 12:
            mes = 1
            ano += 1

    context.user_data['resumo_mes'] = mes
    context.user_data['resumo_ano'] = ano

    await mostrar_resumo(update, context, mes, ano)

# Comando /powerbi
POWER_BI_BASE_LINK = "https://app.powerbi.com/links/vv8SkpDKaL?filter=public%20gastos/usuario%20eq%20'"
async def send_powerbi_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        query = update.callback_query
        user_id = str(query.from_user.id)
        filtered_link = f"{POWER_BI_BASE_LINK}'{user_id}'"
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Veja seu relatório (faça login no Power BI): {filtered_link}", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"Erro ao gerar link do Power BI: {str(e)}")
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text("Erro ao gerar o link do Power BI.", reply_markup=reply_markup)

# Função para gerar e enviar a planilha Excel com gráficos e resumo
async def gerar_planilha_excel(update: Update, context: ContextTypes.DEFAULT_TYPE, mes, ano):
    query = update.callback_query
    await query.answer()

    usuario = str(query.message.chat.id)
    try:
        gastos = listar_gastos_mensais(usuario, mes, ano)
        entradas = listar_entradas_mensais(usuario, mes, ano)
        gastos_resumo = obter_gastos_mensais(usuario, mes, ano)
        total_entradas = obter_entradas_mensais(usuario, mes, ano)
        total_gastos = obter_total_gastos_mensais(usuario, mes, ano)

        if gastos:
            df_gastos = pd.DataFrame(gastos, columns=['ID', 'Valor', 'Categoria', 'Forma de Pagamento', 'Data'])
        else:
            df_gastos = pd.DataFrame(columns=['ID', 'Valor', 'Categoria', 'Forma de Pagamento', 'Data'])

        if entradas:
            df_entradas = pd.DataFrame(entradas, columns=['ID', 'Valor', 'Descrição', 'Data'])
        else:
            df_entradas = pd.DataFrame(columns=['ID', 'Valor', 'Descrição', 'Data'])

        if gastos_resumo:
            df_gastos_resumo = pd.DataFrame(gastos_resumo, columns=['Categoria', 'Total'])
        else:
            df_gastos_resumo = pd.DataFrame(columns=['Categoria', 'Total'])

        df_resumo = pd.DataFrame({
            'Descrição': ['Total de Gastos', 'Total de Entradas', 'Saldo'],
            'Valor': [total_gastos, total_entradas, total_entradas - total_gastos]
        })

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df_gastos.to_excel(writer, sheet_name='Gastos', index=False)
            df_entradas.to_excel(writer, sheet_name='Entradas', index=False)
            df_gastos_resumo.to_excel(writer, sheet_name='Gastos por Categoria', index=False)
            df_resumo.to_excel(writer, sheet_name='Resumo', index=False)

            workbook = writer.book
            worksheet = workbook['Gastos por Categoria']

            chart = BarChart()
            chart.title = f"Gastos por Categoria - {mes:02d}/{ano}"
            chart.x_axis.title = "Categoria"
            chart.y_axis.title = "Valor (R$)"

            data = Reference(worksheet, min_col=2, min_row=1, max_row=len(gastos_resumo) + 1, max_col=2)
            categories = Reference(worksheet, min_col=1, min_row=2, max_row=len(gastos_resumo) + 1)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(categories)

            chart.datalabels = DataLabelList()
            chart.datalabels.showVal = True

            worksheet.add_chart(chart, "D2")

        output.seek(0)

        await query.message.reply_document(
            document=output,
            filename=f"relatorio_financeiro_{usuario}_{mes:02d}_{ano}.xlsx",
            caption=f"Planilha de {mes:02d}/{ano} gerada com sucesso!"
        )
        output.close()

        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Planilha gerada com sucesso!", reply_markup=reply_markup)
        context.user_data['navigation_stack'].append("start")

    except Exception as e:
        logger.error(f"Erro ao gerar planilha Excel: {e}")
        keyboard = [[InlineKeyboardButton("Voltar", callback_data="voltar")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.edit_text(f"Erro ao gerar a planilha: {str(e)}", reply_markup=reply_markup)

# Função principal assíncrona com webhooks
async def main():
    try:
        application = Application.builder().token("7585573573:AAHC-v1EwpHHiBCJ5JSINejrMTdKJRIbqr4").build()

        # Adicionando os handlers
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CallbackQueryHandler(button_start, pattern="^start_"))
        application.add_handler(CallbackQueryHandler(button_gasto, pattern="^(gasto_|definir_limite|voltar)"))
        application.add_handler(CallbackQueryHandler(button_entrada, pattern="^entrada_"))
        application.add_handler(CallbackQueryHandler(button_action, pattern="^(editar_|remover_|confirmar_|voltar)"))
        application.add_handler(CallbackQueryHandler(button_resumo, pattern="^(resumo_|voltar)"))
        application.add_handler(CallbackQueryHandler(button_excel, pattern="^excel_"))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))

        # Iniciando o bot com polling
        await application.run_polling(allowed_updates=Update.ALL)
    except Exception as e:
        logger.error(f"Erro ao iniciar o bot: {e}")
        raise
    finally:
        # Fechar a aplicação adequadamente (se necessário)
        await application.shutdown()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
