"""Idempotent demo seed: public meeting places + a pool of nearby owners.

Without a candidate pool a fresh account sees an empty map (the cold-start
problem, design §8). Seeding a handful of owners clustered around a base point
lets the very first signup find mates immediately. All demo logins use the
password `demo1234`.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import grid_cell, hash_password
from app.models import Dog, MeetingPlace, User

# Gangnam-ish base; demo owners are scattered within a few hundred metres so they
# share the base grid cell or a neighbour.
BASE_LAT, BASE_LNG = 37.5172, 127.0473

_DEMO_PLACES = [
    ("양재시민의숲", "서울 서초구 매헌로 99", 37.4704, 127.0386),
    ("도산공원", "서울 강남구 도산대로45길 20", 37.5240, 127.0370),
    ("매헌근린공원", "서울 서초구 양재동 236", 37.4716, 127.0349),
    ("선릉·정릉 공원", "서울 강남구 선릉로100길 1", 37.5103, 127.0490),
    ("학동공원", "서울 강남구 논현로", 37.5147, 127.0345),
]

# (email, name, dog name, breed, size, temperament, dlat, dlng)
_DEMO_OWNERS = [
    ("jihu@demo.example.com", "지후", "콩이", "말티즈", "small", "playful", 0.0008, 0.0006),
    ("yuna@demo.example.com", "유나", "보리", "푸들", "small", "calm", -0.0011, 0.0009),
    ("minseok@demo.example.com", "민석", "초코", "비글", "medium", "energetic", 0.0015, -0.0012),
    ("seoyeon@demo.example.com", "서연", "구름", "골든리트리버", "large", "calm", -0.0009, -0.0007),
    ("doyun@demo.example.com", "도윤", "바둑", "진돗개", "medium", "shy", 0.0004, 0.0018),
    ("hayeon@demo.example.com", "하연", "탱구", "포메라니안", "small", "playful", 0.0020, 0.0010),
    ("woojin@demo.example.com", "우진", "맥스", "시바견", "medium", "playful", -0.0018, 0.0004),
]


def seed_meeting_places(db: Session) -> int:
    if db.execute(select(MeetingPlace.id).limit(1)).first() is not None:
        return 0
    for name, address, lat, lng in _DEMO_PLACES:
        db.add(MeetingPlace(name=name, address=address, lat=lat, lng=lng, is_public=True))
    db.commit()
    return len(_DEMO_PLACES)


def seed_demo_owners(db: Session) -> int:
    created = 0
    pw = hash_password("demo1234")
    for email, name, dog_name, breed, size, temperament, dlat, dlng in _DEMO_OWNERS:
        if db.execute(select(User.id).where(User.email == email)).first() is not None:
            continue
        lat, lng = BASE_LAT + dlat, BASE_LNG + dlng
        user = User(
            email=email,
            password_hash=pw,
            display_name=name,
            role="user",
            status="active",
            is_verified=True,
            home_lat=lat,
            home_lng=lng,
            grid_cell=grid_cell(lat, lng),
        )
        db.add(user)
        db.flush()
        db.add(
            Dog(
                owner_id=user.id,
                name=dog_name,
                breed=breed,
                size=size,
                temperament=temperament,
            )
        )
        created += 1
    db.commit()
    return created


def seed_all(db: Session) -> dict[str, int]:
    return {
        "meeting_places": seed_meeting_places(db),
        "demo_owners": seed_demo_owners(db),
    }
