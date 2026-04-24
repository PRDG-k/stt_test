import os
import argparse
import uvicorn
import logging
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import router as api_router
from app.api.health import router as health_router
from app.models.database import init_db

# 1. 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("api_logger")

# 2. DB 초기화
init_db()

# 3. 파라미터 파싱
parser = argparse.ArgumentParser()
parser.add_argument("--test", action="store_true", help="Enable test mode")
parser.add_argument("--https", action="store_true", help="Enable HTTPS with self-signed certificate")
args, _ = parser.parse_known_args()

app = FastAPI(title="STT Action API")
app.state.test_mode = args.test

# 4. Request-Response 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Request 로깅 (Path, Method)
    path = request.url.path
    method = request.method
    logger.info(f"Incoming request: {method} {path}")
    
    response = await call_next(request)
    
    # Response 로깅 (Status Code, Duration)
    process_time = (time.time() - start_time) * 1000
    formatted_process_time = "{0:.2f}".format(process_time)
    logger.info(f"Response: {response.status_code} (Completed in {formatted_process_time}ms)")
    
    return response

# 5. CORS 설정 (내부망 접근 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 6. API 라우터 등록
app.include_router(api_router, prefix="/api")
app.include_router(health_router, prefix="/api", tags=["Monitoring"])

# 7. SSL 인증서 자동 생성 함수
def get_ssl_context():
    cert_file = "cert.pem"
    key_file = "key.pem"
    
    if not os.path.exists(cert_file) or not os.path.exists(key_file):
        print("Generating self-signed SSL certificate for HTTPS...")
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization
        import datetime

        # Generate key
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        with open(key_file, "wb") as f:
            f.write(key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption(),
            ))

        # Generate cert
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, u"KR"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, u"Seoul"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, u"Seoul"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"STT-Test"),
            x509.NameAttribute(NameOID.COMMON_NAME, u"localhost"),
        ])
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).add_extension(
            x509.SubjectAlternativeName([x509.DNSName(u"localhost")]),
            critical=False,
        ).sign(key, hashes.SHA256())

        with open(cert_file, "wb") as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))
            
    return cert_file, key_file

if __name__ == "__main__":
    config = {
        "app": "app.main:app",
        "host": "0.0.0.0",
        "port": 8000,
        "reload": True,
        "reload_dirs": ["app"]
    }
    
    if args.https:
        cert, key = get_ssl_context()
        config["ssl_certfile"] = cert
        config["ssl_keyfile"] = key
        print("\n--- HTTPS Mode Enabled ---")
        print("Note: Your browser will show a security warning. Click 'Advanced' and 'Proceed' to test.\n")

    uvicorn.run(**config)
