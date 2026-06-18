from src.services.whatsapp import get_whatsapp_client


async def send_whatsapp_message(to: str, text: str):
    return await get_whatsapp_client().send_text(to, text)


async def mark_message_as_read(message_id: str):
    return await get_whatsapp_client().mark_read(message_id)
