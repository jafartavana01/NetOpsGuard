"""Disposable child process for SQLite ownership/restart integration tests."""
import os
import sys
from datetime import datetime
from types import SimpleNamespace
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from cryptography.fernet import Fernet
# Register the actual model graph, as the app does at startup.
from test_integration import security, scheduler, network_ops_execution
from app.services import ncm_drivers

engine=create_engine(sys.argv[1])
security._fernet=lambda:Fernet(os.environ['NCM_TEST_FERNET'].encode())
if sys.argv[4]=='crash':
    ncm_drivers.get_driver=lambda _:SimpleNamespace(get_configuration=lambda *a:os._exit(23))
else:
    real=network_ops_execution.run_commands_on_device
    network_ops_execution.run_commands_on_device=lambda *a,**k:real(*a,**k,port=int(sys.argv[4]))
with Session(engine) as db:
    import uuid
    try:scheduler.run_schedule(db,uuid.UUID(sys.argv[2]),now=datetime.fromisoformat(sys.argv[3]))
    except scheduler.ncm_lock.Busy:pass
engine.dispose()
