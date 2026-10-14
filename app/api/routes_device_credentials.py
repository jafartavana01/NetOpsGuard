"""Superadmin credential management. No plaintext or ciphertext in responses."""
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from ..database import get_db
from ..services import device_credentials
from .deps import get_current_superadmin, verify_csrf

router = APIRouter(prefix='/api/device-credentials', tags=['device-credentials'])


@router.get('')
def get_credentials(db: Session = Depends(get_db), _admin=Depends(get_current_superadmin)):
    settings = device_credentials.ensure_settings(db)
    db.commit()
    return device_credentials.public_status(settings)


@router.put('', dependencies=[Depends(verify_csrf)])
async def update_credentials(request: Request, db: Session = Depends(get_db), _admin=Depends(get_current_superadmin)):
    # Validate explicitly: FastAPI/Pydantic validation errors can echo secret inputs.
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(400, 'Invalid credential request.') from None
    if not isinstance(data, dict) or set(data) - {'username', 'password', 'revision'}:
        raise HTTPException(422, 'Invalid credential fields.')
    username, password, revision = data.get('username'), data.get('password'), data.get('revision')
    if not isinstance(username, str) or not username.strip() or len(username) > 128:
        raise HTTPException(422, 'Enter an SSH username of 1–128 characters.')
    if password is not None and (not isinstance(password, str) or len(password) > 256):
        raise HTTPException(422, 'Password must be at most 256 characters.')
    if not isinstance(revision, str) or len(revision) != 64:
        raise HTTPException(409, 'Reload saved credentials before saving.')
    return device_credentials.replace(db, username=username.strip(), password=password, expected_revision=revision)
