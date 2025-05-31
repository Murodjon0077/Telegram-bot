import logging
import random
from collections import defaultdict, Counter
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = "7734532599:AAHJ6VGSjMB4fujTSSUq-P6IuVkRpEXfDy4"
ADMIN_ID = 488897571

games = {}  # group_id -> game state
user_stats = defaultdict(lambda: {'wins': 0, 'losses': 0})
user_game_map = {}  # user_id -> group_id for PM actions

ROLES = ["Mafia", "Komissar Katanik", "Doctor", "Villager"]

def get_admin_panel():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Statistikani tozalash", callback_data="reset_stats")],
        [InlineKeyboardButton("Broadcast", callback_data="broadcast")]
    ])

def assign_roles(players):
    roles = ["Mafia", "Komissar Katanik", "Doctor"]
    while len(roles) < len(players):
        roles.append("Villager")
    random.shuffle(roles)
    return dict(zip(players, roles))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Mafia botga xush kelibsiz!")

async def start_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if chat_id in games:
        await update.message.reply_text("O'yin allaqachon boshlangan.")
        return

    members = [member.user for member in await context.bot.get_chat_administrators(chat_id)]
    players = [m.id for m in members if not m.is_bot]
    if len(players) < 4:
        await update.message.reply_text("O'yin uchun kamida 4 ta o'yinchi kerak.")
        return

    roles = assign_roles(players)
    game = {
        "players": roles,
        "alive": set(players),
        "phase": "night",
        "votes": {},
        "chat_id": chat_id,
        "night_actions": {},
    }
    games[chat_id] = game

    for uid, role in roles.items():
        user_game_map[uid] = chat_id
        try:
            await context.bot.send_message(uid, f"Sizning rolingiz: {role}")
        except:
            pass

    await update.message.reply_text("O'yin boshlandi! Rollar yuborildi. Tunda rollar PM orqali harakat qilsin.")
    await context.bot.send_message(chat_id, "TUN boshlandi. Har bir rol egasi PM orqali o'z harakatini yuborsin.")

async def handle_pm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_game_map:
        await update.message.reply_text("Siz hech qaysi o'yinda qatnashmayapsiz.")
        return

    chat_id = user_game_map[user_id]
    game = games.get(chat_id)
    if not game or game['phase'] != "night" or user_id not in game["alive"]:
        await update.message.reply_text("Siz hozir harakat qila olmaysiz.")
        return

    target_text = update.message.text.strip()
    try:
        target_id = int(target_text)
    except:
        await update.message.reply_text("Foydalanuvchi ID ni yuboring (raqam ko'rinishida).")
        return

    if target_id not in game["alive"]:
        await update.message.reply_text("Bu foydalanuvchi o'yinda mavjud emas.")
        return

    role = game["players"][user_id]
    game["night_actions"][user_id] = (role, target_id)
    await update.message.reply_text("Harakatingiz qabul qilindi.")

async def resolve_night(context: ContextTypes.DEFAULT_TYPE, chat_id: int):
    game = games[chat_id]
    actions = game["night_actions"]
    mafia_target = None
    kill_blocked = False

    for uid, (role, target) in actions.items():
        if role == "Mafia":
            mafia_target = target
        elif role == "Komissar Katanik":
            role_target = game["players"].get(target, "Noma'lum")
            try:
                await context.bot.send_message(uid, f"{target} roli: {role_target}")
            except:
                pass
        elif role == "Doctor" and mafia_target == target:
            kill_blocked = True

    msg = ""
    if mafia_target and not kill_blocked:
        game["alive"].remove(mafia_target)
        msg = f"{mafia_target} o'ldirildi!"
    else:
        msg = "Hech kim o'lmedi."

    game["night_actions"] = {}
    game["phase"] = "day"
    await context.bot.send_message(chat_id, f"TUN yakunlandi. {msg}")
    await context.bot.send_message(chat_id, "KUN boshlandi. Kimni o'ldiramiz? /vote [user_id]")

    check_winner(context, chat_id)

async def vote(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    game = games.get(chat_id)
    if not game or game['phase'] != "day":
        await update.message.reply_text("Hozir ovoz berish vaqti emas.")
        return

    try:
        target = int(context.args[0])
    except:
        await update.message.reply_text("Foydalanuvchi ID ni kiriting.")
        return

    voter = update.effective_user.id
    if voter not in game["alive"] or target not in game["alive"]:
        await update.message.reply_text("Bu o'yinchilar hozir tirik emas.")
        return

    game["votes"][voter] = target
    await update.message.reply_text(f"Ovoz {target} ga berildi.")

    if len(game["votes"]) >= len(game["alive"]):
        counts = Counter(game["votes"].values())
        most_voted = counts.most_common(1)[0][0]
        game["alive"].remove(most_voted)
        await context.bot.send_message(chat_id, f"{most_voted} ovoz bilan o'ldirildi.")
        game["votes"] = {}
        game["phase"] = "night"
        await context.bot.send_message(chat_id, "TUN boshlandi. PM orqali harakatlar.")
        await resolve_night(context, chat_id)

def check_winner(context, chat_id):
    game = games[chat_id]
    roles = [game["players"][uid] for uid in game["alive"]]
    mafia_count = roles.count("Mafia")
    others = len(roles) - mafia_count

    if mafia_count == 0:
        winners = [uid for uid, role in game["players"].items() if role != "Mafia"]
        for uid in winners:
            user_stats[uid]["wins"] += 1
        for uid in game["players"]:
            if uid not in winners:
                user_stats[uid]["losses"] += 1
        context.bot.send_message(chat_id, "TINCH AHOLI g'alaba qozondi!")
        games.pop(chat_id, None)
    elif mafia_count >= others:
        winners = [uid for uid, role in game["players"].items() if role == "Mafia"]
        for uid in winners:
            user_stats[uid]["wins"] += 1
        for uid in game["players"]:
            if uid not in winners:
                user_stats[uid]["losses"] += 1
        context.bot.send_message(chat_id, "MAFIYA g'alaba qozondi!")
        games.pop(chat_id, None)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    s = user_stats[uid]
    await update.message.reply_text(f"Sizda {s['wins']} g'alaba, {s['losses']} mag'lubiyat bor.")

async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_text("Admin panel:", reply_markup=get_admin_panel())
    else:
        await update.message.reply_text("Siz admin emassiz.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "reset_stats":
        user_stats.clear()
        await query.edit_message_text("Statistikalar tozalandi.")
    elif query.data == "broadcast":
        await query.edit_message_text("Xabar matnini yuboring:")
        context.user_data["broadcast"] = True

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("broadcast") and update.effective_user.id == ADMIN_ID:
        msg = update.message.text
        for game in games.values():
            for user_id in game["players"]:
                                            try:
                                                await
context.bot.send_message(chat_id=user_id, text=f"[Broadcast]: {msg}")
                                            except:
                                                pass
                                                
context.user_data["broadcast"] = False
                                                    await 
update.message.reply_text("Xabar yuborildi.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("startgame", start_game))
    app.add_handler(CommandHandler("vote", vote))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("admin", admin))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, handle_pm))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_message))
    print("Bot ishga tushdi...")
    app.run_polling()

if name == "main":
    main()
