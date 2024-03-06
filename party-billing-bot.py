import datetime
import logging
import os
import re
from enum import Enum

from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (CommandHandler, ConversationHandler, Filters,
                          MessageHandler, Updater)

logger = logging.getLogger(__file__)


class Status(Enum):
    GET_ITEM = 0
    GET_COST = 1
    GET_CHECK = 2


def start(update, context):
    logger.debug(f'Enter cmd_start: {update=}')

    user_id = update.message.from_user.id
    username = update.message.from_user['username']
    firstname = update.message.from_user['first_name']
    lastname = update.message.from_user['last_name']

    orders = context.bot_data['party']['orders']
    orders[(user_id, username, firstname, lastname)] = []

    date = context.bot_data['party']['data'].get('date', '')
    place = context.bot_data['party']['data'].get('place', '')
    text = 'Привет!\n' \
           'Я учитываю заказы нашей компании на вечеринке ' \
           f'{date} в {place}\nНапиши мне примерное название того что ты ' \
           'хочешь заказать'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return Status.GET_ITEM


def get_item(update, context):
    logger.debug(f'Enter save_item: {update=}')

    item = update.message.text
    context.user_data['item'] = item
    text = f'Ты заказал:\n{item}\nНапиши стоимость, ' \
           'чтобы мы потом правильно раделили итоговый счет на всех.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return Status.GET_COST


def get_cost(update, context):
    logger.debug(f'Enter save_cost: {update=}')

    if re.search(r'[^0-9]', update.message.text):
        text = 'Введите просто цифры! Без посторонних символов!'
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, )
        return Status.GET_COST
    item = context.user_data['item']
    cost = update.message.text
    context.user_data['cost'] = int(cost)
    text = f'Давай проверим:\nТы заказал: {item}\nСтоимость:\n{cost}руб.\n' \
           'Нажми "Да", если все верно, или "Нет", если хочешь прислать ' \
           'заказ заново'
    keyboard = [['Да', 'Нет'],]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup, )
    return Status.GET_CHECK


def confirm_choice(update, context):
    logger.debug(f'Enter confirm_choice: {update=}')

    cost = context.user_data['cost']
    item = context.user_data['item']
    text = f'Спасибо, что ты заказал:\n{item}\nСтоимость:\n{cost}\n' \
           'Я записал заказ в общий список и учту его при разделе счета.\n' \
           'Если захочешь добавить что-то еще, то опять присылай название.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    user_id = update.message.from_user.id
    username = update.message.from_user['username']
    firstname = update.message.from_user['first_name']
    lastname = update.message.from_user['last_name']

    orders = context.bot_data['party']['orders']
    user_orders = orders.get((user_id, username, firstname, lastname), [])
    user_orders.append((item, cost))

    summary_name = f'{firstname} ' if firstname else ''
    summary_name += f'{lastname}' if lastname else ''
    summary_name += f'(@{username})' if username else ''
    text = f'Пользователь {summary_name}:\n' \
           f'{item} - {cost}руб.'
    context.bot.send_message(chat_id=context.bot_data['admin_chat_id'],
                             text=text, )
    return Status.GET_ITEM


def decline_choice(update, context):
    logger.debug(f'Enter decline_choice: {update=}')

    text = 'Ок. Отменяем. Попробуй ввести название заново.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return Status.GET_ITEM


def adm_total(update, context):
    orders = context.bot_data['party']['orders']
    total = 0
    text = ''
    for order in orders:
        _, username, firstname, lastname = order
        summary_name = f'{firstname} ' if firstname else ''
        summary_name += f'{lastname}' if lastname else ''
        summary_name += f'(@{username})' if username else ''
        text += f'Пользователь {summary_name}:\n'
        items = orders[order]
        subtotal = 0
        for (item, cost) in items:
            text += f'\t{item} - {cost}руб.\n'
            subtotal += cost
        text += f'User total: {subtotal}руб.'
        total += subtotal
        update.message.reply_text(text)
    update.message.reply(f'Общая сумма за вечер: {total}руб.')


if __name__ == '__main__':
    load_dotenv()
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    loglevel = os.getenv('LOG_LEVEL', default='INFO')
    logger.debug('Start logging')

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher

    admin_chat_id = int(os.getenv('TG_ADMIN_CHAT'))
    dispatcher.bot_data['admin_chat_id'] = admin_chat_id
    dispatcher.bot_data['party'] = {
        'data': {
            'date': '09 Марта 2024г.',
            'place': 'баре Freedom',
        },
        'orders': {},
    }
    user_conversation = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            Status.GET_ITEM: [
                MessageHandler(Filters.text, get_item),
            ],
            Status.GET_COST: [
                MessageHandler(Filters.text, get_cost),
            ],
            Status.GET_CHECK: [
                MessageHandler(Filters.text('Да'), confirm_choice),
                MessageHandler(Filters.text('Нет'), decline_choice),
            ],
        },
        fallbacks=[],
        name='party_billing_conversation',
        # persistent=True,
    )
    dispatcher.add_handler(
        CommandHandler('total', adm_total, Filters.chat(admin_chat_id))
    )
    dispatcher.add_handler(user_conversation)
    updater.start_polling()
    updater.idle()
