import random
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.utils import executor

API_TOKEN = "7734532599:AAHJ6VGSjMB4fujTSSUq-P6IuVkRpEXfDy4"

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

players = []
roles = {}
game_started = False

@dp.message_handler(commands=["start"])
async def start_handler(message: Message):
    await message.reply("Salom! Mafia o'yiniga xush kelibsiz. /join orqali o'yinga qo‘shiling.")

@dp.message_handler(commands=["join"])
async def join_handler(message: Message):
    global game_started
    user_id = message.from_user.id
    if game_started:
        await message.reply("O'yin allaqachon boshlangan.")
        return
    if user_id not in players:
        players.append(user_id)
        await message.reply("Siz o'yinga qo‘shildingiz.")
    else:
        await message.reply("Siz allaqachon ro'yxatda bor ekansiz.")

@dp.message_handler(commands=["startgame"])
async def start_game(message: Message):
    global game_started
    if game_started:
        await message.reply("O'yin allaqachon boshlangan.")
        return
    if len(players) < 5:
        await message.reply("O'yin boshlash uchun kamida 5 o'yinchi kerak.")
        return

    game_started = True
    random.shuffle(players)

    total_players = len(players)
    mafia_count = max(1, (total_players - 4) // 3)

    assigned_roles = ["Don", "Komissar", "Doctor"] + ["Mafia"] * mafia_count
    remaining = total_players - len(assigned_roles)
    assigned_roles += ["Oddiy aholi"] * remaining
    random.shuffle(assigned_roles)

    for user_id, role in zip(players, assigned_roles):
        roles[user_id] = role
        try:
            await bot.send_message(user_id, f"Sizning rolingiz: {role}")
        except:
            await message.reply(f"⚠️ Foydalanuvchiga xabar yuborib bo‘lmadi: {user_id}")

    await message.reply("🎮 O'yin boshlandi! Rollar shaxsiy xabarda yuborildi.")

    from aiogram.dispatcher.filters import Text

night_actions = {
    "mafia_target": None,
    "doctor_save": None,
    "commissar_check": None
}

@dp.message_handler(commands=["night"])
async def start_night(message: Message):
    if not game_started:
        await message.reply("O'yin hali boshlanmagan.")
        return

    await message.reply("🌙 Tungi bosqich boshlandi. Rollarga shaxsiy xabar yuborildi.")

    for user_id in players:
        role = roles.get(user_id)
        if role in ["Mafia", "Don"]:
            await bot.send_message(user_id, "Mafia, kimni o'ldirmoqchisiz? Foydalanuvchi ID ni yuboring:")
        elif role == "Doctor":
            await bot.send_message(user_id, "Doctor, kimni davolamoqchisiz? Foydalanuvchi ID ni yuboring:")
        elif role == "Komissar":
            await bot.send_message(user_id, "Komissar, kimni tekshirmoqchisiz? Foydalanuvchi ID ni yuboring:")

@dp.message_handler(lambda message: str(message.from_user.id) in roles)
async def handle_night_action(message: Message):
    user_id = message.from_user.id
    role = roles.get(user_id)

    target_id = message.text.strip()
    if target_id not in [str(p) for p in players]:
        await message.reply("❌ Bu foydalanuvchi o'yinda yo'q.")
        return

    if role in ["Mafia", "Don"]:
        night_actions["mafia_target"] = int(target_id)
        await message.reply("✅ Mafia tanlovi qabul qilindi.")
    elif role == "Doctor":
        night_actions["doctor_save"] = int(target_id)
        await message.reply("✅ Doctor tanlovi qabul qilindi.")
    elif role == "Komissar":
        night_actions["commissar_check"] = int(target_id)
        check_role = roles.get(int(target_id))
        if check_role in ["Mafia", "Don"]:
            await message.reply("🔍 Tekshiruv natijasi: Bu odam MAFIA!")
        else:
            await message.reply("🔍 Tekshiruv natijasi: Bu odam mafia emas.")

@dp.message_handler(commands=["morning"])
async def morning_phase(message: Message):
    killed = night_actions["mafia_target"]
    saved = night_actions["doctor_save"]

    if killed == saved:
        result = "🌤 Tinch tun edi. Hech kim o‘lmadi."
    else:
        if killed in players:
            players.remove(killed)
            result = f"☠️ {killed} foydalanuvchi o‘ldirildi."
        else:
            result = "❓ O‘ldirilgan foydalanuvchi topilmadi."

    # tozalash
    night_actions["mafia_target"] = None
    night_actions["doctor_save"] = None
    night_actions["commissar_check"] = None

    await message.reply(result)

    from collections import defaultdict

voting_active = False
votes = defaultdict(int)
already_voted = set()

# G‘alaba sharti tekshiruvi
    win = check_win_conditions()
    if win:
        await message.reply(win)
        reset_game()


@dp.message_handler(commands=["day"])
async def start_day(message: types.Message):
    global voting_active, votes, already_voted
    voting_active = True
    votes.clear()
    already_voted.clear()

    plist = "\n".join([f"{i+1}. ID: {p}" for i, p in enumerate(players)])
    await message.reply(f"🌞 Kunduzi bosqich boshlandi. Ovoz berish: /vote ID\n\n{plist}")


@dp.message_handler(commands=["vote"])
async def vote_handler(message: types.Message):
    global voting_active
    voter = message.from_user.id
    if not voting_active:
        await message.reply("⛔ Hozir ovoz berish emas.")
        return
    if voter not in players:
        await message.reply("❌ Siz o‘yinda emassiz.")
        return
    if voter in already_voted:
        await message.reply("✅ Siz allaqachon ovoz berdingiz.")
        return

    try:
        target = int(message.get_args().strip())
    except:
        await message.reply("⚠️ Format: /vote ID")
        return

    if target not in players:
        await message.reply("🚫 Bunday o‘yinchi yo‘q.")
        return

    votes[target] += 1
    already_voted.add(voter)
    await message.reply(f"📥 Siz {target} foydalanuvchiga ovoz berdingiz.")


@dp.message_handler(commands=["voteresult"])
async def vote_result(message: types.Message):
    global voting_active
    if not voting_active:
        await message.reply("⛔ Ovoz berish yo‘q.")
        return
    if not votes:
        await message.reply("🚫 Ovoz yo‘q.")
        return

    max_vote = max(votes.values())
    tops = [uid for uid, v in votes.items() if v == max_vote]

    if len(tops) == 1:
        eliminated = tops[0]
        players.remove(eliminated)
        await message.reply(f"⚖️ {eliminated} o‘ldirildi. Roli: {roles[eliminated]}")
    else:
        await message.reply("🤷‍♂️ Ovozlar teng. Hech kim chiqmadi.")

    voting_active = False
    votes.clear()
    already_voted.clear()

    win = check_win_conditions()
    if win:
        await message.reply(win)
        reset_game()


def check_win_conditions():
    mafia = sum(1 for uid in players if roles.get(uid) in ["Mafia", "Don"])
    civilians = sum(1 for uid in players if roles.get(uid) in ["Oddiy aholi", "Doctor", "Komissar"])
    if mafia == 0:
        return "🎉 Tinch aholi yutdi! Mafia qolmadi."
    elif mafia >= civilians:
        return "💀 Mafia yutdi! Ular ustunlikka erishdi."
    return None


def reset_game():
    global players, roles, game_started, voting_active
    players.clear()
    roles.clear()
    game_started = False
    voting_active = False
    votes.clear()
    already_voted.clear()


if name == "main":
    executor.start_polling(dp, skip_updates=True)
