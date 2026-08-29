from typing import Annotated

from sqlmodel import Session
from fastapi import Depends

from ..db.connect import PvfDatabaseConnection

engine = PvfDatabaseConnection().get_engine()

# assuming the lifetime of a returned session is always within the lifetime of the http request session

def get_session():
    with Session(engine) as session:
        yield session

def get_next_session():
    return next(get_session())

SessionDep = Annotated[Session, Depends(get_session)]

