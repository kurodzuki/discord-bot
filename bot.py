# -*- coding: utf-8 -*-
import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
import discord
from discord.ext import commands
from discord import app_commands
import websockets
import aiohttp

# ==================== 設定エリア ====================
# セキュリティのため、トークンは環境変数から取得するように変更しています
# 実行環境の環境変数に "DISCORD_TOKEN" としてトークンを設定してください
TOKEN = os.getenv("DISCORD_TOKEN", "YOUR_BOT_TOKEN_HERE")
CONFIG_FILE = "guild_configs.json"

# 開発中、特定のサーバーだけにスラッシュコマンドを即時反映させたい場合は
# 環境変数 "TEST_GUILD_ID" にサーバーIDを設定してください（未設定ならグローバル同期）
TEST_GUILD_ID = os.getenv("TEST_GUILD_ID")

# 起動前チェック：トークンが未設定なら分かりやすいメッセージで即終了する
if not TOKEN or TOKEN == "YOUR_BOT_TOKEN_HERE":
    raise SystemExit(
        "❌ DISCORD_TOKEN が設定されていません。\n"
        "実行環境の環境変数に DISCORD_TOKEN としてBotトークンを設定してください。"
    )

# 起動前チェック：VC常駐機能に必須の PyNaCl が入っているか確認する
try:
    import nacl  # noqa: F401
except ImportError:
    raise SystemExit(
        "❌ PyNaCl がインストールされていません。\n"
        "ボイスチャンネル接続に必須のライブラリです。`pip install pynacl` を実行してください。"
    )
# ====================================================

JMA_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) DiscordBot"}

PREFECTURE_CODES = {
    "北海道": "016000", "青森県": "020000", "岩手県": "030000", "宮城県": "040000",
    "秋田県": "050000", "山形県": "060000", "福島県": "070000", "茨城県": "080000",
    "栃木県": "090000", "群馬県": "100000", "埼玉県": "110000", "千葉県": "120000",
    "東京都": "130000", "神奈川県": "140000", "新潟県": "150000", "富山県": "160000",
    "石川県": "170000", "福井県": "180000", "山梨県": "190000", "長野県": "200000",
    "岐阜県": "210000", "静岡県": "220000", "愛知県": "230000", "三重県": "240000",
    "滋賀県": "250000", "京都府": "260000", "大阪府": "270000", "兵庫県": "280000",
    "奈良県": "290000", "和歌山県": "300000", "鳥取県": "310000", "島根県": "320000",
    "岡山県": "330000", "広島県": "340000", "山口県": "350000", "徳島県": "360000",
    "香川県": "370000", "愛媛県": "380000", "高知県": "390000", "福岡県": "400000",
    "佐賀県": "410000", "長崎県": "420000", "熊本県": "430000", "大分県": "440000",
    "宮崎県": "450000", "鹿児島県": "460100", "沖縄県": "471000"
}

PREFECTURE_AREAS = {
    "北海道": [{"area": "道央（札幌）", "lat": 43.0642, "lon": 141.3469}, {"area": "道南（函館）", "lat": 41.7687, "lon": 140.7288}, {"area": "道北（旭川）", "lat": 43.7706, "lon": 142.3648}, {"area": "道東（釧路）", "lat": 42.9849, "lon": 144.3817}, {"area": "オホーツク（網走）", "lat": 44.0210, "lon": 144.2697}],
    "青森県": [{"area": "津軽（青森）", "lat": 40.8244, "lon": 140.7400}, {"area": "下北（むつ）", "lat": 41.2941, "lon": 141.1804}, {"area": "三八上北（八戸）", "lat": 40.5122, "lon": 141.4871}],
    "岩手県": [{"area": "内陸（盛岡）", "lat": 39.7036, "lon": 141.1527}, {"area": "沿岸北部（宮古）", "lat": 39.6372, "lon": 141.9566}, {"area": "沿岸南部（大船渡）", "lat": 39.0827, "lon": 141.7161}],
    "宮城県": [{"area": "中部（仙台）", "lat": 38.2688, "lon": 140.8721}, {"area": "北部（石巻）", "lat": 38.4358, "lon": 141.3053}, {"area": "南部（白石）", "lat": 38.0039, "lon": 140.6192}],
    "秋田県": [{"area": "沿岸中部（秋田）", "lat": 39.7186, "lon": 140.1024}, {"area": "沿岸北部（能代）", "lat": 40.2081, "lon": 140.0264}, {"area": "内陸南部（横手）", "lat": 39.3134, "lon": 140.5594}],
    "山形県": [{"area": "村山（山形）", "lat": 38.2404, "lon": 140.3636}, {"area": "庄内（酒田）", "lat": 38.9189, "lon": 139.8322}, {"area": "置賜（米沢）", "lat": 37.9157, "lon": 140.1162}],
    "福島県": [{"area": "中通り（福島）", "lat": 37.7500, "lon": 140.4677}, {"area": "浜通り（いわき）", "lat": 37.0503, "lon": 140.8877}, {"area": "会津（会津若松）", "lat": 37.5029, "lon": 139.9272}],
    "茨城県": [{"area": "県央（水戸）", "lat": 36.3418, "lon": 140.4468}, {"area": "県北（日立）", "lat": 36.5996, "lon": 140.6517}, {"area": "鹿行（鹿嶋）", "lat": 35.9691, "lon": 140.6403}, {"area": "県西（筑西）", "lat": 36.3039, "lon": 139.9814}],
    "栃木県": [{"area": "南部（宇都宮）", "lat": 36.5658, "lon": 139.8836}, {"area": "北部（大田原）", "lat": 36.8722, "lon": 140.0125}],
    "群馬県": [{"area": "南部（前橋）", "lat": 36.3911, "lon": 139.0608}, {"area": "北部（沼田）", "lat": 36.6489, "lon": 139.0436}],
    "埼玉県": [{"area": "南部（さいたま）", "lat": 35.8569, "lon": 139.6489}, {"area": "北部（熊谷）", "lat": 36.1475, "lon": 139.3886}, {"area": "秩父地方（秩父）", "lat": 35.9986, "lon": 139.0833}],
    "千葉県": [{"area": "北西部（千葉）", "lat": 35.6046, "lon": 140.1233}, {"area": "北東部（銚子）", "lat": 35.7342, "lon": 140.8267}, {"area": "南部（館山）", "lat": 34.9897, "lon": 139.8592}],
    "東京都": [{"area": "東京地方（東京）", "lat": 35.6895, "lon": 139.6917}, {"area": "伊豆諸島（大島）", "lat": 34.7761, "lon": 139.3608}, {"area": "小笠原（父島）", "lat": 27.0956, "lon": 142.2158}],
    "神奈川県": [{"area": "東部（横浜）", "lat": 35.4475, "lon": 139.6425}, {"area": "西部（小田原）", "lat": 35.2525, "lon": 139.1578}],
    "新潟県": [{"area": "下越（新潟）", "lat": 37.9161, "lon": 139.0364}, {"area": "中越（長岡）", "lat": 37.4475, "lon": 138.8511}, {"area": "上越（高田）", "lat": 37.1144, "lon": 138.2528}, {"area": "佐渡（相川）", "lat": 38.0289, "lon": 138.2447}],
    "富山県": [{"area": "東部（富山）", "lat": 36.6953, "lon": 137.2113}, {"area": "西部（高岡）", "lat": 36.7453, "lon": 137.0169}],
    "石川県": [{"area": "加賀（金沢）", "lat": 36.5946, "lon": 136.6256}, {"area": "能登（輪島）", "lat": 37.3942, "lon": 136.9031}],
    "福井県": [{"area": "嶺北（福井）", "lat": 36.0652, "lon": 136.2219}, {"area": "嶺南（敦賀）", "lat": 35.6528, "lon": 136.0717}],
    "山梨県": [{"area": "中銀・峡中（甲府）", "lat": 35.6639, "lon": 138.5684}, {"area": "富士五湖（河口湖）", "lat": 35.5039, "lon": 138.7583}],
    "長野県": [{"area": "北部（長野）", "lat": 36.6513, "lon": 138.1810}, {"area": "中部（松本）", "lat": 36.2381, "lon": 137.9720}, {"area": "南部（飯田）", "lat": 35.5136, "lon": 137.8286}],
    "岐阜県": [{"area": "美濃地方（岐阜）", "lat": 35.3912, "lon": 136.7223}, {"area": "飛騨地方（高山）", "lat": 36.1458, "lon": 137.2514}],
    "静岡県": [{"area": "中部（静岡）", "lat": 34.9769, "lon": 138.3831}, {"area": "東部（三島）", "lat": 35.1261, "lon": 138.9147}, {"area": "伊豆（下田）", "lat": 34.6789, "lon": 138.9481}, {"area": "西部（浜松）", "lat": 34.7108, "lon": 137.7261}],
    "愛知県": [{"area": "尾張（名古屋）", "lat": 35.1815, "lon": 136.9066}, {"area": "三河西部（岡崎）", "lat": 34.9567, "lon": 137.1614}, {"area": "三河東部（豊橋）", "lat": 34.7692, "lon": 137.3919}],
    "三重県": [{"area": "中勢（津）", "lat": 34.7303, "lon": 136.5086}, {"area": "北勢（四日市）", "lat": 34.9647, "lon": 136.6214}, {"area": "南勢（伊勢）", "lat": 34.4925, "lon": 136.7078}, {"area": "伊賀（上野）", "lat": 34.7672, "lon": 136.1267}],
    "滋賀県": [{"area": "南部（大津）", "lat": 35.0045, "lon": 135.8685}, {"area": "北部（彦根）", "lat": 35.2764, "lon": 136.2508}],
    "京都府": [{"area": "南部（京都）", "lat": 35.0213, "lon": 135.7556}, {"area": "北部（舞鶴）", "lat": 35.4747, "lon": 135.3917}],
    "大阪府": [{"area": "大阪（大阪）", "lat": 34.6937, "lon": 135.5022}],
    "兵庫県": [{"area": "南部（神戸）", "lat": 34.6913, "lon": 135.1830}, {"area": "北部（豊岡）", "lat": 35.5464, "lon": 134.8181}],
    "奈良県": [{"area": "北部（奈良）", "lat": 34.6851, "lon": 135.8328}, {"area": "南部（五條）", "lat": 34.3522, "lon": 135.6989}],
    "和歌山県": [{"area": "北部（和歌山）", "lat": 34.2260, "lon": 135.1675}, {"area": "南部（潮岬）", "lat": 33.4397, "lon": 135.7622}],
    "鳥取県": [{"area": "東部（鳥取）", "lat": 35.5036, "lon": 134.2383}, {"area": "西部（米子）", "lat": 35.4267, "lon": 133.3253}],
    "島根県": [{"area": "東部（松江）", "lat": 35.4723, "lon": 133.0505}, {"area": "西部（浜田）", "lat": 34.8986, "lon": 132.0792}, {"area": "隠岐（西郷）", "lat": 36.2056, "lon": 133.3253}],
    "岡山県": [{"area": "南部（岡山）", "lat": 34.6618, "lon": 133.9350}, {"area": "北部（真庭・津山）", "lat": 35.0647, "lon": 134.0050}],
    "広島県": [{"area": "南部（広島）", "lat": 34.3853, "lon": 132.4553}, {"area": "北部（庄原）", "lat": 34.8528, "lon": 133.0181}],
    "山口県": [{"area": "中部（山口）", "lat": 34.1859, "lon": 131.4714}, {"area": "西部（下関）", "lat": 33.9511, "lon": 130.9458}, {"area": "東部（周南）", "lat": 34.0531, "lon": 131.8028}],
    "徳島県": [{"area": "北部（徳島）", "lat": 34.0658, "lon": 134.5594}, {"area": "南部（日和佐）", "lat": 33.7317, "lon": 134.5358}],
    "香川県": [{"area": "東讃（高松）", "lat": 34.3401, "lon": 134.0434}, {"area": "西讃（多度津）", "lat": 34.2708, "lon": 133.7483}],
    "愛媛県": [{"area": "中予（松山）", "lat": 33.8416, "lon": 132.7661}, {"area": "東予（新居浜）", "lat": 33.9575, "lon": 133.2847}, {"area": "南予（宇和島）", "lat": 33.2225, "lon": 132.5647}],
    "高知県": [{"area": "中部（高知）", "lat": 33.5597, "lon": 133.5311}, {"area": "西部（室戸岬）", "lat": 33.2536, "lon": 134.1758}, {"area": "西南部（宿毛）", "lat": 32.9372, "lon": 132.7303}],
    "福岡県": [{"area": "福岡地方", "lat": 33.5902, "lon": 130.4017}, {"area": "北九州地方", "lat": 33.8834, "lon": 130.8752}, {"area": "筑豊地方", "lat": 33.6433, "lon": 130.6822}, {"area": "筑後地方", "lat": 33.3213, "lon": 130.5847}],
    "佐賀県": [{"area": "南部（佐賀）", "lat": 33.2494, "lon": 130.2989}, {"area": "北部（唐津）", "lat": 33.4478, "lon": 129.9722}],
    "長崎県": [{"area": "南部（長崎）", "lat": 32.7448, "lon": 129.8737}, {"area": "北部（佐世保）", "lat": 33.1794, "lon": 129.7153}, {"area": "壱岐・対馬（厳原）", "lat": 34.2039, "lon": 129.2936}, {"area": "五島（福江）", "lat": 32.6958, "lon": 128.8436}],
    "熊本県": [{"area": "熊本地方（熊本）", "lat": 32.7898, "lon": 130.7417}, {"area": "阿蘇地方（阿蘇）", "lat": 32.9367, "lon": 131.0775}, {"area": "天草・芦北（牛深）", "lat": 32.2033, "lon": 130.0264}, {"area": "球磨地方（人吉）", "lat": 32.2114, "lon": 130.7719}],
    "大分県": [{"area": "中部（大分）", "lat": 33.2382, "lon": 131.6126}, {"area": "北部（中津）", "lat": 33.5956, "lon": 131.1850}, {"area": "西部（日田）", "lat": 33.3228, "lon": 130.9322}, {"area": "南部（佐伯）", "lat": 32.9619, "lon": 131.8997}],
    "宮崎県": [{"area": "南部（宮崎）", "lat": 31.9111, "lon": 131.4239}, {"area": "北部平野部（延岡）", "lat": 32.5825, "lon": 131.6667}, {"area": "西部（都城）", "lat": 31.7214, "lon": 131.0594}],
    "鹿児島県": [{"area": "薩摩（鹿児島）", "lat": 31.5602, "lon": 130.5581}, {"area": "大隅（鹿屋）", "lat": 31.3789, "lon": 130.8525}, {"area": "種子島・屋久島（西之表）", "lat": 30.7350, "lon": 130.9983}, {"area": "奄美地方（名瀬）", "lat": 28.3756, "lon": 129.4939}],
    "沖縄県": [{"area": "本島中南部（那覇）", "lat": 26.2124, "lon": 127.6809}, {"area": "本島北部（名護）", "lat": 26.5917, "lon": 127.9772}, {"area": "宮古島地方（平良）", "lat": 24.8058, "lon": 125.2814}, {"area": "八重山地方（石垣島）", "lat": 24.3361, "lon": 124.1611}]
}

def translate_weather(code):
    weather_map = {
        0: "快晴", 1: "晴れ", 2: "一部曇り", 3: "曇り",
        45: "霧", 48: "霧氷", 51: "霧雨", 53: "霧雨", 55: "強い霧雨",
        56: "着氷性の霧雨", 57: "強い着氷性の霧雨",
        61: "小雨", 63: "雨", 65: "強い雨", 66: "冷たい雨", 67: "強い冷たい雨",
        71: "小雪", 73: "雪", 75: "強い雪", 77: "霧雪",
        80: "にわか雨", 81: "強いにわか雨", 82: "激しいにわか雨",
        85: "にわか雪", 86: "強いにわか雪",
        95: "雷雨", 96: "雷雨（ひょう伴う）", 99: "激しい雷雨（ひょう伴う）"
    }
    return weather_map.get(int(code), "不明")

def load_configs():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_configs(configs):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(configs, f, ensure_ascii=False, indent=4)

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.guild_messages = True
intents.voice_states = True

bot = commands.Bot(command_prefix="!", intents=intents)

running_tasks = []

@bot.event
async def on_ready():
    print(f"ログインしました: {bot.user.name} (ID: {bot.user.id})")
    try:
        if TEST_GUILD_ID:
            guild_obj = discord.Object(id=int(TEST_GUILD_ID))
            bot.tree.copy_global_to(guild=guild_obj)
            synced = await bot.tree.sync(guild=guild_obj)
            print(f"スラッシュコマンドをテストサーバーに同期しました: {len(synced)}個（即時反映）")
        else:
            synced = await bot.tree.sync()
            print(f"スラッシュコマンドをグローバル同期しました: {len(synced)}個（反映まで最大1時間かかる場合があります）")
    except Exception as e:
        print(f"コマンドの同期に失敗しました: {e}")
        print("→ Discord Developer PortalでBotに必要な権限・インテントが有効か確認してください。")
    
    await connect_saved_voices()

    global running_tasks
    if not running_tasks:
        running_tasks = [
            bot.loop.create_task(monitor_disaster_api()),
            bot.loop.create_task(maintain_voice_connection(bot))
        ]
        print("🚀 すべてのバックグラウンドタスクが正常に起動しました！")

async def connect_saved_voices():
    configs = load_configs()
    for guild_id_str, data in configs.items():
        guild = bot.get_guild(int(guild_id_str))
        if not guild:
            continue
        vc_id = data.get("voice_channel_id")
        if not vc_id:
            continue
        vc_channel = guild.get_channel(vc_id)
        if vc_channel and isinstance(vc_channel, discord.VoiceChannel):
            try:
                if not guild.voice_client or not guild.voice_client.is_connected():
                    await vc_channel.connect()
                    print(f"[{guild.name}] 保存されていたVCに接続しました: {vc_channel.name}")
            except Exception as e:
                print(f"[{guild.name}] 起動時VC接続エラー: {e}")

# ==================== P2P地震情報 WebSocket 監視タスク ====================
async def monitor_disaster_api():
    """P2P地震情報API (WebSocket) に常時接続し、地震情報を各サーバーの通知チャンネルへ送信する"""
    await bot.wait_until_ready()
    uri = "wss://api.p2pquake.net/v2/ws"
    
    while not bot.is_closed():
        try:
            print("地震情報API (P2PQuake) に接続を試みています...")
            async with websockets.connect(uri) as websocket:
                print("地震情報APIに接続しました！リアルタイム監視中...")
                async for message in websocket:
                    try:
                        data = json.loads(message)
                        if data.get("code") == 551:
                            earthquake = data.get("earthquake", {})
                            hypocenter = earthquake.get("hypocenter", {})
                            scale = earthquake.get("maxScale", -1)
                            
                            place = hypocenter.get("name", "不明")
                            magnitude = hypocenter.get("magnitude", "-")
                            max_scale_str = translate_p2p_scale(scale)
                            
                            embed = discord.Embed(
                                title="🚨 地震情報（速報）",
                                color=discord.Color.red() if scale >= 40 else discord.Color.orange(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            embed.add_field(name="震源地", value=place, inline=True)
                            embed.add_field(name="最大震度", value=max_scale_str, inline=True)
                            embed.add_field(name="規模 (M)", value=str(magnitude), inline=True)
                            
                            configs = load_configs()
                            for guild_id_str, cfg in configs.items():
                                t_id = cfg.get("text_channel_id")
                                if t_id:
                                    guild = bot.get_guild(int(guild_id_str))
                                    if guild:
                                        channel = guild.get_channel(t_id)
                                        if channel:
                                            try:
                                                await channel.send(embed=embed)
                                            except Exception as e:
                                                print(f"地震通知送信エラー [{guild.name}]: {e}")
                                                
                    except Exception as inner_e:
                        print(f"地震メッセージ解析エラー: {inner_e}")
                        
        except (websockets.ConnectionClosed, asyncio.TimeoutError):
            print("地震情報APIとの接続が切れました。5秒後に再接続します...")
            await asyncio.sleep(5)
        except Exception as e:
            print(f"地震情報WebSocketエラー: {e}")
            await asyncio.sleep(10)

def translate_p2p_scale(scale):
    scale_map = {
        10: "震度1", 20: "震度2", 30: "震度3", 40: "震度4",
        45: "震度5弱", 50: "震度5強", 55: "震度6弱", 60: "震度6強", 70: "震度7"
    }
    return scale_map.get(scale, "不明")

@bot.tree.command(name="setup", description="このサーバーでの通知用テキストチャンネルと常駐するボイスチャンネルを設定します")
async def setup_server(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    
    guild = interaction.guild
    if not guild:
        await interaction.edit_original_response(content="サーバー内で実行してください。")
        return

    if not interaction.user.voice or not interaction.user.voice.channel:
        await interaction.edit_original_response(content="あらかじめ常駐させたいボイスチャンネルに入った状態でコマンドを実行してください！")
        return

    text_channel_id = interaction.channel.id
    voice_channel_id = interaction.user.voice.channel.id

    configs = load_configs()
    configs[str(guild.id)] = {
        "text_channel_id": text_channel_id,
        "voice_channel_id": voice_channel_id
    }
    save_configs(configs)

    vc_channel = guild.get_channel(voice_channel_id)
    if vc_channel:
        try:
            if guild.voice_client:
                await guild.voice_client.move_to(vc_channel)
            else:
                await vc_channel.connect()
        except Exception as e:
            await interaction.edit_original_response(
                content=f"⚠️ 設定は保存しましたが、VCへの接続に失敗しました: {e}"
            )
            return

        await interaction.edit_original_response(
            content=f"✅ 設定を保存しました！\n"
                    f"・通知チャンネル: <#{text_channel_id}>\n"
                    f"・常駐VC: {vc_channel.name}"
        )
    else:
        await interaction.edit_original_response(
            content="⚠️ 設定は保存しましたが、ボイスチャンネルが見つかりませんでした。"
        )

async def maintain_voice_connection(bot):
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            configs = load_configs()
            for guild_id_str, data in configs.items():
                guild = bot.get_guild(int(guild_id_str))
                if not guild:
                    continue
                
                vc_id = data.get("voice_channel_id")
                if not vc_id:
                    continue
                
                vc_channel = guild.get_channel(vc_id)
                if vc_channel and isinstance(vc_channel, discord.VoiceChannel):
                    if not guild.voice_client or not guild.voice_client.is_connected():
                        try:
                            await vc_channel.connect()
                        except Exception as e:
                            print(f"[{guild.name}] VC接続エラー: {e}")
                    elif guild.voice_client.channel.id != vc_id:
                        await guild.voice_client.move_to(vc_channel)
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"VC維持ループエラー: {e}")
        
        await asyncio.sleep(30)

@bot.tree.command(name="bot_start", description="バックグラウンドタスクを再起動します")
async def start_monitoring(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    global running_tasks
    for task in running_tasks:
        task.cancel()
    running_tasks.clear()

    running_tasks = [
        bot.loop.create_task(monitor_disaster_api()),
        bot.loop.create_task(maintain_voice_connection(bot))
    ]
    await interaction.edit_original_response(content="バックグラウンドタスクを再起動しました！")

@bot.tree.command(name="stop", description="このサーバーでのVC常駐を解除し、タスクを停止します")
async def stop_monitoring(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=False)
    guild = interaction.guild
    if guild and guild.voice_client:
        await guild.voice_client.disconnect()

    configs = load_configs()
    if guild and str(guild.id) in configs:
        del configs[str(guild.id)]
        save_configs(configs)

    await interaction.edit_original_response(content="このサーバーのVCから切断し、設定を解除しました。")

# ==================== 天気・警報・地震のコマンド ====================
@bot.tree.command(name="weather", description="指定した都道府県の地方別天気予報を一括表示します")
@app_commands.describe(prefecture="調べたい都道府県名（例: 福岡県、東京都）")
async def cmd_weather_prefecture(interaction: discord.Interaction, prefecture: str):
    await interaction.response.defer(ephemeral=False)

    if prefecture not in PREFECTURE_AREAS:
        await interaction.edit_original_response(content=f"「{prefecture}」は見つかりませんでした。正しい都道府県名を入力してください。")
        return

    embed = discord.Embed(title=f"🌤️ {prefecture} の天気予報", color=discord.Color.blue(), timestamp=datetime.now(timezone.utc))
    areas = PREFECTURE_AREAS[prefecture]
    
    async with aiohttp.ClientSession() as session:
        for area_info in areas:
            lat = area_info["lat"]
            lon = area_info["lon"]
            area_name = area_info["area"]
            
            url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current_weather=true"
            try:
                async with session.get(url) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current_weather", {})
                        temp = current.get("temperature", "不明")
                        weather_code = current.get("weathercode", -1)
                        weather_text = translate_weather(weather_code)
                        
                        embed.add_field(
                            name=area_name,
                            value=f"天気: {weather_text}\n気温: {temp}℃",
                            inline=True
                        )
            except Exception as e:
                print(f"天気の取得に失敗しました [{area_name}]: {e}")
                
    await interaction.edit_original_response(embed=embed)

# ボットの起動
if __name__ == "__main__":
    bot.run(TOKEN)