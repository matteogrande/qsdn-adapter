from pydantic import BaseModel


class Key(BaseModel):
    key_ID: str
    key: str


class KeyContainer(BaseModel):
    keys: list[Key]
