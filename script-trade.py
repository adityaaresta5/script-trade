import imaplib
import email
from email.header import decode_header
import re
import time
import MetaTrader5 as mt5

# Konfigurasi Email
EMAIL = "youremail"  # Ganti dengan email Anda
PASSWORD = "yourpassword"      # Ganti dengan password atau App Password
IMAP_SERVER = "imap.gmail.com"  # Ganti jika menggunakan penyedia email lain

# Konfigurasi MetaTrader5
SYMBOL = "XAUUSDm"  # Simbol trading (contoh: XAUUSDm)
LOT_SIZE = 0.1    # Ukuran lot
DEVIATION = 10      # Deviasi harga

# Variabel global untuk koneksi IMAP
mail = None

def initialize_mt5():
    """Initialize MetaTrader5."""
    if not mt5.initialize():
        print("Initialize() failed, error code =", mt5.last_error())
        quit()

def connect_to_email():
    """Connect to the IMAP server and log in."""
    global mail
    try:
        # Koneksi ke server IMAP
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        
        # Login ke email
        mail.login(EMAIL, PASSWORD)
        print("✅ Login to email successful")
        
        # Pilih folder inbox
        mail.select("inbox")
    except imaplib.IMAP4.error as e:
        print(f"❌ Failed to login to email: {e}")
        quit()
    except Exception as e:
        print(f"Error connecting to email: {e}")
        quit()

def reconnect_if_needed():
    """Reconnect to the IMAP server if connection is lost."""
    global mail
    try:
        mail.noop()  # Ping server to check connection
    except:
        print("Connection lost. Reconnecting to email server...")
        connect_to_email()

def read_new_emails():
    try:
        # Pastikan koneksi IMAP aktif
        reconnect_if_needed()

        # Cari email baru yang belum dibaca (UNSEEN) dari noreply@tradingview.com
        status, messages = mail.search(None, '(FROM "noreply@tradingview.com" UNSEEN)')
        email_ids = messages[0].split()

        if not email_ids:
            return  # Tidak ada email baru, keluar tanpa mencetak apa pun

        print(f"Found {len(email_ids)} new email(s) from TradingView. Processing...")

        for num in email_ids:
            status, msg_data = mail.fetch(num, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])

                    # Parsing isi email
                    if msg.is_multipart():
                        for part in msg.walk():
                            content_type = part.get_content_type()
                            if content_type == "text/plain":
                                body = part.get_payload(decode=True)
                                # Coba decode body dengan utf-8, fallback ke latin-1 jika gagal
                                try:
                                    body = body.decode("utf-8")
                                except UnicodeDecodeError:
                                    body = body.decode("latin-1", errors="ignore")
                                process_signal(body)
                    else:
                        body = msg.get_payload(decode=True)
                        # Coba decode body dengan utf-8, fallback ke latin-1 jika gagal
                        try:
                            body = body.decode("utf-8")
                        except UnicodeDecodeError:
                            body = body.decode("latin-1", errors="ignore")
                        process_signal(body)

    except Exception as e:
        print(f"Error reading emails: {e}")

def process_signal(email_body):
    try:
        # Filter email berdasarkan isi body
        if "Your XAUUSD alert was triggered" in email_body:
            # Ekstrak data menggunakan regex
            match = re.search(r"order (\w+) @ (\d+\.?\d*)", email_body)
            if match:
                direction = match.group(1).upper()  # BUY atau SELL
                price = float(match.group(2))       # Harga

                # Cek apakah ini EXIT (posisi menjadi 0)
                if "New strategy position is 0" in email_body:
                    print(f"🚨 EXIT SIGNAL DETECTED: Closing {direction} position at price {price}")
                    execute_exit(direction, price)
                else:
                    print(f"🚨 ENTRY SIGNAL DETECTED: Opening {direction} position at price {price}")
                    execute_entry(direction, price)
    except Exception as e:
        print(f"Error processing signal: {e}")

def execute_entry(direction, price):
    try:
        # Kirim order entry ke MT5
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": LOT_SIZE,
            "type": 0 if direction == "BUY" else 1,  # 0 = BUY, 1 = SELL
            "price": mt5.symbol_info_tick(SYMBOL).ask if direction == "BUY" else mt5.symbol_info_tick(SYMBOL).bid,
            "deviation": DEVIATION,
            "magic": 123456,
            "comment": "Python Entry",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to execute entry trade: {result.comment}")
        else:
            print(f"Entry trade executed successfully: {result}")
    except Exception as e:
        print(f"Error executing entry trade: {e}")

def execute_exit(direction, price):
    try:
        # Dapatkan posisi saat ini
        positions = mt5.positions_get(symbol=SYMBOL)
        if not positions:
            print("No open positions to close.")
            return
        position = positions[0]
        lot_size = position.volume

        # Kirim order exit ke MT5
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": SYMBOL,
            "volume": lot_size,
            "type": 0 if position.type == 1 else 1,  # 0 = BUY, 1 = SELL
            "position": position.ticket,
            "price": mt5.symbol_info_tick(SYMBOL).ask if position.type == 1 else mt5.symbol_info_tick(SYMBOL).bid,
            "deviation": DEVIATION,
            "magic": 123456,
            "comment": "Python Exit",
            "type_time": mt5.ORDER_TIME_GTC,
        }
        result = mt5.order_send(request)
        if result.retcode != mt5.TRADE_RETCODE_DONE:
            print(f"Failed to execute exit trade: {result.comment}")
        else:
            print(f"Exit trade executed successfully: {result}")
    except Exception as e:
        print(f"Error executing exit trade: {e}")

# Main loop to monitor emails and execute trades
if __name__ == "__main__":
    # Initialize MetaTrader5
    initialize_mt5()

    # Connect to email
    connect_to_email()

    while True:
        # Proses email baru tanpa mencetak pesan jika tidak ada email baru
        read_new_emails()
        time.sleep(1)  # Check every 1 seconds
