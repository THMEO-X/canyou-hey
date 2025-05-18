import discord
from discord.ext import commands
import google.generativeai as genai
import openai
import requests
import os
import json
import storage
from flask import Flask
from threading import Thread
import random

# === Web server giữ bot sống cho UptimeRobot ===
app = Flask('')

@app.route('/')
def home():
    return "Bot is alive!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

# === Lấy API keys từ biến môi trường ===
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ID bạn (owner bot)
AUTHORIZED_USER_ID = 1299386568712392765

# === Cấu hình AI ===
openai.api_key = OPENAI_API_KEY
genai.configure(api_key=GOOGLE_API_KEY)
gemini_model = genai.GenerativeModel("models/gemini-1.5-flash")

# === Cấu hình Discord bot ===
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

STATE_FILE = "channels.json"

def load_channels():
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_channels():
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(monitored_channels, f, ensure_ascii=False, indent=2)

monitored_channels = load_channels()

# === Hàm kiểm tra quyền dùng lệnh !start và !stop ===
def can_use_owner_command(ctx):
    # Cho phép nếu là bạn hoặc chủ server
    if ctx.author.id == AUTHORIZED_USER_ID:
        return True
    if isinstance(ctx.channel, discord.DMChannel):
        # Không có server owner trong DM, chỉ bạn được dùng
        return False
    guild = ctx.guild
    if guild is None:
        return False
    if ctx.author == guild.owner:
        return True
    return False

# === Lệnh bật AI cho channel ===
@bot.command()
async def start(ctx, channel_id: int):
    if not can_use_owner_command(ctx):
        await ctx.send("Bạn không có quyền")
        return
    channel = bot.get_channel(channel_id)
    if channel is None:
        await ctx.send("Không tìm thấy kênh kkk")
        return
    monitored_channels[str(channel_id)] = True
    save_channels()
    await ctx.send(f"AI start <#{channel_id}>.")

# === Lệnh tắt AI cho channel ===
@bot.command()
async def stop(ctx, channel_id: int):
    if not can_use_owner_command(ctx):
        await ctx.send("không có quyền sử dụng lệnh ")
        return
    if str(channel_id) in monitored_channels:
        del monitored_channels[str(channel_id)]
        save_channels()
        await ctx.send(f" stop AI  <#{channel_id}>.")
    else:
        await ctx.send("Kênh chưa được bật AI.")

# === Lệnh !help hiển thị rõ ràng các nhóm lệnh ===
@bot.command()
async def help(ctx):
    embed = discord.Embed(title="Hướng dẫn sử dụng Bot", color=discord.Color.blue())

    embed.add_field(name="Owner Server Commands", value=(
        "`!start <channel_id>` - Bật AI cho kênh\n"
        "`!stop <channel_id>` - Tắt AI cho kênh"
    ), inline=False)

    embed.add_field(name="Member Commands", value=(
        "`!anh <mô tả>` - Tạo ảnh theo mô tả bằng AI"
    ), inline=False)

    await ctx.send(embed=embed)

# === Lệnh !anh tạo ảnh bằng OpenAI ===
@bot.command()
async def anh(ctx, *, prompt: str):
    await ctx.trigger_typing()
    try:
        response = openai.Image.create(
            prompt=prompt,
            n=1,
            size="512x512"
        )
        image_url = response['data'][0]['url']
        await ctx.send(f"Đây là ảnh bạn yêu cầu:\n{image_url}")
    except Exception as e:
        await ctx.send("Đã xảy ra lỗi khi tạo ảnh.")
        print("Lỗi tạo ảnh:", e)

# === Lệnh !server chỉ bạn dùng, không hiển thị trong !help ===
@bot.command()
async def server(ctx):
    if ctx.author.id != AUTHORIZED_USER_ID:
        await ctx.send("Bạn không có quyền sử dụng lệnh này.")
        return
    guild_names = [guild.name for guild in bot.guilds]
    msg = "Bot đang hoạt động trên các server:\n" + "\n".join(guild_names)
    await ctx.send(msg)

# === Hàm gọi AI và chọn câu trả lời theo yêu cầu mới ===
async def generate_best_response(prompt, guild: discord.Guild = None):
    responses = []

    prompt_full = (
        f"Trả lời dễ hiểu, có thể dài hoặc ngắn tùy trường hợp, "
        f"có thể kết hợp với các emoji. "
        f"Giả sử đang trò chuyện trong server Discord "
        f"'{guild.name if guild else 'Unknown Server'}'. "
        f"Dùng điểm mạnh của bản thân để trả lời một cách logic, thân thiện và không gây nhàm chán.\n{prompt}"
    )

    # Gemini
    try:
        gemini_result = gemini_model.generate_content(prompt_full)
        if gemini_result.text:
            responses.append(gemini_result.text.strip())
    except Exception as e:
        print("Gemini lỗi:", e)

    # GPT
    try:
        gpt_result = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt_full}],
            temperature=0.7
        )
        responses.append(gpt_result["choices"][0]["message"]["content"].strip())
    except Exception as e:
        print("GPT lỗi:", e)

    # Groq
    try:
        url = "https://api.groq.com/openai/v1/chat/completions"
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json"
        }
        data = {
            "model": "llama3-8b-8192",
            "messages": [{"role": "user", "content": prompt_full}],
            "temperature": 0.7
        }
        groq_response = requests.post(url, headers=headers, json=data)
        groq_text = groq_response.json()["choices"][0]["message"]["content"]
        responses.append(groq_text.strip())
    except Exception as e:
        print("Groq lỗi:", e)

    if not responses:
        return "Tôi chưa thể trả lời câu hỏi này."

    # Chọn câu trả lời ngắn nhất hoặc ít dấu "..."
    best = min(responses, key=lambda x: len(x) + x.count("..."))
    return best

# === Danh sách emoji server lấy ngẫu nhiên để thỉnh thoảng bot dùng ===
def random_server_emoji(guild: discord.Guild):
    if not guild or not guild.emojis:
        return ""
    # Lấy emoji random có thể dùng
    valid_emojis = [str(e) for e in guild.emojis if e.is_usable()]
    if not valid_emojis:
        return ""
    return random.choice(valid_emojis)

# === Xử lý tin nhắn vào các channel được bật AI ===
@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Kiểm tra channel có được bật AI không
    if str(message.channel.id) in monitored_channels:
        try:
            user_input = message.content

            async with message.channel.typing():
                reply = await generate_best_response(user_input, message.guild)

            # Thỉnh thoảng bot gửi emoji cho vui, không spam
            emoji = ""
            if random.random() < 0.15:  # 15% chance gửi emoji
                emoji = random_server_emoji(message.guild)
                if emoji:
                    reply = f"{emoji} {reply}"

            await message.channel.send(reply)

            # Lưu lịch sử chat
            history = storage.get("history", [])
            history.append({
                "user": str(message.author),
                "channel_id": message.channel.id,
                "question": user_input,
                "answer": reply
            })
            storage.set("history", history[-50:])  # Lưu tối đa 50 dòng

        except Exception as e:
            print(f"Lỗi: {e}")
            await message.channel.send("⚠️ Đã xảy ra lỗi khi tạo phản hồi.")

    await bot.process_commands(message)

# === Khi bot sẵn sàng ===
@bot.event
async def on_ready():
    print(f"Bot đã đăng nhập với tên {bot.user.name}")

# === Khởi động webserver và bot ===
keep_alive()
bot.run(DISCORD_TOKEN)