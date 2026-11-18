import asyncio, os, sqlite3, logging
from datetime import datetime
from aiogram import Bot, Dispatcher, F, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (Message, CallbackQuery, ReplyKeyboardMarkup, KeyboardButton,
                           ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton)

TOKEN = os.environ["9203811742:AAHBoS7mTAVg8xXfGWC2KLGyiQYzEWwCiGQ"]
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))  # Prorector's Telegram ID
DB = os.getenv("DB_PATH", "prorector.db")

# EDIT THESE to your university structure
FACULTIES = {
    "Iqtisodiyot": ["Moliya", "Buxgalteriya", "Marketing"],
    "Axborot texnologiyalari": ["Dasturiy injiniring", "Kiberxavfsizlik"],
    "Filologiya": ["Ingliz tili", "O'zbek tili"],
}
FAC = list(FACULTIES)
CATS = ["Taklif", "Shikoyat", "Muammo", "Savol", "Tashabbus", "Boshqa"]
STATUSES = ["Yangi", "Qabul qilindi", "Ko'rib chiqilmoqda", "Mas'ul xodimga yuborildi",
            "Javob tayyorlanmoqda", "Hal qilindi", "Rad etildi"]

MENU = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="📝 Murojaat yuborish"), KeyboardButton(text="📂 Murojaatlarim")],
    [KeyboardButton(text="🏛 Prorektorga murojaat"), KeyboardButton(text="👤 Shaxsiy kabinet")],
    [KeyboardButton(text="❓ Yordam")]])

def db(q, a=(), one=False):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    cur = con.execute(q, a)
    r = cur.fetchone() if one else cur.fetchall()
    con.commit(); con.close()
    return r

def init_db():
    db("""CREATE TABLE IF NOT EXISTS students(tg_id INTEGER PRIMARY KEY, first TEXT, last TEXT,
        faculty TEXT, direction TEXT, grp TEXT, phone TEXT, username TEXT, student_id TEXT, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS requests(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT, tg_id INTEGER,
        category TEXT, title TEXT, body TEXT, file_id TEXT, file_type TEXT, to_prorector INTEGER,
        status TEXT, response TEXT, created TEXT)""")
    db("""CREATE TABLE IF NOT EXISTS history(code TEXT, status TEXT, at TEXT)""")

def ikb(rows):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=t, callback_data=d)] for t, d in rows])

class Reg(StatesGroup):
    consent = State(); first = State(); last = State(); faculty = State()
    direction = State(); group = State(); phone = State(); sid = State()

class Req(StatesGroup):
    category = State(); title = State(); body = State(); file = State(); confirm = State()

r = Router()

# ---------- Registration ----------
@r.message(CommandStart())
async def start(m: Message, state: FSMContext):
    await state.clear()
    await m.answer("Assalomu alaykum!\nProrector Connect platformasiga xush kelibsiz.\n\n"
                   "Ushbu platforma orqali universitet rahbariyatiga o'z murojaat, taklif va "
                   "muammolaringizni yuborishingiz mumkin.")
    if db("SELECT 1 FROM students WHERE tg_id=?", (m.from_user.id,), one=True):
        return await m.answer("Asosiy menyu:", reply_markup=MENU)
    await state.set_state(Reg.consent)
    await m.answer("Davom etish uchun shaxsiy ma'lumotlaringizni (ism, telefon, fakultet, guruh) "
                   "murojaatlarni ko'rib chiqish maqsadida qayta ishlashga rozilik bering.",
                   reply_markup=ikb([("✅ Roziman", "consent")]))

@r.callback_query(Reg.consent, F.data == "consent")
async def consent(c: CallbackQuery, state: FSMContext):
    await state.set_state(Reg.first); await c.message.answer("Ismingizni kiriting:"); await c.answer()

@r.message(Reg.first)
async def reg_first(m: Message, state: FSMContext):
    await state.update_data(first=m.text.strip()[:50]); await state.set_state(Reg.last)
    await m.answer("Familiyangizni kiriting:")

@r.message(Reg.last)
async def reg_last(m: Message, state: FSMContext):
    await state.update_data(last=m.text.strip()[:50]); await state.set_state(Reg.faculty)
    await m.answer("Fakultetni tanlang:", reply_markup=ikb([(f, f"rf:{i}") for i, f in enumerate(FAC)]))

@r.callback_query(Reg.faculty, F.data.startswith("rf:"))
async def reg_fac(c: CallbackQuery, state: FSMContext):
    f = FAC[int(c.data[3:])]; await state.update_data(faculty=f); await state.set_state(Reg.direction)
    await c.message.answer("Yo'nalishni tanlang:", reply_markup=ikb([(d, f"rd:{i}") for i, d in enumerate(FACULTIES[f])]))
    await c.answer()

@r.callback_query(Reg.direction, F.data.startswith("rd:"))
async def reg_dir(c: CallbackQuery, state: FSMContext):
    d = (await state.get_data())["faculty"]
    await state.update_data(direction=FACULTIES[d][int(c.data[3:])]); await state.set_state(Reg.group)
    await c.message.answer("Guruhingizni kiriting (masalan: 201-guruh):"); await c.answer()

@r.message(Reg.group)
async def reg_group(m: Message, state: FSMContext):
    await state.update_data(grp=m.text.strip()[:30]); await state.set_state(Reg.phone)
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True,
                             keyboard=[[KeyboardButton(text="📱 Telefon raqamni yuborish", request_contact=True)]])
    await m.answer("Telefon raqamingizni yuboring:", reply_markup=kb)

@r.message(Reg.phone, F.contact)
async def reg_phone(m: Message, state: FSMContext):
    await state.update_data(phone=m.contact.phone_number); await state.set_state(Reg.sid)
    await m.answer("Talaba ID raqamingiz (ixtiyoriy). O'tkazish uchun «-» yuboring:", reply_markup=ReplyKeyboardRemove())

@r.message(Reg.sid)
async def reg_sid(m: Message, state: FSMContext):
    d = await state.get_data(); sid = None if m.text.strip() == "-" else m.text.strip()[:30]
    db("INSERT OR REPLACE INTO students VALUES(?,?,?,?,?,?,?,?,?,?)",
       (m.from_user.id, d["first"], d["last"], d["faculty"], d["direction"], d["grp"], d["phone"],
        m.from_user.username, sid, datetime.now().isoformat()))
    await state.clear(); await m.answer("✅ Ro'yxatdan o'tdingiz!", reply_markup=MENU)

# ---------- Request flow ----------
async def begin(m: Message, state: FSMContext, prorector: bool):
    if not db("SELECT 1 FROM students WHERE tg_id=?", (m.from_user.id,), one=True):
        return await m.answer("Avval /start orqali ro'yxatdan o'ting.")
    await state.update_data(prorector=prorector)
    if prorector:
        await state.update_data(category="Prorektorga"); await state.set_state(Req.title)
        return await m.answer("Murojaat mavzusini kiriting:")
    await state.set_state(Req.category)
    await m.answer("Kategoriyani tanlang:", reply_markup=ikb([(c, f"c:{i}") for i, c in enumerate(CATS)]))

@r.message(F.text == "📝 Murojaat yuborish")
async def new_req(m: Message, state: FSMContext): await begin(m, state, False)

@r.message(F.text == "🏛 Prorektorga murojaat")
async def new_pro(m: Message, state: FSMContext): await begin(m, state, True)

@r.callback_query(Req.category, F.data.startswith("c:"))
async def req_cat(c: CallbackQuery, state: FSMContext):
    await state.update_data(category=CATS[int(c.data[2:])]); await state.set_state(Req.title)
    await c.message.answer("Murojaat sarlavhasini kiriting:"); await c.answer()

@r.message(Req.title, F.text)
async def req_title(m: Message, state: FSMContext):
    await state.update_data(title=m.text.strip()[:150]); await state.set_state(Req.body)
    await m.answer("Murojaat mazmunini batafsil yozing:")

@r.message(Req.body, F.text)
async def req_body(m: Message, state: FSMContext):
    await state.update_data(body=m.text.strip()[:3500]); await state.set_state(Req.file)
    await m.answer("Rasm yoki PDF yuboring (ixtiyoriy):", reply_markup=ikb([("⏭ O'tkazib yuborish", "skip")]))

async def preview(m: Message, state: FSMContext):
    d = await state.get_data(); await state.set_state(Req.confirm)
    await m.answer(f"📋 Ko'rib chiqing:\n\nKategoriya: {d['category']}\nSarlavha: {d['title']}\n\n{d['body']}\n\n"
                   f"Fayl: {'bor' if d.get('file_id') else 'yo`q'}",
                   reply_markup=ikb([("✅ Yuborish", "send"), ("❌ Bekor qilish", "cancel")]))

@r.message(Req.file, F.photo | F.document)
async def req_file(m: Message, state: FSMContext):
    if m.photo: fid, ft = m.photo[-1].file_id, "photo"
    else:
        if m.document.mime_type not in ("application/pdf", "image/jpeg", "image/png") or m.document.file_size > 10_000_000:
            return await m.answer("Faqat PDF/JPG/PNG, 10 MB gacha.")
        fid, ft = m.document.file_id, "doc"
    await state.update_data(file_id=fid, file_type=ft); await preview(m, state)

@r.callback_query(Req.file, F.data == "skip")
async def req_skip(c: CallbackQuery, state: FSMContext):
    await preview(c.message, state); await c.answer()

@r.callback_query(Req.confirm, F.data == "cancel")
async def req_cancel(c: CallbackQuery, state: FSMContext):
    await state.clear(); await c.message.answer("Bekor qilindi.", reply_markup=MENU); await c.answer()

@r.callback_query(Req.confirm, F.data == "send")
async def req_send(c: CallbackQuery, state: FSMContext, bot: Bot):
    d = await state.get_data(); now = datetime.now()
    db("INSERT INTO requests(tg_id,category,title,body,file_id,file_type,to_prorector,status,created) VALUES(?,?,?,?,?,?,?,?,?)",
       (c.from_user.id, d["category"], d["title"], d["body"], d.get("file_id"), d.get("file_type"),
        int(d["prorector"]), "Yangi", now.isoformat()))
    rid = db("SELECT last_insert_rowid() AS i", one=True)["i"]
    code = f"PRC-{now.year}-{rid:05d}"
    db("UPDATE requests SET code=? WHERE id=?", (code, rid))
    db("INSERT INTO history VALUES(?,?,?)", (code, "Yangi", now.isoformat()))
    await state.clear()
    await c.message.answer(f"✅ Murojaatingiz qabul qilindi.\nID: {code}", reply_markup=MENU); await c.answer()
    if ADMIN_ID:
        s = db("SELECT * FROM students WHERE tg_id=?", (c.from_user.id,), one=True)
        txt = (f"🆕 {code} | {d['category']}\n{s['first']} {s['last']} ({s['faculty']}, {s['direction']}, {s['grp']})\n"
               f"Tel: {s['phone']}\n\n{d['title']}\n{d['body']}\n\n/reply {code} matn\n/status {code} 1-7")
        await bot.send_message(ADMIN_ID, txt)
        if d.get("file_id"):
            (bot.send_photo if d["file_type"] == "photo" else bot.send_document)
            await (bot.send_photo if d["file_type"] == "photo" else bot.send_document)(ADMIN_ID, d["file_id"])

# ---------- Tracking, profile, help ----------
@r.message(F.text == "📂 Murojaatlarim")
async def my_reqs(m: Message):
    rows = db("SELECT * FROM requests WHERE tg_id=? ORDER BY id DESC LIMIT 10", (m.from_user.id,))
    if not rows: return await m.answer("Hozircha murojaat yo'q.")
    await m.answer("Murojaatlaringiz:", reply_markup=ikb([(f"{x['code']} • {x['status']}", f"v:{x['code']}") for x in rows]))

@r.callback_query(F.data.startswith("v:"))
async def view(c: CallbackQuery):
    code = c.data[2:]; x = db("SELECT * FROM requests WHERE code=? AND tg_id=?", (code, c.from_user.id), one=True)
    if not x: return await c.answer("Topilmadi")
    h = "\n".join(f"• {a['at'][:16]} — {a['status']}" for a in db("SELECT * FROM history WHERE code=?", (code,)))
    await c.message.answer(f"{code}\nSana: {x['created'][:16]}\nKategoriya: {x['category']}\nHolat: {x['status']}\n\n"
                           f"Javob: {x['response'] or 'Hali yo`q'}\n\nTarix:\n{h}"); await c.answer()

@r.message(F.text == "👤 Shaxsiy kabinet")
async def profile(m: Message):
    s = db("SELECT * FROM students WHERE tg_id=?", (m.from_user.id,), one=True)
    if not s: return await m.answer("Avval /start.")
    await m.answer(f"👤 {s['first']} {s['last']}\n{s['faculty']} / {s['direction']} / {s['grp']}\nTel: {s['phone']}",
                   reply_markup=ikb([("✏️ Profilni qayta to'ldirish", "reedit")]))

@r.callback_query(F.data == "reedit")
async def reedit(c: CallbackQuery, state: FSMContext):
    await state.set_state(Reg.first); await c.message.answer("Ismingizni kiriting:"); await c.answer()

@r.message(F.text == "❓ Yordam")
async def help_(m: Message):
    await m.answer("Murojaat yuborish — rasmiy murojaat.\nMurojaatlarim — holatni kuzatish.\n"
                   "Prorektorga murojaat — to'g'ridan-to'g'ri.\nMuammo bo'lsa /start bosing.")

# ---------- Prorector commands ----------
def is_admin(m: Message): return m.from_user.id == ADMIN_ID

@r.message(Command("reply"), is_admin)
async def reply(m: Message, bot: Bot):
    p = m.text.split(maxsplit=2)
    if len(p) < 3: return await m.answer("/reply PRC-2026-00001 matn")
    x = db("SELECT * FROM requests WHERE code=?", (p[1],), one=True)
    if not x: return await m.answer("Topilmadi.")
    db("UPDATE requests SET response=? WHERE code=?", (p[2], p[1]))
    await bot.send_message(x["tg_id"], f"📩 {p[1]} bo'yicha rasmiy javob:\n\n{p[2]}"); await m.answer("Yuborildi ✅")

@r.message(Command("status"), is_admin)
async def status(m: Message, bot: Bot):
    p = m.text.split()
    if len(p) != 3 or not p[2].isdigit() or not 1 <= int(p[2]) <= 7:
        return await m.answer("/status CODE 1-7\n" + "\n".join(f"{i+1}. {s}" for i, s in enumerate(STATUSES)))
    x = db("SELECT * FROM requests WHERE code=?", (p[1],), one=True)
    if not x: return await m.answer("Topilmadi.")
    st = STATUSES[int(p[2]) - 1]
    db("UPDATE requests SET status=? WHERE code=?", (st, p[1]))
    db("INSERT INTO history VALUES(?,?,?)", (p[1], st, datetime.now().isoformat()))
    await bot.send_message(x["tg_id"], f"🔔 {p[1]} holati: {st}"); await m.answer("Yangilandi ✅")

@r.message(Command("myid"))
async def myid(m: Message): await m.answer(f"Sizning ID: {m.from_user.id}")

async def main():
    logging.basicConfig(level=logging.INFO); init_db()
    bot = Bot(TOKEN); dp = Dispatcher(); dp.include_router(r)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
