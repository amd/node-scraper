from pydantic import BaseModel


class ProcessCollectorArgs(BaseModel):
    top_n_process: int = 10
