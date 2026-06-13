"""Dog profile CRUD. Delete is soft (deleted_at) so historical matches/reviews
that reference a dog stay intact (design §4 crud_mapping)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.models import Dog, User
from app.schemas import DogIn, DogOut, DogUpdate

router = APIRouter(prefix="/api/v1/dogs", tags=["dogs"])


def _owned_dog(db: Session, user: User, dog_id: int) -> Dog:
    dog = db.get(Dog, dog_id)
    if dog is None or dog.deleted_at is not None or dog.owner_id != user.id:
        raise AppError("not_found", "Dog not found", 404)
    return dog


@router.post("", status_code=201, response_model=DogOut)
def create_dog(
    body: DogIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Dog:
    dog = Dog(owner_id=user.id, **body.model_dump())
    db.add(dog)
    db.commit()
    db.refresh(dog)
    return dog


@router.get("", response_model=list[DogOut])
def list_my_dogs(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[Dog]:
    return list(
        db.execute(
            select(Dog)
            .where(Dog.owner_id == user.id, Dog.deleted_at.is_(None))
            .order_by(Dog.id)
        ).scalars()
    )


@router.get("/{dog_id}", response_model=DogOut)
def get_dog(
    dog_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Dog:
    return _owned_dog(db, user, dog_id)


@router.patch("/{dog_id}", response_model=DogOut)
def update_dog(
    dog_id: int,
    body: DogUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dog:
    dog = _owned_dog(db, user, dog_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(dog, field, value)
    db.commit()
    db.refresh(dog)
    return dog


@router.delete("/{dog_id}", status_code=204)
def delete_dog(
    dog_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> Response:
    dog = _owned_dog(db, user, dog_id)
    dog.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return Response(status_code=204)
