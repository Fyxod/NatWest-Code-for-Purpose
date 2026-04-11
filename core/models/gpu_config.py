from pydantic import BaseModel


class GPULLMConfig(BaseModel):
    model: str
    port: int
