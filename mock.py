#!/usr/bin/env python3
"""
Mock PDF Source Server
Simula una sorgente di PDF con autenticazione JWT
"""

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response
import uvicorn
from datetime import datetime

app = FastAPI(title="Mock PDF Source")

# Simula un JWT valido (stesso formato di auth.py)
VALID_JWT_PREFIX = None
REQUEST_COUNT = 0
FAIL_AFTER_REQUESTS = 3  # Fallisce dopo N richieste per simulare scadenza JWT

@app.get("/")
async def root():
    return {
        "service": "Mock PDF Source",
        "status": "running",
        "endpoints": {
            "download": "GET /{issue_id}/{date}",
            "reset": "POST /reset",
            "config": "GET /config"
        }
    }

@app.get("/config")
async def get_config():
    """Mostra configurazione attuale"""
    return {
        "fail_after_requests": FAIL_AFTER_REQUESTS,
        "current_request_count": REQUEST_COUNT,
        "valid_jwt_prefix": VALID_JWT_PREFIX[:20] if VALID_JWT_PREFIX else None,
        "next_response": "401 (JWT expired)" if REQUEST_COUNT >= FAIL_AFTER_REQUESTS else "200 (OK)"
    }

@app.post("/reset")
async def reset():
    """Reset contatore per testare nuovamente la scadenza JWT"""
    global REQUEST_COUNT, VALID_JWT_PREFIX
    REQUEST_COUNT = 0
    VALID_JWT_PREFIX = None
    return {
        "status": "reset",
        "message": "Il prossimo JWT sarà accettato, poi scadrà dopo 3 richieste"
    }

@app.post("/config")
async def update_config(fail_after: int = 3):
    """Configura dopo quante richieste il JWT scade"""
    global FAIL_AFTER_REQUESTS
    FAIL_AFTER_REQUESTS = fail_after
    return {
        "status": "updated",
        "fail_after_requests": FAIL_AFTER_REQUESTS
    }

@app.get("/{issue_id}/{date}")
async def download_publication(
    issue_id: str,
    date: str,
    authorization: str = Header(None)
):
    """
    Scarica una pubblicazione (mock)
    
    Comportamento:
    - Richiede header Authorization: Bearer <jwt>
    - Le prime N richieste con un nuovo JWT ritornano 200
    - Dopo N richieste, ritorna 401 per simulare scadenza
    - Un nuovo JWT resetta il contatore
    """
    global REQUEST_COUNT, VALID_JWT_PREFIX
    
    # Controlla presenza header
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header"
        )
    
    # Estrai JWT
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header format"
        )
    
    jwt = authorization[7:]  # Rimuovi "Bearer "
    jwt_prefix = jwt[:20] if len(jwt) >= 20 else jwt
    
    # Primo JWT o JWT cambiato = reset contatore
    if VALID_JWT_PREFIX is None or VALID_JWT_PREFIX != jwt_prefix:
        print(f"📝 New JWT detected: {jwt_prefix}... - Resetting counter")
        VALID_JWT_PREFIX = jwt_prefix
        REQUEST_COUNT = 0
    
    REQUEST_COUNT += 1
    
    print(f"📥 Request #{REQUEST_COUNT} for {issue_id}/{date} with JWT {jwt_prefix}...")
    
    # Simula scadenza JWT dopo N richieste
    if REQUEST_COUNT > FAIL_AFTER_REQUESTS:
        print(f"❌ JWT expired! (request #{REQUEST_COUNT} > {FAIL_AFTER_REQUESTS})")
        raise HTTPException(
            status_code=401,
            detail="JWT expired"
        )
    
    # Genera PDF mock
    pdf_content = f"""%PDF-1.4
%Mock PDF Document
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj
2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj
3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj
4 0 obj
<<
/Length 55
>>
stream
BT
/F1 12 Tf
100 700 Td
(Mock PDF - {issue_id} - {date}) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f 
0000000015 00000 n 
0000000074 00000 n 
0000000131 00000 n 
0000000229 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
333
%%EOF
""".encode('utf-8')
    
    print(f"✅ Returning 200 OK (request #{REQUEST_COUNT}/{FAIL_AFTER_REQUESTS})")
    
    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename={issue_id}_{date}.pdf"
        }
    )

if __name__ == "__main__":
    print("=" * 60)
    print("🎭 Mock PDF Source Server")
    print("=" * 60)
    print(f"📍 Server: http://localhost:8001")
    print(f"📋 API Docs: http://localhost:8001/docs")
    print()
    print("Comportamento:")
    print(f"  • Prime {FAIL_AFTER_REQUESTS} richieste con un JWT → 200 OK")
    print(f"  • Dopo {FAIL_AFTER_REQUESTS} richieste → 401 JWT expired")
    print("  • Nuovo JWT → reset contatore")
    print()
    print("Comandi utili:")
    print("  • GET  /config        → Stato attuale")
    print("  • POST /reset         → Reset manuale")
    print("  • POST /config?fail_after=N → Cambia soglia")
    print("=" * 60)
    print()
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8001,
        log_level="warning"  # Riduce verbosità, vediamo solo i nostri print
    )
