# backend/database/__init__.py
"""
Database Package for REG-01 System
รวม Models, Connection และ Session Management
"""

from database.models import (
    Base,
    User,
    Message,
    Session,
    FAQ,
    AuditLog,
    create_all_tables,
    drop_all_tables
)

from database.connection import (
    engine,
    db_session,
    get_db,
    get_db_dependency,
    init_database,
    check_database_health,
    get_database_stats,
    backup_database,
    vacuum_database,
    close_database
)

from database.session_manager import (
    get_or_create_user,
    get_or_create_history,
    save_history,
    get_bot_enabled,
    set_bot_enabled,
    cleanup_old_sessions,
    clear_history,
    migrate_from_json,
    export_to_json
)

__all__ = [
    # Models
    'Base',
    'User',
    'Message',
    'Session',
    'FAQ',
    'AuditLog',
    'create_all_tables',
    'drop_all_tables',
    
    # Connection
    'engine',
    'db_session',
    'get_db',
    'get_db_dependency',
    'init_database',
    'check_database_health',
    'get_database_stats',
    'backup_database',
    'vacuum_database',
    'close_database',
    
    # Session Manager
    'get_or_create_user',
    'get_or_create_history',
    'save_history',
    'get_bot_enabled',
    'set_bot_enabled',
    'cleanup_old_sessions',
    'clear_history',
    'migrate_from_json',
    'export_to_json',
]

# Version
__version__ = '1.0.0'
