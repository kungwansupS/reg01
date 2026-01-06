#!/usr/bin/env python3
"""
ตรวจสอบว่า database_router.py ถูกต้องหรือไม่
"""

import os

print("🔍 Checking database_router.py...\n")

# ตรวจสอบตำแหน่งที่เป็นไปได้
possible_paths = [
    "backend/router/database_router.py",
    "router/database_router.py",
]

found = False
for path in possible_paths:
    if os.path.exists(path):
        print(f"✅ Found: {path}")
        found = True
        
        # ตรวจสอบเนื้อหา
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # ตรวจสอบว่าใช้ with statement หรือไม่
        if 'with SessionDatabase() as db:' in content:
            print("   ❌ ERROR: ยังใช้ 'with SessionDatabase() as db:' (ผิด)")
            print("   💡 ต้องแก้เป็น:")
            print("      db = SessionDatabase()")
            print("      try:")
            print("          with db.get_connection() as conn:")
        elif 'db = SessionDatabase()' in content and 'with db.get_connection()' in content:
            print("   ✅ CORRECT: ใช้ db.get_connection() ถูกต้อง")
        elif 'with SessionDatabase() as db:' not in content:
            print("   ⚠️ WARNING: ไม่พบ SessionDatabase() ในไฟล์")
        
        # ตรวจสอบ import
        if 'from memory.session_db import SessionDatabase' in content:
            print("   ✅ Import path: from memory.session_db (ถูกต้อง)")
        elif 'from backend.memory.session_db import SessionDatabase' in content:
            print("   ❌ Import path: from backend.memory.session_db (ผิด)")
        
        print()

if not found:
    print("❌ ไม่พบ database_router.py ในตำแหน่งที่คาดหวัง")
    print("💡 ให้คัดลอกไฟล์ database_router_no_context.py ไปวางที่:")
    print("   - backend/router/database_router.py")
    print("   หรือ")
    print("   - router/database_router.py")
