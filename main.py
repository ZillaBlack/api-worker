from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import stripe
import redis
import os
from datetime import datetime
import time

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# CHAVES
# ======================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
REDIS_URL = os.getenv("REDIS_URL")

if not REDIS_URL:
    raise Exception("ERRO: REDIS_URL não configurada")

# ======================
# CONEXÃO REDIS COM RECONEXÃO AUTOMÁTICA
# ======================
class RedisClient:
    def __init__(self, url):
        self.url = url
        self.client = None
        self._connect()
    
    def _connect(self):
        try:
            self.client = redis.Redis.from_url(self.url, decode_responses=True, socket_keepalive=True)
            self.client.ping()
            print("✅ Redis conectado com sucesso!")
        except Exception as e:
            print(f"⚠️ Erro ao conectar Redis: {e}")
            self.client = None
    
    def get_client(self):
        if self.client is None:
            self._connect()
        return self.client
    
    def smembers(self, key):
        client = self.get_client()
        if client:
            try:
                return client.smembers(key)
            except:
                self._connect()
                return self.get_client().smembers(key) if self.get_client() else set()
        return set()
    
    def sadd(self, key, value):
        client = self.get_client()
        if client:
            try:
                return client.sadd(key, value)
            except:
                self._connect()
                return self.get_client().sadd(key, value) if self.get_client() else 0
        return 0
    
    def expire(self, key, time):
        client = self.get_client()
        if client:
            try:
                return client.expire(key, time)
            except:
                self._connect()
                return self.get_client().expire(key, time) if self.get_client() else 0
        return 0
    
    def hset(self, key, mapping):
        client = self.get_client()
        if client:
            try:
                return client.hset(key, mapping=mapping)
            except:
                self._connect()
                return self.get_client().hset(key, mapping=mapping) if self.get_client() else 0
        return 0
    
    def ping(self):
        client = self.get_client()
        if client:
            try:
                return client.ping()
            except:
                return False
        return False

redis_client_wrapper = RedisClient(REDIS_URL)

def redis_client():
    return redis_client_wrapper.get_client()

# Configurar Stripe
stripe.api_key = STRIPE_SECRET_KEY

# ======================
# MAPEAMENTO (mesmo de antes)
# ======================
PRICE_TO_PLAN = {
    "price_6oU5kD8hReh0alN2Wy8k80d": {"name": "Over Limite FT", "period": "monthly"},
    "price_28E3cvdCbc8SctV2Wy8k80e": {"name": "Over Limite FT", "period": "quarterly"},
    "price_dRm6oH2XxdcWalN7cO8k80f": {"name": "Over Limite FT", "period": "semester"},
    "price_bJecN52Xx8WG9hJeFg8k80g": {"name": "Over Limite FT", "period": "yearly"},
    "price_5kQ14nbu38WG65xbt48k80h": {"name": "Quero Gol", "period": "monthly"},
    "price_4gM3cv2Xxa0K2Tl8gS8k80i": {"name": "Quero Gol", "period": "quarterly"},
    "price_9B64gz7dN3CmdxZdBc8k80j": {"name": "Quero Gol", "period": "semester"},
    "price_eVq00jdCbdcW8dFdBc8k80k": {"name": "Quero Gol", "period": "yearly"},
    "price_4gMaEXapZ1ue0Ld7cO8k80l": {"name": "Over 1.5 in Live", "period": "monthly"},
    "price_fZu9AT55F1ue3Xp2Wy8k80m": {"name": "Over 1.5 in Live", "period": "quarterly"},
    "price_8x29ATfKj0qa65x2Wy8k80n": {"name": "Over 1.5 in Live", "period": "semester"},
    "price_28E5kDbu32yi2TlfJk8k80o": {"name": "Over 1.5 in Live", "period": "yearly"},
    "price_9B6dR9bu37SCbpR54G8k80p": {"name": "TotalCanto HT", "period": "monthly"},
    "price_8x27sLfKjfl41Ph9kW8k80q": {"name": "TotalCanto HT", "period": "quarterly"},
    "price_fZu14napZb4O65xfJk8k80r": {"name": "TotalCanto HT", "period": "semester"},
    "price_dRm14napZb4O65xfJk8k80s": {"name": "TotalCanto HT", "period": "yearly"},
    "price_8x200j55Fc8S2Tl7cO8k80t": {"name": "TotalCanto FT", "period": "monthly"},
    "price_3cIdR92Xx7SCdxZeFg8k80u": {"name": "TotalCanto FT", "period": "quarterly"},
    "price_eVqcN58hR8WG3Xpcx88k80v": {"name": "TotalCanto FT", "period": "semester"},
    "price_bJe6oHfKjeh00LdgNo8k80w": {"name": "TotalCanto FT", "period": "yearly"},
    "price_bJe5kDfKj8WG9hJcx88k80x": {"name": "Momentum of Gol", "period": "monthly"},
    "price_14AfZh41B0qagKbdBc8k80y": {"name": "Momentum of Gol", "period": "quarterly"},
    "price_28EaEX7dN1ue9hJdBc8k80z": {"name": "Momentum of Gol", "period": "semester"},
    "price_7sYfZh2Xx3Cm2Tl0Oq8k80A": {"name": "Momentum of Gol", "period": "yearly"},
}

COMBO_MAPPING = {
    "price_cNifZh7dN1uedxZfJk8k80B": {"name": "Bundle Gols", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"]},
    "price_14AfZh41B0qagKbdBc8k80y": {"name": "Bundle Gols", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"]},
    "price_28EaEX7dN1ue9hJdBc8k80z": {"name": "Bundle Gols", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"]},
    "price_14A9AT9lVa0K65xdBc8k80E": {"name": "Bundle Gols", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT"]},
    "price_dRmfZh2Xx5Ku2Tl54G8k80F": {"name": "Bundle Cantos", "bots": ["TotalCanto HT", "TotalCanto FT"]},
    "price_6oU3cvbu36OyeC37cO8k80G": {"name": "Bundle Cantos", "bots": ["TotalCanto HT", "TotalCanto FT"]},
    "price_cNi14n2Xxeh0eC3eFg8k80H": {"name": "Bundle Cantos", "bots": ["TotalCanto HT", "TotalCanto FT"]},
    "price_8x28wP0Ppgp8dxZ2Wy8k80I": {"name": "Bundle Cantos", "bots": ["TotalCanto HT", "TotalCanto FT"]},
    "price_7sY4gz2Xxeh065xbt48k80J": {"name": "Full Bots", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"]},
    "price_3cI8wPgOn2yi3Xp54G8k80K": {"name": "Full Bots", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"]},
    "price_3cI14n8hR6Oy1Phcx88k80L": {"name": "Full Bots", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"]},
    "price_6oU7sL0Ppa0KctV2Wy8k80M": {"name": "Full Bots", "bots": ["Quero Gol", "Over 1.5 in Live", "Over Limite FT", "TotalCanto HT", "TotalCanto FT", "Momentum of Gol"]},
}

# ======================
# ENDPOINTS
# ======================

@app.get("/")
async def root():
    return {"status": "online", "service": "TotalBot Backend", "timestamp": datetime.now().isoformat()}

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.get("/ping")
async def ping():
    return "pong"

@app.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return {"status": "error"}
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        
        if customer_email:
            line_items = stripe.checkout.Session.list_line_items(session["id"])
            if line_items.data:
                price_id = line_items.data[0].price.id
                print(f"💰 Compra: {customer_email} - {price_id}")
                
                if price_id in COMBO_MAPPING:
                    for bot_name in COMBO_MAPPING[price_id]["bots"]:
                        redis_client_wrapper.sadd(f"access:{customer_email}", bot_name)
                    print(f"✅ Combo ativado: {customer_email}")
                elif price_id in PRICE_TO_PLAN:
                    redis_client_wrapper.sadd(f"access:{customer_email}", PRICE_TO_PLAN[price_id]["name"])
                    print(f"✅ Bot ativado: {customer_email}")
                
                redis_client_wrapper.expire(f"access:{customer_email}", 365 * 24 * 3600)
    
    return {"status": "success"}

@app.get("/check/{email}/{bot_name}")
async def check_access(email: str, bot_name: str):
    try:
        email_clean = email.lower().strip()
        bot_clean = bot_name.lower().strip()
        
        bots = redis_client_wrapper.smembers(f"access:{email_clean}")
        user_bots = [b.lower().strip() for b in bots]
        
        if bot_clean in user_bots:
            return {"granted": True}
        return {"granted": False}
    except Exception as e:
        print(f"Erro no check_access: {e}")
        return {"granted": False}

@app.get("/debug/access/{email}")
async def debug_access(email: str):
    try:
        bots = list(redis_client_wrapper.smembers(f"access:{email.lower()}"))
        return {
            "email": email,
            "bots": bots,
            "total": len(bots),
            "redis_connected": redis_client_wrapper.ping()
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
