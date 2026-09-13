import asyncio
import logging
import os
import random
import sqlite3
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

TOKEN = os.getenv("BOT_TOKEN", "8554416932:AAGhOIgzgHGYTTd9H3ghd5HApxerB-9e20U")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8985238179"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1004374137941"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# ==================== KHỞI TẠO DATABASE CHUNG ====================
DB_FILE = "shared_game.db"

def init_db():
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("""
      CREATE TABLE IF NOT EXISTS users (
          user_id INTEGER PRIMARY KEY,
          username TEXT,
          balance REAL DEFAULT 0.0,
          total_bet REAL DEFAULT 0.0
      )
  """)
  conn.commit()
  conn.close()

init_db()

def get_user(user_id: int, username: str):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT user_id, username, balance, total_bet FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if not row:
    cursor.execute("INSERT INTO users (user_id, username, balance, total_bet) VALUES (?, ?, 0.0, 0.0)", (user_id, username))
    conn.commit()
    row = (user_id, username, 0.0, 0.0)
  else:
    cursor.execute("UPDATE users SET username = ? WHERE user_id = ?", (username, user_id))
    conn.commit()
  conn.close()
  return {"user_id": row[0], "username": row[1], "balance": row[2], "total_bet": row[3]}

def update_balance(user_id: int, amount: float):
  conn = sqlite3.connect(DB_FILE)
  cursor = conn.cursor()
  cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
  row = cursor.fetchone()
  if row:
    new_bal = row[0] + amount
    cursor.execute("UPDATE users SET balance = ? WHERE user_id = ?", (new_bal, user_id))
    conn.commit()
  conn.close()

# Trò chơi và Trạng thái hệ thống
current_session = 105021
current_jackpot = 300000.0
recent_tai_xiu = []
recent_chan_le = []
game_running = True
game_phase = "BETTING"
countdown_timer = 30
current_bets = {}

def get_dice_emoji(val: int) -> str:
  return ["⚀", "⚁", "⚂", "⚃", "⚄", "⚅"][val - 1]

def build_statistics_string():
  tx_str = "".join(["🔴" if x == "T" else "🔵" for x in recent_tai_xiu])
  cl_str = "".join(["⚫️" if x == "C" else "⚪️" for x in recent_chan_le])
  return f"""🚥 <b>THỐNG KÊ 12 PHIÊN GẦN NHẤT</b>
KẾT QUẢ 12 PHIÊN GẦN NHẤT TÀI XỈU: 
{tx_str if tx_str else "Chưa có dữ liệu"}

KẾT QUẢ 12 PHIÊN GẦN NHẤT CHẴN LẺ:
{cl_str if cl_str else "Chưa có dữ liệu"}"""

def build_main_keyboard():
  return InlineKeyboardMarkup(
      inline_keyboard=[[InlineKeyboardButton(text="Nạp Tiền 💵", callback_data="btn_nap_tien")]]
  )

def calculate_total_bets_by_side():
  total_tai = sum(b.get("Tai", 0) for b in current_bets.values())
  total_xiu = sum(b.get("Xiu", 0) for b in current_bets.values())
  total_chan = sum(b.get("Chan", 0) for b in current_bets.values())
  total_le = sum(b.get("Le", 0) for b in current_bets.values())
  return total_tai, total_xiu, total_chan, total_le

async def run_game_loop():
  global current_session, current_jackpot, recent_tai_xiu, recent_chan_le, game_running, game_phase, countdown_timer, current_bets
  await asyncio.sleep(3)

  while True:
    if game_running:
      game_phase = "BETTING"
      countdown_timer = 30
      current_bets = {}

      start_msg = await bot.send_message(
          chat_id=GROUP_CHAT_ID,
          text=f"""🎲 <b>BẮT ĐẦU PHIÊN MỚI (#{current_session})</b>
⏳ Thời gian đặt cược: <b>{countdown_timer} giây</b>

👉 <b>Cú pháp đặt cược:</b>
• Đặt Tài: <code>/Tai [số tiền]</code>
• Đặt Xỉu: <code>/Xiu [số tiền]</code>
• Đặt Chẵn: <code>/C [số tiền]</code>
• Đặt Lẻ: <code>/L [số tiền]</code>""",
          reply_markup=build_main_keyboard()
      )

      for _ in range(30):
        await asyncio.sleep(1)
        countdown_timer -= 1
        t_tai, t_xiu, t_chan, t_le = calculate_total_bets_by_side()

        update_text = f"""🎲 <b>PHIÊN ĐANG DIỄN RA (#{current_session})</b>
⏳ Thời gian đặt cược còn lại: <b>{countdown_timer}s</b>

📊 <b>TỔNG TIỀN CƯỢC HIỆN TẠI:</b>
🔴 <b>Tài:</b> <code>{t_tai:,.0f} VNĐ</code>
🔵 <b>Xỉu:</b> <code>{t_xiu:,.0f} VNĐ</code>
⚫️ <b>Chẵn:</b> <code>{t_chan:,.0f} VNĐ</code>
⚪️ <b>Lẻ:</b> <code>{t_le:,.0f} VNĐ</code>"""
        try:
          await start_msg.edit_text(update_text, reply_markup=build_main_keyboard())
        except Exception:
          pass

      game_phase = "ROLLING"
      await bot.send_message(chat_id=GROUP_CHAT_ID, text=f"🔒 <b>Hết giờ đặt cược phiên #{current_session}! Đang lắc xúc xắc...</b>")

      try:
        dice1_msg = await bot.send_dice(chat_id=GROUP_CHAT_ID, emoji="🎲")
        await asyncio.sleep(0.5)
        dice2_msg = await bot.send_dice(chat_id=GROUP_CHAT_ID, emoji="🎲")
        await asyncio.sleep(0.5)
        dice3_msg = await bot.send_dice(chat_id=GROUP_CHAT_ID, emoji="🎲")
        
        await asyncio.sleep(3.5)

        d1 = dice1_msg.dice.value
        d2 = dice2_msg.dice.value
        d3 = dice3_msg.dice.value
        total = d1 + d2 + d3

        tx_result = "Xỉu" if total <= 10 else "Tài"
        tx_code = "X" if total <= 10 else "T"
        cl_result = "Chẵn" if total % 2 == 0 else "Lẻ"
        cl_code = "C" if total % 2 == 0 else "L"

        recent_tai_xiu.append(tx_code)
        if len(recent_tai_xiu) > 12: recent_tai_xiu.pop(0)

        recent_chan_le.append(cl_code)
        if len(recent_chan_le) > 12: recent_chan_le.pop(0)

        total_thang_phien = 0
        total_thua_phien = 0

        for uid, bets in current_bets.items():
          user_win_amount = 0
          win_details = []
          lose_details = []

          for bet_key, bet_amt in bets.items():
            if bet_key == "Tai":
              if tx_code == "T":
                reward = bet_amt * 1.9
                user_win_amount += reward
                total_thang_phien += reward
                win_details.append(f"Tài (+{reward:,.0f}đ)")
              else:
                total_thua_phien += bet_amt
                lose_details.append("Tài")
            elif bet_key == "Xiu":
              if tx_code == "X":
                reward = bet_amt * 1.9
                user_win_amount += reward
                total_thang_phien += reward
                win_details.append(f"Xỉu (+{reward:,.0f}đ)")
              else:
                total_thua_phien += bet_amt
                lose_details.append("Xỉu")
            elif bet_key == "Chan":
              if cl_code == "C":
                reward = bet_amt * 1.9
                user_win_amount += reward
                total_thang_phien += reward
                win_details.append(f"Chẵn (+{reward:,.0f}đ)")
              else:
                total_thua_phien += bet_amt
                lose_details.append("Chẵn")
            elif bet_key == "Le":
              if cl_code == "L":
                reward = bet_amt * 1.9
                user_win_amount += reward
                total_thang_phien += reward
                win_details.append(f"Lẻ (+{reward:,.0f}đ)")
              else:
                total_thua_phien += bet_amt
                lose_details.append("Lẻ")

          if user_win_amount > 0:
            update_balance(uid, user_win_amount)

          user_info = get_user(uid, str(uid))
          current_bal = user_info["balance"]

          try:
            notif_text = f"""🔔 <b>THÔNG BÁO KẾT QUẢ PHIÊN #{current_session}</b>
🎲 Kết quả: {get_dice_emoji(d1)} {get_dice_emoji(d2)} {get_dice_emoji(d3)} ➡️ <b>{total} điểm ({tx_result} | {cl_result})</b>\n"""
            if win_details: notif_text += f"🎉 <b>THẮNG:</b> {', '.join(win_details)}\n"
            if lose_details: notif_text += f"❌ <b>THUA:</b> {', '.join(lose_details)}\n"
            notif_text += f"💰 Số dư hiện tại của bạn: <b>{current_bal:,.0f} VNĐ</b>"

            await bot.send_message(chat_id=uid, text=notif_text, parse_mode=ParseMode.HTML)
          except Exception as e:
            logging.error(f"Lỗi gửi tin nhắn cho user {uid}: {e}")

        cong_hu = total_thua_phien * 0.005
        current_jackpot += cong_hu

        result_text = f"""KẾT QUẢ XX PHIÊN (#{current_session})

_____________________
|   {get_dice_emoji(d1)} {get_dice_emoji(d2)} {get_dice_emoji(d3)} ➡️ {total} điểm → {tx_result} | {cl_result}
|  
|  TỔNG ĐIỂM XÚC XẮC: {total}  
|  
|  TỔNG THẮNG: {total_thang_phien:,.0f} VND
|  TỔNG THUA: {total_thua_phien:,.0f} VND
|  CỘNG HŨ: {cong_hu:,.0f} VND  
|  HŨ HIỆN TẠI: {current_jackpot:,.0f} VND
|_____________________

{build_statistics_string()}"""

        await bot.send_message(chat_id=GROUP_CHAT_ID, text=result_text, reply_markup=build_main_keyboard())
        current_session += 1

      except Exception as e:
        logging.error(f"Lỗi vòng quay: {e}")

    await asyncio.sleep(2)

# ==================== XỬ LÝ LỆNH CƯỢC TRỰC TIẾP TRONG NHÓM ====================
@dp.message(F.text.regexp(r"^/(Tai|Xiu|C|L)(\s+\d+)?$"))
async def handle_bet_commands(message: types.Message):
  text = message.text.strip()
  parts = text.split()
  cmd = parts[0][1:].capitalize()
  
  if cmd == "Tai":
    bet_type = "Tai"
  elif cmd == "Xiu":
    bet_type = "Xiu"
  elif cmd == "C":
    bet_type = "Chan"
  elif cmd == "L":
    bet_type = "Le"
  else:
    return
  
  await process_user_bet_direct(message, bet_type, parts)

async def process_user_bet_direct(message: types.Message, bet_type: str, args: list):
  global game_phase, current_bets
  if game_phase != "BETTING":
    await message.reply("⚠️ Đã hết thời gian đặt cược phiên này!")
    return

  if len(args) < 2:
    await message.reply("⚠️ Vui lòng nhập số tiền cược! Ví dụ: `/Tai 50000`", parse_mode=ParseMode.HTML)
    return

  try:
    amount = float(args[1])
    if amount <= 0: raise ValueError()
  except ValueError:
    await message.reply("⚠️ Số tiền cược không hợp lệ!")
    return

  user = message.from_user
  user_data = get_user(user.id, user.username or user.full_name)
  current_bal = user_data["balance"]

  if current_bal < amount:
    await message.reply(f"❌ Số dư không đủ! Số dư hiện tại: <b>{current_bal:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)
    return

  update_balance(user.id, -amount)
  updated_data = get_user(user.id, user.username or user.full_name)
  new_balance = updated_data["balance"]

  if user.id not in current_bets: current_bets[user.id] = {}
  current_bets[user.id][bet_type] = current_bets[user.id].get(bet_type, 0) + amount

  await message.reply(f"✅ Đã cược <b>{amount:,.0f} VNĐ</b> vào <b>{bet_type.upper()}</b>!\n💰 Số dư còn lại: <b>{new_balance:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)

@dp.message(Command("sodu"))
async def cmd_sodu(message: types.Message):
  user = message.from_user
  user_data = get_user(user.id, user.username or user.full_name)
  await message.reply(f"💰 Số dư: <b>{user_data['balance']:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
  await message.answer(f"🎲 Chào mừng đến phiên #{current_session}. Gõ /sodu để xem số dư.", reply_markup=build_main_keyboard(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "btn_nap_tien")
async def callback_nap(callback: types.CallbackQuery):
  user = callback.from_user
  random_content = f"NAP{user.id}{random.randint(100, 999)}"
  qr_url = f"https://img.vietqr.io/image/970422-2105200999999-compact2.jpg?amount=50000&addInfo={random_content}&accountName=KHONG%20QUOC%20BAO"
  
  caption = f"""🏦 <b>HƯỚNG DẪN NẠP TIỀN TỰ ĐỘNG</b>
Số tài khoản: <code>2105200999999</code> (MB Bank)
Chủ TK: <b>KHONG QUOC BAO</b>
Nội dung chuyển khoản bắt buộc: <code>{random_content}</code>"""

  try:
    await callback.message.answer_photo(photo=qr_url, caption=caption, parse_mode=ParseMode.HTML)
  except Exception:
    await callback.message.answer(caption, parse_mode=ParseMode.HTML)

  admin_msg = f"""🔔 <b>CÓ YÊU CẦU NẠP TIỀN MỚI TỪ BOT XÚC XẮC!</b>
👤 Khách: @{user.username or user.full_name} (ID: <code>{user.id}</code>)
📝 Nội dung mã: <code>{random_content}</code>"""

  try:
    await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode=ParseMode.HTML)
  except Exception as e:
    logging.error(f"Không gửi được thông báo nạp cho admin: {e}")

  await callback.answer("Đã tạo thông tin nạp tiền và báo Admin!")

async def handle_ping(request):
  return web.Response(text="Dice Bot Running perfectly!")

async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  await web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080))).start()

async def main():
  await start_web_server()
  asyncio.create_task(run_game_loop())
  await dp.start_polling(bot)

if __name__ == "__main__":
  asyncio.run(main())
