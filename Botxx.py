import asyncio
import logging
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Import Database dùng chung
from database import db

TOKEN = os.getenv("BOT_TOKEN", "8554416932:AAGhOIgzgHGYTTd9H3ghd5HApxerB-9e20U")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8985238179"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-1004374137941"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Trò chơi và Trạng thái hệ thống
current_session = 105021
current_jackpot = 300000.0
recent_tai_xiu = []
recent_chan_le = []
game_running = True
game_phase = "BETTING"
countdown_timer = 30
current_bets = {}  # { user_id: {"Tai": x, "Xiu": y, "Chan": z, "Le": t} }

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
⚪️ <b>Lẻ:</b> <code>{t_le:,.0f} VNĐ</code>

👉 <i>Cú pháp: /Tai, /Xiu, /C, /L [số tiền]</i>"""
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
            db.update_balance(uid, user_win_amount)

          user_info = db.get_user(uid, str(uid))
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

async def process_user_bet(message: types.Message, bet_type: str):
  global game_phase, current_bets
  if game_phase != "BETTING":
    await message.reply("⚠️ Đã hết thời gian đặt cược phiên này!")
    return

  args = message.text.split()
  if len(args) < 2:
    await message.reply("⚠️ Sai cú pháp! Ví dụ: `/Tai 50000`", parse_mode=ParseMode.HTML)
    return

  try:
    amount = float(args[1])
    if amount <= 0: raise ValueError()
  except ValueError:
    await message.reply("⚠️ Số tiền cược không hợp lệ!")
    return

  user = message.from_user
  user_data = db.get_user(user.id, user.username or user.first_name)
  current_bal = user_data["balance"]

  if current_bal < amount:
    await message.reply(f"❌ Số dư không đủ! Số dư hiện tại: <b>{current_bal:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)
    return

  # Trừ tiền trực tiếp vào database chung
  db.update_balance(user.id, -amount)
  updated_data = db.get_user(user.id, user.username or user.first_name)
  new_balance = updated_data["balance"]

  if user.id not in current_bets: current_bets[user.id] = {}
  current_bets[user.id][bet_type] = current_bets[user.id].get(bet_type, 0) + amount

  await message.reply(f"✅ Đã cược <b>{amount:,.0f} VNĐ</b> vào <b>{bet_type.upper()}</b>!\n💰 Số dư còn lại: <b>{new_balance:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)

@dp.message(Command("Tai"))
async def cmd_tai(message: types.Message): await process_user_bet(message, "Tai")
@dp.message(Command("Xiu"))
async def cmd_xiu(message: types.Message): await process_user_bet(message, "Xiu")
@dp.message(Command("C"))
async def cmd_chan(message: types.Message): await process_user_bet(message, "Chan")
@dp.message(Command("L"))
async def cmd_le(message: types.Message): await process_user_bet(message, "Le")

@dp.message(Command("sodu"))
async def cmd_sodu(message: types.Message):
  user = message.from_user
  user_data = db.get_user(user.id, user.username or user.first_name)
  await message.reply(f"💰 Số dư: <b>{user_data['balance']:,.0f} VNĐ</b>", parse_mode=ParseMode.HTML)

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
  await message.answer(f"🎲 Chào mừng đến phiên #{current_session}. Gõ /sodu để xem số dư.", reply_markup=build_main_keyboard(), parse_mode=ParseMode.HTML)

@dp.callback_query(F.data == "btn_nap_tien")
async def callback_nap(callback: types.CallbackQuery):
  await callback.message.answer("💲 Để nạp tiền, vui lòng sử dụng Bot chính (@BTV88_bot) để thao tác nạp.")
  await callback.answer()

async def handle_ping(request):
  return web.Response(text="Dice Bot Running!")

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
  main()
