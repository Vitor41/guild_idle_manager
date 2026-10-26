from urllib.parse import parse_qs

from fastapi import Request


async def read_form_fields(request: Request) -> dict[str, str]:
    body = await request.body()
    parsed = parse_qs(body.decode("utf-8"), keep_blank_values=True)
    return {key: values[0] if values else "" for key, values in parsed.items()}


async def read_form_multi_fields(request: Request) -> dict[str, list[str]]:
    body = await request.body()
    return parse_qs(body.decode("utf-8"), keep_blank_values=True)
