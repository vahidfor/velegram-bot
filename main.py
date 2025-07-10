import os
import sqlite3
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler
)

# Load environment variables
load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_TELEGRAM_ID"))

# Connection states (Corrected to range(15) to match 15 variables)
(
    REGISTER_PHONE, REGISTER_NAME, REGISTER_DEVICE, 
    ASK_DISCOUNT, 
    ASK_TARGET, ASK_AMOUNT, 
    ASK_TOPUP, 
    ADMIN_ADD_SERVICE, ADMIN_ADD_DISCOUNT, ADMIN_CHARGE_USER, ADMIN_DEDUCT_CREDIT, ADMIN_BROADCAST, ADMIN_MESSAGE_USER, 
    SUPPORT_MESSAGE, ADMIN_ADD_SERVICE_CONTENT_TO_USER
) = range(15)

# Connect to database
conn = sqlite3.connect("users.db", check_same_thread=False)
cursor = conn.cursor()

# Create database tables (if they don't exist)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY,
    username TEXT,
    credit INTEGER DEFAULT 0,
    discount_used INTEGER DEFAULT 0,
    is_approved INTEGER DEFAULT 0,
    phone_number TEXT,
    full_name TEXT,
    device_type TEXT
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS codes (
    code TEXT PRIMARY KEY,
    value INTEGER
)
""")
cursor.execute("""
CREATE TABLE IF NOT EXISTS services (
    type TEXT PRIMARY KEY,
    content TEXT,         
    is_file INTEGER DEFAULT 0 
)
""")
conn.commit()

# --- Inline Keyboards and Callbacks ---

# We define the main keyboard as InlineKeyboardMarkup
def get_main_inline_keyboard(is_admin):
    keyboard = [
        [
            InlineKeyboardButton("📃 دریافت برنامه", callback_data="get_app"), 
            InlineKeyboardButton("🎁 فعال‌سازی کد تخفیف", callback_data="activate_discount")
        ],
        [
            InlineKeyboardButton("🏦 اعتبار من", callback_data="my_credit"), 
            InlineKeyboardButton("🔁 انتقال اعتبار", callback_data="transfer_credit")
        ],
        [
            InlineKeyboardButton("ℹ️ وضعیت من", callback_data="my_status"), 
            InlineKeyboardButton("🌐 دریافت سرویس‌ها", callback_data="get_service")
        ],
        [
            InlineKeyboardButton("💳 افزایش اعتبار", callback_data="topup"), 
            InlineKeyboardButton("✉️ پیام به پشتیبانی", callback_data="support_message")
        ]
    ]
    if is_admin:
        keyboard.append([InlineKeyboardButton("🎛 پنل مدیریت", callback_data="admin_panel")])
    
    return InlineKeyboardMarkup(keyboard)

# Callback handler for main menu actions
async def main_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Check if the query is a "cancel" action from a conversation
    if data in ["cancel_transfer", "cancel_topup", "cancel_support"]:
        await query.edit_message_text("عملیات لغو شد.", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))
        return ConversationHandler.END

    if data == "get_app":
        return await get_app(update, context)
    elif data == "activate_discount":
        # Start discount conversation
        await query.edit_message_text("🎁 لطفاً کد تخفیف را وارد کنید:")
        return ASK_DISCOUNT
    elif data == "my_credit":
        # Execute my_credit logic directly
        cursor.execute("SELECT credit FROM users WHERE id=?", (query.from_user.id,))
        credit = cursor.fetchone()
        if credit:
            await query.edit_message_text(f"💳 اعتبار شما: {credit[0]} تومان", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))
        else:
            await query.edit_message_text("❌ کاربر یافت نشد. لطفاً دوباره /start را بزنید.")
        return ConversationHandler.END 
    elif data == "transfer_credit":
        # Start transfer conversation
        await query.edit_message_text("🔁 لطفاً ID عددی دریافت‌کننده را وارد کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_transfer")]]))
        return ASK_TARGET
    elif data == "my_status":
        # Execute my_status logic
        user = query.from_user
        cursor.execute("SELECT credit, discount_used, is_approved, phone_number, full_name, device_type FROM users WHERE id=?", (user.id,))
        user_data = cursor.fetchone()
        
        if user_data:
            credit, discount_used, approved, phone_number, full_name, device_type = user_data
            await query.edit_message_text(f"""👤 @{user.username}
🆔 {user.id}
📝 نام: {full_name or 'نامشخص'}
📞 شماره تلفن: {phone_number or 'نامشخص'}
💻 دستگاه: {device_type or 'نامشخص'}
💳 اعتبار: {credit} تومان
🎁 کد تخفیف: {"استفاده شده" if discount_used else "فعال نشده"}
✅ وضعیت تأیید: {"تأیید شده" if approved else "در انتظار تأیید"}
""", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))
        else:
            await query.edit_message_text("❌ کاربر یافت نشد. لطفاً دوباره /start را بزنید.")
        return ConversationHandler.END
    elif data == "get_service":
        return await get_service(update, context)
    elif data == "topup":
        # Start topup conversation
        await query.edit_message_text("💳 مقدار و توضیحات پرداخت خود را وارد کنید:\nمثال: 100000 - کارت به کارت به 6274xxxxxxxxxxxx", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_topup")]]))
        return ASK_TOPUP
    elif data == "support_message":
        # Start support message conversation
        await query.edit_message_text("✉️ لطفاً پیام خود را برای پشتیبانی ارسال کنید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="cancel_support")]]))
        return SUPPORT_MESSAGE
    elif data == "admin_panel":
        return await admin(update, context)
    
    # Fallback for "main_menu" callback or unexpected data
    await query.edit_message_text("منوی اصلی:", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))
    return ConversationHandler.END

# --- User Interface Functions ---

# /start - Start interaction
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Check if user has a ReplyKeyboardMarkup visible and remove it
    await update.message.reply_text("خوش آمدید.", reply_markup=ReplyKeyboardRemove())

    cursor.execute("SELECT full_name FROM users WHERE id=?", (user.id,))
    user_info = cursor.fetchone()

    if not user_info or user_info[0] is None:
        # If user is not registered, start registration
        cursor.execute("INSERT OR IGNORE INTO users (id, username) VALUES (?, ?)", (user.id, user.username))
        conn.commit()
        return await ask_phone_number(update, context)

    # If user is registered, show main menu with Inline Keyboard
    await update.message.reply_text(
        "سلام! به ربات VPN خوش اومدی 👋\n\nلطفاً یک گزینه را انتخاب کنید:", 
        reply_markup=get_main_inline_keyboard(user.id == ADMIN_ID)
    )

# --- Registration Flow ---

async def ask_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is the only place we use ReplyKeyboardMarkup to request contact
    keyboard = [[KeyboardButton("ارسال شماره تلفن", request_contact=True)]]
    await update.message.reply_text(
        "لطفاً برای ثبت‌نام، شماره تلفن خود را ارسال کنید (با استفاده از دکمه زیر):",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return REGISTER_PHONE

async def register_phone_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    contact = update.message.contact
    if contact and contact.user_id == user_id:
        phone_number = contact.phone_number
        cursor.execute("UPDATE users SET phone_number=? WHERE id=?", (phone_number, user_id))
        conn.commit()
        await update.message.reply_text("شماره تلفن شما با موفقیت ثبت شد. حالا لطفا نام و نام خانوادگی خود را وارد کنید:", reply_markup=ReplyKeyboardRemove())
        return REGISTER_NAME
    else:
        await update.message.reply_text("لطفا از دکمه 'ارسال شماره تلفن' استفاده کنید.")
        return REGISTER_PHONE

async def register_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    full_name = update.message.text.strip()
    cursor.execute("UPDATE users SET full_name=? WHERE id=?", (full_name, user_id))
    conn.commit()
    
    # Use Inline Keyboard for device selection
    device_keyboard = [
        [InlineKeyboardButton("📱 اندروید", callback_data="register_device_android")],
        [InlineKeyboardButton("🍏 آیفون", callback_data="register_device_iphone")],
        [InlineKeyboardButton("🖥 ویندوز", callback_data="register_device_windows")]
    ]
    await update.message.reply_text("نام شما ثبت شد. حالا نوع دستگاه خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(device_keyboard))
    return REGISTER_DEVICE

async def register_device(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Handle inline callback for device registration
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    device_map = {
        "register_device_android": "اندروید",
        "register_device_iphone": "آیفون",
        "register_device_windows": "ویندوز"
    }
    
    device_type = device_map.get(data)
    
    if device_type:
        cursor.execute("UPDATE users SET device_type=?, is_approved=1 WHERE id=?", (device_type, user.id))
        conn.commit()

        # Admin notification about new registration
        cursor.execute("SELECT phone_number, full_name FROM users WHERE id=?", (user.id,))
        registered_user = cursor.fetchone()
        
        if registered_user:
            phone_number, full_name = registered_user
            await context.bot.send_message(
                ADMIN_ID, 
                f"🎉 کاربر جدید ثبت‌نام کرد:\n"
                f"نام: {full_name}\n"
                f"نام کاربری: @{user.username}\n"
                f"ID: {user.id}\n"
                f"شماره تلفن: {phone_number}\n"
                f"دستگاه: {device_type}"
            )
        
        await query.edit_message_text(
            f"ثبت‌نام شما با موفقیت انجام شد ({device_type}). می‌توانید از دکمه‌های زیر استفاده کنید.",
            reply_markup=get_main_inline_keyboard(user.id == ADMIN_ID)
        )
        return ConversationHandler.END
    else:
        await query.edit_message_text("❌ لطفاً یک گزینه معتبر را انتخاب کنید.")
        return REGISTER_DEVICE

# --- General User Functions ---

# Get App (Modified to use Inline Keyboard)
async def get_app(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    # We send the Inline keyboard for app selection
    await query.edit_message_text(
        "لطفاً دستگاه خود را انتخاب کنید:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📱 اندروید", callback_data="app_android"), InlineKeyboardButton("🍏 آیفون", callback_data="app_iphone")],
            [InlineKeyboardButton("🖥 ویندوز", callback_data="app_windows"), InlineKeyboardButton("❓ راهنمای اتصال", callback_data="app_guide")],
            [InlineKeyboardButton("بازگشت", callback_data="main_menu")]
        ])
    )

async def send_app_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    selected_option = query.data
    
    # Note: Ensure the files exist at this path.
    # BASE_IMAGE_PATH should be adjusted based on the actual file location in your Replit environment
    BASE_IMAGE_PATH = "/home/Vahidfor/Image/" 

    links = {
        "app_android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
        "app_iphone": "https://apps.apple.com/app/openvpn-connect/id590379981",
        "app_windows": "https://openvpn.net/client-connect-vpn-for-windows/",
        "app_guide": {
            "type": "guide_photos",
            "files": [
                f"{BASE_IMAGE_PATH}photo1.jpg", f"{BASE_IMAGE_PATH}photo2.jpg", f"{BASE_IMAGE_PATH}photo3.jpg", 
                f"{BASE_IMAGE_PATH}photo4.jpg", f"{BASE_IMAGE_PATH}photo5.jpg", f"{BASE_IMAGE_PATH}photo6.jpg", 
                f"{BASE_IMAGE_PATH}photo7.jpg", f"{BASE_IMAGE_PATH}photo8.jpg", f"{BASE_IMAGE_PATH}photo9.jpg", 
                f"{BASE_IMAGE_PATH}photo10.jpg",
            ],
            "captions": [
                "1. برنامه OpenVPN را از استور نصب کنید...", "2. روی تب file کلیک کنید ...", "3. روی browse کلیک کنید ...",
                "4. پوشه ای که فایل دریافتی را ذخیره کرده اید بروید.", "5. فایل دریافتی را انتخاب و وارد برنامه کنید.", 
                "6. روی ok کلیک کنید.", "7. username و password دریافتی را درقسمت مشخص شده وارد کنید.",
                "8. درخواست اتصال را تایید کنید.", "9.اگر به متصل نشد روی دکمه کنار فایل کلیک کنید و منتظر بمانید .",
                "10.پس از اتصال موفقیت‌آمیز، وضعیت را سبز ببینید...",
            ],
            "additional_note": "نکته : در دستگاه های آیفون(ios) و برخی دستگاه های با اندروید قدیمی لازم است تا ابتدا فایل را باز کرده و با زدن دکمه share و انتخاب نام برنامه آن را وارد برنامه کنید و باقی مراحل را طی کنید.\nدر صورت وجود مشکل با پشتیبانی تماس بگیرید"
        }
    }

    if selected_option == "app_guide":
        guide_info = links[selected_option]
        if guide_info["type"] == "guide_photos":
            media = []
            for i, file_path in enumerate(guide_info["files"]):
                try:
                    # In a typical Replit environment, you might need to handle file paths carefully
                    # This code assumes the files are locally accessible at BASE_IMAGE_PATH
                    with open(file_path, 'rb') as photo_file:
                        caption = guide_info["captions"][i] if i < len(guide_info["captions"]) else f"راهنما - عکس {i+1}"
                        # Telegram requires InputMediaPhoto to be created with a media object
                        media.append(InputMediaPhoto(media=photo_file.read(), caption=caption))
                except FileNotFoundError:
                    await query.message.reply_text(f"خطا: فایل راهنمای {file_path} پیدا نشد.")
                    return
                except Exception as e:
                    await query.message.reply_text(f"خطا در بارگذاری عکس {file_path}: {e}")
                    return
            
            if media:
                try:
                    await context.bot.send_media_group(chat_id=query.message.chat_id, media=media)
                    if "additional_note" in guide_info:
                        await query.message.reply_text(guide_info["additional_note"])
                except Exception as e:
                    await query.message.reply_text(f"خطا در ارسال گروهی تصاویر: {e}")
            else:
                await query.message.reply_text("هیچ عکسی برای راهنما یافت نشد.")
    else:
        await query.edit_message_text(links.get(selected_option, "❌ گزینه نامعتبر"))
    
    # After sending the link/guide, send the main menu inline keyboard
    await context.bot.send_message(query.from_user.id, "بازگشت به منوی اصلی:", reply_markup=get_main_inline_keyboard(query.from_user.id == ADMIN_ID))
    
# Get Service (Modified to use Inline Keyboard)
async def get_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    
    # Check if user is approved
    cursor.execute("SELECT is_approved FROM users WHERE id=?", (user_id,))
    approved = cursor.fetchone()
    
    if not approved or approved[0] == 0:
        await query.edit_message_text("⛔ شما هنوز ثبت‌نام خود را تکمیل نکرده‌اید یا توسط ادمین تأیید نشده‌اید. لطفاً ثبت‌نام کنید یا منتظر تأیید بمانید.")
        return

    # If approved, show service options with Inline Keyboard
    service_keyboard = [
        [InlineKeyboardButton("🔐 OpenVPN", callback_data="request_service_openvpn")],
        [InlineKeyboardButton("🛰 V2Ray", callback_data="request_service_v2ray")],
        [InlineKeyboardButton("📡 Proxy تلگرام", callback_data="request_service_proxy")],
        [InlineKeyboardButton("بازگشت", callback_data="main_menu")]
    ]
    await query.edit_message_text("کدام سرویس را می‌خواهید؟", reply_markup=InlineKeyboardMarkup(service_keyboard))

async def send_service_request_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    data = query.data
    
    if not data.startswith("request_service_"):
        await query.edit_message_text("❌ درخواست سرویس نامعتبر.")
        return
        
    service_key = data.replace("request_service_", "")
    service_type_text = {
        "openvpn": "OpenVPN",
        "v2ray": "V2Ray",
        "proxy": "Proxy تلگرام"
    }.get(service_key, service_key)

    # Notify admin about the service request and request service content
    msg_for_admin = (
        f"🌐 درخواست سرویس جدید از کاربر:\n"
        f"کاربر: @{user.username}\n"
        f"ID: {user.id}\n"
        f"نوع سرویس درخواستی: {service_type_text}\n\n"
        f"لطفاً سرویس مربوطه را برای این کاربر ارسال کنید."
    )
    
    context.bot_data[f"service_request_{user.id}"] = service_key

    # Admin inline keyboard for response
    keyboard = [
        [InlineKeyboardButton("✅ ارسال سرویس", callback_data=f"send_service_{user.id}")],
        [InlineKeyboardButton("❌ رد درخواست", callback_data=f"reject_service_{user.id}")],
        [InlineKeyboardButton("✉️ چت با کاربر", callback_data=f"chat_user_{user.id}")]
    ]

    await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.edit_message_text("✅ درخواست شما به ادمین ارسال شد. لطفاً منتظر دریافت سرویس بمانید.")

# Discount related functions 
async def apply_discount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id if update.effective_user else update.message.from_user.id
    code = update.message.text.strip()

    cursor.execute("SELECT discount_used FROM users WHERE id=?", (user_id,))
    user_data = cursor.fetchone()

    if user_data and user_data[0]:
        await update.message.reply_text("⛔ شما قبلاً از کد تخفیف استفاده کرده‌اید.")
        return ConversationHandler.END

    cursor.execute("SELECT value FROM codes WHERE code=?", (code,))
    row = cursor.fetchone()
    if row:
        value = row[0]
        cursor.execute("UPDATE users SET credit = credit + ?, discount_used = 1 WHERE id=?", (value, user_id))
        conn.commit()
        await update.message.reply_text(f"✅ {value} تومان اعتبار اضافه شد.")
    else:
        await update.message.reply_text("❌ کد تخفیف نامعتبر است.")
    
    return ConversationHandler.END

# Transfer Credit related functions
async def ask_amount(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        context.user_data["target_id"] = int(update.message.text)
        await update.message.reply_text("چه مقدار اعتبار منتقل شود؟")
        return ASK_AMOUNT
    except ValueError:
        await update.message.reply_text("❌ ID عددی نامعتبر است. لطفا یک ID عددی وارد کنید.")
        return ConversationHandler.END

async def do_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        amount = int(update.message.text)
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ باید مثبت باشد.")
            return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ مبلغ عددی نامعتبر است.")
        return ConversationHandler.END

    sender = update.effective_user.id
    receiver = context.user_data["target_id"]
    
    cursor.execute("SELECT credit FROM users WHERE id=?", (sender,))
    current = cursor.fetchone()[0]
    
    cursor.execute("SELECT id FROM users WHERE id=?", (receiver,))
    if not cursor.fetchone():
        await update.message.reply_text("❌ ID دریافت‌کننده نامعتبر است.")
        return ConversationHandler.END

    if current < amount:
        await update.message.reply_text("❌ اعتبار شما کافی نیست.")
    else:
        cursor.execute("UPDATE users SET credit = credit - ? WHERE id=?", (amount, sender))
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id=?", (amount, receiver))
        conn.commit()
        await update.message.reply_text("✅ انتقال انجام شد.")
    return ConversationHandler.END

# Topup related functions
async def send_topup_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    # Ensure user is set to pending approval 
    cursor.execute("UPDATE users SET is_approved = 0 WHERE id=?", (user.id,))
    conn.commit()

    msg = f"💳 درخواست افزایش اعتبار از:\n@{user.username}\n🆔 {user.id}\n💬 توضیح: {update.message.text}"
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg) # Send message to admin
    await update.message.reply_text("✅ درخواست شما به ادمین ارسال شد. لطفاً منتظر تأیید ادمین بمانید.")
    return ConversationHandler.END

# Support Message related functions
async def send_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    support_message = update.message.text
    msg_for_admin = f"✉️ پیام جدید از پشتیبانی:\nکاربر: @{user.username} (ID: {user.id})\nپیام: {support_message}"
    
    await context.bot.send_message(chat_id=ADMIN_ID, text=msg_for_admin) 
    await update.message.reply_text("پیام شما به پشتیبانی ارسال شد. در اسرع وقت پاسخ خواهیم داد.")
    return ConversationHandler.END

# --- Admin Panel Functions ---

def get_admin_inline_keyboard():
    keyboard = [
        [InlineKeyboardButton("🧾 تأیید/رد کاربران", callback_data="admin_approve_reject"), 
         InlineKeyboardButton("💰 شارژ کاربر", callback_data="admin_charge_user")],
        [InlineKeyboardButton("➖ کسر اعتبار", callback_data="admin_deduct_credit"), 
         InlineKeyboardButton("➕ افزودن کد تخفیف", callback_data="admin_add_discount")],
        [InlineKeyboardButton("🛰 افزودن سرویس V2Ray", callback_data="admin_add_v2ray"), 
         InlineKeyboardButton("🔐 افزودن OpenVPN", callback_data="admin_add_openvpn")],
        [InlineKeyboardButton("📡 افزودن Proxy تلگرام", callback_data="admin_add_proxy"), 
         InlineKeyboardButton("📢 پیام همگانی", callback_data="admin_broadcast")],
        [InlineKeyboardButton("👥 چت با کاربر", callback_data="admin_chat_user")],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data="main_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)

# We use the /admin command as an entry point, and also the 'admin_panel' callback
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Determine the user ID based on the update type (message or callback query)
    user_id = update.effective_user.id if update.effective_user else update.callback_query.from_user.id
    
    if user_id != ADMIN_ID: 
        return
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text("🎛 پنل مدیریت:", reply_markup=get_admin_inline_keyboard())
    else:
        # If /admin command is used
        await update.message.reply_text("🎛 پنل مدیریت:", reply_markup=get_admin_inline_keyboard())

# Admin Callback Handler for Panel Actions
async def admin_panel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_approve_reject":
        return await list_pending_and_approve_reject(update, context)
    elif data == "admin_charge_user":
        # Start charge conversation
        await query.edit_message_text("💰 ID کاربر و مبلغ (مثال: 123456789 10000):")
        return ADMIN_CHARGE_USER
    elif data == "admin_deduct_credit":
        # Start deduct conversation
        await query.edit_message_text("➖ ID کاربر و مبلغ کسر (مثال: 123456789 5000):")
        return ADMIN_DEDUCT_CREDIT
    elif data == "admin_add_discount":
        # Start add discount conversation
        await query.edit_message_text("➕ کد و مقدار را وارد کن (مثال: vip50 5000):")
        return ADMIN_ADD_DISCOUNT
    elif data.startswith("admin_add_"):
        # Start add service conversation (V2Ray, OpenVPN, Proxy)
        service_type = data.replace("admin_add_", "")
        context.user_data["servicetype"] = service_type
        await query.edit_message_text(f"🛰 لطفاً لینک، متن سرویس ({service_type}) را وارد کنید یا **فایل مربوطه را ارسال نمایید:**")
        return ADMIN_ADD_SERVICE
    elif data == "admin_broadcast":
        # Start broadcast conversation
        await query.edit_message_text("📢 پیام همگانی را ارسال کنید:")
        return ADMIN_BROADCAST
    elif data == "admin_chat_user":
        # Start admin chat conversation
        await query.edit_message_text("👥 لطفاً ID کاربر مورد نظر برای چت را وارد کنید:")
        return ADMIN_MESSAGE_USER

# Admin: List users (Remains similar, using Inline Keyboard)
async def list_pending_and_approve_reject(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    cursor.execute("SELECT id, username, phone_number, full_name, device_type FROM users WHERE is_approved=0")
    users = cursor.fetchall()
    
    if not users:
        await query.edit_message_text("✅ کاربر در انتظار تأیید/رد وجود ندارد.")
        return

    # Send messages to the admin chat directly
    for uid, uname, phone, name, device in users:
        btn_approve = InlineKeyboardButton("✅ تأیید", callback_data=f"approve_{uid}")
        btn_reject = InlineKeyboardButton("❌ رد", callback_data=f"reject_{uid}")
        btn_chat = InlineKeyboardButton("✉️ چت", callback_data=f"chat_user_{uid}")
        
        keyboard = InlineKeyboardMarkup([[btn_approve, btn_reject, btn_chat]])
        
        await context.bot.send_message(
            chat_id=ADMIN_ID, 
            text=f"درخواست از: @{uname} | ID: {uid}\nنام: {name or 'نامشخص'}\nشماره: {phone or 'نامشخص'}\nدستگاه: {device or 'نامشخص'}", 
            reply_markup=keyboard
        )

# Admin: Handle Approve/Reject/Chat callbacks
async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if '_' not in query.data:
        return

    action, uid_str = query.data.split("_")
    uid = int(uid_str)
    
    if action == "approve":
        cursor.execute("UPDATE users SET is_approved=1 WHERE id=?", (uid,))
        conn.commit()
        await query.edit_message_text(f"✅ کاربر {uid} تأیید شد.")
        await context.bot.send_message(chat_id=uid, text="اکانت شما توسط ادمین تأیید شد. اکنون می‌توانید از خدمات استفاده کنید.", reply_markup=get_main_inline_keyboard(False))
    
    elif action == "reject":
        cursor.execute("UPDATE users SET is_approved=0 WHERE id=?", (uid,)) 
        conn.commit()
        await query.edit_message_text(f"❌ کاربر {uid} رد شد.")
        await context.bot.send_message(chat_id=uid, text="متاسفانه درخواست شما توسط ادمین رد شد. لطفاً با پشتیبانی تماس بگیرید.")

    elif action == "chat_user":
        context.user_data['chat_target_user_id'] = uid
        await query.edit_message_text(f"✉️ در حال چت با کاربر {uid}. لطفاً پیام خود را ارسال کنید.")
        return ADMIN_MESSAGE_USER
    
    elif action == "send_service":
        return await admin_send_service_to_user(update, context)

# Admin: Deduct credit (ConversationHandler)
async def do_deduct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid, amount = update.message.text.strip().split()
        uid = int(uid)
        amount = int(amount)
        
        if amount <= 0:
            await update.message.reply_text("❌ مبلغ کسر باید مثبت باشد.")
            return ConversationHandler.END

        cursor.execute("SELECT credit FROM users WHERE id=?", (uid,))
        user_credit = cursor.fetchone()
        
        if not user_credit:
            await update.message.reply_text("❌ کاربر مورد نظر یافت نشد.")
            return ConversationHandler.END
        
        cursor.execute("UPDATE users SET credit = credit - ? WHERE id=?", (amount, uid))
        conn.commit()
        
        await update.message.reply_text("✅ اعتبار کاربر کسر شد.", reply_markup=get_admin_inline_keyboard())
        try:
            await context.bot.send_message(chat_id=uid, text=f"➖ {amount} تومان از اعتبار شما کسر شد.")
        except Exception as e:
            print(f"Error sending message to user {uid}: {e}")

    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ورودی یا عملیات: {e}")
    return ConversationHandler.END

# Admin: Chat with user (ConversationHandler)
async def admin_message_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_uid = context.user_data.get('chat_target_user_id')
    
    # If target_uid is not set yet, assume the input is the user ID (when initiated from admin_panel_callback_handler)
    if not target_uid:
        try:
            target_uid = int(update.message.text.strip())
            context.user_data['chat_target_user_id'] = target_uid
            await update.message.reply_text(f"لطفاً پیام خود را برای کاربر {target_uid} ارسال کنید:")
            return ADMIN_MESSAGE_USER
        except ValueError:
            await update.message.reply_text("❌ ID عددی نامعتبر است.")
            return ConversationHandler.END
    
    # If target_uid is set, this input is the message content
    message = update.message.text
    
    try:
        await context.bot.send_message(chat_id=target_uid, text=f"💬 پاسخ از ادمین:\n{message}")
        await update.message.reply_text("✅ پیام شما ارسال شد.", reply_markup=get_admin_inline_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ خطا در ارسال پیام به کاربر: {e}")
    
    del context.user_data['chat_target_user_id']
    return ConversationHandler.END

# Admin: Add Service (ConversationHandler)
async def save_service_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s_type = context.user_data["servicetype"]
    is_file_flag = 0 
    content_to_save = None

    if update.message.document: 
        content_to_save = update.message.document.file_id 
        is_file_flag = 1
        await update.message.reply_text(f"✅ فایل شما با File ID: `{content_to_save}` ذخیره شد.", parse_mode='Markdown', reply_markup=get_admin_inline_keyboard())
    elif update.message.text: 
        content_to_save = update.message.text.strip()
        is_file_flag = 0
        await update.message.reply_text("✅ سرویس متنی/لینک ذخیره شد.", reply_markup=get_admin_inline_keyboard())
    else: 
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فایل یا متن/لینک ارسال کنید.")
        return ConversationHandler.END 

    if content_to_save:
        cursor.execute("REPLACE INTO services (type, content, is_file) VALUES (?, ?, ?)", (s_type, content_to_save, is_file_flag))
        conn.commit()
    return ConversationHandler.END 

# Admin: Add Discount Code (ConversationHandler)
async def save_discount_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        code, val = update.message.text.strip().split()
        cursor.execute("INSERT INTO codes (code, value) VALUES (?, ?)", (code, int(val)))
        conn.commit()
        await update.message.reply_text("✅ کد اضافه شد.", reply_markup=get_admin_inline_keyboard())
    except:
        await update.message.reply_text("❌ فرمت اشتباه.")
    return ConversationHandler.END

# Admin: Charge User (ConversationHandler)
async def do_charge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        uid, amount = update.message.text.strip().split()
        cursor.execute("UPDATE users SET credit = credit + ? WHERE id=?", (int(amount), int(uid)))
        conn.commit()
        await update.message.reply_text("✅ شارژ شد.", reply_markup=get_admin_inline_keyboard())
    except:
        await update.message.reply_text("❌ خطا در ورودی.")
    return ConversationHandler.END

# Admin: Broadcast (ConversationHandler)
async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message.text
    cursor.execute("SELECT id FROM users")
    for (uid,) in cursor.fetchall():
        try:
            await context.bot.send_message(chat_id=uid, text=msg)
        except Exception as e: 
            print(f"Error sending broadcast to {uid}: {e}")
            continue
    await update.message.reply_text("📢 پیام ارسال شد.", reply_markup=get_admin_inline_keyboard())
    return ConversationHandler.END

# Admin: Send Service to User (triggered by admin action via inline button)
async def admin_send_service_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action, uid_str = query.data.split("_")
    uid = int(uid_str)
    
    context.user_data['target_user_id'] = uid
    
    await context.bot.send_message(
        chat_id=ADMIN_ID, 
        text=f"لطفاً فایل یا متن سرویس را برای کاربر {uid} ارسال کنید:"
    )
    return ADMIN_ADD_SERVICE_CONTENT_TO_USER

async def receive_service_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_uid = context.user_data.get('target_user_id')
    
    if not target_uid:
        await update.message.reply_text("❌ خطایی رخ داد. کاربر هدف مشخص نیست. لطفاً مجدداً تلاش کنید.")
        return ConversationHandler.END
    
    if update.message.document: # Admin sent a file
        content_to_send = update.message.document.file_id
        try:
            await context.bot.send_document(chat_id=target_uid, document=content_to_send, caption="✅ فایل سرویس شما:")
            await update.message.reply_text("✅ فایل سرویس با موفقیت برای کاربر ارسال شد.", reply_markup=get_admin_inline_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال فایل به کاربر: {e}")
            
    elif update.message.text: # Admin sent a text/link
        content_to_send = update.message.text.strip()
        try:
            await context.bot.send_message(chat_id=target_uid, text=f"✅ سرویس شما:\n{content_to_send}")
            await update.message.reply_text("✅ سرویس متنی با موفقیت برای کاربر ارسال شد.", reply_markup=get_admin_inline_keyboard())
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال پیام به کاربر: {e}")
            
    else:
        await update.message.reply_text("❌ ورودی نامعتبر. لطفاً فایل یا متن/لینک ارسال کنید.")
        return ADMIN_ADD_SERVICE_CONTENT_TO_USER
        
    return ConversationHandler.END 

# Function to cancel conversation
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "عملیات لغو شد.", reply_markup=get_main_inline_keyboard(update.effective_user.id == ADMIN_ID)
    )
    return ConversationHandler.END

# --- Main setup ---

def main():
    application = Application.builder().token(TOKEN).build()

    # --- Conversation Handlers ---

    # Registration Conversation Handler
    register_conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            REGISTER_PHONE: [MessageHandler(filters.CONTACT, register_phone_number)],
            REGISTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, register_name)],
            REGISTER_DEVICE: [CallbackQueryHandler(register_device, pattern="^register_device_")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        per_user=True
    )
    application.add_handler(register_conv_handler)

    # Main Callback Handler (handles all main menu inline buttons and cancellations)
    application.add_handler(CallbackQueryHandler(main_callback_handler, pattern="^(get_app|activate_discount|my_credit|transfer_credit|my_status|get_service|topup|support_message|admin_panel|main_menu|cancel_transfer|cancel_topup|cancel_support)$"))
    
    # App selection callback handler
    application.add_handler(CallbackQueryHandler(send_app_link, pattern="^app_"))
    
    # Service request callback handler
    application.add_handler(CallbackQueryHandler(send_service_request_to_admin, pattern="^request_service_"))
    
    # Discount Conversation Handler
    discount_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ASK_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, apply_discount)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(discount_conv_handler)

    # Transfer Conversation Handler
    transfer_conv_handler = ConversationHandler(
        entry_points=[],
        states={
            ASK_TARGET: [MessageHandler(filters.TEXT & ~filters.COMMAND, ask_amount)],
            ASK_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_transfer)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(transfer_conv_handler)

    # Topup Conversation Handler
    topup_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ASK_TOPUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_topup_request)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(topup_conv_handler)
    
    # Support Message Conversation Handler
    support_message_conv_handler = ConversationHandler(
        entry_points=[],
        states={ SUPPORT_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_support_message)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(support_message_conv_handler)

    # --- Admin Handlers ---
    
    # Admin Panel (handled by callback in main_callback_handler or /admin command)
    application.add_handler(CommandHandler("admin", admin))
    
    # Admin Panel Callback Handler (handles all admin inline buttons)
    application.add_handler(CallbackQueryHandler(admin_panel_callback_handler, pattern="^admin_"))
    
    # Admin Approval/Rejection/Chat/Send Service Callback Handler 
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern="^(approve_|reject_|chat_user_|send_service_)"))
    
    # Admin Add Service (Manual addition to DB)
    admin_add_service_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_ADD_SERVICE: [MessageHandler(filters.TEXT | filters.Document & ~filters.COMMAND, save_service_admin)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_add_service_conv_handler)

    # Admin Add Discount
    admin_add_discount_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_ADD_DISCOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, save_discount_code)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_add_discount_conv_handler)

    # Admin Charge User
    admin_charge_user_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_CHARGE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_charge)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_charge_user_conv_handler)

    # Admin Deduct Credit
    admin_deduct_credit_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_DEDUCT_CREDIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_deduct)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_deduct_credit_conv_handler)

    # Admin Broadcast
    admin_broadcast_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_broadcast)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_broadcast_conv_handler)

    # Admin Chat with User 
    admin_message_user_conv_handler = ConversationHandler(
        entry_points=[],
        states={ ADMIN_MESSAGE_USER: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_message_user)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_message_user_conv_handler)

    # Admin sends service to user flow 
    admin_send_service_flow_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(admin_send_service_to_user, pattern="^send_service_")],
        states={ ADMIN_ADD_SERVICE_CONTENT_TO_USER: [MessageHandler(filters.TEXT | filters.Document & ~filters.COMMAND, receive_service_content)]},
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    application.add_handler(admin_send_service_flow_handler)

    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
