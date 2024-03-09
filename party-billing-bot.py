import logging
import os
import re
import traceback
from enum import Enum

import redis
from dotenv import load_dotenv
from telegram import (InlineKeyboardButton, InlineKeyboardMarkup,
                      ReplyKeyboardMarkup, ReplyKeyboardRemove)
from telegram.ext import (CallbackQueryHandler, CommandHandler,
                          ConversationHandler, Filters, MessageHandler,
                          Updater)

from logger_handlers import TelegramLogsHandler
from persistence import RedisPersistence


logger = logging.getLogger(__file__)


class ConversationStatus(Enum):
    GET_ITEM = 0
    GET_COST = 1
    GET_CHECK = 2
    ADM_COMMANDS = 100


def get_user_bill(update, context, user_id):
    guest = context.bot_data['party']['guests'][user_id]
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
    negate_payd = '' if guest['bill_payd'] else 'не '
    text += f'Счет {negate_payd}оплачен.\n'
    reply_markup = None
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
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup)
    return subtotal


def send_user_bill(update, context, user_id):
    guest = context.bot_data['party']['guests'][user_id]
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
    text += 'Счет оплачивать переводом на номер 89110327182 (Сбер или ' \
            'Тинькофф)\nПосле оплаты чек из банковского приложения отправь ' \
            'сюда боту.\nОбычно приложение отправляет чек в формате PDF, но ' \
            'если ты захочешь отправить скриншот экрана, то отправляй ' \
            'картинку БЕЗ сжатия.\n'
    negate_payd = '' if guest['bill_payd'] else 'не '
    text += f'Счет {negate_payd}оплачен.\n'
    guest['bill_sent'] = True
    text += 'Счет отправлен.\n'
    context.bot.send_message(chat_id=user_id, text=text, )


def help(update, context):
    logger.debug(f'Enter help: {update=}')

    date = context.bot_data['party'].get('date', '')
    place = context.bot_data['party'].get('place', '')
    text = 'Привет!\n' \
           'Я учитываю заказы нашей компании на вечеринке ' \
           f'{date} в {place}\nЕсли ты участник этой вечеринки, то пришли ' \
           'комманду /start'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return ConversationHandler.END


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
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)
    return ConversationStatus.ADM_COMMANDS


def start(update, context):
    logger.debug(f'Enter cmd_start: {update=}')

    user_id = update.message.from_user.id
    username = update.message.from_user['username']
    firstname = update.message.from_user['first_name']
    lastname = update.message.from_user['last_name']

    guests = context.bot_data['party']['guests']
    if user_id not in guests:
        guests[user_id] = {'name': (username, firstname, lastname),
                           'bill_sent': False,
                           'bill_payd': False,
                           'orders': [('Бронирование', 300)], }

    date = context.bot_data['party'].get('date', '')
    place = context.bot_data['party'].get('place', '')
    text = f'Всем привет!\nЖдем вас на вечеринке {date} в {place}.\n' \
           'Это демо версия бота для учета заказов, пожалуйста, не серчайте ' \
           'за баги).\nОн отправляет ваш заказ официанту и суммирует его '\
           'общую стоимость после чего под конец вечера вам будет выставлен ' \
           'счет.\nПри достижении суммы депозита наш бот прекратит свою '\
           'работу и заказы будут приниматься только за баром.\n' \
           'Напишите через запятую наименование позиций, ' \
           'которые вы хотите заказать:'

    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return ConversationStatus.GET_ITEM


def get_item(update, context):
    logger.debug(f'Enter save_item: {update=}')

    item = update.message.text
    context.user_data['item'] = item
    text = f'Ты заказал(а):\n{item}\nТеперь напиши общуюсь стоимость всех ' \
           'позиций. Отменить заказ или исправить можно после следующего шага.'
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
    text = f'Давай проверим:\nТы заказал(а):\n{item}\nСтоимостью:\n' \
           f'{cost}руб.\n Нажми "Да", если все верно, или "Нет", если ' \
           'хочешь исправить или отменить заказ.'
    keyboard = [['Да', 'Нет'],]
    reply_markup = ReplyKeyboardMarkup(keyboard, one_time_keyboard=True)
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup, )
    return ConversationStatus.GET_CHECK


def confirm_choice(update, context):
    logger.debug(f'Enter confirm_choice: {update=}')

    if context.bot_data['party']['status'] == 'closed':
        text = 'Бот завершил работу, новые заказы будут принимать только за ' \
               'стойкой бара'
        context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                                 reply_markup=ReplyKeyboardRemove(), )
        return ConversationHandler.END

    cost = context.user_data['cost']
    item = context.user_data['item']
    text = f'Спасибо, что ты заказал:\n{item}\nСтоимостью:\n{cost}\n' \
           'Спуститесь за заказом через 5 минут (горячие блюда могут ' \
           'готовится дольше).\nЧтобы сделать новый заказ снова пришлите ' \
           'наименование позиций.'
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

    text = 'Отмена. Чтобы сделать заказ снова пришлите наименование позиций.'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=ReplyKeyboardRemove(), )
    return ConversationStatus.GET_ITEM


def forward_document(update, context):
    logger.debug(f'Enter forward_document: {update=}')

    update.message.forward(context.bot_data['admin_chat_id'])


def adm_total(update, context):
    logger.debug(f'Enter adm_total: {update=}')

    guests = context.bot_data['party']['guests']
    total = 0
    for user_id in guests:
        total += get_user_bill(update, context, user_id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f'Общая сумма за вечер: {total}руб.')
    return ConversationStatus.ADM_COMMANDS


def adm_debtors(update, context):
    logger.debug(f'Enter adm_debtors: {update=}')

    guests = context.bot_data['party']['guests']
    total = 0
    for user_id, guest in guests.items():
        if not guest['bill_payd']:
            total += get_user_bill(update, context, user_id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f'Сумма неоплаченных счетов: {total}руб.')
    return ConversationStatus.ADM_COMMANDS


def adm_sendbills(update, context):
    logger.debug(f'Enter adm_debtors: {update=}')

    guests = context.bot_data['party']['guests']
    total = 0
    for user_id, guest in guests.items():
        if not guest['bill_payd']:
            total += 1
            send_user_bill(update, context, user_id)
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text=f'Отправлено {total} неоплаченных счетов.')
    return ConversationStatus.ADM_COMMANDS


def adm_close(update, context):
    logger.debug(f'Enter adm_close: {update=}')

    context.bot_data['party']['status'] = 'closed'
    text = 'Вечеринка закрыта.\nИспользуйте следующие команды:\n' \
           '/sendbills - отправить счета всем, кто еще не оплатил\n' \
           '/total - получить полный подсчет по всем участникам вечеринки\n' \
           '/debtors - список тех кто еще не оплатил свой счет'
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, )
    return ConversationStatus.ADM_COMMANDS


def adm_start_party(update, context):
    logger.debug(f'Enter adm_start_party: {update=}')

    context.bot_data['party']['status'] = 'in progress'
    context.bot_data['party']['guests'] = {}
    context.bot.send_message(chat_id=update.effective_chat.id,
                             text='Все счета удалены, вечеринка запущена.')
    return ConversationStatus.ADM_COMMANDS


def adm_party_info(update, context):
    logger.debug(f'Enter adm_party_info: {update=}')
    date = context.bot_data['party']['date']
    place = context.bot_data['party']['place']
    status = context.bot_data['party']['status']
    text = 'Информация о текущей вечеринке:\n' \
           f'Дата вечеринки: {date}\n' \
           f'Место вечеринки (в): {place}\n' \
           f'Статус вечеринки: {status}'
    keyboard = [
        [InlineKeyboardButton('Изменить дату вечеринки (не работает)',
                              callback_data='change_party_date')],
        [InlineKeyboardButton('Изменить место вечеринки (не работает)',
                              callback_data='change_party_place')],
        [InlineKeyboardButton('Закрыть вечеринку',
                              callback_data='close_party')]
        if status == 'in progress' else
        [InlineKeyboardButton('Начать вечеринку',
                              callback_data='start_party')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text=text,
                             reply_markup=reply_markup)
    return ConversationStatus.ADM_COMMANDS


def adm_send_bill(update, context):
    user_id = int(update.callback_query.data.split(':')[1])
    send_user_bill(update, context, user_id)
    get_user_bill(update, context, user_id)
    return ConversationStatus.ADM_COMMANDS


def adm_close_bill(update, context):
    user_id = int(update.callback_query.data.split(':')[1])
    guest = context.bot_data['party']['guests'][user_id]
    guest['bill_payd'] = True
    text = re.sub(r'не оплачен', r'оплачен',
                  update.callback_query.message.text)
    update.callback_query.edit_message_text(text, reply_markup=None)
    return ConversationStatus.ADM_COMMANDS


def error_handler(update, context):
    logger.error(msg="Исключение при обработке сообщения:",
                 exc_info=context.error)


def main():
    load_dotenv(override=True)
    tg_token = os.getenv('TELEGRAM_BOT_TOKEN')
    admin_chat_id = int(os.getenv('TG_ADMIN_CHAT'))
    loglevel = os.getenv('LOG_LEVEL', default='INFO')
    logging.basicConfig(level=loglevel,
                        format="%(asctime)s %(levelname)s %(message)s", )
    logger.addHandler(TelegramLogsHandler(tg_token, admin_chat_id))
    logger.debug('Start logging')

    redis_host = os.getenv('REDIS_HOST')
    redis_port = os.getenv('REDIS_PORT')
    redis_password = os.getenv('REDIS_PASSWORD')

    redis_storage = redis.Redis(host=redis_host, port=redis_port,
                                password=redis_password)
    try:
        redis_storage.ping()
        persistence = RedisPersistence(redis_storage)
    except redis.ConnectionError:
        logger.warning('Redis not available. Run without persistence.')
        persistence = False

    updater = Updater(tg_token, persistence=persistence)
    dispatcher = updater.dispatcher

    dispatcher.bot_data['admin_chat_id'] = admin_chat_id
    if 'party' not in dispatcher.bot_data:
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
                CommandHandler('debtors', adm_debtors,
                               Filters.chat(admin_chat_id)),
                CommandHandler('sendbills', adm_sendbills,
                               Filters.chat(admin_chat_id)),
                CommandHandler('closeparty', adm_close,
                               Filters.chat(admin_chat_id)),
                CommandHandler('party', adm_party_info,
                               Filters.chat(admin_chat_id)),
                CallbackQueryHandler(adm_close, pattern=r'^close_party$'),
                CallbackQueryHandler(adm_start_party,
                                     pattern=r'^start_party$'),
                CallbackQueryHandler(adm_send_bill, pattern=r'^sendbill:\d+$'),
                CallbackQueryHandler(adm_close_bill,
                                     pattern=r'^closebill:\d+$'),
            ]
        },
        fallbacks=[
            CommandHandler('stop', help, ~Filters.chat(admin_chat_id)),
        ],
        name='party_billing_conversation',
        persistent=persistence,
    )
    dispatcher.add_handler(user_conversation)
    dispatcher.add_handler(
        MessageHandler(~Filters.chat(admin_chat_id) & Filters.document,
                       forward_document)
    )

    dispatcher.add_error_handler(error_handler)

    updater.start_polling()
    updater.idle()


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        logger.error({'Error': error, 'Traceback': traceback.format_exc()})
