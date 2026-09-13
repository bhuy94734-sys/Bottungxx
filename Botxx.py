import asyncio
import logging
import os
import random
from aiohttp import web
from aiogram import Bot, Dispatcher, F, types
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Lấy Token và Admin ID từ biến môi trường trên Render hoặc điền trực tiếp
TOKEN = os.getenv("BOT_TOKEN", "8554416932:AAGhOIgzgHGYTTd9H3ghd5HApxerB-9e20U")
ADMIN_ID = int(os.getenv("ADMIN_ID", "8985238179"))
GROUP_CHAT_ID = int(os.getenv("GROUP_CHAT_ID", "-100123456789"))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Biến trạng thái trò chơi và tài chính
current_session = 105020
current_jackpot = 300000.0  # Hũ mặc định khởi tạo là 300,000đ
recent_tai_xiu = []
recent_chan_le = []
game_running = True  # Trạng thái vòng lặp tung xúc xắc (bật/tắt)

# Giả lập cơ sở dữ liệu người chơi trong phiên: {user_id: {"balance": float, "username": str}}
players_in_session = {}


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


async def run_game_loop():
  global current_session, current_jackpot, recent_tai_xiu, recent_chan_le, game_running
  await asyncio.sleep(5)
  while True:
    if game_running:
      d1 = random.randint(1, 6)
      d2 = random.randint(1, 6)
      d3 = random.randint(1, 6)
      total = d1 + d2 + d3

      if total <= 10:
        tx_result = "Xỉu"
        tx_code = "X"
      else:
        tx_result = "Tài"
        tx_code = "T"

      cl_result = "Chẵn" if total % 2 == 0 else "Lẻ"
      cl_code = "C" if total % 2 == 0 else "L"

      recent_tai_xiu.append(tx_code)
      if len(recent_tai_xiu) > 12:
        recent_tai_xiu.pop(0)

      recent_chan_le.append(cl_code)
      if len(recent_chan_le) > 12:
        recent_chan_le.pop(0)

      tong_thang = random.randint(500000, 3000000)
      tong_thua = random.randint(500000, 3000000)
      cong_hu = tong_thua * 0.005
      current_jackpot += cong_hu

      text = f"""KẾT QUẢ XX PHIÊN (#{current_session})

_____________________
|   {get_dice_emoji(d1)} {get_dice_emoji(d2)} {get_dice_emoji(d3)} ➡️ {total} điểm → {tx_result} | {cl_result}
|  
|  TỔNG ĐIỂM XÚC XẮC: {total}  
|  
|  TỔNG THẮNG: {tong_thang:,.0f} VND
|  TỔNG THUA: {tong_thua:,.0f} VND
|  CỘNG HŨ: {cong_hu:,.0f} VND  
|  HŨ HIỆN TẠI: {current_jackpot:,.0f} VND
|_____________________

{build_statistics_string()}"""

      try:
        await bot.send_message(
            chat_id=GROUP_CHAT_ID, text=text, reply_markup=build_main_keyboard()
        )
      except Exception as e:
        logging.error(f"Lỗi gửi kết quả game: {e}")

      current_session += 1
    await asyncio.sleep(30)


# ==================== CÁC LỆNH DÀNH CHO ADMIN ====================


@dp.message(Command("stop"))
async def admin_stop_game(message: types.Message):
  global game_running
  if message.from_user.id != ADMIN_ID:
    await message.answer("Bạn không có quyền sử dụng lệnh này!")
    return

  game_running = not game_running
  status_text = "tiếp tục chạy" if game_running else "đã dừng lại"
  await message.answer(
      f"🛑 Bot đã chuyển trạng thái tung xúc xắc thành: <b>{status_text}</b>",
      parse_mode=ParseMode.HTML,
  )


@dp.message(Command("resethu"))
async def admin_reset_hu(message: types.Message):
  global current_jackpot
  if message.from_user.id != ADMIN_ID:
    await message.answer("Bạn không có quyền sử dụng lệnh này!")
    return

  current_jackpot = 300000.0
  await message.answer(
      "🔄 Đã reset hũ về mức mặc định: <b>300,000 VNĐ</b>", parse_mode=ParseMode.HTML
  )


@dp.message(Command("conghu"))
async def admin_cong_hu(message: types.Message):
  global current_jackpot
  if message.from_user.id != ADMIN_ID:
    await message.answer("Bạn không có quyền sử dụng lệnh này!")
    return

  args = message.text.split()
  if len(args) < 2:
    await message.answer(
        "⚠️ Vui lòng nhập số tiền cần cộng thêm vào hũ. Ví dụ: <code>/conghu"
        " 50000</code>",
        parse_mode=ParseMode.HTML,
    )
    return

  try:
    amount = float(args[1])
    current_jackpot += amount
    await message.answer(
        f"➕ Đã cộng thêm <b>{amount:,.0f} VNĐ</b> vào hũ.\n💰 Hũ hiện tại:"
        f" <b>{current_jackpot:,.0f} VNĐ</b>",
        parse_mode=ParseMode.HTML,
    )
  except ValueError:
    await message.answer("⚠️ Số tiền không hợp lệ!")


@dp.message(Command("checkplayer"))
async def admin_check_player(message: types.Message):
  if message.from_user.id != ADMIN_ID:
    await message.answer("Bạn không có quyền sử dụng lệnh này!")
    return

  if not players_in_session:
    await message.answer("👥 Hiện tại chưa có người chơi nào ghi nhận trong phiên.")
    return

  player_list_str = f"👥 <b>DANH SÁCH NGƯỜI CHƠI ({len(players_in_session)})</b>:\n\n"
  for uid, info in players_in_session.items():
    player_list_str += f"👤 @{info['username']} (ID: <code>{uid}</code>)\n💰 Số dư: <b>{info['balance']:,.0f} VNĐ</b>\n------------------\n"

  await message.answer(player_list_str, parse_mode=ParseMode.HTML)


# ==================== CÁC LỆNH NGƯỜI DÙNG & NẠP TIỀN ====================


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
  welcome_text = f"""🎲 <b>HỆ THỐNG XÚC XẮC TỰ ĐỘNG</b>

Chào mừng bạn đến với hệ thống game tự động phiên #{current_session}.
Nhấn nút bên dưới để tiến hành nạp tiền tham gia."""
  await message.answer(
      welcome_text, reply_markup=build_main_keyboard(), parse_mode=ParseMode.HTML
  )


@dp.callback_query(F.data == "btn_nap_tien")
async def callback_nap_tien(callback: types.CallbackQuery):
  amounts = [
      20000, 30000, 50000, 100000, 200000, 300000, 500000, 1000000,
      2000000, 3000000, 4000000, 5000000, 10000000, 20000000, 50000000
  ]
  keyboard_buttons = [
      [InlineKeyboardButton(text=f"💵 {amt:,.0f} VNĐ", callback_data=f"deposit_amt_{amt}")]
      for amt in amounts
  ]
  keyboard_buttons.append([
      InlineKeyboardButton(text="🌐 Truy cập Bot chính", url="https://t.me/BTV88_bot")
  ])
  keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

  instruction = """📋 <b>HƯỚNG DẪN NẠP TIỀN NHANH</b>
Vui lòng chọn số tiền cần nạp bên dưới để hệ thống tự động tạo mã QR chuyển khoản:

🏦 <b>NGÂN HÀNG:</b> MB BANK
🏧 <b>STK:</b> <code>2105200999999</code>
👨‍💻 <b>CTK:</b> KHONG QUOC BAO

<i>Chọn nhanh mệnh giá bên dưới:</i>"""

  await callback.message.edit_text(
      instruction, reply_markup=keyboard, parse_mode=ParseMode.HTML
  )
  await callback.answer()


@dp.callback_query(F.data.startswith("deposit_amt_"))
async def process_deposit_amount(callback: types.CallbackQuery):
  amount = int(callback.data.split("_")[2])
  user_id = callback.from_user.id
  username = callback.from_user.username or callback.from_user.full_name
  random_content = f"NAP{user_id}{random.randint(100, 999)}"

  # Lưu hoặc cập nhật người chơi tạm thời vào danh sách người chơi
  if user_id not in players_in_session:
    players_in_session[user_id] = {"balance": 0.0, "username": username}

  bank_bin = "970422"
  account_no = "2105200999999"
  template = "compact2"
  qr_url = f"https://img.vietqr.io/image/{bank_bin}-{account_no}-{template}.jpg?amount={amount}&addInfo={random_content}&accountName=KHONG%20QUOC%20BAO"

  caption = f"""🏦 <b>MÃ QR CHUYỂN KHOẢN TỰ ĐỘNG</b>

Ngân hàng: <b>MB BANK</b>
Số tài khoản: <code>{account_no}</code>
Chủ tài khoản: <b>KHONG QUOC BAO</b>
Số tiền: <b>{amount:,.0f} VNĐ</b>
Nội dung chuyển khoản: <code>{random_content}</code>

⚠️ <i>Vui lòng dùng app ngân hàng quét mã QR trên hoặc chuyển đúng nội dung để hệ thống tự động duyệt tiền!</i>"""

  try:
    await callback.message.answer_photo(photo=qr_url, caption=caption, parse_mode=ParseMode.HTML)
  except Exception:
    await callback.message.answer(caption, parse_mode=ParseMode.HTML)

  admin_msg = f"""🔔 <b>CÓ YÊU CẦU NẠP TIỀN MỚI!</b>
👤 Khách: @{username} (ID: <code>{user_id}</code>)
💰 Số tiền: <b>{amount:,.0f} VNĐ</b>
📝 Nội dung: <code>{random_content}</code>"""

  admin_kb = InlineKeyboardMarkup(
      inline_keyboard=[
          [
              InlineKeyboardButton(text="✅ Duyệt", callback_data=f"approve_{user_id}_{amount}"),
              InlineKeyboardButton(text="❌ Từ chối", callback_data=f"reject_{user_id}_{amount}"),
          ]
      ]
  )

  try:
    await bot.send_message(
        chat_id=ADMIN_ID, text=admin_msg, reply_markup=admin_kb, parse_mode=ParseMode.HTML
    )
  except Exception as e:
    logging.error(f"Lỗi gửi thông báo cho admin: {e}")

  await callback.answer("Đã tạo mã QR nạp tiền thành công!")


@dp.callback_query(F.data.startswith("approve_") | F.data.startswith("reject_"))
async def admin_handle_deposit(callback: types.CallbackQuery):
  if callback.from_user.id != ADMIN_ID:
    await callback.answer("Bạn không có quyền thao tác!", show_alert=True)
    return

  parts = callback.data.split("_")
  action = parts[0]
  user_id = int(parts[1])
  amount = float(parts[2])

  if action == "approve":
    # Cộng dồn tiền vào số dư của khách
    if user_id in players_in_session:
      players_in_session[user_id]["balance"] += amount
    else:
      players_in_session[user_id] = {"balance": amount, "username": str(user_id)}

    current_balance = players_in_session[user_id]["balance"]

    await bot.send_message(
        chat_id=user_id,
        text=(
            f"✅ Giao dịch nạp tiền <b>{amount:,.0f} VNĐ</b> đã được duyệt!\nSố"
            f" dư hiện tại: <b>{current_balance:,.0f} VNĐ</b>"
        ),
        parse_mode=ParseMode.HTML,
    )
    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n<b>✅ ĐÃ DUYỆT cho user {user_id}</b>",
        parse_mode=ParseMode.HTML,
    )
  else:
    await bot.send_message(
        chat_id=user_id,
        text=f"❌ Giao dịch nạp tiền <b>{amount:,.0f} VNĐ</b> đã bị từ chối.",
        parse_mode=ParseMode.HTML,
    )
    await callback.message.edit_caption(
        caption=callback.message.caption + f"\n\n<b>❌ ĐÃ TỪ CHỐI đơn của user {user_id}</b>",
        parse_mode=ParseMode.HTML,
    )
  await callback.answer("Đã xử lý.")


# Web server giả lập duy trì UptimeRobot
async def handle_ping(request):
  return web.Response(text="Bot is running with Admin commands!")


async def start_web_server():
  app = web.Application()
  app.router.add_get("/", handle_ping)
  runner = web.AppRunner(app)
  await runner.setup()
  port = int(os.getenv("PORT", 8080))
  site = web.TCPSite(runner, "0.0.0.0", port)
  await site.start()


async def main():
  await start_web_server()
  asyncio.create_task(run_game_loop())
  await dp.start_polling(bot)


if __name__ == "__main__":
  asyncio.run(main())
