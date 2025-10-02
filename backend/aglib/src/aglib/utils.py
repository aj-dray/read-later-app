from litellm.utils import token_counter as lltc

def token_counter(text: str, provider: str, model: str):
    return lltc(model=f"{provider}/{model}", text=text)


