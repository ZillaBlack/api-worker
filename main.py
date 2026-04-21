from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import stripe
import redis
import os
from datetime import datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Chaves vêm do ambiente (seguro)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
REDIS_URL = os.getenv("REDIS_URL")

# Validação
for key, name in [(STRIPE_SECRET_KEY, "STRIPE_SECRET_KEY"), 
                  (STRIPE_WEBHOOK_SECRET, "STRIPE_WEBHOOK_SECRET"),
                  (REDIS_URL, "REDIS_URL")]:
    if not key:
        raise Exception(f"ERRO: {name} não configurada")

stripe.api_key = STRIPE_SECRET_KEY
redis_client = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# Mapeamento de produtos
PRODUCT_MAP = {
    "price_6oU5kD8hReh0alN2Wy8k80d": "Over Limite FT",
    "price_28E3cvdCbc8SctV2Wy8k80e": "Over Limite FT",
    "price_dRm6oH2XxdcWalN7cO8k80f": "Over Limite FT",
    "price_bJecN52Xx8WG9hJeFg8k80g": "Over Limite FT",
    "price_5kQ14nbu38WG65xbt48k80h": "Quero Gol",
    "price_4gM3cv2Xxa0K2Tl8gS8k80i": "Quero Gol",
    "price_9B64gz7dN3CmdxZdBc8k80j": "Quero Gol",
    "price_eVq00jdCbdcW8dFdBc8k80k": "Quero Gol",
    "price_4gMaEXapZ1ue0Ld7cO8k80l": "Over 1.5 in Live",
    "price_fZu9AT55F1ue3Xp2Wy8k80m": "Over 1.5 in Live",
    "price_8x29ATfKj0qa65x2Wy8k80n": "Over 1.5 in Live",
    "price_28E5kDbu32yi2TlfJk8k80o": "Over 1.5 in Live",
    "price_9B6dR9bu37SCbpR54G8k80p": "TotalCanto HT",
    "price_8x27sLfKjfl41Ph9kW8k80q": "TotalCanto HT",
    "price_fZu14napZb4O65xfJk8k80r": "TotalCanto HT",
    "price_dRm14napZb4O65xfJk8k80s": "TotalCanto HT",
    "price_8x200j55Fc8S2Tl7cO8k80t": "TotalCanto FT",
    "price_3cIdR92Xx7SCdxZeFg8k80u": "TotalCanto FT",
    "price_eVqcN58hR8WG3Xpcx88k80v": "TotalCanto FT",
    "price_bJe6oHfKjeh00LdgNo8k80w": "TotalCanto FT",
    "price_bJe5kDfKj8WG9hJcx88k80x": "Momentum of Gol",
    "price_14AfZh41B0qagKbdBc8k80y": "Momentum of Gol",
    "price_28EaEX7dN1ue9hJdBc8k80z": "Momentum of Gol",
    "price_7sYfZh2Xx3Cm2Tl0Oq8k80A": "Momentum of Gol",
}

COMBO_MAP = {
    "price_cNifZh7dN1uedxZfJk8k80B": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"],
    "price_14AfZh41B0qagKbdBc8k80y": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"],
    "price_28EaEX7dN1ue9hJdBc8k80z": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"],
    "price_14A9AT9lVa0K65xdBc8k80E": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"],
    "price_dRmfZh2Xx5Ku2Tl54G8k80F": ["TotalCanto HT", "TotalCanto FT"],
    "price_6oU3cvbu36OyeC37cO8k80G": ["TotalCanto HT", "TotalCanto FT"],
    "price_cNi14n2Xxeh0eC3eFg8k80H": ["TotalCanto HT", "TotalCanto FT"],
    "price_8x28wP0Ppgp8dxZ2Wy8k80I": ["TotalCanto HT", "TotalCanto FT"],
    "price_7sY4gz2Xxeh065xbt48k80J": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"],
    "price_3cI8wPgOn2yi3Xp54G8k80K": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"],
    "price_3cI14n8hR6Oy1Phcx88k80L": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"],
    "price_6oU7sL0Ppa0KctV2Wy8k80M": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"],
}

@app.get("/")
async def root():
    return {"status": "online", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def webhook_handler(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print(f"Erro: {e}")
        return {"status": "error"}
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        
        if customer_email:
            items = stripe.checkout.Session.list_line_items(session["id"])
            if items.data:
                price_id = items.data[0].price.id
                
                if price_id in COMBO_MAP:
                    for bot in COMBO_MAP[price_id]:
                        redis_client.sadd(f"user:{customer_email}", bot)
                elif price_id in PRODUCT_MAP:
                    redis_client.sadd(f"user:{customer_email}", PRODUCT_MAP[price_id])
                
                redis_client.expire(f"user:{customer_email}", 365 * 24 * 3600)
                print(f"✅ Ativado: {customer_email}")
    
    return {"status": "ok"}

@app.get("/check/{email}/{bot}")
async def check_access(email: str, bot: str):
    key = f"user:{email.lower()}"
    bots = redis_client.smembers(key)
    return {"granted": bot.lower() in [b.lower() for b in bots]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)