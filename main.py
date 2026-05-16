from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
import stripe
import redis
import os
from datetime import datetime

app = FastAPI()

# CORS para permitir seus bots consultarem
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ======================
# CHAVES VINDAS DE VARIÁVEIS DE AMBIENTE
# ======================
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
REDIS_URL = os.getenv("REDIS_URL")

if not STRIPE_SECRET_KEY:
    raise Exception("ERRO: STRIPE_SECRET_KEY não configurada")
if not STRIPE_WEBHOOK_SECRET:
    raise Exception("ERRO: STRIPE_WEBHOOK_SECRET não configurada")
if not REDIS_URL:
    raise Exception("ERRO: REDIS_URL não configurada")

stripe.api_key = STRIPE_SECRET_KEY

# ======================
# CONEXÃO REDIS
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

# ======================
# MAPEAMENTO DE PLANOS (NOVOS)
# ======================
# START: Quero Gol, Over Limite FT, Over 1.5 in Live
# BUSINESS: Momentum of Gol, Over Limite FT, Over 1.5 in Live, Quero Gol, TotalCanto HT, TotalCanto FT
# ULTRA: Tudo do BUSINESS + Total Score, XC Over

PLAN_FEATURES = {
    "START": [
        "Quero Gol",
        "Over Limite FT", 
        "Over 1.5 in Live"
    ],
    "BUSINESS": [
        "Momentum of Gol",
        "Over Limite FT",
        "Over 1.5 in Live",
        "Quero Gol",
        "TotalCanto HT",
        "TotalCanto FT"
    ],
    "ULTRA": [
        "Momentum of Gol",
        "Over Limite FT",
        "Over 1.5 in Live",
        "Quero Gol",
        "TotalCanto HT",
        "TotalCanto FT",
        "Total Score",
        "XC Over"
    ]
}

# Mapeamento dos Price IDs do Stripe para os Planos
PRICE_TO_PLAN = {
    # START (15, 35, 55, 90)
    "price_28E5kDeGf4Gq0Ld7cO8k80N": {"name": "START", "period": "monthly"},
    "price_cNicN5cy77SCctVcx88k80O": {"name": "START", "period": "quarterly"},
    "price_6oUaEXcy7eh079B1Su8k80P": {"name": "START", "period": "semester"},
    "price_fZu00j9lV2yi0LdfJk8k80Q": {"name": "START", "period": "yearly"},
    
    # BUSINESS (35, 75, 130, 220)
    "price_3cI8wPgOn1uedxZap08k80Z": {"name": "BUSINESS", "period": "monthly"},
    "price_fZufZh7dN7SC9hJfJk8k810": {"name": "BUSINESS", "period": "quarterly"},
    "price_9B65kDfKjc8SctVcx88k811": {"name": "BUSINESS", "period": "semester"},
    "price_aFa9ATfKj3Cm0Ld40C8k812": {"name": "BUSINESS", "period": "yearly"},
    
    # ULTRA (90, 220, 370, 650)
    "price_4gM5kD7dN0qa2Tl54G8k813": {"name": "ULTRA", "period": "monthly"},
    "price_8x2cN5eGf2yi65x54G8k814": {"name": "ULTRA", "period": "quarterly"},
    "price_cNifZhapZc8S0Ld9kW8k817": {"name": "ULTRA", "period": "semester"},
    "price_9B614n2Xx0qa3XpgNo8k816": {"name": "ULTRA", "period": "yearly"},
}

# ======================
# FUNÇÕES AUXILIARES
# ======================
def grant_plan_access(email: str, plan_name: str):
    """Concede acesso a todos os bots do plano"""
    if plan_name not in PLAN_FEATURES:
        print(f"⚠️ Plano desconhecido: {plan_name}")
        return False
    
    bots = PLAN_FEATURES[plan_name]
    for bot_name in bots:
        redis_client_wrapper.sadd(f"access:{email}", bot_name)
    
    # Salvar também qual plano o usuário possui
    redis_client_wrapper.sadd(f"user_plan:{email}", plan_name)
    
    print(f"✅ Plano {plan_name} ativado para {email} -> {len(bots)} bots liberados")
    return True

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
    """Recebe notificação do Stripe"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        print(f"Erro no webhook: {e}")
        return {"status": "error"}
    
    customer_email = None
    price_id = None
    
    # ======================
    # PROCESSAR INVOICE.PAID
    # ======================
    if event["type"] == "invoice.paid":
        invoice = event["data"]["object"]
        customer_email = invoice.get("customer_email")
        
        if invoice.get("lines", {}).get("data"):
            line = invoice["lines"]["data"][0]
            if "price" in line:
                price_id = line["price"]["id"]
            elif line.get("plan"):
                price_id = line["plan"]["id"]
    
    # ======================
    # PROCESSAR PAYMENT_INTENT.SUCCEEDED
    # ======================
    elif event["type"] == "payment_intent.succeeded":
        payment_intent = event["data"]["object"]
        customer_email = payment_intent.get("receipt_email")
        
        if payment_intent.get("customer"):
            try:
                subscriptions = stripe.Subscription.list(customer=payment_intent["customer"], limit=1)
                if subscriptions.data:
                    price_id = subscriptions.data[0]["items"]["data"][0]["price"]["id"]
            except Exception as e:
                print(f"Erro ao buscar subscription: {e}")
    
    # ======================
    # PROCESSAR CHECKOUT.SESSION.COMPLETED
    # ======================
    elif event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        customer_email = session.get("customer_email")
        
        try:
            line_items = stripe.checkout.Session.list_line_items(session["id"])
            if line_items.data:
                price_id = line_items.data[0].price.id
        except Exception as e:
            print(f"Erro ao buscar line items: {e}")
    
    # ======================
    # SALVAR ACESSO NO REDIS
    # ======================
    if customer_email and price_id:
        print(f"💰 Compra detectada: {customer_email} - Price ID: {price_id}")
        
        if price_id in PRICE_TO_PLAN:
            plan = PRICE_TO_PLAN[price_id]
            grant_plan_access(customer_email, plan["name"])
            redis_client_wrapper.expire(f"access:{customer_email}", 365 * 24 * 3600)
            return {"status": "success", "plan": plan["name"]}
        else:
            print(f"⚠️ Price ID não mapeado: {price_id}")
            return {"status": "error", "message": "Price ID not mapped"}
    
    return {"status": "ignored"}

# ======================
# ENDPOINTS DE CONSULTA
# ======================

@app.get("/check/{email}/{bot_name}")
async def check_access(email: str, bot_name: str):
    """Verifica se o email tem acesso ao bot"""
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

@app.get("/user-plan/{email}")
async def get_user_plan(email: str):
    """Retorna o plano do usuário e os bots disponíveis"""
    try:
        email_clean = email.lower().strip()
        
        # Buscar plano do usuário
        plans = redis_client_wrapper.smembers(f"user_plan:{email_clean}")
        user_plan = list(plans)[0] if plans else "FREE"
        
        # Buscar bots disponíveis
        bots = list(redis_client_wrapper.smembers(f"access:{email_clean}"))
        
        return {
            "email": email,
            "plan": user_plan,
            "bots": bots,
            "total_bots": len(bots),
            "redis_connected": redis_client_wrapper.ping()
        }
    except Exception as e:
        return {"error": str(e)}

@app.post("/register-chat")
async def register_chat(request: Request):
    """Registra o chat_id do usuário"""
    try:
        data = await request.json()
        email = data.get("email")
        chat_id = data.get("chat_id")
        bot_name = data.get("bot_name")
        
        if email and chat_id:
            key = f"user:{email}:chats"
            redis_client_wrapper.hset(key, {bot_name: chat_id})
            print(f"✅ Chat registrado: {email} -> {bot_name} ({chat_id})")
            return {"status": "ok"}
        return {"status": "error", "message": "Missing data"}
    except Exception as e:
        print(f"Erro no register_chat: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/result")
async def register_result(request: Request):
    """Recebe resultados dos alertas confirmados"""
    try:
        data = await request.json()
        print(f"📊 Resultado registrado: {data.get('bot_name')} - {data.get('result')}")
        return {"status": "success"}
    except Exception as e:
        print(f"Erro no register_result: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/debug/access/{email}")
async def debug_access(email: str):
    """Endpoint para debug - mostra todos os bots que o email tem acesso"""
    try:
        bots = list(redis_client_wrapper.smembers(f"access:{email.lower()}"))
        plans = list(redis_client_wrapper.smembers(f"user_plan:{email.lower()}"))
        return {
            "email": email,
            "plan": plans[0] if plans else "FREE",
            "bots": bots,
            "total": len(bots),
            "redis_connected": redis_client_wrapper.ping()
        }
    except Exception as e:
        return {"error": str(e)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
