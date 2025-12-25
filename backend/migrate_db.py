#!/usr/bin/env python3
"""
Database Migration Script
ย้ายข้อมูลจาก JSON files ไปยัง SQLite Database
"""

import sys
import os

# เพิ่ม path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from database.connection import init_database, backup_database, get_database_stats
from database.session_manager import migrate_from_json, export_to_json
import logging

# ตั้งค่า logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^70}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*70}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}✅ {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}❌ {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKCYAN}ℹ️  {text}{Colors.ENDC}")


def print_warning(text):
    print(f"{Colors.WARNING}⚠️  {text}{Colors.ENDC}")


def main():
    print_header("REG-01 DATABASE MIGRATION TOOL")
    
    print("เลือกการทำงาน:")
    print("1. สร้าง Database ใหม่")
    print("2. ย้ายข้อมูลจาก JSON → Database")
    print("3. Export ข้อมูลจาก Database → JSON")
    print("4. สำรองฐานข้อมูล")
    print("5. แสดงสถิติ Database")
    print("0. ออก")
    
    choice = input("\nเลือก (0-5): ").strip()
    
    if choice == "1":
        # สร้าง Database
        print_info("กำลังสร้าง Database...")
        
        if init_database():
            print_success("สร้าง Database สำเร็จ!")
            
            # แสดงสถิติ
            stats = get_database_stats()
            print_info(f"Database Type: {stats.get('database_type', 'unknown')}")
            print_info(f"Database Path: {stats.get('database_path', 'unknown')}")
        else:
            print_error("สร้าง Database ไม่สำเร็จ")
    
    elif choice == "2":
        # Migration
        print_warning("⚠️  การย้ายข้อมูลจะแทนที่ข้อมูลเดิม (ถ้ามี)")
        confirm = input("ต้องการดำเนินการต่อ? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print_info("ยกเลิกการย้ายข้อมูล")
            return
        
        # สร้าง Database ก่อน
        print_info("กำลังสร้าง Database...")
        init_database()
        
        # เริ่มย้ายข้อมูล
        json_dir = input("\nระบุโฟลเดอร์ JSON (Enter = ใช้ default): ").strip()
        
        if not json_dir:
            json_dir = "backend/memory/session_storage"
        
        if not os.path.exists(json_dir):
            print_error(f"ไม่พบโฟลเดอร์: {json_dir}")
            return
        
        print_info(f"กำลังย้ายข้อมูลจาก: {json_dir}")
        
        stats = migrate_from_json(json_dir)
        
        print_header("MIGRATION RESULTS")
        print_info(f"Total files: {stats['total_files']}")
        print_success(f"Migrated: {stats['migrated']}")
        print_warning(f"Skipped: {stats['skipped']}")
        
        if stats['failed'] > 0:
            print_error(f"Failed: {stats['failed']}")
        
        # แสดงสถิติหลังย้าย
        db_stats = get_database_stats()
        print_header("DATABASE STATISTICS")
        print_info(f"Total Users: {db_stats.get('total_users', 0)}")
        print_info(f"Total Messages: {db_stats.get('total_messages', 0)}")
        print_info(f"Total FAQs: {db_stats.get('total_faqs', 0)}")
    
    elif choice == "3":
        # Export
        output_dir = input("\nระบุโฟลเดอร์สำหรับ export (Enter = ใช้ default): ").strip()
        
        if not output_dir:
            output_dir = "backend/database/exports"
        
        print_info(f"กำลัง export ไปยัง: {output_dir}")
        
        if export_to_json(output_dir):
            print_success(f"Export สำเร็จ! ไฟล์อยู่ที่: {output_dir}")
        else:
            print_error("Export ไม่สำเร็จ")
    
    elif choice == "4":
        # Backup
        print_info("กำลังสำรองฐานข้อมูล...")
        
        if backup_database():
            print_success("สำรองฐานข้อมูลสำเร็จ!")
        else:
            print_error("สำรองฐานข้อมูลไม่สำเร็จ")
    
    elif choice == "5":
        # Statistics
        print_header("DATABASE STATISTICS")
        
        stats = get_database_stats()
        
        print_info(f"Database Type: {stats.get('database_type', 'unknown')}")
        print_info(f"Database Path: {stats.get('database_path', 'unknown')}")
        print_info(f"Total Users: {stats.get('total_users', 0)}")
        print_info(f"Total Messages: {stats.get('total_messages', 0)}")
        print_info(f"Total FAQs: {stats.get('total_faqs', 0)}")
        print_info(f"Total Logs: {stats.get('total_logs', 0)}")
    
    elif choice == "0":
        print_info("ออกจากโปรแกรม")
        return
    
    else:
        print_error("ตัวเลือกไม่ถูกต้อง")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print_warning("\n\nยกเลิกการทำงาน")
    except Exception as e:
        print_error(f"เกิดข้อผิดพลาด: {e}")
        import traceback
        traceback.print_exc()
