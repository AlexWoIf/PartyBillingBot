import logging
import os
import re
from enum import Enum

from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (CallbackQueryHandler, CommandHandler,
                          ConversationHandler, Filters, MessageHandler,
                          Updater)

logger = logging.getLogger(__file__)


class ConversationStatus(Enum):
    GET_ITEM = 0
    GET_COST = 1
    GET_CHECK = 2
    ADM_COMMANDS = 100


def help(update, context):
    logger.debug(f'Enter help: {update=}')

    date = context.bot_data['party'].get('date', '')
    place = context.bot_data['party'].get('place', '')
    text = 'Привет!\n' \
           'Я учитываю заказы нашей компании на вечеринке ' \
           f'{date} в {place}\nЕсли ты участник этой вечеринки, то пришли ' \
           'комманду /start'
    update.message.reply_text(text)


def adm_help(update, context):
    logger.debug(f'Enter adm_help: {update=}')

    text = 'Привет!\n' \
           'Ты находишься в административном канале где происходит ' \
           'управление ботом.\n Бот выполняет следующие команды:\n' \
           '/startparty - запускает прием заказов на вечеринке\n' \
           '/closeparty - останавливает прием заказов и рассылает счет всем ' \
           'участникам, у кого он не погашен\n' \
           '/total - выводит информацию о текущем счете всех участников\n' \
           '/party - выводит информацию о текущей вечеринке'
    update.message.reply_text(text)
    return ConversationStatus.ADM_COMMANDS


def start(update, context):
    logger.debug(f'Enter cmd_start: {update=}')

    user_id = update.message.from_user.id
    username = update.message.from_user['username']
    firstname = update.message.from_user['first_name']
    lastname = update.message.from_user['last_name']

    guests = context.bot_data['party']['guests']
    guests[user_id] = {'name': (username, firstname, lastname),
                       'bill_sent': False,
                       'bill_payd': False,
                       'orders': [], }

    date = context.bot_data['party'].get('date', '')
    place = context.bot_data['party'].get('place', '')
    text = 'Отлично, что ты решил к нам присоединиться!\n' \
           f'Я учитываю заказы нашей компании {date} в {place}\n' \
           'Присылай мне сообщение каждый раз, когда ты делаешь заказ, и в ' \
           'конце вечера я пришлю тебе твой счет.\n' \
           'Напиши мне примерное название того что ты хочешь заказать:'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return ConversationStatus.GET_ITEM


def get_item(update, context):
    logger.debug(f'Enter save_item: {update=}')

    item = update.message.text
    context.user_data['item'] = item
    text = f'Ты заказал:\n{item}\nНапиши стоимость, ' \
           'чтобы мы потом правильно разделили итоговый счет на всех.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return ConversationStatus.GET_COST


def get_cost(update, context):
    logger.debug(f'Enter save_cost: {update=}')

    if re.search(r'[^0-9]', update.message.text):
        text = 'Введите просто цифры! Без посторонних символов!'
        context.bot.send_message(chat_id=update.effective_chat.id, text=text, )
        return ConversationStatus.GET_COST
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
    return ConversationStatus.GET_CHECK


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

    guests = context.bot_data['party']['guests']
    user = guests.get(user_id)
    user['orders'].append((item, cost))

    summary_name = f'{firstname} ' if firstname else ''
    summary_name += f'{lastname}' if lastname else ''
    summary_name += f'(@{username})' if username else ''
    text = f'Пользователь {summary_name}:\n' \
           f'{item} - {cost}руб.'
    context.bot.send_message(chat_id=context.bot_data['admin_chat_id'],
                             text=text, )
    return ConversationStatus.GET_ITEM


def decline_choice(update, context):
    logger.debug(f'Enter decline_choice: {update=}')

    text = 'Ок. Отменяем. Попробуй ввести название заново.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return ConversationStatus.GET_ITEM


def adm_total(update, context):
    guests = context.bot_data['party']['guests']
    total = 0
    for user_id, guest in guests.items():
        text = ''
        username, firstname, lastname = guest['name']
        summary_name = f'{firstname} ' if firstname else ''
        summary_name += f'{lastname}' if lastname else ''
        summary_name += f'(@{username})' if username else ''
        text += f'Гость {summary_name}:\n'
        items = guest['orders']
        subtotal = 0
        for (item, cost) in items:
            text += f'\t{item} - {cost}руб.\n'
            subtotal += cost
        text += f'User total: {subtotal}руб.\n'
        total += subtotal
        negate_payd = '' if guest['bill_payd'] else 'не '
        text += f'Счет {negate_payd}оплачен.\n'
        if not guest['bill_payd']:
            negate_sent = '' if guest['bill_sent'] else 'не '
            text += f'Счет {negate_sent}отправлен.\n'
        keyboard = [
            [InlineKeyboardButton('✉ Отправить счет 🧾',
                                  callback_data=f'sendbill:{user_id}')],
            [InlineKeyboardButton('✅ Отметить оплату 💰',
                                  callback_data=f'closebill:{user_id}')],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, reply_markup=reply_markup)
    update.message.reply_text(f'Общая сумма за вечер: {total}руб.')


def adm_close(update, context):
    context.bot_data['party']['status'] = 'closed'
    guests = context.bot_data['party']['guests']
    total = 0
    for user_id, guest in guests.items():
        text = ''
        username, firstname, lastname = guest['name']
        summary_name = f'{firstname} ' if firstname else ''
        summary_name += f'{lastname}' if lastname else ''
        summary_name += f'(@{username})' if username else ''
        text += f'Гость {summary_name}:\n'
        items = guest['orders']
        subtotal = 0
        for (item, cost) in items:
            text += f'\t{item} - {cost}руб.\n'
            subtotal += cost
        text += f'User total: {subtotal}руб.\n'
        total += subtotal
        negate_payd = '' if guest['bill_payd'] else 'не '
        text += f'Счет {negate_payd}оплачен.\n'
        reply_markup = None
        if not guest['bill_payd']:
            text += 'Счет отправлен.\n'
            context.bot.send_message(chat_id=user_id, text=text)
            keyboard = [
                [InlineKeyboardButton('✉ Отправить счет 🧾',
                                      callback_data=f'sendbill:{user_id}')],
                [InlineKeyboardButton('✅ Отметить оплату 💰',
                                      callback_data=f'closebill:{user_id}')],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text(text, reply_markup=reply_markup)
    update.message.reply_text(f'Общая сумма за вечер: {total}руб.')


def send_bill(update, context):
    user_id = int(update.callback_query.data.split(':')[1])
    guest = context.bot_data['party']['guests'][user_id]
    guest['bill_sent'] = True
    text = re.sub(r'не отправлен', r'отправлен',
                  update.callback_query.message.text)
    context.bot.send_message(chat_id=user_id, text=text)
    update.callback_query.edit_message_text(text)


def close_bill(update, context):
    user_id = int(update.callback_query.data.split(':')[1])
    guest = context.bot_data['party']['guests'][user_id]
    guest['bill_payd'] = True
    text = re.sub(r'не оплачен', r'оплачен',
                  update.callback_query.message.text)
    update.callback_query.edit_message_text(text, reply_markup=None)


if __name__ == '__main__':
    load_dotenv()
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    loglevel = os.getenv('LOG_LEVEL', default='INFO')
    logging.basicConfig(level=loglevel,
                        format="%(asctime)s %(levelname)s %(message)s", )
    logger.debug('Start logging')

    updater = Updater(tg_token)
    dispatcher = updater.dispatcher

    admin_chat_id = int(os.getenv('TG_ADMIN_CHAT'))
    dispatcher.bot_data['admin_chat_id'] = admin_chat_id
    dispatcher.bot_data['party'] = {
        'date': '09 Марта 2024г.',
        'place': 'баре Freedom',
        'status': 'in progress',
        'guests': {},
    }
    user_conversation = ConversationHandler(
        entry_points=[
            MessageHandler(Filters.chat(admin_chat_id), adm_help),
            CommandHandler('start', start),
            MessageHandler(~Filters.chat(admin_chat_id), help),
        ],
        states={
            ConversationStatus.GET_ITEM: [
                MessageHandler(Filters.text, get_item),
            ],
            ConversationStatus.GET_COST: [
                MessageHandler(Filters.text, get_cost),
            ],
            ConversationStatus.GET_CHECK: [
                MessageHandler(Filters.text('Да'), confirm_choice),
                MessageHandler(Filters.text('Нет'), decline_choice),
            ],
            ConversationStatus.ADM_COMMANDS: [
                CommandHandler('total', adm_total,
                               Filters.chat(admin_chat_id)),
                CommandHandler('closeparty', adm_close,
                               Filters.chat(admin_chat_id)),
                CallbackQueryHandler(send_bill, pattern=r'^sendbill:\d+$'),
                CallbackQueryHandler(close_bill, pattern=r'^closebill:\d+$'),
            ]
        },
        fallbacks=[],
        name='party_billing_conversation',
        # persistent=True,
    )
    dispatcher.add_handler(user_conversation)

    updater.start_polling()
    updater.idle()
